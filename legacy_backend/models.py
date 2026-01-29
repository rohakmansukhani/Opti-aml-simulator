from sqlalchemy import Column, String, Integer, DateTime, Boolean, DECIMAL, Text, ForeignKey, JSON, Float, Index, ForeignKeyConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
import datetime
from datetime import datetime as dt, timezone
from database import Base

# Helper for consistent UTC timestamps
def utc_now():
    return dt.now(timezone.utc)

class Transaction(Base):
    """
    Schema-agnostic transaction model.
    All user CSV data is stored in raw_data JSONB.
    """
    __tablename__ = "transactions"
    
    # System columns only
    transaction_id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.customer_id"), nullable=False, index=True)
    upload_id = Column(UUID(as_uuid=True), ForeignKey("data_uploads.upload_id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)  # UTC
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)  # UTC (TTL)
    
    # All user CSV data stored here
    raw_data = Column(JSON, nullable=False, default={})

    # Relationships
    customer = relationship("Customer", back_populates="transactions")
    alert_transactions = relationship("AlertTransaction", back_populates="transaction")  # ✅ ADDED

class Customer(Base):
    """
    Schema-agnostic customer model.
    All user CSV data is stored in raw_data JSONB.
    """
    __tablename__ = "customers"
    
    customer_id = Column(String, primary_key=True)
    upload_id = Column(UUID(as_uuid=True), ForeignKey('data_uploads.upload_id'), nullable=True, index=True)
    raw_data = Column(JSON, nullable=False, default={})
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    # Keep other relationships that work:
    transactions = relationship("Transaction", back_populates="customer")
    alerts = relationship("Alert", back_populates="customer")

class Alert(Base):
    __tablename__ = "alerts"

    alert_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = Column(String, ForeignKey("customers.customer_id"), nullable=True)  # Nullable for anonymization
    customer_name = Column(String)
    scenario_id = Column(String, ForeignKey("scenarios_config.scenario_id"))
    scenario_name = Column(String)
    scenario_description = Column(Text)
    alert_date = Column(DateTime(timezone=True), nullable=False, index=True)  # UTC
    alert_status = Column(String, default="OPN")
    trigger_details = Column(JSON)
    risk_classification = Column(String)
    risk_score = Column(Integer)
    run_id = Column(String, ForeignKey("simulation_runs.run_id"), nullable=False, index=True)
    excluded = Column(Boolean, default=False)
    exclusion_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utc_now)  # UTC
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Investigation Workflow
    assigned_to = Column(String, nullable=True) # User ID
    investigation_status = Column(String, default='New') # New, In Progress, Closed
    outcome = Column(String, nullable=True) # False Positive, True Positive, Suspicious
    sar_reference = Column(String, nullable=True)
    investigation_notes = Column(Text, nullable=True)
    is_anonymized = Column(Boolean, default=False, index=True)
    anonymized_at = Column(DateTime(timezone=True), nullable=True)

    customer = relationship("Customer", back_populates="alerts")
    simulation_run = relationship("SimulationRun", back_populates="alerts")
    alert_transactions = relationship("AlertTransaction", back_populates="alert")  # ✅ ADDED

class UserProfile(Base):
    __tablename__ = "profiles"
    
    id = Column(String, primary_key=True) # Linked to auth.users.id
    email = Column(String, unique=True, nullable=False)
    full_name = Column(String)
    avatar_url = Column(String)
    organization_id = Column(String)
    role = Column(String, default="analyst") # admin, analyst, viewer
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now)

class ScenarioConfig(Base):
    __tablename__ = "scenarios_config"

    scenario_id = Column(String, primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), index=True, nullable=True) # Owner
    scenario_name = Column(String, nullable=False)
    description = Column(Text)
    priority = Column(String, nullable=True)  # ✅ ADD THIS LINE
    frequency = Column(String)
    transaction_types = Column(JSON)
    channels = Column(JSON)
    direction = Column(String)
    thresholds = Column(JSON)
    lookback_days = Column(Integer)
    aggregation_logic = Column(String)
    enabled = Column(Boolean, default=True)
    refinements = Column(JSON)
    config_json = Column(JSON) 
    field_mappings = Column(JSON, nullable=True)
    updated_at = Column(DateTime, default=utc_now)

class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    run_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), index=True, nullable=True)  # UUID type
    upload_id = Column(UUID(as_uuid=True), ForeignKey("data_uploads.upload_id"), nullable=True, index=True)  # Added
    run_type = Column(String)
    scenarios_run = Column(JSON)
    date_range_start = Column(DateTime(timezone=False))
    date_range_end = Column(DateTime(timezone=False))
    total_transactions = Column(Integer, default=0)
    total_alerts = Column(Integer)
    status = Column(String)
    progress_percentage = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=False), default=utc_now)
    completed_at = Column(DateTime(timezone=False))
    metadata_info = Column(JSON, nullable=True)

    alerts = relationship("Alert", back_populates="simulation_run")

