from sqlalchemy.orm import Session
import pandas as pd
from datetime import datetime
import uuid
from typing import List, Dict, Set, Optional
from decimal import Decimal


# Models
from models import SimulationRun, Alert, Transaction, Customer, ScenarioConfig, AlertExclusionLog
# Core Engines
from core.universal_engine import UniversalScenarioEngine
from core.config_models import ScenarioConfigModel
from core.field_mapper import apply_field_mappings_to_df


class SimulationService:
    """
    Manages the lifecycle of AML simulation execution.
    
    This service orchestrates the entire simulation workflow:
    1. Creating simulation run records
    2. Loading user-scoped data
    3. Executing scenarios via UniversalScenarioEngine
    4. Saving alerts to database
    5. Updating run status
    
    Supports both database-backed and stateless ("pendrive mode") execution.
    
    Attributes:
        db: SQLAlchemy database session for persistence
    
    Example:
        >>> service = SimulationService(db)
        >>> run = service.create_run('ad_hoc', ['rapid-movement'], user_id='user-123')
        >>> service.execute_run(run.run_id)
    """
    
    def __init__(self, db: Session):
        """
        Initialize the simulation service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        
    def create_run(self, run_type: str, scenarios: List[str], user_id: str = None) -> SimulationRun:
        """
        Create a new simulation run record.
        
        Args:
            run_type: Type of run ('ad_hoc', 'scheduled', 'comparison')
            scenarios: List of scenario IDs to execute
            user_id: User who initiated the run (for multi-tenancy)
            
        Returns:
            SimulationRun object with status='pending'
            
        Example:
            >>> run = service.create_run(
            ...     run_type='ad_hoc',
            ...     scenarios=['rapid-movement', 'structuring'],
            ...     user_id='user-abc-123'
            ... )
            >>> print(run.run_id)
            'run-def-456'
        """
        run_id = str(uuid.uuid4())
        run = SimulationRun(
            run_id=run_id,
            user_id=user_id,
            run_type=run_type,
            scenarios_run=scenarios,
            status="pending",
            created_at=datetime.utcnow()
        )
        self.db.add(run)
        self.db.commit()
        return run

    def _flatten_raw_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extracts raw_data JSONB into DataFrame columns.
        """
        if df.empty or 'raw_data' not in df.columns:
            return df
        
        # Extract raw_data JSONB into columns
        meta_df = pd.json_normalize(df['raw_data'])
        
        if meta_df.empty:
            return df.drop(columns=['raw_data'])
        
        # System columns to keep from database query
        system_cols = ['customer_id', 'transaction_id', 'upload_id', 'created_at', 'expires_at']
        df_system = df[[col for col in system_cols if col in df.columns]]
        
        # Combine: system columns (from DB) + user data (from raw_data JSONB)
        result = pd.concat([df_system, meta_df], axis=1)
        
        # ✅ FIX: Parse date columns
        date_columns = ['transaction_date', 'account_opening_date', 'date_of_birth', 'created_date']
        for col in date_columns:
            if col in result.columns:
                result[col] = pd.to_datetime(result[col], errors='coerce', utc=True)
                # Remove timezone for compatibility
                if result[col].dtype == 'datetime64[ns, UTC]':
                    result[col] = result[col].dt.tz_localize(None)
        
        # ✅ FIX: Parse numeric columns
        numeric_columns = ['transaction_amount', 'balance', 'annual_income', 'risk_score']
        for col in numeric_columns:
            if col in result.columns:
                result[col] = pd.to_numeric(result[col], errors='coerce')
        
        print(f"[DATA_FLATTEN] Loaded {len(meta_df.columns)} fields from raw_data")
        
        return result

    def load_simulation_data(self, user_id: str):
        """
        Load transaction and customer data for a specific user.
        
        Fetches data from the database, scoped to the user via DataUpload join,
        and flattens the raw_data JSONB column into DataFrame columns.
        
        Args:
            user_id: User UUID to scope data loading
            
        Returns:
            Tuple of (customers_df, transactions_df) as pandas DataFrames
            
        Raises:
            ValueError: If user has no uploaded data
            
        Example:
            >>> customers_df, transactions_df = service.load_simulation_data('user-123')
            >>> print(f"Loaded {len(transactions_df)} transactions")
            Loaded 5000 transactions
        """
        from models import DataUpload
        
        # We join with DataUpload to ensure we only load data belonging to the specific user
        customers_query = self.db.query(Customer).join(DataUpload).filter(DataUpload.user_id == user_id)
        transactions_query = self.db.query(Transaction).join(DataUpload).filter(DataUpload.user_id == user_id)
        
        customers_df = pd.read_sql(customers_query.statement, self.db.bind)
        transactions_df = pd.read_sql(transactions_query.statement, self.db.bind)
        
        # Flatten raw_data for both
        customers_df = self._flatten_raw_data(customers_df)
        transactions_df = self._flatten_raw_data(transactions_df)
        
        return customers_df, transactions_df

    def execute_run(self, run_id: str, transactions_df: Optional[pd.DataFrame] = None, customers_df: Optional[pd.DataFrame] = None):
        """
        Execute a simulation run against transaction data.
        """
        run = self.db.query(SimulationRun).filter(SimulationRun.run_id == run_id).first()
        if not run:
            return
        
        # Update Status to Running
        run.status = "running"
        self.db.commit()
        
        try:
            # Check mode: Stateless (Pendrive) VS Database (Chunked)
            if transactions_df is not None and customers_df is not None:
                # --- STATELESS MODE (Existing Logic) ---
                self._run_batch(run, run_id, transactions_df, customers_df)
                
                # Finalize
                run.total_alerts = self.db.query(Alert).filter(Alert.run_id == run_id, Alert.excluded == False).count()
                run.total_transactions = len(transactions_df)
                run.status = "completed"
                run.completed_at = datetime.utcnow()
                run.progress_percentage = 100
                self.db.commit()
            
            else:
                # --- DATABASE MODE (Chunked Execution) ---
                if not run.user_id:
                    raise ValueError(f"Run {run_id} has no associated user_id for data loading")
                
                self._execute_db_run_chunked(run, run_id)
            
        except Exception as e:
            # Global Failure Handler
            print(f"Simulation execution failed: {e}")
            import traceback
            traceback.print_exc()
            self.db.rollback()
            run.status = "failed"
            run.metadata_info = {"error": str(e)}
            self.db.commit()
            raise e

    def _execute_db_run_chunked(self, run, run_id):
        """
        Execute run in chunks by customer to ensure aggregation correctness
        while maintaining low memory footprint.
        """
        from models import DataUpload
        from sqlalchemy import func
        
        # 1. Get all customer IDs for this user
        # We process by customer chunks to ensure "Group By Customer" works correctly
        print(f"Fetching customer list for user {run.user_id}...")
        cust_id_query = self.db.query(Customer.customer_id).join(DataUpload).filter(
            DataUpload.user_id == run.user_id
        )
        all_cust_ids = [r[0] for r in cust_id_query.all()]
        total_custs = len(all_cust_ids)
        
        if total_custs == 0:
            print("No customers found.")
            run.status = "completed"
            run.completed_at = datetime.utcnow()
            run.progress_percentage = 100
            self.db.commit()
            return

        BATCH_SIZE = 1000  # Customers per batch
        total_txns_processed = 0
        total_alerts_saved = 0
        
        print(f"Starting chunked execution for {total_custs} customers in batches of {BATCH_SIZE}")
        
        for i in range(0, total_custs, BATCH_SIZE):
            batch_cust_ids = all_cust_ids[i : i + BATCH_SIZE]
            
            # Load Data for this batch
            batch_customers_df, batch_txns_df = self._load_data_for_customers(run.user_id, batch_cust_ids)
            
            if batch_txns_df.empty:
                continue
                
            # Execute Engine on Batch
            self._run_batch(run, run_id, batch_txns_df, batch_customers_df)
            
            # Update Progress
            total_txns_processed += len(batch_txns_df)
            progress = int(((i + len(batch_cust_ids)) / total_custs) * 100)
            
            # Update run occasionally
            run.progress_percentage = progress
            run.total_transactions = total_txns_processed
            self.db.commit()
            
            # Memory Cleanup
            del batch_customers_df
            del batch_txns_df
            import gc
            gc.collect()

        # Finalize
        run.status = "completed"
        run.completed_at = datetime.utcnow()
        run.total_transactions = total_txns_processed
        run.total_alerts = self.db.query(Alert).filter(Alert.run_id == run_id, Alert.excluded == False).count()
        self.db.commit()

    def _load_data_for_customers(self, user_id: str, customer_ids: List[str]):
        """Load transactions and customer details for a specific list of IDs"""
        from models import DataUpload
        
        # Load Customers
        customers_query = self.db.query(Customer).join(DataUpload).filter(
            DataUpload.user_id == user_id,
            Customer.customer_id.in_(customer_ids)
        )
        customers_df = pd.read_sql(customers_query.statement, self.db.bind)
        customers_df = self._flatten_raw_data(customers_df)
        
        # Load Transactions
        transactions_query = self.db.query(Transaction).join(DataUpload).filter(
            DataUpload.user_id == user_id,
            Transaction.customer_id.in_(customer_ids)
        )
        transactions_df = pd.read_sql(transactions_query.statement, self.db.bind)
        transactions_df = self._flatten_raw_data(transactions_df)
        
        return customers_df, transactions_df

    def _run_batch(self, run, run_id, transactions_df, customers_df):
        """
        Process a single batch of data (in-memory) through the engine.
        Refactored from original execute_run.
        """
        # --- Apply Run-Level Dynamic Mappings ---
        if run.metadata_info and 'field_mappings' in run.metadata_info:
            mappings = run.metadata_info['field_mappings']
            if mappings:
                transactions_df = apply_field_mappings_to_df(transactions_df, mappings)
                customers_df = apply_field_mappings_to_df(customers_df, mappings)

        # --- Apply Date Range Filter ---
        if run.metadata_info and 'date_range' in run.metadata_info:
            date_range = run.metadata_info['date_range']
            start_date = pd.to_datetime(date_range.get('start')).tz_localize(None)
            end_date = pd.to_datetime(date_range.get('end')).tz_localize(None)
            
            if start_date and end_date and not transactions_df.empty:
                if 'transaction_date' in transactions_df.columns:
                    transactions_df['transaction_date'] = pd.to_datetime(transactions_df['transaction_date'], utc=True).dt.tz_localize(None)
                    mask = (transactions_df['transaction_date'] >= start_date) & (transactions_df['transaction_date'] <= end_date)
                    transactions_df = transactions_df.loc[mask]

        if transactions_df.empty:
            return

        # Initialize Engine
        engine = UniversalScenarioEngine(db_session=self.db)
        all_alerts = []
        scenarios_to_run = run.scenarios_run or []
        
        # Execute Each Scenario
        for scenario_id in scenarios_to_run:
            config_record = self.db.query(ScenarioConfig).filter(ScenarioConfig.scenario_id == scenario_id).first()
            
            if not config_record:
                print(f"[ERROR] Scenario {scenario_id} not found in database!")
                continue
            
            if not config_record.config_json:
                print(f"[ERROR] Scenario {scenario_id} has no config_json!")
                continue
            
            try:

                
                conf_data = config_record.config_json.copy()
                conf_data['scenario_id'] = scenario_id
                conf_data['scenario_name'] = config_record.scenario_name
                
                # Check if aggregation exists
                if 'aggregation' not in conf_data:
                    # Valid error check, but removing noisy debug label
                    print(f"[ERROR] No 'aggregation' key in config_json for {scenario_id}!")
                    continue
                
                if 'threshold' not in conf_data:
                    print(f"[WARN] No 'threshold' key in config_json for {scenario_id}")
                
                scenario_config = ScenarioConfigModel(**conf_data)
                
                # Apply Scenario-Specific Mappings
                current_txns = transactions_df.copy()
                current_cust = customers_df.copy()
                
                if config_record.field_mappings:
                    current_txns = apply_field_mappings_to_df(current_txns, config_record.field_mappings)
                    current_cust = apply_field_mappings_to_df(current_cust, config_record.field_mappings)

                # Run Engine
                alerts = engine.execute(scenario_config, current_txns, current_cust, run_id)
                all_alerts.extend(alerts)
                
            except Exception as e:
                print(f"[ERROR] Failed to execute scenario {scenario_id}: {e}")
                import traceback
                traceback.print_exc()
                continue

        # Deduplicate Alerts
        seen_keys = set()
        deduplicated_alerts = []
        
        for alert in all_alerts:
            # Convert Series to dict if needed
            if isinstance(alert, pd.Series):
                alert = alert.to_dict()
            
            a_date = alert.get('alert_date', pd.Timestamp.utcnow())
            if isinstance(a_date, datetime):
                a_date = a_date.date()
            
            key = (str(alert.get('customer_id')), str(a_date), str(alert.get('scenario_id')))
            
            if key not in seen_keys:
                seen_keys.add(key)
                deduplicated_alerts.append(alert)
                
        # Persist Results via Bulk Operations
        alert_mappings = []
        exclusion_mappings = []
        trace_mappings = [] # New: Alert Transactions
        
        # Helper index for lookup (Transactions DF is available as transactions_df)
        # Create a quick ID->Amount and ID->UploadID map for performance
        txn_amount_map = {}
        txn_upload_map = {}
        if not transactions_df.empty:
            if 'transaction_amount' in transactions_df.columns:
                txn_amount_map = transactions_df.set_index('transaction_id')['transaction_amount'].to_dict()
            if 'upload_id' in transactions_df.columns:
                txn_upload_map = transactions_df.set_index('transaction_id')['upload_id'].to_dict()

        from models import AlertTransaction

        for alert_data in deduplicated_alerts:
            is_excluded = alert_data.get('excluded', False)
            alert_id = alert_data.get('alert_id') or str(uuid.uuid4())
            
            # ✅ EXTRACT SCALAR VALUES (handle Series)
            def extract_value(data, key, default=None):
                val = data.get(key, default)
                if isinstance(val, pd.Series):
                    return val.iloc[0] if len(val) > 0 else default
                return val
            
            # ✅ Extract customer_id with fallback to lookup from transactions
            customer_id = extract_value(alert_data, 'customer_id')
            
            # If customer_id is None, try to get it from involved transactions
            if customer_id is None or str(customer_id) == 'None':
                involved_txns = alert_data.get('involved_transactions', [])
                if involved_txns and not transactions_df.empty:
                    # Get customer_id from first involved transaction
                    first_txn_id = involved_txns[0] if isinstance(involved_txns, list) else involved_txns
                    matching_txn = transactions_df[transactions_df['transaction_id'] == first_txn_id]
                    if not matching_txn.empty:
                        customer_id = matching_txn.iloc[0]['customer_id']
                        print(f"[FIX] Mapped customer_id from transaction: {customer_id}")
            
            customer_name = extract_value(alert_data, 'customer_name', 'Unknown')
            scenario_id = extract_value(alert_data, 'scenario_id')
            scenario_name = extract_value(alert_data, 'scenario_name')
            alert_date = extract_value(alert_data, 'alert_date', pd.Timestamp.utcnow())
            risk_score = extract_value(alert_data, 'risk_score', 0)
            
            # Determine risk classification
            if risk_score >= 70: risk_classification = 'HIGH'
            elif risk_score >= 40: risk_classification = 'MEDIUM'
            else: risk_classification = 'LOW'
            
            # Prepare Alert Mapping
            alert_mappings.append({
                "alert_id": alert_id,
                "customer_id": str(customer_id),
                "customer_name": str(customer_name) if customer_name else 'Unknown',
                "scenario_id": str(scenario_id),
                "scenario_name": str(scenario_name),
                "scenario_description": f"Generated by {scenario_name}",
                "alert_date": alert_date,
                "alert_status": 'OPN',
                "trigger_details": alert_data.get('trigger_details'),
                "risk_classification": risk_classification,
                "risk_score": risk_score,
                "run_id": run_id,
                "excluded": is_excluded,
                "exclusion_reason": alert_data.get('exclusion_reason'),
                "assigned_to": None,
                "investigation_status": 'New',
                "updated_at": datetime.utcnow()
            })
            
            # Traceability Logic
            involved_ids = alert_data.get('involved_transactions', [])
            if involved_ids:
                total_val = sum([Decimal(str(txn_amount_map.get(tid, 0))) for tid in involved_ids])
                seq = 1
                for tid in involved_ids:
                    amt = Decimal(str(txn_amount_map.get(tid, 0)))
                    pct = (amt / total_val * 100) if total_val > 0 else 0
                    txn_upload = txn_upload_map.get(tid)
                    
                    if txn_upload:
                        trace_mappings.append({
                            "alert_id": alert_id,
                            "transaction_id": tid,
                            "upload_id": txn_upload,
                            "contribution_percentage": round(pct, 2),
                            "is_primary_trigger": False, 
                            "sequence_order": seq
                        })
                    seq += 1
            
            # Prepared Exclusion Log Mapping
            if is_excluded:
                exclusion_mappings.append({
                    "log_id": str(uuid.uuid4()), 
                    "alert_id": alert_id,
                    "exclusion_reason": alert_data.get('exclusion_reason', 'Unknown'),
                    "rule_id": "Refinement",
                    "risk_flags": alert_data.get('trigger_details', {}),
                    "created_at": datetime.utcnow()
                })

        # Execute Bulk Inserts
        if alert_mappings:
            # ✅ DEBUG: Check customer_id values before insert
            print(f"[ALERT DEBUG] Creating {len(alert_mappings)} alerts")
            if alert_mappings:
                sample_alert = alert_mappings[0]
                print(f"[ALERT DEBUG] Sample alert:")
                print(f"  customer_id: '{sample_alert.get('customer_id')}'")
                print(f"  trigger_details: {sample_alert.get('trigger_details', {})}")
            
            self.db.bulk_insert_mappings(Alert, alert_mappings)
        
        if trace_mappings:
            self.db.bulk_insert_mappings(AlertTransaction, trace_mappings)
            
        if exclusion_mappings:
            self.db.bulk_insert_mappings(AlertExclusionLog, exclusion_mappings)

        self.db.commit()

    def _execute_single_scenario(self, scenario_config: dict, customer_ids: List[str], upload_id: str, run_id: str, user_id: str):
        """
        Execute a single scenario for a sample of customers.
        Used for previewing scenario logic.
        """
        # 1. Load Data for these customers
        customers_df, transactions_df = self._load_data_for_customers(user_id, customer_ids)
        
        if transactions_df.empty:
            return pd.DataFrame()

        # 2. Prepare Scenario Config
        conf_data = scenario_config.get('config_json', {}).copy()
        conf_data['scenario_id'] = scenario_config.get('scenario_id', 'PREVIEW')
        conf_data['scenario_name'] = scenario_config.get('scenario_name', 'Preview')
        
        # 3. Apply Field Mappings if present in the config
        if 'field_mappings' in scenario_config and scenario_config['field_mappings']:
             transactions_df = apply_field_mappings_to_df(transactions_df, scenario_config['field_mappings'])
             customers_df = apply_field_mappings_to_df(customers_df, scenario_config['field_mappings'])

        scenario_model = ScenarioConfigModel(**conf_data)
        
        # 4. Initialize Engine and Run
        engine = UniversalScenarioEngine(db_session=self.db)
        alerts = engine.execute(scenario_model, transactions_df, customers_df, run_id)
        
        return pd.DataFrame(alerts)
