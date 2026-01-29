from django.db import models
import uuid
from django.utils import timezone

class UserProfile(models.Model):
    id = models.CharField(primary_key=True, max_length=255) # Linked to auth.users.id or internal
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, null=True, blank=True)
    avatar_url = models.CharField(max_length=500, null=True, blank=True)
    organization_id = models.CharField(max_length=255, null=True, blank=True)
    role = models.CharField(max_length=50, default="analyst") # admin, analyst, viewer
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'profiles'

class DataUpload(models.Model):
    upload_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, null=True, related_name='uploads')
    upload_timestamp = models.DateTimeField(default=timezone.now)
    filename = models.CharField(max_length=255)
    dataset_name = models.CharField(max_length=255, null=True, blank=True)  # e.g., "January 2024", "Q1 Data"
    record_count_transactions = models.IntegerField(null=True, blank=True)
    record_count_customers = models.IntegerField(null=True, blank=True)
    schema_snapshot = models.JSONField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=50, default="active")


    class Meta:
        db_table = 'data_uploads'

class Customer(models.Model):
    customer_id = models.CharField(primary_key=True, max_length=255)
    upload = models.ForeignKey(DataUpload, on_delete=models.CASCADE, null=True, related_name='customers')
    raw_data = models.JSONField(default=dict)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'customers'

class Transaction(models.Model):
    transaction_id = models.CharField(primary_key=True, max_length=255)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='transactions')
    upload = models.ForeignKey(DataUpload, on_delete=models.CASCADE, null=True, related_name='transactions')
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    raw_data = models.JSONField(default=dict)

    class Meta:
        db_table = 'transactions'

class ScenarioConfig(models.Model):
    scenario_id = models.CharField(primary_key=True, max_length=255)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, null=True, related_name='scenarios')
    scenario_name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    priority = models.CharField(max_length=50, null=True, blank=True)
    frequency = models.CharField(max_length=50, null=True, blank=True)
    transaction_types = models.JSONField(null=True, blank=True)
    channels = models.JSONField(null=True, blank=True)
    direction = models.CharField(max_length=50, null=True, blank=True)
    thresholds = models.JSONField(null=True, blank=True)
    lookback_days = models.IntegerField(null=True, blank=True)
    aggregation_logic = models.CharField(max_length=255, null=True, blank=True)
    enabled = models.BooleanField(default=True)
    refinements = models.JSONField(null=True, blank=True)
    config_json = models.JSONField(null=True, blank=True)
    field_mappings = models.JSONField(null=True, blank=True)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'scenarios_config'

class SimulationRun(models.Model):
    run_id = models.CharField(primary_key=True, default=uuid.uuid4, max_length=255)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, null=True, related_name='simulation_runs')
    upload = models.ForeignKey(DataUpload, on_delete=models.CASCADE, null=True, related_name='simulation_runs')
    run_type = models.CharField(max_length=50, null=True, blank=True)
    scenarios_run = models.JSONField(null=True, blank=True)
    date_range_start = models.DateTimeField(null=True, blank=True)
    date_range_end = models.DateTimeField(null=True, blank=True)
    total_transactions = models.IntegerField(default=0)
    total_alerts = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=50, null=True, blank=True)
    progress_percentage = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    metadata_info = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'simulation_runs'

