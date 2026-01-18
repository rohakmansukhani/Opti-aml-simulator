from sqlalchemy import Column, String, Integer, DateTime, Boolean, DECIMAL, Text, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
import datetime
from database import Base

class Transaction(Base):
    __tablename__ = "transactions"
    
    transaction_id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.customer_id"), nullable=False, index=True)
    account_number = Column(String)
    transaction_date = Column(DateTime, nullable=False, index=True)
    transaction_amount = Column(DECIMAL(15, 2), nullable=False)
    debit_credit_indicator = Column(String(1))  # 'D' or 'C'
    transaction_type = Column(String)
    channel = Column(String)
    transaction_narrative = Column(Text)
    beneficiary_name = Column(String)
    beneficiary_bank = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # TTL Support
    upload_id = Column(String, ForeignKey("data_uploads.upload_id"), nullable=True, index=True)
    expires_at = Column(DateTime, nullable=True, index=True)

    customer = relationship("Customer", back_populates="transactions")

class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(String, primary_key=True)
    customer_name = Column(String, nullable=False)
    customer_type = Column(String)
    occupation = Column(String)
    annual_income = Column(DECIMAL(15, 2))
    account_type = Column(String)
    risk_score = Column(Integer)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # TTL Support
    upload_id = Column(String, ForeignKey("data_uploads.upload_id"), nullable=True, index=True)
    expires_at = Column(DateTime, nullable=True, index=True)

    transactions = relationship("Transaction", back_populates="customer")
    alerts = relationship("Alert", back_populates="customer")

class Alert(Base):
    __tablename__ = "alerts"

    alert_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = Column(String, ForeignKey("customers.customer_id"), nullable=False)
    customer_name = Column(String)
    scenario_id = Column(String, ForeignKey("scenarios_config.scenario_id"))
    scenario_name = Column(String)
    scenario_description = Column(Text)
    alert_date = Column(DateTime, nullable=False, index=True)
    alert_status = Column(String, default="OPN")
    trigger_details = Column(JSON)
    risk_classification = Column(String)
    risk_score = Column(Integer)
    run_id = Column(String, ForeignKey("simulation_runs.run_id"), nullable=False, index=True)
    excluded = Column(Boolean, default=False)
    exclusion_reason = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    customer = relationship("Customer", back_populates="alerts")
    simulation_run = relationship("SimulationRun", back_populates="alerts")

class UserProfile(Base):
    __tablename__ = "profiles"
    
    id = Column(String, primary_key=True) # Linked to auth.users.id
    email = Column(String, unique=True, nullable=False)
    full_name = Column(String)
    avatar_url = Column(String)
    organization_id = Column(String)
    role = Column(String, default="analyst") # admin, analyst, viewer
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)

class ScenarioConfig(Base):
    __tablename__ = "scenarios_config"

    scenario_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("profiles.id"), index=True, nullable=True) # Owner
    scenario_name = Column(String, nullable=False)
    description = Column(Text)
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
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)

class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    run_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("profiles.id"), index=True, nullable=True) # Initiator
    run_type = Column(String) 
    scenarios_run = Column(JSON)
    date_range_start = Column(DateTime)
    date_range_end = Column(DateTime)
    total_transactions = Column(Integer, default=0) # Added for historical stats persistence
    total_alerts = Column(Integer)
    status = Column(String) 
    progress_percentage = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime)
    metadata_info = Column(JSON, nullable=True)

    alerts = relationship("Alert", back_populates="simulation_run")

# Re-declare dependencies to existing tables if needed or leave implicit


class VerifiedEntity(Base):
    __tablename__ = "verified_entities"
    
    entity_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_name = Column(String, index=True)
    entity_type = Column(String) # University, FinancialInstitution, CryptoExchange
    country = Column(String)
    risk_category = Column(String) # LOW, MEDIUM, HIGH
    is_active = Column(Boolean, default=True)
    valid_from = Column(DateTime, default=datetime.datetime.utcnow)
    valid_to = Column(DateTime, nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    log_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
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
    exclusion_timestamp = Column(DateTime, default=datetime.datetime.utcnow)
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
    last_updated = Column(DateTime, default=datetime.datetime.utcnow)
    
    customer = relationship("Customer")

class DataUpload(Base):
    __tablename__ = "data_uploads"
    
    upload_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("profiles.id"), nullable=True)
    upload_timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    filename = Column(String)
    record_count_transactions = Column(Integer)
    record_count_customers = Column(Integer)
    schema_snapshot = Column(JSON)
    expires_at = Column(DateTime)
    status = Column(String, default="active")
