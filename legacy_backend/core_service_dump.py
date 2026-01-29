"""
COMPREHENSIVE DUMP OF CORE & SERVICE FILES
===========================================
This file contains all the questionable/duplicate files from core/ and services/
for analysis before refactoring.

Purpose: Identify what can be deleted, merged, or consolidated.
"""

# =============================================================================
# FILE 1: core/config_models.py (82 lines)
# Purpose: Pydantic models for scenario configuration
# Status: ✅ KEEP - Used by universal_engine.py
# =============================================================================

"""
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict, Union, Literal

# --- Filter Models ---
class AmountRange(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None

class CustomFilter(BaseModel):
    field: str
    operator: Literal['equals', 'contains', 'greater_than', 'less_than', 'in']
    value: Union[str, int, float, List[Union[str, int, float]]]

class ScenarioFilters(BaseModel):
    transaction_type: Optional[List[str]] = None
    channel: Optional[List[str]] = None
    direction: Optional[Literal['debit', 'credit', 'both']] = 'both'
    customer_type: Optional[List[str]] = None
    amount_range: Optional[AmountRange] = None
    custom_field_filters: Optional[List[CustomFilter]] = None

# --- Aggregation Models ---
class TimeWindow(BaseModel):
    value: int
    unit: Literal['days', 'hours', 'months']
    type: Literal['rolling', 'calendar'] = 'calendar'

class ScenarioAggregation(BaseModel):
    method: Literal['sum', 'count', 'avg', 'max', 'min']
    field: str
    group_by: List[str]
    time_window: Optional[TimeWindow] = None

# --- Threshold Models ---
class FieldBasedThreshold(BaseModel):
    reference_field: str
    calculation: str # e.g. "reference_field * 3 / 12"

class SegmentBasedThreshold(BaseModel):
    segment_field: str
    values: Dict[str, float]
    default: float = 0.0

class ScenarioThreshold(BaseModel):
    type: Literal['fixed', 'customer_based', 'segment_based', 'field_based', 'dynamic']
    fixed_value: Optional[float] = None
    field_based: Optional[FieldBasedThreshold] = None
    segment_based: Optional[SegmentBasedThreshold] = None

# --- Alert Condition Models ---
class AdditionalCondition(BaseModel):
    field: str
    operator: Literal['equals', 'greater_than', 'less_than']
    value: Union[str, int, float]

class AlertCondition(BaseModel):
    expression: str # e.g. "aggregated_value > threshold"
    additional_conditions: Optional[List[AdditionalCondition]] = None

# --- Refinement Config ---
class RefinementConfig(BaseModel):
    type: Literal['event_based', 'behavioral', 'threshold_adjustment']
    enabled: bool = True
    config: Dict[str, Any]

# --- Top Level Configuration ---
class ScenarioConfigModel(BaseModel):
    scenario_id: str
    scenario_name: str
    description: Optional[str] = None
    frequency: Literal['daily', 'monthly', 'realtime', 'end_of_month'] = 'daily'
    
    filters: Optional[Union[ScenarioFilters, List[Dict[str, Any]]]] = None
    aggregation: Optional[ScenarioAggregation] = None
    threshold: Optional[ScenarioThreshold] = None
    alert_condition: Optional[AlertCondition] = None
    
    refinements: Optional[List[RefinementConfig]] = None
    field_mappings: Optional[Dict[str, str]] = None
"""

# =============================================================================
# FILE 2: core/data_quality.py (228 lines)
# Purpose: Data quality validation for uploads
# Status: ⚠️ CONSOLIDATE - Overlaps with services/data_quality_service.py
# Recommendation: Keep this one, delete services/data_quality_service.py
# =============================================================================

