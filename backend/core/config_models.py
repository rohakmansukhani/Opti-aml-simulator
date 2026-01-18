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
    type: Literal['fixed', 'customer_based', 'segment_based', 'field_based', 'dynamic'] # Added dynamic mapping to field_based in logic likely
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

# --- Refinement Config (Placeholder per user Layers) ---
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
    
    # Accept BOTH formats: ScenarioFilters object OR simple array
    filters: Optional[Union[ScenarioFilters, List[Dict[str, Any]]]] = None
    aggregation: Optional[ScenarioAggregation] = None
    threshold: Optional[ScenarioThreshold] = None
    alert_condition: Optional[AlertCondition] = None
    
    refinements: Optional[List[RefinementConfig]] = None
    field_mappings: Optional[Dict[str, str]] = None  # Maps scenario fields to actual DB columns

