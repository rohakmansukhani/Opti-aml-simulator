from ninja import NinjaAPI, Router, File, UploadedFile, Body
from ninja.security import django_auth
from django.shortcuts import get_object_or_404
from simulation.models import Transaction, Alert, SimulationRun, ScenarioConfig, DataUpload, Customer
from .schemas import (
    DashboardStats, SimulationSummary, ErrorResponse, 
    ScenarioCreateSchema, ScenarioTestRequest, SimulationRunRequest,
    ComparisonRequest, AlertDetailResponse, DatasetSummary,
    SchemaValidationRequest, SchemaValidationResponse, SchemaMappingItem,
    ComparisonRuleRequest
)
from django.db.models import Count, Q
import csv
import io
from django.http import HttpResponse
from django.utils import timezone
from typing import List, Optional
import logging
from simulation.services.data_ingestion import DataIngestionService


logger = logging.getLogger(__name__)


api = NinjaAPI(title="AML Simulator API", version="2.0", auth=django_auth)


# --- Upload Router ---
upload_router = Router(tags=["Upload"])


@upload_router.post("/data/")
def upload_data(request, files: List[UploadedFile] = File(...), dataset_name: str = ""):
    """
    Unified upload endpoint for both transactions and customers.
    Accepts multiple files under the 'files' key.
    """
    if not dataset_name:
        latest = DataUpload.objects.order_by('-upload_timestamp').first()
        dataset_name = latest.dataset_name if latest else "New Dataset"


    service = DataIngestionService()
    upload = None
    
    for file in files:
        upload = service.process_upload(
            io.BytesIO(file.read()), 
            file.name, 
            dataset_name, 
            existing_upload=upload
        )
    
    if not upload:
        return {"status": "error", "message": "No files processed"}
        
    return {
        "status": "success", 
        "upload_id": str(upload.upload_id),
        "total_transactions": upload.record_count_transactions,
        "total_customers": upload.record_count_customers
    }


@upload_router.delete("/{upload_id}", response={200: dict, 404: dict})
def delete_dataset(request, upload_id: str):
    """
    Delete a dataset and all associated records (transactions, customers, alerts, runs).
    """
    try:
        upload = DataUpload.objects.get(upload_id=upload_id)
        upload.delete()
        return 200, {"status": "deleted", "upload_id": upload_id}
    except DataUpload.DoesNotExist:
        return 404, {"status": "error", "message": "Dataset not found"}


# --- Dashboard Router ---
dashboard_router = Router(tags=["Dashboard"])


@dashboard_router.get("/stats/", response=DashboardStats)
def get_dashboard_stats(request):
    total_runs = SimulationRun.objects.count()
    total_alerts = Alert.objects.count()
    total_tx = Transaction.objects.count()
    total_customers = Customer.objects.count()
    
    all_runs = SimulationRun.objects.order_by('created_at').all()
    scenarios = {s.scenario_id: s.scenario_name for s in ScenarioConfig.objects.all()}
    
    all_summaries = []
    for i, s in enumerate(all_runs, 1):
        all_summaries.append(SimulationSummary(
            run_id=str(s.run_id),
            run_number=i,
            status=s.status,
            total_alerts=s.total_alerts or 0,
            scenarios_run=s.scenarios_run or [],
            scenario_names=[scenarios.get(sid, sid) for sid in (s.scenarios_run or [])],
            created_at=s.created_at
        ))
    
    recent_data = all_summaries[::-1][:5]
        
    latest_upload = DataUpload.objects.order_by('-upload_timestamp').first()
    
    return {
        "total_alerts": total_alerts,
        "transactions_scanned": total_tx,
        "customers_scanned": total_customers,
        "total_simulations": total_runs,
        "has_data": total_tx > 0,
        "dataset_name": latest_upload.dataset_name if latest_upload else None,
        "recent_simulations": recent_data
    }


# --- Simulation Router ---
simulation_router = Router(tags=["Simulation"])


@simulation_router.get("/runs/", response=List[SimulationSummary])
def get_simulation_runs(request):
    runs = SimulationRun.objects.order_by('created_at').all()
    scenarios = {s.scenario_id: s.scenario_name for s in ScenarioConfig.objects.all()}
    
    results = []
    for i, r in enumerate(runs, 1):
        results.append(SimulationSummary(
            run_id=str(r.run_id),
            run_number=i,
            status=r.status,
            total_alerts=r.total_alerts or 0,
            scenarios_run=r.scenarios_run or [],
            scenario_names=[scenarios.get(sid, sid) for sid in (r.scenarios_run or [])],
            created_at=r.created_at
        ))
    return results[::-1]