"""
Data Quality Validation

Validates uploaded data for quality issues before processing:
- Negative amounts
- Future dates
- Missing critical fields
- Duplicates
- Data type mismatches

import pandas as pd
from typing import Dict, List, Any
from datetime import datetime, timezone
import structlog

logger = structlog.get_logger("data_quality")


class DataQualityValidator:
    '''
    Validates data quality for transactions and customers.
    
    Returns a quality report with:
    - valid: bool (whether data passes validation)
    - issues: list of quality issues found
    - quality_score: 0-100 score
    - total_rows: number of rows validated
    '''
    
    @staticmethod
    def validate_transactions(df: pd.DataFrame) -> Dict[str, Any]:
        '''Validate transaction data quality.'''
        issues = []
        warnings = []
        
        # Check for negative amounts
        negative_amounts = (df['transaction_amount'] < 0).sum()
        if negative_amounts > 0:
            issues.append({
                "severity": "error",
                "field": "transaction_amount",
                "message": f"{negative_amounts} transactions have negative amounts",
                "count": negative_amounts
            })
        
        # Check for future dates
        now = pd.Timestamp.now(tz=timezone.utc)
        df['transaction_date'] = pd.to_datetime(df['transaction_date'], utc=True)
        future_dates = (df['transaction_date'] > now).sum()
        if future_dates > 0:
            warnings.append({
                "severity": "warning",
                "field": "transaction_date",
                "message": f"{future_dates} transactions are future-dated",
                "count": future_dates
            })
        
        # Check for duplicates
        if 'transaction_id' in df.columns:
            dupes = df.duplicated(subset=['transaction_id']).sum()
            if dupes > 0:
                issues.append({
                    "severity": "error",
                    "field": "transaction_id",
                    "message": f"{dupes} duplicate transaction IDs found",
                    "count": dupes
                })
        
        # Check for missing customer IDs
        missing_customers = df['customer_id'].isna().sum()
        if missing_customers > 0:
            issues.append({
                "severity": "error",
                "field": "customer_id",
                "message": f"{missing_customers} transactions missing customer_id",
                "count": missing_customers
            })
        
        # Calculate quality score
        total_issues = len(issues)
        total_warnings = len(warnings)
        quality_score = max(0, 100 - (total_issues * 15) - (total_warnings * 5))
        
        is_valid = total_issues == 0
        
        result = {
            "valid": is_valid,
            "issues": issues,
            "warnings": warnings,
            "total_rows": len(df),
            "quality_score": quality_score,
            "summary": {
                "errors": total_issues,
                "warnings": total_warnings,
                "clean_rows": len(df) - sum(i['count'] for i in issues + warnings)
            }
        }
        
        return result
    
    @staticmethod
    def validate_customers(df: pd.DataFrame) -> Dict[str, Any]:
        '''Validate customer data quality.'''
        issues = []
        warnings = []
        
        # Check for duplicate customer IDs
        if 'customer_id' in df.columns:
            dupes = df.duplicated(subset=['customer_id']).sum()
            if dupes > 0:
                issues.append({
                    "severity": "error",
                    "field": "customer_id",
                    "message": f"{dupes} duplicate customer IDs found",
                    "count": dupes
                })
        
        # Check for missing customer IDs
        missing_ids = df['customer_id'].isna().sum()
        if missing_ids > 0:
            issues.append({
                "severity": "error",
                "field": "customer_id",
                "message": f"{missing_ids} customers missing customer_id",
                "count": missing_ids
            })
        
        # Calculate quality score
        total_issues = len(issues)
        total_warnings = len(warnings)
        quality_score = max(0, 100 - (total_issues * 15) - (total_warnings * 5))
        
        is_valid = total_issues == 0
        
        result = {
            "valid": is_valid,
            "issues": issues,
            "warnings": warnings,
            "total_rows": len(df),
            "quality_score": quality_score,
            "summary": {
                "errors": total_issues,
                "warnings": total_warnings,
                "clean_rows": len(df) - sum(i['count'] for i in issues + warnings)
            }
        }
        
        return result
"""

# =============================================================================
# FILE 3: core/smart_layer.py (263 lines)
# Purpose: Event detection and smart alert refinement
# Status: ✅ KEEP - Used by universal_engine.py for refinements
# =============================================================================

