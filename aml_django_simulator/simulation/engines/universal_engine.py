import logging
import uuid
from typing import List, Dict, Any
from datetime import datetime, timedelta
from django.db.models import Sum, Count, Q, F, Avg, Max, Min
from django.utils import timezone
from simulation.models import Transaction, Customer, Alert, AlertTransaction, ScenarioConfig
from .smart_layer import SmartLayerProcessor
import json

logger = logging.getLogger(__name__)

class UniversalScenarioEngine:
    """
    Universal, schema-agnostic AML scenario execution engine (Django Native).
    Replaces DataFrame operations with efficient SQL queries via Django ORM.
    """

    def __init__(self):
        self.smart_layer = SmartLayerProcessor()

    def execute(self, scenario_config_id: str, run_id: str, user_id: str) -> List[Dict]:
        """
        Execute a scenario by fetching its config from DB.
        """
        try:
            from simulation.models import SimulationRun
            config_obj = ScenarioConfig.objects.get(scenario_id=scenario_config_id)
            config = config_obj.config_json or {}
            run = SimulationRun.objects.get(run_id=run_id)
            
            # Use the core logic method
            alerts = self.run_scenario_logic(
                config=config,
                upload_id=run.upload_id,
                user_id=user_id,
                scenario_name=config_obj.scenario_name,
                field_mappings=run.metadata_info.get('field_mappings') if run.metadata_info else None
            )
            
            # Enrich with IDs needed for persistence
            for alert in alerts:
                alert['scenario_id'] = scenario_config_id
                alert['run_id'] = run_id
                
            return alerts

        except ScenarioConfig.DoesNotExist:
            logger.error(f"Scenario {scenario_config_id} not found")
            return []
        except Exception as e:
            logger.error(f"Execution failed for {scenario_config_id}: {e}", exc_info=True)
            return []

    def run_scenario_logic(self, config: Dict, upload_id: str = None, user_id: str = "demo-user", scenario_name: str = "Test Scenario", field_mappings: Dict = None) -> List[Dict]:
        """
        Core scenario execution logic, decoupled from specific DB records for Config/Run.
        Enables dry-runs and API-based testing.
        """
        self.field_mappings = field_mappings or {}
        try:
            # 1. Build Base Query (Filters)
            if upload_id:
                qs = Transaction.objects.filter(upload_id=upload_id)
            else:
                qs = Transaction.objects.filter(upload__status='active')
            
            qs = qs.select_related('customer')
            
            # Apply Scenario Filters
            qs = self.apply_filters(qs, config.get('filters', []))
            
            # 2. Aggregation
            aggregation = config.get('aggregation', {})
            agg_field = aggregation.get('field', 'transaction_amount')
            
            # Resolve aggregation field via mapping
            agg_field = self.field_mappings.get(agg_field, agg_field)
            agg_function = aggregation.get('function', 'sum')
            rolling_window_days = aggregation.get('rolling_window_days', 30)
            time_window = aggregation.get('time_window', {})
            count_threshold = aggregation.get('count_threshold', {})

            # Rolling window days for later scan
            rolling_window_days = aggregation.get('rolling_window_days', 30)

            txns = qs.values('transaction_id', 'customer_id', 'created_at', 'raw_data',
                             'customer__raw_data', 'customer__customer_id')

            grouped_data = {}
            for txn in txns:
                cust_id = txn['customer_id']
                raw = txn['raw_data']

                try:
                    val = float(raw.get(agg_field, 0))
                except (TypeError, ValueError):
                    val = 0.0

                if cust_id not in grouped_data:
                    grouped_data[cust_id] = {
                        'values': [],  # Store all values for flexible aggregation
                        'txns': [],
                        'dates': [],
                        'customer_data': txn['customer__raw_data'] or {}
                    }

                grouped_data[cust_id]['values'].append(val)
                grouped_data[cust_id]['txns'].append(txn['transaction_id'])
                grouped_data[cust_id]['dates'].append(txn['created_at'])

            # 3. Thresholds and Alert Generation
            threshold_cfg = config.get('threshold', {})
            threshold_type = threshold_cfg.get('type', 'fixed')

            alerts = []
            for cust_id, data in grouped_data.items():
                # 3. Identify Peak Window (Sliding Window Scan)
                # We sort transactions by date and find the window of size 'rolling_window_days' 
                # that yields the maximum aggregate value.
                items = sorted(zip(data['dates'], data['values'], data['txns']))
                
                max_agg_val = 0.0
                best_window_txns = []
                best_window_date = timezone.now()
                
                if not items:
                    continue

                for i in range(len(items)):
                    current_start_date = items[i][0]
                    current_window_end = current_start_date + timedelta(days=rolling_window_days or 30)
                    
                    window_values = []
                    window_txns = []
                    
                    for j in range(i, len(items)):
                        if items[j][0] <= current_window_end:
                            window_values.append(items[j][1])
                            window_txns.append(items[j][2])
                        else:
                            break
                    
                    # Calculate aggregate for this window
                    if agg_function == 'sum':
                        current_agg = sum(window_values)
                    elif agg_function == 'count':
                        current_agg = float(len(window_values))
                    elif agg_function == 'avg':
                        current_agg = sum(window_values) / len(window_values)
                    elif agg_function == 'max':
                        current_agg = max(window_values)
                    elif agg_function == 'min':
                        current_agg = min(window_values)
                    else:
                        current_agg = sum(window_values)
                    
                    if current_agg > max_agg_val:
                        max_agg_val = current_agg
                        best_window_txns = window_txns
                        best_window_date = items[j-1][0] if j > i else items[i][0]

                agg_val = max_agg_val
                txn_count = len(best_window_txns)
                
                if count_threshold.get('enabled'):
                    min_txns = count_threshold.get('min_transactions', 1)
                    if txn_count < min_txns:
                        continue

                # Calculate threshold based on type
                if threshold_type == 'dynamic':
                    dynamic_cfg = threshold_cfg.get('dynamic', {})
                    try:
                        threshold_val = self.calculate_dynamic_threshold(dynamic_cfg, data['customer_data'])
                    except Exception as e:
                        logger.warning(f"Dynamic threshold calculation failed for {cust_id}: {e}")
                        threshold_val = float(threshold_cfg.get('fixed_value', 10000))
                elif threshold_type == 'segment':
                    segment_cfg = threshold_cfg.get('segment', {})
                    threshold_val = self.calculate_segment_threshold(segment_cfg, data['customer_data'])
                else:
                    # Default to fixed
                    threshold_val = float(threshold_cfg.get('fixed_value', 0))
                
                if agg_val >= threshold_val:
                    risk_score = min(100, int((agg_val / threshold_val) * 50)) if threshold_val > 0 else 50

                    reason = self._generate_trigger_reason(
                        cust_id=cust_id,
                        customer_data=data['customer_data'],
                        agg_val=agg_val,
                        agg_function=agg_function,
                        agg_field=agg_field,
                        rolling_window_days=rolling_window_days,
                        txn_count=txn_count,
                        threshold_val=threshold_val,
                        threshold_cfg=threshold_cfg,
                        scenario_name=scenario_name
                    )

                    # Get alert_metadata and enrichment from config
                    alert_metadata = config.get('alert_metadata', {})
                    enrichment = config.get('enrichment', {})

                    # Build enrichment data if enabled
                    enrichment_data = {}
                    if enrichment.get('include_customer_profile', False):
                        enrichment_data['customer_profile'] = {
                            'name': data['customer_data'].get('customer_name', data['customer_data'].get('name', 'Unknown')),
                            'occupation': data['customer_data'].get('occupation', 'Unknown'),
                            'annual_income': data['customer_data'].get('annual_income', 0),
                            'account_type': data['customer_data'].get('account_type', 'Unknown'),
                            'customer_type': data['customer_data'].get('customer_type', 'Unknown'),
                            'risk_score': data['customer_data'].get('risk_score', 0)
                        }

                    if enrichment.get('calculate_velocity_metrics', False):
                        # Calculate velocity metrics from transaction dates
                        dates = sorted(data['dates'])
                        if len(dates) > 1:
                            total_days = (dates[-1] - dates[0]).days or 1
                            enrichment_data['velocity_metrics'] = {
                                'transactions_per_day': round(len(dates) / total_days, 2),
                                'avg_amount_per_transaction': round(agg_val / len(values) if values else 0, 2),
                                'date_range_days': total_days
                            }

                    if enrichment.get('include_geographic_risk', False):
                        # Include geographic data if available
                        enrichment_data['geographic_risk'] = {
                            'country': data['customer_data'].get('country', 'Unknown'),
                            'region': data['customer_data'].get('region', 'Unknown')
                        }

                    alert = {
                        "alert_id": str(uuid.uuid4()),
                        "customer_id": cust_id,
                        "scenario_name": scenario_name,
                        "alert_date": best_window_date,
                        "risk_score": risk_score,
                        "risk_classification": alert_metadata.get('severity', 'MEDIUM'),
                        "trigger_details": {
                            "aggregated_value": agg_val,
                            "aggregation_function": agg_function.upper(),
                            "aggregation_field": agg_field,
                            "rolling_window_days": rolling_window_days,
                            "threshold_used": threshold_val,
                            "threshold_type": threshold_type,
                            "transaction_count": txn_count
                        },
                        "trigger_reason": reason,
                        "involved_transactions": best_window_txns,
                        "alert_metadata": {
                            "severity": alert_metadata.get('severity', 'MEDIUM'),
                            "category": alert_metadata.get('category', ''),
                            "sub_category": alert_metadata.get('sub_category', ''),
                            "regulatory_tags": alert_metadata.get('regulatory_tags', []),
                            "investigation_priority": alert_metadata.get('investigation_priority', 3),
                            "auto_escalate": alert_metadata.get('auto_escalate', False)
                        },
                        "enrichment_data": enrichment_data
                    }
                    alerts.append(alert)

            # 4. Refinements (Smart Layer)
            refinements = config.get('refinements', [])
            if refinements:
                alerts = self.smart_layer.apply_refinements(alerts, user_id, refinements)

            return alerts
        except Exception as e:
            logger.error(f"Logic execution failed: {e}", exc_info=True)
            return []

    def apply_filters(self, qs, filters):
        """Build Q object from filter config supporting transaction and customer fields"""
        # Discover schema for this queryset to handle non-prefixed fields
        tx_fields = set()
        cust_fields = set()
        
        # Get upload_id from queryset if possible (optimized)
        first_tx = qs.first()
        if first_tx:
            upload_id = first_tx.upload_id
            
            # Inspect transaction fields
            if first_tx.raw_data:
                tx_fields = set(first_tx.raw_data.keys())
            
            # Inspect customer fields
            last_cust = Customer.objects.filter(upload_id=upload_id).first()
            if last_cust and last_cust.raw_data:
                cust_fields = set(last_cust.raw_data.keys())

        q_obj = Q()
        logger.info(f"Applying {len(filters)} filters: {filters}")
        for f in filters:
            field = f.get('field')
            val = f.get('value')
            op = f.get('operator')
            
            if not field or not op:
                continue

            # Resolve field name via mapping
            field = self.field_mappings.get(field, field)

            # Handle customer table prefix or auto-detection
            if field.startswith('customer.'):
                clean_field = field.replace('customer.', '')
                orm_lookup = f"customer__raw_data__{clean_field}"
            elif field in cust_fields and field not in tx_fields:
                # Auto-route to customer if field only exists there
                orm_lookup = f"customer__raw_data__{field}"
            else:
                orm_lookup = f"raw_data__{field}"
            
            # Map operators with more intelligence
            if op in ['equals', '==']:
                # For exact match, try to be robust about types
                try:
                    # If val looks like a number, try numeric match too
                    fval = float(val)
                    q_obj &= (Q(**{orm_lookup: val}) | Q(**{orm_lookup: fval}))
                except (ValueError, TypeError):
                    # Otherwise stick to original val (string)
                    q_obj &= Q(**{orm_lookup: val})
            elif op in ['greater_than', '>']:
                try:
                    q_obj &= Q(**{f"{orm_lookup}__gt": float(val)})
                except:
                    q_obj &= Q(**{f"{orm_lookup}__gt": val})
            elif op == '>=':
                try:
                    q_obj &= Q(**{f"{orm_lookup}__gte": float(val)})
                except:
                    q_obj &= Q(**{f"{orm_lookup}__gte": val})
            elif op in ['less_than', '<']:
                try:
                    q_obj &= Q(**{f"{orm_lookup}__lt": float(val)})
                except:
                    q_obj &= Q(**{f"{orm_lookup}__lt": val})
            elif op == '<=':
                try:
                    q_obj &= Q(**{f"{orm_lookup}__lte": float(val)})
                except:
                    q_obj &= Q(**{f"{orm_lookup}__lte": val})
            elif op == 'in':
                if isinstance(val, str):
                    val = [v.strip() for v in val.split(',')]
                # For IN, try to also include numeric versions if possible
                ext_val = []
                for v in val:
                    ext_val.append(v)
                    try:
                        ext_val.append(float(v))
                    except: pass
                q_obj &= Q(**{f"{orm_lookup}__in": ext_val})
        
        logger.info(f"Generated Q Object: {q_obj}")
        filtered_qs = qs.filter(q_obj)
        logger.info(f"Records after filtering: {filtered_qs.count()}")
        return filtered_qs

    def calculate_dynamic_threshold(self, dynamic_cfg: Dict, customer_data: Dict) -> float:
        """
        Evaluates a dynamic threshold expression.
        Uses reference_field from customer_data and applies the formula.
        Supports fallback_value, min_threshold, and max_threshold bounds.
        Example formula: 'reference_field * 0.5'
        """
        reference_field = dynamic_cfg.get('reference_field', '')
        formula = dynamic_cfg.get('formula', '')
        fallback_value = float(dynamic_cfg.get('fallback_value', 50000))
        min_threshold = dynamic_cfg.get('min_threshold')
        max_threshold = dynamic_cfg.get('max_threshold')

        if not reference_field or not formula:
            return fallback_value

        try:
            # Get the reference field value from customer data
            base_val = float(customer_data.get(reference_field, 0))

            # Replace 'reference_field' in formula with actual value and evaluate
            calc_formula = formula.replace('reference_field', str(base_val))
            result = float(eval(calc_formula))

            # Apply bounds if specified
            if min_threshold is not None:
                result = max(float(min_threshold), result)
            if max_threshold is not None:
                result = min(float(max_threshold), result)

            return max(0, result)
        except Exception as e:
            logger.warning(f"Dynamic threshold formula evaluation failed: {e}")
            return fallback_value

    def calculate_segment_threshold(self, segment_cfg: Dict, customer_data: Dict) -> float:
        """
        Returns threshold based on customer segment.
        Looks up the segment field value in customer_data and finds matching threshold.
        If no match found, returns the first segment's threshold or a high default.
        """
        segment_field = segment_cfg.get('field', '')
        segment_values = segment_cfg.get('values', [])

        # If no segment config, return high threshold (essentially no trigger)
        if not segment_field or not segment_values:
            return float('inf')

        # Get customer's segment value
        customer_segment = str(customer_data.get(segment_field, '')).strip()

        # Find matching segment threshold
        for seg in segment_values:
            if str(seg.get('segment', '')).strip().lower() == customer_segment.lower():
                return float(seg.get('threshold', 10000))

        # If no match found, return infinity (no alert for undefined segments)
        return float('inf')
    def _generate_trigger_reason(self, cust_id: str, customer_data: Dict, agg_val: float, agg_function: str, agg_field: str, rolling_window_days: int, txn_count: int, threshold_val: float, threshold_cfg: Dict, scenario_name: str) -> str:
        """Generates a human-readable reason for the alert."""
        name = customer_data.get('customer_name', customer_data.get('name', cust_id))
        occupation = customer_data.get('occupation', 'Unknown')
        income = customer_data.get('annual_income', 0)

        reason = f"Customer {name} ({occupation}, Income: {income}) triggered '{scenario_name}'. "
        reason += f"{agg_function.upper()}({agg_field}): {agg_val:,.2f} across {txn_count} transactions in {rolling_window_days}-day window. "

        t_type = threshold_cfg.get('type', 'fixed')
        if t_type == 'dynamic':
            dynamic_cfg = threshold_cfg.get('dynamic', {})
            ref_field = dynamic_cfg.get('reference_field', '?')
            formula = dynamic_cfg.get('formula', '?')
            reason += f"Dynamic threshold of {threshold_val:,.2f} used (formula: {formula}, based on {ref_field}). "
        elif t_type == 'segment':
            segment_cfg = threshold_cfg.get('segment', {})
            seg_field = segment_cfg.get('field', '?')
            seg_value = customer_data.get(seg_field, 'Unknown')
            reason += f"Segment-based threshold of {threshold_val:,.2f} used (segment: {seg_field}={seg_value}). "
        else:
            reason += f"Fixed threshold of {threshold_val:,.2f} used. "

        return reason