class Alert(models.Model):
    alert_id = models.CharField(primary_key=True, default=uuid.uuid4, max_length=255)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, related_name='alerts')
    customer_name = models.CharField(max_length=255, null=True, blank=True)
    scenario = models.ForeignKey(ScenarioConfig, on_delete=models.SET_NULL, null=True, related_name='alerts')
    scenario_name = models.CharField(max_length=255, null=True, blank=True)
    scenario_description = models.TextField(null=True, blank=True)
    alert_date = models.DateTimeField()
    alert_status = models.CharField(max_length=50, default="OPN")
    trigger_details = models.JSONField(null=True, blank=True)
    trigger_reason = models.TextField(null=True, blank=True)
    risk_classification = models.CharField(max_length=50, null=True, blank=True)
    risk_score = models.IntegerField(null=True, blank=True)
    simulation_run = models.ForeignKey(SimulationRun, on_delete=models.CASCADE, related_name='alerts')
    excluded = models.BooleanField(default=False)
    exclusion_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Investigation
    assigned_to = models.CharField(max_length=255, null=True, blank=True)
    investigation_status = models.CharField(max_length=50, default='New')
    outcome = models.CharField(max_length=50, null=True, blank=True)
    sar_reference = models.CharField(max_length=255, null=True, blank=True)
    investigation_notes = models.TextField(null=True, blank=True)
    is_anonymized = models.BooleanField(default=False)
    anonymized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'alerts'

class AlertTransaction(models.Model):
    # Use AutoField ID as primary key
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name='alert_transactions')
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='alert_transactions')
    upload = models.ForeignKey(DataUpload, on_delete=models.CASCADE)
    
    contribution_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_primary_trigger = models.BooleanField(default=False)
    sequence_order = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'alert_transactions'
        constraints = [
            models.UniqueConstraint(fields=['alert', 'transaction'], name='unique_alert_transaction')
        ]

class Account(models.Model):
    account_id = models.CharField(primary_key=True, max_length=255)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='accounts')
    account_number = models.CharField(max_length=255, null=True, blank=True)
    account_type = models.CharField(max_length=50, null=True, blank=True)
    account_status = models.CharField(max_length=50, default='Active')
    currency_code = models.CharField(max_length=10, default='GBP')
    
    account_open_date = models.DateTimeField()
    account_close_date = models.DateTimeField(null=True, blank=True)
    last_transaction_date = models.DateTimeField(null=True, blank=True)
    
    risk_rating = models.TextField(null=True, blank=True)
    is_pep = models.BooleanField(default=False)
    
    current_balance = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    average_monthly_balance = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    
    upload = models.ForeignKey(DataUpload, on_delete=models.CASCADE, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    raw_data = models.JSONField(default=dict)

    class Meta:
        db_table = 'accounts'

class VerifiedEntity(models.Model):
    entity_id = models.CharField(primary_key=True, default=uuid.uuid4, max_length=255)
    entity_name = models.CharField(max_length=255, null=True, blank=True)
    entity_type = models.CharField(max_length=100, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    risk_category = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'verified_entities'

class AlertExclusionLog(models.Model):
    log_id = models.CharField(primary_key=True, default=uuid.uuid4, max_length=255)
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, null=True, related_name='exclusion_logs')
    exclusion_timestamp = models.DateTimeField(default=timezone.now)
    rule_id = models.CharField(max_length=255, null=True, blank=True)
    exclusion_reason = models.TextField(null=True, blank=True)
    risk_flags = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'alert_exclusion_logs'

class FieldMetadata(models.Model):
    metadata_id = models.CharField(primary_key=True, default=uuid.uuid4, max_length=255)
    upload = models.ForeignKey(DataUpload, on_delete=models.CASCADE, related_name='field_metadata')
    table_name = models.CharField(max_length=100)
    field_name = models.CharField(max_length=100)
    field_type = models.CharField(max_length=50)
    total_records = models.IntegerField(null=True, blank=True)
    non_null_count = models.IntegerField(null=True, blank=True)
    null_count = models.IntegerField(null=True, blank=True)
    distinct_count = models.IntegerField(null=True, blank=True)
    min_value = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    max_value = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    avg_value = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    recommended_operators = models.JSONField(null=True, blank=True)
    sample_values = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'field_metadata'

class FieldValueIndex(models.Model):
    index_id = models.CharField(primary_key=True, default=uuid.uuid4, max_length=255)
    upload = models.ForeignKey(DataUpload, on_delete=models.CASCADE, related_name='field_value_index')
    table_name = models.CharField(max_length=100)
    field_name = models.CharField(max_length=100)
    field_value = models.CharField(max_length=500)
    value_count = models.IntegerField(default=1)
    value_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    first_seen = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'field_value_index'

class BeneficiaryHistory(models.Model):
    history_id = models.CharField(primary_key=True, default=uuid.uuid4, max_length=255)
    beneficiary_name = models.CharField(max_length=255, null=True, blank=True)
    beneficiary_account = models.CharField(max_length=255, null=True, blank=True)
    upload = models.ForeignKey(DataUpload, on_delete=models.CASCADE, null=True, related_name='beneficiary_history')
    total_transactions = models.IntegerField(default=0)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    first_seen = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField(default=timezone.now)
    std_dev_amount = models.FloatField(null=True, blank=True)
    avg_days_between_txns = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = 'beneficiary_history'

class CustomerRiskProfile(models.Model):
    profile_id = models.CharField(primary_key=True, default=uuid.uuid4, max_length=255)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, related_name='risk_profiles')
    is_pep = models.BooleanField(default=False)
    high_risk_occupation = models.BooleanField(default=False)
    has_adverse_media = models.BooleanField(default=False)
    previous_sar_count = models.IntegerField(default=0)
    account_age_days = models.IntegerField(default=0)
    last_updated = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'customer_risk_profiles'