"""
Smart Layer for Event Detection and Alert Refinement

import pandas as pd
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from models import VerifiedEntity, AlertExclusionLog
from datetime import datetime
import uuid

class EventDetector:
    '''Detects legitimate events in transactions with Context Awareness'''
    
    EDUCATION_KEYWORDS = [
        'university', 'tuition', 'education', 'school', 
        'college', 'student fee', 'semester'
    ]
    LOAN_KEYWORDS = ['loan', 'emi', 'mortgage', 'repayment', 'installment', 'financing']
    FIXED_DEPOSIT_KEYWORDS = ['fixed deposit', 'fd', 'term deposit', 'investment', 'fd maturity']
    SALARY_KEYWORDS = ['salary', 'payroll', 'wages', 'compensation', 'monthly income']

    def __init__(self, db: Session):
        self.db = db

    def is_verified_entity(self, entity_name: str, entity_type: str) -> bool:
        '''Check if entity is in verified whitelist'''
        if not entity_name:
            return False
            
        entity = self.db.query(VerifiedEntity).filter(
            VerifiedEntity.entity_name.ilike(f"%{entity_name}%"),
            VerifiedEntity.entity_type == entity_type,
            VerifiedEntity.is_active == True
        ).first()
        
        return entity is not None

    def detect_event_context(self, narrative: str, amount: float, beneficiary: str) -> Optional[Dict]:
        '''Detect event type and validate context (Amount, Beneficiary).'''
        if not narrative:
            return None
        
        narrative_lower = str(narrative).lower()
        event_type = None
        
        if any(kw in narrative_lower for kw in self.EDUCATION_KEYWORDS):
            event_type = 'education'
        elif any(kw in narrative_lower for kw in self.LOAN_KEYWORDS):
            event_type = 'loan'
        elif any(kw in narrative_lower for kw in self.FIXED_DEPOSIT_KEYWORDS):
            event_type = 'fixed_deposit'
            
        if not event_type:
            return None

        # Context Checks
        is_verified = False
        amount_reasonable = True
        
        if event_type == 'education':
            is_verified = self.is_verified_entity(beneficiary, 'University')
            if amount > 50000:
                amount_reasonable = False
        
        if event_type == 'loan':
            is_verified = self.is_verified_entity(beneficiary, 'FinancialInstitution')
            
        return {
            "type": event_type,
            "is_verified": is_verified,
            "amount_reasonable": amount_reasonable
        }

class SmartLayerProcessor:
    '''Main smart layer orchestrator 2.0'''
    
    def __init__(self, db: Session):
        self.db = db
        self.event_detector = EventDetector(db)
    
    def apply_refinements(
        self,
        alerts: pd.DataFrame,
        transactions: pd.DataFrame,
        refinement_rules: List[Dict],
        lookback_days: int = 30
    ) -> pd.DataFrame:
        '''Apply all refinement rules to alerts with context checks (VECTORIZED)'''
        
        if alerts.empty:
            return alerts
            
        if 'excluded' not in alerts.columns:
            alerts['excluded'] = False
        if 'exclusion_reason' not in alerts.columns:
            alerts['exclusion_reason'] = None
        
        # VECTORIZED APPROACH: Process all alerts at once instead of iterrows
        for rule in refinement_rules:
            rule_id = rule.get('rule_id', 'unknown')
            
            if rule['type'] == 'event_based':
                excluded_events = rule.get('excluded_events', [])
                
                # Build keyword pattern for all excluded events
                event_keywords = {
                    'education': ['tuition', 'university', 'college', 'school'],
                    'crypto': ['crypto', 'bitcoin', 'binance', 'coinbase'],
                    'loan': ['loan', 'mortgage', 'credit'],
                }
                
                # Combine all keywords for excluded events
                all_keywords = []
                for event in excluded_events:
                    all_keywords.extend(event_keywords.get(event, []))
                
                if not all_keywords:
                    continue
                
                # Vectorized: Find all transactions matching keywords
                import re
                keyword_pattern = '|'.join(map(re.escape, all_keywords))
                compiled_regex = re.compile(keyword_pattern, re.IGNORECASE)
                
                matching_txns = transactions[
                    transactions['transaction_narrative'].str.contains(
                        compiled_regex, 
                        na=False,
                        regex=True
                    )
                ].copy()
                
                if matching_txns.empty:
                    continue
                
                # Vectorized: Get customer IDs with matching transactions
                customers_with_matches = set(matching_txns['customer_id'].unique())
                
                # Vectorized: Mark alerts for these customers
                mask = (
                    alerts['customer_id'].isin(customers_with_matches) &
                    (~alerts['excluded'])
                )
                
                # For alerts that match, verify context
                matched_alerts = alerts[mask].copy()
                
                for idx in matched_alerts.index:
                    alert = alerts.loc[idx]
                    
                    # Get trigger window transactions
                    trigger_txns = self._get_trigger_window_transactions(
                        alert, 
                        transactions, 
                        lookback_days
                    )
                    
                    should_exclude = False
                    exclusion_reason = None
                    risk_flags = {}
                    
                    # Check transactions in trigger window
                    for _, txn in trigger_txns.iterrows():
                        narrative = txn.get('transaction_narrative')
                        amount = txn.get('transaction_amount', 0)
                        beneficiary = txn.get('beneficiary_name')
                        
                        context = self.event_detector.detect_event_context(narrative, amount, beneficiary)
                        
                        if context and context['type'] in excluded_events:
                            risk_flags = {
                                'event_type': context['type'],
                                'is_verified': context['is_verified'],
                                'amount_reasonable': context['amount_reasonable'],
                                'beneficiary': beneficiary,
                                'amount': float(amount)
                            }
                            
                            if context['type'] == 'education':
                                if context['is_verified'] and context['amount_reasonable']:
                                    should_exclude = True
                                    exclusion_reason = f"Verified {context['type']} transaction to {beneficiary}"
                            else:
                                should_exclude = True
                                exclusion_reason = f"Legitimate {context['type']} transaction"
                            
                            if should_exclude:
                                break
                    
                    if should_exclude:
                        alerts.at[idx, 'excluded'] = True
                        alerts.at[idx, 'exclusion_reason'] = exclusion_reason
                        
                        # Write exclusion log
                        alert_id = alert.get('alert_id')
                        if alert_id:
                            self._write_exclusion_log(
                                alert_id=alert_id,
                                rule_id=rule_id,
                                exclusion_reason=exclusion_reason,
                                risk_flags=risk_flags
                            )
        
        return alerts
"""

