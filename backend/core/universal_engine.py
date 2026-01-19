import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import timedelta
import logging
from simpleeval import simple_eval
import uuid

from .config_models import ScenarioConfigModel, TimeWindow
# Assuming SmartLayerProcessor is available
from .smart_layer import SmartLayerProcessor

logger = logging.getLogger(__name__)

class FilterProcessor:
    """
    Handles the filtering of transaction data based on scenario configurations.
    """
    
    def apply_filters(self, transactions: pd.DataFrame, filter_config) -> pd.DataFrame:
        if not filter_config:
            return transactions
            
        df = transactions.copy()
        
        # Handle simple array format from frontend
        if isinstance(filter_config, list):
            for filter_item in filter_config:
                df = self._apply_single_filter(df, filter_item)
            return df
        
        # Handle complex ScenarioFilters object format
        if hasattr(filter_config, 'transaction_type') and filter_config.transaction_type:
            df = df[df['transaction_type'].isin(filter_config.transaction_type)]
            
        if hasattr(filter_config, 'channel') and filter_config.channel:
            df = df[df['channel'].isin(filter_config.channel)]
            
        if hasattr(filter_config, 'direction') and filter_config.direction:
            if filter_config.direction == 'debit':
                df = df[df['debit_credit_indicator'] == 'D']
            elif filter_config.direction == 'credit':
                df = df[df['debit_credit_indicator'] == 'C']
                
        # 2. Amount Range
        if hasattr(filter_config, 'amount_range') and filter_config.amount_range:
            ar = filter_config.amount_range
            if ar.min is not None:
                df = df[df['transaction_amount'] >= ar.min]
            if ar.max is not None:
                df = df[df['transaction_amount'] <= ar.max]
                
        # 3. Custom Field Filters
        if hasattr(filter_config, 'custom_field_filters') and filter_config.custom_field_filters:
            for custom in filter_config.custom_field_filters:
                df = self._apply_single_filter(df, custom)
                
        return df
    
    def _apply_single_filter(self, df: pd.DataFrame, filter_config: Any) -> pd.DataFrame:
        """
        Apply a single filter. Handles both dict (simple) and object (custom) formats.
        Unified logic for cleaner maintenance.
        """
        # Extract fields based on type
        if isinstance(filter_config, dict):
            field = filter_config.get('field')
            operator = filter_config.get('operator')
            value = filter_config.get('value')
        else:
            field = getattr(filter_config, 'field', None)
            operator = getattr(filter_config, 'operator', None)
            value = getattr(filter_config, 'value', None)
            
        if not field:
            return df
            
        if field not in df.columns:
            print(f"[ERROR] Filter field '{field}' not found! Available: {list(df.columns)}")
            return df
        
        # Normalize operator
        op = str(operator).lower() if operator else ''
        
        # SAFE TYPE CASTING
        # Ensure 'value' matches the column's dtype
        target_dtype = df[field].dtype
        
        try:
            if np.issubdtype(target_dtype, np.number):
                if isinstance(value, list):
                    value = [float(v) for v in value]
                else:
                    value = float(value)
            elif np.issubdtype(target_dtype, np.datetime64):
                if isinstance(value, list):
                    value = [pd.to_datetime(v) for v in value]
                else:
                    value = pd.to_datetime(value)
            # Else keep as is (string/object)
        except Exception:
            # If casting fails, we might just proceed (pandas might handle it or error later)
            # But usually it's better to just log and try
            pass

        # Apply Logic
        if op in ['==', 'equals']:
            return df[df[field] == value]
        elif op in ['!=', 'not_equals']:
            return df[df[field] != value]
        elif op in ['>', 'greater_than', 'greaterthan']:
            return df[df[field] > value]
        elif op in ['<', 'less_than', 'lessthan']:
            return df[df[field] < value]
        elif op in ['>=', 'greater_than_or_equal']:
             return df[df[field] >= value]
        elif op in ['<=', 'less_than_or_equal']:
             return df[df[field] <= value]
        elif op == 'in':
            val_list = value if isinstance(value, list) else [value]
            return df[df[field].isin(val_list)]
        elif op == 'contains':
            return df[df[field].astype(str).str.contains(str(value), case=False, na=False)]
        
        return df