class DataQualityMetrics(models.Model):
    metric_id = models.CharField(primary_key=True, default=uuid.uuid4, max_length=255)
    upload = models.ForeignKey(DataUpload, on_delete=models.CASCADE, related_name='quality_metrics')
    completeness_score = models.FloatField(null=True, blank=True)
    validity_score = models.FloatField(null=True, blank=True)
    uniqueness_score = models.FloatField(null=True, blank=True)
    field_level_issues = models.JSONField(null=True, blank=True)
    row_level_issues = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'data_quality_metrics'

class AuditLog(models.Model):
    log_id = models.CharField(primary_key=True, default=uuid.uuid4, max_length=255)
    timestamp = models.DateTimeField(default=timezone.now)
    user_id = models.CharField(max_length=255, null=True, blank=True)
    action_type = models.CharField(max_length=100, null=True, blank=True)
    target_entity_id = models.CharField(max_length=255, null=True, blank=True)
    details = models.JSONField(null=True, blank=True)
    risk_score_snapshot = models.FloatField(null=True, blank=True)
    justification_notes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'audit_logs'

class ComparisonReport(models.Model):
    report_id = models.CharField(primary_key=True, default=uuid.uuid4, max_length=255)
    run = models.ForeignKey(SimulationRun, on_delete=models.CASCADE, null=True, related_name='comparison_reports')
    report_type = models.CharField(max_length=100, null=True, blank=True)
    report_data = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'comparison_reports'

class ScenarioVersion(models.Model):
    version_id = models.CharField(primary_key=True, default=uuid.uuid4, max_length=255)
    scenario = models.ForeignKey(ScenarioConfig, on_delete=models.CASCADE, related_name='versions')
    version_number = models.IntegerField()
    config_snapshot = models.JSONField(null=True, blank=True)
    change_description = models.TextField(null=True, blank=True)
    changed_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'scenario_versions'

class SimulationComparison(models.Model):
    comparison_id = models.CharField(primary_key=True, default=uuid.uuid4, max_length=255)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, null=True)
    base_run = models.ForeignKey(SimulationRun, on_delete=models.CASCADE, related_name='base_comparisons')
    challenger_run = models.ForeignKey(SimulationRun, on_delete=models.CASCADE, related_name='challenger_comparisons')
    alerts_delta = models.IntegerField(null=True, blank=True)
    efficiency_score = models.FloatField(null=True, blank=True)
    overlap_count = models.IntegerField(null=True, blank=True)
    comparison_details = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'simulation_comparisons'