# =============================================================================
# FILE 4: services/comparison_service.py (357 lines)
# Purpose: Compare two simulation runs
# Status: ✅ KEEP - Used by api/comparison.py
# Note: Could be simplified but provides good functionality
# =============================================================================

"""
Comparison Engine - Analyzes two simulation runs

Key functionality:
- Compare baseline vs refined runs
- Calculate alert reduction metrics
- Granular customer-level diff
- Risk analysis of suppressed alerts

from typing import Dict, List, Any
from sqlalchemy.orm import Session
from models import Alert, SimulationRun
import structlog

class ComparisonEngine:
    def __init__(self, db: Session):
        self.db = db
    
    def compare_runs(self, baseline_run_id: str, refined_run_id: str) -> Dict[str, Any]:
        '''Main comparison method'''
        # Load alerts
        baseline_alerts = self._load_alerts(baseline_run_id)
        refined_alerts = self._load_alerts(refined_run_id)
        
        # Calculate metrics
        summary = self._calculate_summary(baseline_alerts, refined_alerts)
        granular_diff = self._calculate_granular_diff(baseline_alerts, refined_alerts)
        risk_analysis = self._analyze_risk(baseline_alerts, refined_alerts, granular_diff)
        
        return {
            "summary": summary,
            "granular_diff": granular_diff,
            "risk_analysis": risk_analysis
        }
    
    def _load_alerts(self, run_id: str) -> List[Alert]:
        '''Load all alerts for a run'''
        return self.db.query(Alert).filter(Alert.run_id == run_id).all()
    
    def _calculate_summary(self, baseline_alerts, refined_alerts) -> Dict:
        '''Calculate high-level reduction metrics'''
        baseline_count = len(baseline_alerts)
        refined_count = len(refined_alerts)
        net_change = baseline_count - refined_count
        
        if baseline_count == 0:
            percent_reduction = 0.0
        else:
            percent_reduction = (net_change / baseline_count) * 100
        
        return {
            "baseline_alerts": baseline_count,
            "refined_alerts": refined_count,
            "net_change": net_change,
            "percent_reduction": round(percent_reduction, 2)
        }
    
    def _calculate_granular_diff(self, baseline_alerts, refined_alerts, limit=50) -> List[Dict]:
        '''Calculate customer-level granular diff'''
        baseline_customers = set(alert.customer_id for alert in baseline_alerts)
        refined_customers = set(alert.customer_id for alert in refined_alerts)
        removed_customers = baseline_customers - refined_customers
        
        granular_diff = []
        for customer_id in removed_customers:
            customer_alerts = [a for a in baseline_alerts if a.customer_id == customer_id]
            
            granular_diff.append({
                "customer_id": customer_id,
                "status": "removed",
                "alert_count": len(customer_alerts),
                "scenarios": list(set(a.scenario_id for a in customer_alerts))
            })
        
        granular_diff.sort(key=lambda x: x["alert_count"], reverse=True)
        return granular_diff[:limit] if limit else granular_diff
    
    def _analyze_risk(self, baseline_alerts, refined_alerts, granular_diff) -> Dict:
        '''Analyze risk of suppressed alerts'''
        high_risk_suppressions = len(granular_diff)
        
        if not granular_diff:
            risk_score = 0.0
            risk_level = "SAFE"
        else:
            risk_score = 50.0  # Simplified
            risk_level = "CRITICAL" if high_risk_suppressions > 0 else "SAFE"
        
        return {
            "risk_score": round(risk_score, 2),
            "risk_level": risk_level,
            "high_risk_suppressions": high_risk_suppressions,
            "total_suppressions": len(granular_diff)
        }
"""