class AggregationProcessor:
    """
    Handles data aggregation.
    """
    def aggregate_data(self, transactions: pd.DataFrame, agg_config) -> pd.DataFrame:
        if not agg_config or transactions.empty:
            return pd.DataFrame()
            
        df = transactions.copy()
        group_fields = agg_config.group_by.copy()
        
        # Time Window
        if agg_config.time_window:
            tw = agg_config.time_window
            if tw.unit == 'days' and tw.type == 'calendar':
                if 'transaction_date' in df.columns:
                    df['time_group'] = df['transaction_date'].dt.floor(f'{tw.value}D')
                    group_fields.append('time_group')
            elif tw.unit == 'months' and tw.type == 'calendar':
                 if 'transaction_date' in df.columns:
                    df['time_group'] = df['transaction_date'].dt.to_period('M')
                    group_fields.append('time_group')

        method = agg_config.method
        field = agg_config.field
        
        # Rolling Windows
        if agg_config.time_window and agg_config.time_window.type == 'rolling':
            return self._apply_rolling_window(df, agg_config, group_fields)

        # Standard GroupBy
        try:
            # Ensure all group fields exist
            missing_group = [f for f in group_fields if f not in df.columns]
            if missing_group:
                print(f"[WARN] Missing group fields: {missing_group}")
                return pd.DataFrame()

            if method == 'sum':
                result = df.groupby(group_fields)[field].sum().reset_index()
            elif method == 'count':
                result = df.groupby(group_fields)[field].count().reset_index()
            elif method == 'avg':
                 result = df.groupby(group_fields)[field].mean().reset_index()
            elif method == 'max':
                 result = df.groupby(group_fields)[field].max().reset_index()
            elif method == 'min':
                 result = df.groupby(group_fields)[field].min().reset_index()
            else:
                 return pd.DataFrame()
        except Exception as e:
            print(f"[ERROR] Aggregation Failed: {e}")
            return pd.DataFrame()

        result.rename(columns={field: 'aggregated_value'}, inplace=True)
        return result

    def _apply_rolling_window(self, df: pd.DataFrame, agg_config, group_fields) -> pd.DataFrame:
        tw = agg_config.time_window
        field = agg_config.field
        
        if 'transaction_date' not in df.columns:
            return pd.DataFrame()
            
        window_size = tw.value
        
        if tw.unit == 'months':
            entity_key = 'customer_id' if 'customer_id' in group_fields else group_fields[0]
            df = df.copy()
            df['period'] = df['transaction_date'].dt.to_period('M')
            monthly_agg = df.groupby([entity_key, 'period'])[field].sum().reset_index()
            monthly_agg = monthly_agg.sort_values([entity_key, 'period'])
            monthly_agg['aggregated_value'] = monthly_agg.groupby(entity_key)[field].transform(
                lambda x: x.rolling(window=window_size, min_periods=1).sum()
            )
            monthly_agg['transaction_date'] = monthly_agg['period'].dt.to_timestamp(how='end')
            return monthly_agg[[entity_key, 'transaction_date', 'aggregated_value']]
            
        elif tw.unit == 'days':
            df = df.sort_values(group_fields + ['transaction_date'])
            entity_key = 'customer_id' if 'customer_id' in group_fields else group_fields[0]
            df.set_index('transaction_date', inplace=True)
            rolled = df.groupby(entity_key)[field].rolling(f"{window_size}D")
            
            if agg_config.method == 'sum': result = rolled.sum()
            elif agg_config.method == 'count': result = rolled.count()
            else: result = rolled.sum()
            
            result = result.reset_index()
            result.rename(columns={field: 'aggregated_value'}, inplace=True)
            return result
        return pd.DataFrame()

class ThresholdProcessor:
    def apply_thresholds(self, aggregated_data: pd.DataFrame, customers: pd.DataFrame, threshold_config) -> pd.DataFrame:
        if not threshold_config or aggregated_data.empty:
            return aggregated_data
            
        # Merging logic handled by Smart Merge in Engine now, but we keep this as fallback?
        # Actually, if Engine merged fields, aggregated_data might have lost them due to groupby!
        # Thresholds might need customer attributes (e.g. Segment).
        # We need to re-merge customer data if grouping removed it.
        
        if 'customer_id' in aggregated_data.columns:
             # Check if we need fields
             t_type = threshold_config.type
             needed_field = None
             if t_type == 'segment_based' and threshold_config.segment_based:
                 needed_field = threshold_config.segment_based.segment_field
             elif t_type == 'field_based' and threshold_config.field_based:
                 needed_field = threshold_config.field_based.reference_field
             
             if needed_field and needed_field not in aggregated_data.columns and needed_field in customers.columns:
                 aggregated_data = aggregated_data.merge(customers[['customer_id', needed_field]], on='customer_id', how='left')

        t_type = threshold_config.type
        
        if t_type == 'fixed':
            aggregated_data['threshold'] = threshold_config.fixed_value
        elif t_type == 'segment_based':
            seg = threshold_config.segment_based
            if seg and seg.segment_field in aggregated_data.columns:
                aggregated_data['threshold'] = aggregated_data[seg.segment_field].map(seg.values).fillna(seg.default)
            else:
                aggregated_data['threshold'] = seg.default
        elif t_type == 'field_based' and threshold_config.field_based:
            fb = threshold_config.field_based
            ref = fb.reference_field
            calc = fb.calculation
            def eval_calc(row):
                try:
                    val = row.get(ref, 0)
                    return simple_eval(calc, names={'reference_field': val})
                except: return 0
            aggregated_data['threshold'] = aggregated_data.apply(eval_calc, axis=1)
                
        return aggregated_data