@simulation_router.get("/{run_id}/alerts/")
def get_simulation_alerts(request, run_id: str):
    alerts = Alert.objects.filter(simulation_run_id=run_id).all()
    data = []
    for a in alerts:
        data.append({
            "alert_id": str(a.alert_id),
            "customer_id": a.customer_id,
            "customer_name": a.customer_name or (a.customer.raw_data.get('name', 'Unknown') if a.customer else 'Unknown'),
            "scenario_name": a.scenario_name,
            "risk_score": a.risk_score,
            "status": "new"
        })
    return data


@simulation_router.get("/{run_id}/export/")
def export_run_results(request, run_id: str):
    """Export simulation alerts to CSV."""
    run = get_object_or_404(SimulationRun, run_id=run_id)
    alerts = Alert.objects.filter(simulation_run_id=run_id).all()
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="simulation_{run_id}_alerts.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Alert ID', 'Scenario', 'Risk Score', 'Customer ID', 'Customer Name', 'Occupation', 'Annual Income', 'Date', 'Trigger Reason'])
    
    for a in alerts:
        cust_name = a.customer_name or (a.customer.raw_data.get('name', 'Unknown') if a.customer else 'Unknown')
        occupation = a.customer.raw_data.get('occupation', 'N/A') if a.customer else 'N/A'
        income = a.customer.raw_data.get('annual_income', 'N/A') if a.customer else 'N/A'
        alert_date = a.alert_date.strftime('%Y-%m-%d %H:%M:%S') if a.alert_date else 'N/A'
        
        writer.writerow([
            str(a.alert_id),
            a.scenario_name,
            a.risk_score,
            a.customer_id,
            cust_name,
            occupation,
            income,
            alert_date,
            a.trigger_reason
        ])
        
    return response


@simulation_router.get("/{run_id}/status")
def get_run_status(request, run_id: str):
    run = get_object_or_404(SimulationRun, run_id=run_id)
    return {
        "run_id": str(run.run_id),
        "status": run.status,
        "total_alerts": run.total_alerts
    }


@simulation_router.get("/alerts/{alert_id}/")
def get_alert_detail(request, alert_id: str):
    alert = get_object_or_404(Alert, alert_id=alert_id)
    return {
        "alert_id": str(alert.alert_id),
        "scenario_name": alert.scenario_name,
        "risk_score": alert.risk_score,
        "customer_id": alert.customer_id,
        "customer_name": alert.customer_name or (alert.customer.raw_data.get('name', 'Unknown') if alert.customer else 'Unknown'),
        "trigger_details": alert.trigger_details,
        "trigger_reason": alert.trigger_reason,
        "status": "new"
    }


@simulation_router.get("/datasets/", response=List[DatasetSummary])
def get_datasets(request):
    """List all available datasets."""
    uploads = DataUpload.objects.order_by('-upload_timestamp').all()
    return [DatasetSummary(
        upload_id=str(u.upload_id),
        dataset_name=u.dataset_name or u.filename,
        record_count_transactions=u.record_count_transactions or 0,
        record_count_customers=u.record_count_customers or 0,
        upload_timestamp=u.upload_timestamp,
        is_active=(u.status == 'active')
    ) for u in uploads]


