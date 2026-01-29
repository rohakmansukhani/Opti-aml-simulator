from ninja import Schema
from datetime import datetime
from typing import List, Optional, Union

class SimulationSummary(Schema):
    run_id: str
    run_number: int = 0
    status: str
    total_alerts: int = 0
    scenarios_run: List[str]
    scenario_names: List[str] = []
    created_at: datetime

class SimulationRunRequest(Schema):
    scenarios: List[str]
    run_type: str = 'ad_hoc'
    upload_id: Optional[str] = None
    field_mappings: Optional[dict] = None

class AlertWorkflowUpdate(Schema):
    assigned_to: Optional[str] = None
    investigation_status: Optional[str] = None # New, In Progress, Closed
    outcome: Optional[str] = None # False Positive, True Positive, Suspicious
    sar_reference: Optional[str] = None
    investigation_notes: Optional[str] = None

class TraceabilityItem(Schema):
    transaction_id: str
    contribution_percentage: float
    amount: float
    date: datetime
    beneficiary: Optional[str] = None
    description: Optional[str] = None

class AlertDetailResponse(Schema):
    alert_id: str
    scenario_name: str
    risk_score: int
    alert_date: datetime
    customer_name: str
    customer_id: str
    status: str
    assigned_to: Optional[str] = None
    investigation_status: str
    outcome: Optional[str] = None
    sar_reference: Optional[str] = None
    investigation_notes: Optional[str] = None
    contributing_transactions: List[TraceabilityItem]
    trigger_details: dict

class FilterItem(Schema):
    field: str
    operator: str
    value: Union[str, int, float, List[str], List[int], List[float], None]

class FilterValidationRequest(Schema):
    upload_id: Optional[str] = None
    filters: List[FilterItem]

class ScenarioTestRequest(Schema):
    upload_id: Optional[str] = None
    scenario_id: Optional[str] = None
    config_json: Optional[dict] = None

class DashboardStats(Schema):
    total_alerts: int
    transactions_scanned: int
    customers_scanned: int
    total_simulations: int
    has_data: bool = False
    dataset_name: Optional[str] = None
    dataset_id: Optional[str] = None
    recent_simulations: List[SimulationSummary]

class ErrorResponse(Schema):
    message: str
    details: Optional[str] = None

class ScenarioCreateSchema(Schema):
    scenario_id: Optional[str] = None
    scenario_name: str
    description: Optional[str] = None
    priority: str = "MEDIUM"
    enabled: bool = True
    config_json: dict

class ComparisonRequest(Schema):
    baseline_run_id: str
    refined_run_id: str

class ComparisonRuleRequest(Schema):
    baseline_scenario_id: str
    refined_scenario_id: str

class DatasetSummary(Schema):
    upload_id: str
    dataset_name: str
    record_count_transactions: int
    record_count_customers: int
    upload_timestamp: datetime
    is_active: bool

class SchemaValidationRequest(Schema):
    upload_id: str
    scenario_ids: List[str]

class SchemaMappingItem(Schema):
    rule_field: str
    source_table: str  # 'transaction' or 'customer'
    suggested_dataset_column: Optional[str] = None

class SchemaValidationResponse(Schema):
    is_valid: bool
    missing_fields: List[SchemaMappingItem]
    available_columns: dict # { 'transactions': [], 'customers': [] }