class AlertConditionEvaluator:
    def evaluate_condition(self, data: pd.DataFrame, condition_config) -> pd.DataFrame:
        if data.empty: return pd.DataFrame()
        
        if 'threshold' in data.columns and 'aggregated_value' in data.columns:
             alerts = data[data['aggregated_value'] > data['threshold']].copy()
             if not condition_config: return alerts
             if not getattr(condition_config, 'expression', None): return alerts
        
        if not condition_config: return pd.DataFrame()
        expr = condition_config.expression
        
        def safe_eval(row):
            try:
                names = row.to_dict()
                return simple_eval(expr, names=names)
            except: return False
        
        alerts = data[data.apply(safe_eval, axis=1)].copy()
        return alerts

class UniversalScenarioEngine:
    """
    Universal, schema-agnostic AML scenario execution engine.
    
    This engine dynamically determines data requirements from scenario configuration
    and executes a multi-stage pipeline to generate alerts:
    
    Pipeline Stages:
        1. Customer Field Detection - Identifies required customer fields
        2. Smart Merge - Joins customer data only if needed
        3. Filter Application - Applies transaction filters
        4. Aggregation - Groups and aggregates data
        5. Threshold Evaluation - Checks alert thresholds
        6. Condition Evaluation - Evaluates alert conditions
        7. Refinements - Applies smart exclusions
    
    The engine is designed to work with any schema by using flexible field mapping
    and dynamic column detection.
    
    Attributes:
        db_session: Database session for smart layer queries (optional)
        filter_processor: Handles transaction filtering
        aggregation_processor: Handles data aggregation
        threshold_processor: Evaluates alert thresholds
        condition_evaluator: Evaluates alert conditions
        smart_layer: Applies intelligent exclusions (optional)
    
    Example:
        >>> engine = UniversalScenarioEngine(db_session=db)
        >>> alerts = engine.execute(
        ...     scenario_config=scenario,
        ...     transactions=txn_df,
        ...     customers=cust_df,
        ...     run_id="run-123"
        ... )
        >>> print(f"Generated {len(alerts)} alerts")
    """
    
    def __init__(self, db_session=None):
        """
        Initialize the scenario execution engine.
        
        Args:
            db_session: SQLAlchemy database session for smart layer queries.
                       If None, smart layer refinements will be skipped.
        """
        self.db_session = db_session
        self.filter_processor = FilterProcessor()
        self.aggregation_processor = AggregationProcessor()
        self.threshold_processor = ThresholdProcessor()
        self.condition_evaluator = AlertConditionEvaluator()
        self.smart_layer = SmartLayerProcessor(db_session) if db_session else None
    
    def _get_required_customer_fields(self, scenario_config: ScenarioConfigModel) -> set:
        """
        Intelligently determines which customer fields are needed for the scenario.
        
        Scans the scenario configuration to identify all customer-related fields
        referenced in filters, aggregations, thresholds, and conditions. This
        ensures smart merging - only joining customer data if actually needed.
        
        Args:
            scenario_config: Validated scenario configuration
            
        Returns:
            Set of customer field names required for execution
            
        Example:
            >>> fields = engine._get_required_customer_fields(scenario)
            >>> print(fields)
            {'occupation', 'annual_income', 'risk_score'}
        """
        required = set()
        
        # Check filters
        if scenario_config.filters:
            for f in scenario_config.filters:
                if hasattr(f, 'field') and f.field:
                    if f.field.startswith('customer_'):
                        required.add(f.field)
        
        # Check aggregation group_by
        if scenario_config.aggregation and hasattr(scenario_config.aggregation, 'group_by'):
            for field in scenario_config.aggregation.group_by or []:
                if field.startswith('customer_'):
                    required.add(field)
        
        # Check threshold calculations
        if scenario_config.threshold and hasattr(scenario_config.threshold, 'calculation'):
            calc = scenario_config.threshold.calculation or ""
            for field in ['customer_type', 'occupation', 'annual_income', 'risk_score']:
                if field in calc:
                    required.add(field)
        
        # Check alert conditions
        if scenario_config.alert_condition and hasattr(scenario_config.alert_condition, 'expression'):
            expr = scenario_config.alert_condition.expression or ""
            for field in ['customer_type', 'occupation', 'annual_income', 'risk_score']:
                if field in expr:
                    required.add(field)
        
        return required

    def _smart_merge_customers(self, transactions: pd.DataFrame, customers: pd.DataFrame, required_fields: set) -> pd.DataFrame:
        """
        Intelligently merges customer data with transactions ONLY if required.
        
        Performs a left join only when customer fields are actually needed by the
        scenario. This optimization significantly improves performance for scenarios
        that only analyze transaction data.
        
        Args:
            transactions: Transaction DataFrame
            customers: Customer DataFrame
            required_fields: Set of customer fields needed (from _get_required_customer_fields)
            
        Returns:
            Merged DataFrame with customer fields if needed, otherwise original transactions
            
        Example:
            >>> enriched = engine._smart_merge_customers(txns, custs, {'occupation'})
            >>> assert 'occupation' in enriched.columns
        """
        if not required_fields:
            print("[OPTIMIZATION] No customer fields needed - skipping merge")
            return transactions.copy()
        
        if customers.empty:
            print("[WARN] Customer data is empty, cannot merge")
            return transactions.copy()
        
        # Only select required customer columns + customer_id for join
        customer_cols = ['customer_id'] + [f for f in required_fields if f in customers.columns]
        
        # Deduplicate customers by customer_id to prevent merge explosion
        customers_subset = customers[customer_cols].copy()
        customers_subset = customers_subset.drop_duplicates(subset=['customer_id'])
        
        # DEBUG: Check for duplicate columns BEFORE merge
        print(f"[DEBUG] Transactions columns: {list(transactions.columns)}")
        print(f"[DEBUG] Customers columns: {list(customers_subset.columns)}")
        
        # Check if transactions has duplicate customer_id columns
        txn_customer_id_count = list(transactions.columns).count('customer_id')
        cust_customer_id_count = list(customers_subset.columns).count('customer_id')
        
        if txn_customer_id_count > 1:
            print(f"[ERROR] Transactions DataFrame has {txn_customer_id_count} 'customer_id' columns!")
            # Drop duplicates, keeping first
            transactions = transactions.loc[:, ~transactions.columns.duplicated()]
            print(f"[FIX] Dropped duplicate columns. New columns: {list(transactions.columns)}")
        
        if cust_customer_id_count > 1:
            print(f"[ERROR] Customers DataFrame has {cust_customer_id_count} 'customer_id' columns!")
            customers_subset = customers_subset.loc[:, ~customers_subset.columns.duplicated()]
            print(f"[FIX] Dropped duplicate columns. New columns: {list(customers_subset.columns)}")
        
        # Perform left join
        merged = transactions.merge(
            customers_subset,
            on='customer_id',
            how='left',
            suffixes=('', '_cust')
        )
        
        print(f"[MERGE] Joined {len(required_fields)} customer fields")
        return merged

    def execute(self, scenario_config: ScenarioConfigModel, transactions: pd.DataFrame, customers: pd.DataFrame, run_id: str) -> List[Dict]:
        """
        Execute an AML scenario against transaction data.
        
        This is the main entry point for scenario execution. It orchestrates the
        entire pipeline from filtering to alert generation.
        
        Args:
            scenario_config: Validated scenario configuration (Pydantic model)
            transactions: Transaction DataFrame with columns:
                - transaction_id (str, required)
                - customer_id (str, required)
                - transaction_date (datetime, required)
                - transaction_amount (float, required)
                - transaction_type, channel, etc. (optional)
            customers: Customer DataFrame with columns:
                - customer_id (str, required)
                - customer_name, occupation, annual_income, etc. (optional)
            run_id: Unique identifier for this simulation run
            
        Returns:
            List of alert dictionaries, each containing:
                - alert_id: Unique alert identifier
                - customer_id: Customer who triggered alert
                - customer_name: Customer name
                - scenario_id: Scenario that generated alert
                - scenario_name: Human-readable scenario name
                - alert_date: Date alert was triggered
                - risk_score: Calculated risk score
                - trigger_details: JSON with alert details
                - run_id: Simulation run identifier
                
        Raises:
            ValueError: If required columns are missing from input DataFrames
            
        Example:
            >>> alerts = engine.execute(
            ...     scenario_config=rapid_movement_scenario,
            ...     transactions=txn_df,
            ...     customers=cust_df,
            ...     run_id="run-abc-123"
            ... )
            >>> for alert in alerts:
            ...     print(f"Alert for {alert['customer_name']}: {alert['risk_score']}")
        """
        print(f"\n{'='*60}")
        print(f"[EXECUTE] Scenario: {scenario_config.scenario_name}")
        
        # Step 0: Intelligent Customer Field Detection
        required_customer_fields = self._get_required_customer_fields(scenario_config)
        print(f"[STEP 0] Required customer fields: {required_customer_fields}")
        
        # Step 1: Smart Merge
        enriched_data = self._smart_merge_customers(transactions, customers, required_customer_fields)
        print(f"[STEP 1] Data enrichment complete: {len(enriched_data)} rows")
        
        # Step 2: Apply Filters
        filtered = self.filter_processor.apply_filters(enriched_data, scenario_config.filters)
        if filtered.empty:
            print("[WARN] All transactions filtered out!")
            return []
        print(f"[STEP 2] After filters: {len(filtered)} rows")
        
        # Step 3: Aggregations
        aggregated = self.aggregation_processor.aggregate_data(filtered, scenario_config.aggregation)
        if aggregated.empty:
            print("[WARN] No data after aggregation")
            return []
        print(f"[STEP 3] After aggregation: {len(aggregated)} rows")
        
        # Step 4: Thresholds
        with_thresh = self.threshold_processor.apply_thresholds(aggregated, customers, scenario_config.threshold)
        print(f"[STEP 4] Thresholds applied: {len(with_thresh)} rows")
        
        # Step 5: Conditions
        alerts_df = self.condition_evaluator.evaluate_condition(with_thresh, scenario_config.alert_condition)
        if alerts_df.empty:
            print("[INFO] No alerts triggered")
            return []
        print(f"[STEP 5] Alerts triggered: {len(alerts_df)}")
        
        # Step 6: Refinements
        if scenario_config.refinements and self.smart_layer:
            refinements_list = [r.dict() for r in scenario_config.refinements]
            alerts_df = self.smart_layer.apply_refinements(alerts_df, enriched_data, refinements_list)
            print(f"[STEP 6] After refinements: {len(alerts_df)} alerts")
            
        # Step 7: Metadata
        alerts_df['scenario_id'] = scenario_config.scenario_id
        alerts_df['scenario_name'] = scenario_config.scenario_name
        alerts_df['run_id'] = run_id
        
        return self._generate_alert_objects(alerts_df)

    def _generate_alert_objects(self, df: pd.DataFrame) -> List[Dict]:
        alerts = []
        for _, row in df.iterrows():
            # Calculate risk score based on aggregated amount
            # Higher amounts = higher risk
            agg_amount = row.get('aggregated_amount', 0)
            if agg_amount >= 100000:  # Very high amount
                risk_score = 85
            elif agg_amount >= 50000:  # High amount
                risk_score = 70
            elif agg_amount >= 20000:  # Medium-high amount
                risk_score = 55
            elif agg_amount >= 10000:  # Medium amount
                risk_score = 40
            else:  # Lower amounts
                risk_score = 25
            
            base = {
                "alert_id": str(uuid.uuid4()),
                "scenario_id": row.get('scenario_id'),
                "scenario_name": row.get('scenario_name'),
                "customer_id": row.get('customer_id'),
                "customer_name": row.get('customer_name', 'Unknown'),
                "run_id": row.get('run_id'),
                "alert_date": row.get('transaction_date', pd.Timestamp.utcnow()),
                "risk_score": risk_score,
                "excluded": row.get('excluded', False),
                "exclusion_reason": row.get('exclusion_reason'),
                "is_excluded": row.get('excluded', False)
            }
            details = row.to_dict()
            base['trigger_details'] = {str(k): str(v) for k,v in details.items()}
            alerts.append(base)
        return alerts