@simulation_router.post("/validate-schema/", response=SchemaValidationResponse)
def validate_schema(request, payload: SchemaValidationRequest = Body(...)):
    """Check if the selected dataset has all required fields for selected scenarios."""
    upload = get_object_or_404(DataUpload, upload_id=payload.upload_id)
    scenarios = ScenarioConfig.objects.filter(scenario_id__in=payload.scenario_ids)
    
    # Get available columns from the dataset
    tx_cols = []
    cust_cols = []
    
    last_tx = Transaction.objects.filter(upload=upload).first()
    if last_tx and last_tx.raw_data:
        tx_cols = list(last_tx.raw_data.keys())
        
    last_cust = Customer.objects.filter(upload=upload).first()
    if last_cust and last_cust.raw_data:
        cust_cols = list(last_cust.raw_data.keys())
    
    missing_fields = []
    required_tx_fields = set()
    required_cust_fields = set()
    
    for s in scenarios:
        config = s.config_json or {}
        filters = config.get('filters', [])
        aggregation = config.get('aggregation', {})
        
        # Check filters
        for f in filters:
            field = f.get('field')
            if not field: continue
            
            if field.startswith('customer.'):
                required_cust_fields.add(field.replace('customer.', ''))
            elif field in cust_cols and field not in tx_cols:
                required_cust_fields.add(field)
            else:
                required_tx_fields.add(field)
        
        # Check aggregation
        agg_field = aggregation.get('field')
        if agg_field:
            if agg_field.startswith('customer.'):
                required_cust_fields.add(agg_field.replace('customer.', ''))
            elif agg_field in cust_cols and agg_field not in tx_cols:
                required_cust_fields.add(agg_field)
            else:
                required_tx_fields.add(agg_field)
            
    # Find missing
    for f in required_tx_fields:
        if f not in tx_cols:
            missing_fields.append(SchemaMappingItem(rule_field=f, source_table='transaction'))
            
    for f in required_cust_fields:
        if f not in cust_cols:
            missing_fields.append(SchemaMappingItem(rule_field=f, source_table='customer'))
            
    return SchemaValidationResponse(
        is_valid=(len(missing_fields) == 0),
        missing_fields=missing_fields,
        available_columns={
            'transactions': sorted(tx_cols),
            'customers': sorted(cust_cols)
        }
    )


@simulation_router.post("/run/")
def run_simulation(request, data: SimulationRunRequest):
    """Execute a simulation run synchronously."""
    from simulation.services.simulation_service import SimulationService
    import uuid
    
    # Use provided upload_id or latest
    upload_id = data.upload_id
    if not upload_id:
        latest = DataUpload.objects.order_by('-upload_timestamp').first()
        upload_id = str(latest.upload_id) if latest else None
        
    if not upload_id:
        return {"status": "error", "message": "No dataset found to run simulation against"}

    # Create run record
    run = SimulationRun.objects.create(
        status="pending",
        scenarios_run=data.scenarios,
        upload_id=upload_id,
        run_type=data.run_type,
        total_alerts=0,
        created_at=timezone.now(),
        metadata_info={
            "field_mappings": data.field_mappings
        }
    )
    
    # Execute simulation synchronously
    service = SimulationService()
    user_id = str(request.user.id) if request.user.is_authenticated else "anonymous"
    
    try:
        logger.info(f"Starting simulation execution for run {run.run_id}")
        service.execute_run(str(run.run_id), user_id)
        logger.info(f"Simulation {run.run_id} completed successfully")
    except Exception as e:
        logger.error(f"Simulation {run.run_id} failed: {str(e)}", exc_info=True)
        return {
            "status": "error", 
            "run_id": str(run.run_id),
            "message": f"Simulation failed: {str(e)}"
        }
    
    return {
        "status": "success",
        "run_id": str(run.run_id)
    }


# --- Rules Router ---
rules_router = Router(tags=["Rules"])


@rules_router.get("/scenarios/")
def get_scenarios(request):
    scenarios = ScenarioConfig.objects.all()
    return [{
        "scenario_id": str(s.scenario_id),
        "scenario_name": s.scenario_name,
        "description": s.description,
        "is_active": s.enabled,
        "priority": s.priority,
        "config": s.config_json
    } for s in scenarios]


@rules_router.post("/scenarios/")
def create_scenario(request, payload: ScenarioCreateSchema = Body(...)):
    """
    Create or update a scenario configuration.
    """
    import uuid

    # Check if updating existing scenario
    if payload.scenario_id:
        try:
            scenario = ScenarioConfig.objects.get(scenario_id=payload.scenario_id)
            scenario.scenario_name = payload.scenario_name
            scenario.description = payload.description
            scenario.priority = payload.priority
            scenario.enabled = payload.enabled
            scenario.config_json = payload.config_json
            scenario.save()
            return {
                "status": "updated",
                "scenario_id": str(scenario.scenario_id),
                "scenario_name": scenario.scenario_name
            }
        except ScenarioConfig.DoesNotExist:
            pass

    # Create new scenario
    scenario = ScenarioConfig.objects.create(
        scenario_id=str(uuid.uuid4()),
        scenario_name=payload.scenario_name,
        description=payload.description,
        priority=payload.priority,
        enabled=payload.enabled,
        config_json=payload.config_json
    )

    return {
        "status": "created",
        "scenario_id": str(scenario.scenario_id),
        "scenario_name": scenario.scenario_name
    }