# =============================================================================
# FILE 5: services/data_ingestion.py (343 lines)
# Purpose: Process CSV/Excel uploads and build field indexes
# Status: ✅ KEEP - Used by api/data.py for uploads
# =============================================================================

"""
Data Ingestion Service

Handles:
- Reading CSV/Excel files
- Schema-agnostic processing (stores everything in raw_data JSONB)
- Field index building for autocomplete
- Account extraction from customer data

import pandas as pd
import numpy as np
from pydantic import BaseModel
from typing import List, Dict
import io

class DataIngestionService:
    def _read_file(self, file_content: bytes, filename: str) -> pd.DataFrame:
        '''Read CSV or Excel file'''
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(file_content))
        elif filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(io.BytesIO(file_content))
        else:
            raise ValueError("Unsupported file format")
        
        # Clean data
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.astype(object)
        df = df.where(pd.notnull(df), None)
        return df

    def process_transactions_csv(self, file_content: bytes, filename: str = "data.csv"):
        '''Process transaction CSV and build field index'''
        df = self._read_file(file_content, filename)
        
        # Header mapping
        mapping = {
            'id': 'transaction_id',
            'txn_id': 'transaction_id',
            'date': 'transaction_date',
            'amount': 'transaction_amount',
            'cust_id': 'customer_id',
        }
        
        valid_records = []
        errors = []
        
        for idx, row in enumerate(df.to_dict(orient='records')):
            try:
                # Build raw_data with ALL fields
                raw_data = {}
                for k, v in row.items():
                    clean_k = str(k).lower().strip().replace(' ', '_')
                    if v is not None:
                        if isinstance(v, (np.integer, np.floating)):
                            raw_data[clean_k] = float(v) if isinstance(v, np.floating) else int(v)
                        else:
                            raw_data[clean_k] = str(v)
                
                # Extract required PKs
                processed_row = {'raw_data': raw_data}
                
                for k, v in row.items():
                    clean_k = str(k).lower().strip().replace(' ', '_')
                    target_k = mapping.get(clean_k, clean_k)
                    
                    if target_k == 'transaction_id':
                        processed_row['transaction_id'] = str(v)
                    elif target_k == 'customer_id':
                        processed_row['customer_id'] = str(v)
                
                if 'transaction_id' not in processed_row or 'customer_id' not in processed_row:
                    raise ValueError("Missing required fields")
                
                valid_records.append(processed_row)
                
            except Exception as e:
                errors.append({"row": idx + 2, "error": str(e)})
        
        # Build field index
        computed_index = self._build_field_index(valid_records, 'transactions')
        
        return valid_records, errors, computed_index
    
    def _build_field_index(self, records: List[dict], table_name: str) -> dict:
        '''Build searchable field index for autocomplete'''
        from collections import Counter
        
        field_values = {}
        
        for record in records:
            data_to_index = record.get('raw_data', {}).copy()
            
            for field_name, field_value in data_to_index.items():
                if field_name not in field_values:
                    field_values[field_name] = Counter()
                
                str_value = str(field_value) if field_value is not None else None
                if str_value:
                    field_values[field_name][str_value] += 1
        
        # Build index result
        index_result = {}
        total_records = len(records)
        
        for field_name, value_counts in field_values.items():
            field_type = self._infer_field_type(list(value_counts.keys()))
            distinct_count = len(value_counts)
            
            metadata = {
                "field_name": field_name,
                "field_type": field_type,
                "total_records": total_records,
                "distinct_count": distinct_count,
                "sample_values": list(value_counts.keys())[:10]
            }
            
            values = []
            if distinct_count < 1000:
                for value, count in value_counts.items():
                    percentage = (count / total_records) * 100
                    values.append({
                        "field_value": value,
                        "value_count": count,
                        "value_percentage": round(percentage, 2)
                    })
            
            index_result[field_name] = {
                "metadata": metadata,
                "values": values
            }
        
        return index_result
"""