class VerifiedEntity(Base):
    __tablename__ = "verified_entities"
    
    entity_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), index=True, nullable=True)  # UUID type
    entity_name = Column(String, index=True)
    entity_type = Column(String)
    country = Column(String)
    risk_category = Column(String)
    is_active = Column(Boolean, default=True)
    valid_from = Column(DateTime(timezone=False), default=utc_now)
    valid_to = Column(DateTime(timezone=False), nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    log_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=utc_now)
    user_id = Column(String)
    action_type = Column(String) # create_refinement, approve_rule, deploy_rule
    target_entity_id = Column(String) # e.g. scenario_id
    details = Column(JSON)
    risk_score_snapshot = Column(Float, nullable=True)
    justification_notes = Column(String, nullable=True)

class AlertExclusionLog(Base):
    __tablename__ = "alert_exclusion_logs"
    
    log_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    alert_id = Column(String, ForeignKey("alerts.alert_id"))
    exclusion_timestamp = Column(DateTime, default=utc_now)
    rule_id = Column(String, nullable=True)
    exclusion_reason = Column(String)
    risk_flags = Column(JSON) # Snapshot of risk indicators at time of exclusion

class CustomerRiskProfile(Base):
    __tablename__ = "customer_risk_profiles"
    
    profile_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = Column(String, ForeignKey("customers.customer_id"))
    is_pep = Column(Boolean, default=False)
    high_risk_occupation = Column(Boolean, default=False)
    has_adverse_media = Column(Boolean, default=False)
    previous_sar_count = Column(Integer, default=0)
    account_age_days = Column(Integer, default=0)
    last_updated = Column(DateTime, default=utc_now)
    
    customer = relationship("Customer")

class DataUpload(Base):
    __tablename__ = "data_uploads"
    
    upload_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)  # UUID type
    user_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=True)  # UUID type
    upload_timestamp = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))
    filename = Column(String)
    record_count_transactions = Column(Integer)
    record_count_customers = Column(Integer)
    expires_at = Column(DateTime(timezone=True))  # Timezone-aware
    status = Column(String, default="active")

class Account(Base):
    __tablename__ = "accounts"

    account_id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False, index=True)
    account_number = Column(String)
    account_type = Column(String)  # Savings, Current, NRI, Loan, FD
    account_status = Column(String, default='Active')  # Active, Dormant, Closed
    currency_code = Column(String, default='GBP')
    
    # Dates
    account_open_date = Column(DateTime(timezone=False), nullable=False, index=True)
    account_close_date = Column(DateTime(timezone=False))
    last_transaction_date = Column(DateTime(timezone=False))
    
    # Risk & Compliance
    risk_rating = Column(Text)  # LOW, MEDIUM, HIGH
    is_pep = Column(Boolean, default=False)
    
    # Balances
    current_balance = Column(DECIMAL(18, 2))
    average_monthly_balance = Column(DECIMAL(18, 2))
    
    # Metadata
    upload_id = Column(UUID(as_uuid=True), ForeignKey("data_uploads.upload_id"), index=True)
    created_at = Column(DateTime, default=utc_now)
    expires_at = Column(DateTime(timezone=True))
    
    # Schema-agnostic storage
    raw_data = Column(JSON, default={}, nullable=False)

class FieldValueIndex(Base):
    __tablename__ = "field_value_index"

    index_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    upload_id = Column(UUID(as_uuid=True), ForeignKey("data_uploads.upload_id", ondelete="CASCADE"), nullable=False)
    table_name = Column(String, nullable=False)  # 'transactions' or 'customers'
    field_name = Column(String, nullable=False, index=True)
    field_value = Column(String, nullable=False)
    value_count = Column(Integer, default=1)
    value_percentage = Column(DECIMAL(5, 2))
    first_seen = Column(DateTime, default=utc_now)
    last_seen = Column(DateTime, default=utc_now)

    __table_args__ = (
        Index('idx_field_value_upload_table', 'upload_id', 'table_name'),
        Index('idx_field_value_search', 'field_name', 'field_value'),
        Index('idx_field_value_count', 'field_name', 'value_count'),
    )

class FieldMetadata(Base):
    __tablename__ = "field_metadata"

    metadata_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    upload_id = Column(UUID(as_uuid=True), ForeignKey("data_uploads.upload_id", ondelete="CASCADE"), nullable=False)
    table_name = Column(String, nullable=False)
    field_name = Column(String, nullable=False)
    field_type = Column(String, nullable=False)  # 'text', 'numeric', 'date', 'boolean'
    
    # Statistics
    total_records = Column(Integer)
    non_null_count = Column(Integer)
    null_count = Column(Integer)
    distinct_count = Column(Integer)
    
    # Numeric stats
    min_value = Column(DECIMAL(18, 2))
    max_value = Column(DECIMAL(18, 2))
    avg_value = Column(DECIMAL(18, 2))
    
    # Recommendations
    recommended_operators = Column(JSON)
    sample_values = Column(JSON)
    
    created_at = Column(DateTime, default=utc_now)

    __table_args__ = (
        Index('idx_field_metadata_upload', 'upload_id', 'table_name'),
    )