@rules_router.delete("/scenarios/{scenario_id}", response={200: dict, 404: dict})
def delete_scenario(request, scenario_id: str):
    """
    Delete a scenario configuration.
    """
    try:
        scenario = ScenarioConfig.objects.get(scenario_id=scenario_id)
        scenario.delete()
        return 200, {"status": "deleted", "scenario_id": scenario_id}
    except ScenarioConfig.DoesNotExist:
        return 404, {"status": "error", "message": "Scenario not found"}


@rules_router.get("/fields/")
def get_available_fields(request):
    """
    Dynamically discover fields from the latest raw_data in transactions and customers.
    """
    fields = {"transactions": [], "customers": []}

    # Inspect latest transaction for keys
    last_tx = Transaction.objects.order_by('-created_at').first()
    if last_tx and last_tx.raw_data:
        fields["transactions"] = sorted(list(last_tx.raw_data.keys()))

    # Inspect latest customer for keys
    last_cust = Customer.objects.order_by('-created_at').first()
    if last_cust and last_cust.raw_data:
        fields["customers"] = sorted(list(last_cust.raw_data.keys()))
        
    return fields

@rules_router.get("/latest-run/{scenario_id}")
def get_scenario_latest_run(request, scenario_id: str):
    """Get the latest run ID that included this scenario."""
    # Oracle doesn't support __contains on JSONField. 
    # Workaround: Fetch recent runs and filter in Python.
    recent_runs = SimulationRun.objects.all().order_by('-created_at')[:50]
    run = None
    for r in recent_runs:
        if r.scenarios_run and scenario_id in r.scenarios_run:
            run = r
            break
    
    if not run:
        return 404, {"error": "No run found for this scenario"}
        
    return {
        "run_id": str(run.run_id),
        "created_at": run.created_at,
        "total_alerts": run.total_alerts
    }


@rules_router.get("/values/", response=List[str])
def get_field_values(request, field: str, search: str = None):
    """
    Get unique values for a specific field from raw_data.
    """
    from django.db.models import F

    # Check Transaction
    last_tx = Transaction.objects.order_by('-created_at').first()
    is_tx_field = last_tx and field in last_tx.raw_data if last_tx else False
    
    if is_tx_field:
        qs = Transaction.objects.all()
        lookup = f"raw_data__{field}"
        if search:
           qs = qs.filter(**{f"{lookup}__icontains": search})
        
        values = qs.values_list(lookup, flat=True).distinct()[:50]
        return [str(v) for v in values if v is not None]

    # Check Customer
    last_cust = Customer.objects.order_by('-created_at').first()
    is_cust_field = last_cust and field in last_cust.raw_data if last_cust else False
    
    if is_cust_field:
        qs = Customer.objects.all()
        lookup = f"raw_data__{field}"
        if search:
            qs = qs.filter(**{f"{lookup}__icontains": search})
            
        values = qs.values_list(lookup, flat=True).distinct()[:50]
        return [str(v) for v in values if v is not None]

    return []


from ninja import Schema
from typing import Optional, Any


class FilterItem(Schema):
    field: str
    operator: str
    value: Any


class ValidationPayload(Schema):
    upload_id: Optional[str] = None
    filters: List[FilterItem]


@rules_router.post("/validation/filters")
def validate_filters(request, payload: ValidationPayload = Body(...)):
    """
    Test filters against the latest dataset.
    """
    filters = payload.filters
    if not filters:
        return {"match_count": 0, "total_records": 0}

    # Get latest upload
    upload = DataUpload.objects.filter(record_count_transactions__gt=0).order_by('-upload_timestamp').first()
    if not upload:
        return {"match_count": 0, "total_records": 0}

    # Determine which fields belong to customers vs transactions
    tx_fields = set()
    cust_fields = set()

    last_tx = Transaction.objects.filter(upload=upload).first()
    if last_tx and last_tx.raw_data:
        tx_fields = set(last_tx.raw_data.keys())

    last_cust = Customer.objects.filter(upload=upload).first()
    if last_cust and last_cust.raw_data:
        cust_fields = set(last_cust.raw_data.keys())

    qs = Transaction.objects.filter(upload=upload)

    # Build query
    query = Q()
    for f in filters:
        field = f.field
        op = f.operator
        val = f.value

        if not field: continue

        # Determine lookup
        if field in cust_fields:
            key = f"customer__raw_data__{field}"
        else:
            key = f"raw_data__{field}"

        if op == '==':
            query &= Q(**{key: val})
        elif op == '!=':
            query &= ~Q(**{key: val})
        elif op == '>':
            query &= Q(**{f"{key}__gt": val})
        elif op == '<':
            query &= Q(**{f"{key}__lt": val})
        elif op == '>=':
             query &= Q(**{f"{key}__gte": val})
        elif op == '<=':
             query &= Q(**{f"{key}__lte": val})
        elif op == 'in':
            if isinstance(val, str):
                vals = [v.strip() for v in val.split(',')]
            else:
                vals = val
            vals = [v for v in vals if v]
            if vals:
                 query &= Q(**{f"{key}__in": vals})

    match_count = qs.filter(query).count()
    return {
        "match_count": match_count,
        "total_records": qs.count(),
        "upload_id": str(upload.upload_id)
    }


