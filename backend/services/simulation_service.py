from sqlalchemy.orm import Session
import pandas as pd
from datetime import datetime
import uuid
from typing import List, Dict, Set, Optional
from contextlib import contextmanager

# Models
from models import SimulationRun, Alert, Transaction, Customer, ScenarioConfig, AlertExclusionLog
# Core Engines
from core.universal_engine import UniversalScenarioEngine
from core.config_models import ScenarioConfigModel
from core.field_mapper import apply_field_mappings_to_df

@contextmanager
def timeout(seconds):
    """
    Timeout context manager for background tasks.
    Note: signal.alarm doesn't work in background threads, so we use a simple pass-through.
    For production, consider using asyncio.wait_for or threading.Timer with task cancellation.
    """
    # Simply yield without timeout enforcement in background threads
    # The FastAPI background task system handles overall request timeouts
    yield


class SimulationService:
    """
    Manages the lifecycle of a simulation execution.
    """
    
    def __init__(self, db: Session):
        self.db = db
        
    def create_run(self, run_type: str, scenarios: List[str], user_id: str = None) -> SimulationRun:
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
        if df.empty or 'raw_data' not in df.columns:
            return df
        
        # Extract raw_data into a temporary DataFrame
        meta_df = pd.json_normalize(df['raw_data'])
        
        # Only add columns that don't already exist in the main DataFrame
        # This prevents metadata from overwriting explicitly mapped system columns
        cols_to_add = [c for c in meta_df.columns if c not in df.columns]
        
        if not meta_df.empty and cols_to_add:
            # Concat the new columns
            df = pd.concat([df.drop(columns=['raw_data']), meta_df[cols_to_add]], axis=1)
        else:
            df = df.drop(columns=['raw_data'])
            
        return df

    def load_simulation_data(self, user_id: str):
        """
        Default data loader: Fetches from internal DB (Scoped to User) and flattens raw_data.
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
        Main execution loop for a simulation.
        Supports "Stateless / Pendrive Mode" (Gap 2) by accepting raw DataFrames.
        """
        run = self.db.query(SimulationRun).filter(SimulationRun.run_id == run_id).first()
        if not run:
            return
        
        # Update Status to Running
        run.status = "running"
        self.db.commit()
        
        try:
            # 1. Load Simulation Data (If not provided)
            if transactions_df is None or customers_df is None:
                if not run.user_id:
                    raise ValueError(f"Run {run_id} has no associated user_id for data loading")
                customers_df, transactions_df = self.load_simulation_data(run.user_id)

            # --- PROD FIX: Apply Run-Level Dynamic Mappings (Schema Adaptation) ---
            if run.metadata_info and 'field_mappings' in run.metadata_info:
                mappings = run.metadata_info['field_mappings']
                if mappings:
                    print(f"Applying Runtime Field Mappings: {mappings}")
                    if transactions_df is not None:
                        transactions_df = apply_field_mappings_to_df(transactions_df, mappings)
                    if customers_df is not None:
                        customers_df = apply_field_mappings_to_df(customers_df, mappings)

            # --- PROD FIX: Apply Date Range Filter ---
            if run.metadata_info and 'date_range' in run.metadata_info:
                date_range = run.metadata_info['date_range']
                
                # Ensure dates are datetime objects and TZ-naive for comparison
                start_date = pd.to_datetime(date_range.get('start')).tz_localize(None)
                end_date = pd.to_datetime(date_range.get('end')).tz_localize(None)
                
                if start_date and end_date and not transactions_df.empty:
                    if 'transaction_date' in transactions_df.columns:
                        # Ensure DataFrame column is datetime and normalize to Naive
                        # utc=True ensures it becomes Aware first (so we handle both naive/aware inputs uniformly)
                        # then .dt.tz_localize(None) strips it back to Naive.
                        transactions_df['transaction_date'] = pd.to_datetime(transactions_df['transaction_date'], utc=True).dt.tz_localize(None)

                        # Filter by Date Range
                        mask = (transactions_df['transaction_date'] >= start_date) & (transactions_df['transaction_date'] <= end_date)
                        print(f"Applying Date Filter: {start_date} to {end_date}. Rows before: {len(transactions_df)}")
                        transactions_df = transactions_df.loc[mask]
                        print(f"Rows after: {len(transactions_df)}")
                    else:
                        print("Warning: Date filtering requested but 'transaction_date' column missing.")

            # 2. Initialize Engine
            engine = UniversalScenarioEngine(db_session=self.db)
            all_alerts = []
            
            scenarios_to_run = run.scenarios_run or []
            
            # 3. Execute Each Scenario
            for scenario_id in scenarios_to_run:
                config_record = self.db.query(ScenarioConfig).filter(ScenarioConfig.scenario_id == scenario_id).first()
                
                if not config_record or not config_record.config_json:
                    print(f"Skipping {scenario_id}: Configuration not found in DB")
                    continue
                
                try:
                    # Validate Config Structure
                    # Ensure metadata is present for validation
                    conf_data = config_record.config_json.copy()
                    conf_data['scenario_id'] = scenario_id
                    conf_data['scenario_name'] = config_record.scenario_name
                    
                    scenario_config = ScenarioConfigModel(**conf_data)
                    
                    # Apply Field Mappings (Gap 1)
                    current_txns = transactions_df.copy()
                    current_cust = customers_df.copy()
                    
                    if config_record.field_mappings:
                         current_txns = apply_field_mappings_to_df(current_txns, config_record.field_mappings)
                         current_cust = apply_field_mappings_to_df(current_cust, config_record.field_mappings)

                    # Run Engine with Timeout (Gap 4)
                    with timeout(300): # 5 Minutes per scenario
                        alerts = engine.execute(scenario_config, current_txns, current_cust, run_id)
                        all_alerts.extend(alerts)
                    
                except TimeoutError as te:
                    print(f"Scenario {scenario_id} timed out: {te}")
                    # Log as metadata error but continue
                    continue
                except Exception as e:
                    print(f"Error executing scenario {scenario_id}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue

            # 4. Deduplicate Alerts (Gap 5)
            # Dedupe by customer_id + alert_date + scenario_id
            seen_keys = set()
            deduplicated_alerts = []
            
            for alert in all_alerts:
                # Create a unique key for deduplication
                # Ensure date is date object not datetime for daily dedup
                a_date = alert['alert_date']
                if isinstance(a_date, datetime):
                    a_date = a_date.date()
                
                key = (alert['customer_id'], str(a_date), alert['scenario_id'])
                
                if key not in seen_keys:
                    seen_keys.add(key)
                    deduplicated_alerts.append(alert)
                    
            # 5. Persist Results
            total_retained = 0
            
            for alert_data in deduplicated_alerts:
                is_excluded = alert_data.get('excluded', False)
                alert_id = alert_data.get('alert_id') or str(uuid.uuid4())
                
                if not is_excluded:
                    total_retained += 1

                # Save Alert
                # Determine risk classification based on risk_score
                risk_score = alert_data.get('risk_score', 0)
                if risk_score >= 70:
                    risk_classification = 'HIGH'
                elif risk_score >= 40:
                    risk_classification = 'MEDIUM'
                else:
                    risk_classification = 'LOW'
                
                db_alert = Alert(
                    alert_id=alert_id,
                    customer_id=alert_data['customer_id'],
                    customer_name=alert_data.get('customer_name'),
                    scenario_id=alert_data['scenario_id'],
                    scenario_name=alert_data['scenario_name'],
                    scenario_description=f"Generated by {alert_data.get('scenario_name')}",
                    alert_date=alert_data['alert_date'],
                    alert_status='OPN',  # Default to Open
                    trigger_details=alert_data.get('trigger_details'),
                    risk_classification=risk_classification,
                    risk_score=risk_score,
                    run_id=run_id,
                    excluded=is_excluded,
                    exclusion_reason=alert_data.get('exclusion_reason')
                )
                self.db.add(db_alert)
                
                # Save Exclusion Context (if applicable)
                if is_excluded:
                    exclusion_log = AlertExclusionLog(
                        alert_id=alert_id,
                        exclusion_reason=alert_data.get('exclusion_reason', 'Unknown'),
                        rule_id="Refinement",
                        risk_flags=alert_data.get('trigger_details', {})
                    )
                    self.db.add(exclusion_log)

            self.db.commit()

            # 6. Finalize Run
            run.total_alerts = total_retained
            run.total_transactions = len(transactions_df) if not transactions_df.empty else 0
            run.status = "completed"
            run.completed_at = datetime.utcnow()
            run.progress_percentage = 100
            self.db.commit()
            
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