# =============================================================================
# FILE 6: services/data_quality_service.py (94 lines)
# Purpose: Data quality metrics for uploads
# Status: ⚠️ DELETE - Duplicate of core/data_quality.py
# Recommendation: Use core/data_quality.py instead
# =============================================================================

"""
DUPLICATE - This overlaps with core/data_quality.py

from sqlalchemy.orm import Session
import pandas as pd
from models import DataQualityMetric, Transaction, DataUpload

class DataQualityService:
    def __init__(self, db: Session):
        self.db = db

    def check_upload_quality(self, upload_id: str) -> dict:
        '''Runs data quality checks on upload'''
        # Load data
        upload = self.db.query(DataUpload).filter(DataUpload.upload_id == upload_id).first()
        if not upload:
            raise ValueError("Upload not found")
        
        txns = self.db.query(Transaction.raw_data).filter(Transaction.upload_id == upload_id).all()
        df = pd.DataFrame([t[0] for t in txns])
        
        # Calculate metrics
        completeness_score = 95.0  # Simplified
        validity_score = 90.0
        uniqueness_score = 100.0
        
        # Persist
        metric = DataQualityMetric(
            upload_id=upload_id,
            completeness_score=completeness_score,
            validity_score=validity_score,
            uniqueness_score=uniqueness_score
        )
        
        self.db.add(metric)
        self.db.commit()
        
        return {
            "scores": {
                "completeness": completeness_score,
                "validity": validity_score,
                "uniqueness": uniqueness_score
            }
        }
"""

# =============================================================================
# FILE 7: services/beneficiary_service.py (116 lines)
# Purpose: Build beneficiary transaction history
# Status: ⚠️ EVALUATE - Not used in main flow, might be legacy
# Recommendation: Check if used anywhere, if not DELETE
# =============================================================================

"""
Beneficiary Service - Builds transaction history profiles

from sqlalchemy.orm import Session
import pandas as pd
from models import Transaction, BeneficiaryHistory

class BeneficiaryService:
    def __init__(self, db: Session):
        self.db = db
        
    def build_history_for_upload(self, upload_id: str):
        '''Scans transactions and builds beneficiary profiles'''
        # Fetch transactions
        query = self.db.query(Transaction.raw_data, Transaction.created_at).filter(
            Transaction.upload_id == upload_id
        )
        
        df = pd.read_sql(query.statement, self.db.bind)
        
        if df.empty:
            return {"status": "no_data"}
        
        # Extract beneficiary
        def get_ben(row):
            raw = row['raw_data']
            return raw.get('beneficiary_name') or raw.get('beneficiary')
        
        df['beneficiary_name'] = df.apply(get_ben, axis=1)
        df = df.dropna(subset=['beneficiary_name'])
        
        # Group by beneficiary
        stats = df.groupby('beneficiary_name').agg({
            'amount': ['count', 'sum', 'std'],
            'date': ['min', 'max']
        })
        
        # Prepare records
        history_records = []
        for _, row in stats.iterrows():
            record = {
                "beneficiary_name": row['beneficiary_name'],
                "upload_id": upload_id,
                "total_transactions": int(row['amount_count']),
                "total_amount": float(row['amount_sum'])
            }
            history_records.append(record)
        
        # Bulk insert
        if history_records:
            self.db.bulk_insert_mappings(BeneficiaryHistory, history_records)
            self.db.commit()
        
        return {"status": "success", "count": len(history_records)}
"""