@rules_router.post("/validation/scenario")
def validate_scenario(request, payload: ScenarioTestRequest = Body(...)):
    """
    Test a complete scenario (existing or new) against the latest dataset.
    """
    from simulation.engines.universal_engine import UniversalScenarioEngine
    
    upload_id = payload.upload_id
    if not upload_id:
        upload = DataUpload.objects.order_by('-upload_timestamp').first()
        upload_id = str(upload.upload_id) if upload else None

    if not upload_id:
        return {"status": "error", "message": "No dataset found to test against"}

    engine = UniversalScenarioEngine()
    
    # If config_json is provided (Draft), use it. Otherwise use existing scenario_id.
    config = payload.config_json
    scenario_name = "Draft Scenario"
    
    if not config and payload.scenario_id:
        try:
            scenario_obj = ScenarioConfig.objects.get(scenario_id=payload.scenario_id)
            config = scenario_obj.config_json
            scenario_name = scenario_obj.scenario_name
        except ScenarioConfig.DoesNotExist:
            return {"status": "error", "message": "Scenario ID not found"}

    if not config:
        return {"status": "error", "message": "No configuration provided for testing"}

    # Run dry-run logic
    alerts = engine.run_scenario_logic(
        config=config,
        upload_id=upload_id,
        user_id=str(request.user.id),
        scenario_name=scenario_name
    )

    return {
        "status": "success",
        "upload_id": upload_id,
        "alerts_generated": len(alerts),
        "alerts": alerts[:10],
        "message": f"Scenario matching generated {len(alerts)} alerts."
    }


# --- Comparison Router ---
comparison_router = Router(tags=["Comparison"])

@comparison_router.post("/compare/")
def compare_strategies(request, payload: ComparisonRuleRequest):
    """Compare the latest runs of two scenarios."""
    from simulation.engines.comparison_engine import ComparisonEngine
    
    # Oracle workaround: Filter in Python
    recent_runs = SimulationRun.objects.all().order_by('-created_at')[:100]
    
    b_run = None
    for r in recent_runs:
        if r.scenarios_run and payload.baseline_scenario_id in r.scenarios_run:
            b_run = r
            break
            
    r_run = None
    for r in recent_runs:
        if r.scenarios_run and payload.refined_scenario_id in r.scenarios_run:
            r_run = r
            break
    
    if not b_run or not r_run:
        return 404, {
            "error": "Missing run data", 
            "baseline_exists": b_run is not None,
            "refined_exists": r_run is not None
        }

    engine = ComparisonEngine()
    comparison = engine.compare_runs(str(b_run.run_id), str(r_run.run_id))
    
    # Enrich summary with run dates
    comparison['summary']['baseline_date'] = b_run.created_at
    comparison['summary']['refined_date'] = r_run.created_at
    
    return comparison

@comparison_router.get("/compare/{b_run_id}/{r_run_id}/export/")
def export_comparison(request, b_run_id: str, r_run_id: str):
    """Export comparison result to CSV (Simplified for now)."""
    from simulation.engines.comparison_engine import ComparisonEngine
    engine = ComparisonEngine()
    data = engine.compare_runs(b_run_id, r_run_id)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="comparison_{b_run_id}_vs_{r_run_id}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Customer ID', 'Status', 'Risk Score', 'Risk Change', 'Scenario', 'Amount', 'Reason'])
    
    for item in data.get('granular_diff', []):
        writer.writerow([
            item['customer_id'],
            item['status'],
            item['risk_score'],
            item['risk_change'],
            item['scenario'],
            item['amount'],
            item['reason']
        ])
        
    return response


# Register Routers
api.add_router("/dashboard/", dashboard_router)
api.add_router("/upload/", upload_router)
api.add_router("/simulation/", simulation_router)
api.add_router("/rules/", rules_router)
api.add_router("/comparison/", comparison_router)