class AlertTransaction(Base):
    __tablename__ = "alert_transactions"

    alert_id = Column(String, ForeignKey("alerts.alert_id", ondelete="CASCADE"), primary_key=True)
    transaction_id = Column(String, primary_key=True) # Part of composite FK
    upload_id = Column(UUID(as_uuid=True), primary_key=True) # Added for Partitioning Support
    
    contribution_percentage = Column(DECIMAL(5, 2))
    
    __table_args__ = (
        ForeignKeyConstraint(
            ['transaction_id', 'upload_id'],
            ['transactions.transaction_id', 'transactions.upload_id'],
            ondelete="CASCADE"
        ),
    )
    is_primary_trigger = Column(Boolean, default=False)
    sequence_order = Column(Integer)

    alert = relationship("Alert", back_populates="alert_transactions")
    transaction = relationship("Transaction", back_populates="alert_transactions")

# Phase 4: Intelligence & Comparison Models

class SimulationComparison(Base):
    __tablename__ = "simulation_comparisons"
    
    comparison_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    base_run_id = Column(String, ForeignKey("simulation_runs.run_id", ondelete="CASCADE"), nullable=False)
    challenger_run_id = Column(String, ForeignKey("simulation_runs.run_id", ondelete="CASCADE"), nullable=False)
    
    # Metrics
    alerts_delta = Column(Integer) # challenger - base
    efficiency_score = Column(Float) # Efficiency gain/loss
    overlap_count = Column(Integer) # Common alerts
    
    # Store detailed comparison JSON (New Alerts, Dropped Alerts, etc.)
    comparison_details = Column(JSON)
    
    created_at = Column(DateTime, default=utc_now)

class BeneficiaryHistory(Base):
    __tablename__ = "beneficiary_history"
    
    history_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    beneficiary_name = Column(String, index=True) # Normalized name
    beneficiary_account = Column(String, index=True, nullable=True) # Account/IBAN if available
    
    # Let's scope to Data Upload -> User so we don't leak data across tenants
    upload_id = Column(UUID(as_uuid=True), ForeignKey("data_uploads.upload_id", ondelete="CASCADE"), index=True)
    
    # Usage Stats
    total_transactions = Column(Integer, default=0)
    total_amount = Column(DECIMAL(18, 2), default=0)
    first_seen = Column(DateTime, default=utc_now)
    last_seen = Column(DateTime, default=utc_now)
    
    # Risk Indicators (for Stability Checks)
    std_dev_amount = Column(Float, nullable=True)
    avg_days_between_txns = Column(Float, nullable=True)
    
    __table_args__ = (
        Index('idx_beneficiary_upload', 'upload_id', 'beneficiary_name'),
    )

class ComparisonReport(Base):
    """
    Stores advanced aggregation reports (e.g. Rolling Window analysis results).
    """
    __tablename__ = "comparison_reports"
    
    report_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("simulation_runs.run_id", ondelete="CASCADE"))
    report_type = Column(String) # 'TIME_CLUSTERING', 'ROLLING_WINDOW', 'BENEFICIARY_RISK'
    report_data = Column(JSON)
    created_at = Column(DateTime, default=utc_now)

# Relationships
SimulationRun.comparisons_base = relationship("SimulationComparison", foreign_keys=[SimulationComparison.base_run_id])
SimulationRun.comparisons_challenger = relationship("SimulationComparison", foreign_keys=[SimulationComparison.challenger_run_id])

# Phase 5: Advanced Features Models

class ScenarioVersion(Base):
    __tablename__ = "scenario_versions"
    
    version_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    scenario_id = Column(String, ForeignKey("scenarios_config.scenario_id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False) # 1, 2, 3...
    
    # Snapshot of the config at this version
    config_snapshot = Column(JSON) 
    change_description = Column(String)
    changed_by = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=True)
    created_at = Column(DateTime, default=utc_now)
    
class DataQualityMetric(Base):
    __tablename__ = "data_quality_metrics"
    
    metric_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    upload_id = Column(UUID(as_uuid=True), ForeignKey("data_uploads.upload_id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Overall Score
    completeness_score = Column(Float) # % of non-null required fields
    validity_score = Column(Float) # % of valid formats
    uniqueness_score = Column(Float) # % of unique IDs
    
    # Detailed Report
    field_level_issues = Column(JSON) # {"transaction_amount": {"nulls": 50, "negatives": 2}}
    row_level_issues = Column(JSON) # Sample of bad rows
    
    created_at = Column(DateTime, default=utc_now)

# Global Relationships
ScenarioConfig.versions = relationship("ScenarioVersion", backref="scenario", order_by="desc(ScenarioVersion.version_number)")
DataUpload.quality_metrics = relationship("DataQualityMetric", uselist=False, backref="upload")