# =============================================================================
# FILE 8: services/simulation_service.py (520 lines)
# Purpose: Orchestrates simulation execution
# Status: ⚠️ REFACTOR - Thin wrapper around universal_engine.py
# Recommendation: Merge into api/simulation.py or universal_engine.py
# Lines saved: ~250 lines
# =============================================================================

"""
Simulation Service - Orchestrates AML simulation execution

This is a THIN WRAPPER around UniversalScenarioEngine.
Most of this logic can be moved to api/simulation.py or universal_engine.py

from sqlalchemy.orm import Session
import pandas as pd
from models import SimulationRun, Alert, Transaction, Customer
from core.universal_engine import UniversalScenarioEngine

class SimulationService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_run(self, run_type: str, scenarios: List[str], user_id: str) -> SimulationRun:
        '''Create simulation run record'''
        run = SimulationRun(
            run_type=run_type,
            scenarios_run=scenarios,
            user_id=user_id,
            status="pending"
        )
        self.db.add(run)
        self.db.commit()
        return run
    
    def load_simulation_data(self, user_id: str):
        '''Load transaction and customer data for user'''
        from models import DataUpload
        
        customers_query = self.db.query(Customer).join(DataUpload).filter(
            DataUpload.user_id == user_id
        )
        transactions_query = self.db.query(Transaction).join(DataUpload).filter(
            DataUpload.user_id == user_id
        )
        
        customers_df = pd.read_sql(customers_query.statement, self.db.bind)
        transactions_df = pd.read_sql(transactions_query.statement, self.db.bind)
        
        # Flatten raw_data
        customers_df = self._flatten_raw_data(customers_df)
        transactions_df = self._flatten_raw_data(transactions_df)
        
        return customers_df, transactions_df
    
    def execute_run(self, run_id: str):
        '''Execute simulation run'''
        run = self.db.query(SimulationRun).filter(SimulationRun.run_id == run_id).first()
        
        run.status = "running"
        self.db.commit()
        
        # Load data
        customers_df, transactions_df = self.load_simulation_data(run.user_id)
        
        # Execute scenarios
        engine = UniversalScenarioEngine(db_session=self.db)
        all_alerts = []
        
        for scenario_id in run.scenarios_run:
            alerts = engine.execute(scenario_id, transactions_df, customers_df, run_id)
            all_alerts.extend(alerts)
        
        # Save alerts
        self.db.bulk_insert_mappings(Alert, all_alerts)
        
        run.status = "completed"
        run.total_alerts = len(all_alerts)
        self.db.commit()
"""

# =============================================================================
# ANALYSIS SUMMARY
# =============================================================================

"""
FILES TO KEEP (5):
1. core/config_models.py - Pydantic models for scenarios ✅
2. core/data_quality.py - Data quality validation ✅
3. core/smart_layer.py - Event detection and refinements ✅
4. services/comparison_service.py - Run comparison ✅
5. services/data_ingestion.py - CSV/Excel processing ✅

FILES TO DELETE (1):
1. services/data_quality_service.py - Duplicate of core/data_quality.py ❌

FILES TO REFACTOR (2):
1. services/simulation_service.py - Merge into api/simulation.py ⚠️
2. services/beneficiary_service.py - Check if used, likely delete ⚠️

MISSING SOURCE FILES (compiled .pyc only):
1. core/scenarios.cpython-313.pyc - Source file missing
2. core/db_utils.cpython-313.pyc - Source file missing
3. core/scenario_engine.cpython-313.pyc - Possibly replaced by universal_engine.py
4. core/schema_mapper.cpython-313.pyc - Possibly overlaps with field_mapper.py

ESTIMATED SAVINGS:
- Delete data_quality_service.py: ~94 lines
- Merge simulation_service.py: ~250 lines
- Delete beneficiary_service.py (if unused): ~116 lines
- Total: ~460 lines from services/ alone
"""
