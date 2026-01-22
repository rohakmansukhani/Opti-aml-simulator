from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Header
from fastapi.responses import StreamingResponse
import io
import pandas as pd
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel

from database import get_db, _get_engine, DEFAULT_DB_URL, resolve_db_url, get_service_engine
from services.simulation_service import SimulationService
from auth import get_current_user
from models import DataUpload, Customer
from datetime import datetime, timezone

def run_simulation_background(run_id: str, db_url: str):
    # Use service role for background system operations to bypass RLS
    SessionLocal = get_service_engine()
    db = SessionLocal()
    try:
        service = SimulationService(db)
        service.execute_run(run_id)
    finally:
        db.close()

router = APIRouter(prefix="/api/simulation", tags=["Simulation"])

class RunRequest(BaseModel):
    scenarios: List[str]
    run_type: str = "baseline"
    field_mappings: Optional[Dict[str, str]] = None
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None

@router.post("/check-schema")
async def check_schema(
    request: RunRequest,
    db: Session = Depends(get_db),
    user_data: dict = Depends(get_current_user)
):
    """
    Validates if the current DB has all columns required by the selected scenarios.
    Returns list of missing fields.
    """
    from models import ScenarioConfig, Transaction, Customer, DataUpload
    from sqlalchemy import inspect
    
    user_id = user_data.get("sub")
    
    # 1. Collect all required fields from scenarios
    required_fields = set()
    
    scenarios = db.query(ScenarioConfig).filter(
        ScenarioConfig.scenario_id.in_(request.scenarios)
    ).all()
    
    for sc in scenarios:
        config = sc.config_json
        if not config:
            continue
        
        # Filters
        if 'filters' in config:
            for f in config['filters']:
                if 'field' in f:
                    required_fields.add(f['field'])
                
        # Aggregation
        if 'aggregation' in config and 'field' in config['aggregation']:
            required_fields.add(config['aggregation']['field'])
        
        # Aggregation group_by
        if 'aggregation' in config and 'group_by' in config['aggregation']:
            group_by = config['aggregation']['group_by']
            if isinstance(group_by, list):
                required_fields.update(group_by)
            elif isinstance(group_by, str):
                required_fields.add(group_by)
            
        # Threshold (Field based)
        if 'threshold' in config:
            if 'field_based' in config['threshold']:
                ref_field = config['threshold']['field_based'].get('reference_field')
                if ref_field:
                    required_fields.add(ref_field)
            
            # Segment-based threshold
            if 'segment_based' in config['threshold']:
                segment_field = config['threshold']['segment_based'].get('segment_field')
                if segment_field:
                    required_fields.add(segment_field)

    # 2. Get available columns from BOTH physical columns AND raw_data
    available_columns = set()
    
    # Add physical columns from inspector
    inspector = inspect(db.bind)
    for table in [Transaction, Customer]:
        for col in inspector.get_columns(table.__tablename__):
            available_columns.add(col['name'])
    
    # Extract fields from raw_data JSONB (same logic as /schema endpoint)
    latest_upload = db.query(DataUpload).filter(
        DataUpload.user_id == user_id
    ).order_by(DataUpload.upload_timestamp.desc()).first()
    
    if latest_upload:
        # Get sample transaction to inspect raw_data keys
        sample_txn = db.query(Transaction).filter(
            Transaction.upload_id == latest_upload.upload_id
        ).first()
        
        if sample_txn and sample_txn.raw_data:
            # Add all keys from raw_data JSONB
            for field_name in sample_txn.raw_data.keys():
                available_columns.add(field_name)
        
        # Get sample customer to inspect raw_data keys
        sample_cust = db.query(Customer).filter(
            Customer.upload_id == latest_upload.upload_id
        ).first()
        
        if sample_cust and sample_cust.raw_data:
            # Add all keys from customer raw_data
            for field_name in sample_cust.raw_data.keys():
                available_columns.add(field_name)
    
    # 3. Determine missing fields
    missing = [f for f in required_fields if f and f not in available_columns]
    
    return {
        "status": "ok" if not missing else "missing_fields",
        "missing_fields": missing,
        "available_columns": sorted(list(available_columns))
    }

@router.post("/run")
async def start_simulation(
    request: RunRequest,
    background_tasks: BackgroundTasks,
    user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_db_url: Optional[str] = Header(None)
):
    user_id = user_data.get("sub")
    service = SimulationService(db)
    
    # Pass mappings and dates to create_run (Need to update Service signature)
    # Storing mappings in metadata or just passing to execution?
    # Ideally passing to execution.
    # Service logic updates needed.
    
    run = service.create_run(request.run_type, request.scenarios, user_id)
    
    # Pass the current DB URL to the background task
    target_url = resolve_db_url(x_db_url) or DEFAULT_DB_URL
    
    # Update Run Metadata with Mappings/Dates for context
    run.metadata_info = {
        "field_mappings": request.field_mappings,
        "date_range": {
            "start": request.date_range_start.isoformat() if request.date_range_start else None,
            "end": request.date_range_end.isoformat() if request.date_range_end else None
        }
    }
    
    # ✅ Explicitly save Date Ranges to columns
    if request.date_range_start:
        run.date_range_start = request.date_range_start
    if request.date_range_end:
        run.date_range_end = request.date_range_end
        
    db.commit()
    
    background_tasks.add_task(run_simulation_background, run.run_id, target_url)
    
    return {"run_id": run.run_id, "status": "pending"}

@router.get("/{run_id}/status")
async def get_status(
    run_id: str, 
    user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from models import SimulationRun
    user_id = user_data.get("sub")
    
    run = db.query(SimulationRun).filter(
        SimulationRun.run_id == run_id,
        SimulationRun.user_id == user_id
    ).first()
    
    if not run:
        raise HTTPException(404, "Run not found or access denied")
    return {
        "run_id": run.run_id,
        "status": run.status,
        "total_alerts": run.total_alerts,
        "error": run.metadata_info
    }

@router.get("/runs")
async def list_simulation_runs(
    user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all completed simulation runs for the current user."""
    from models import SimulationRun, ScenarioConfig
    user_id = user_data.get("sub")
    
    runs = db.query(SimulationRun).filter(
        SimulationRun.user_id == user_id,
        SimulationRun.status == 'completed'
    ).order_by(SimulationRun.created_at.desc()).all()

    # Create mapping of Scenario ID -> Name
    all_scenarios = db.query(ScenarioConfig).all()
    scenario_map = {s.scenario_id: s.scenario_name for s in all_scenarios}
    
    results = []
    for r in runs:
        scenario_names = []
        if r.scenarios_run:
            for sid in r.scenarios_run:
                # Resolve ID to name, fallback to ID if not found
                scenario_names.append(scenario_map.get(sid, sid))

        results.append({
            "run_id": r.run_id,
            "run_type": r.run_type,
            "total_alerts": r.total_alerts,
            "created_at": r.created_at.isoformat(),
            "scenarios_run": r.scenarios_run, # Keep IDs for logic
            "scenario_names": scenario_names, # Add Names for display
            "status": r.status,
            "metadata_info": r.metadata_info
        })
    
    return results

@router.get("/{run_id}/alerts")
async def get_run_alerts(
    run_id: str, 
    user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from models import Alert, SimulationRun
    user_id = user_data.get("sub")
    
    # Verify ownership
    run_exists = db.query(SimulationRun).filter(
        SimulationRun.run_id == run_id,
        SimulationRun.user_id == user_id
    ).first()
    
    if not run_exists:
        raise HTTPException(404, "Run not found or access denied")
        
    alerts = db.query(Alert).filter(Alert.run_id == run_id).all()
    return alerts

@router.get("/{run_id}/export/excel")
async def export_run_results(
    run_id: str, 
    user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from models import Alert, SimulationRun
    user_id = user_data.get("sub")
    
    # Verify ownership
    run_exists = db.query(SimulationRun).filter(
        SimulationRun.run_id == run_id,
        SimulationRun.user_id == user_id
    ).first()
    
    if not run_exists:
        raise HTTPException(404, "Run not found or access denied")
    
    # Query alerts using pandas
    alerts_query = db.query(Alert).filter(Alert.run_id == run_id)
    df = pd.read_sql(alerts_query.statement, db.bind)
    
    if df.empty:
        # Create empty DF with headers if no data to avoid crash
        df = pd.DataFrame(columns=['alert_id', 'customer_id', 'scenario_id', 'risk_score'])

    # Clean up JSON columns for Excel
    if 'trigger_details' in df.columns:
        df['trigger_details'] = df['trigger_details'].astype(str)
        
    # Remove timezones from all datetime columns
    for col in df.select_dtypes(include=['datetime64[ns, UTC]', 'datetime64[ns]', 'datetime']).columns:
        df[col] = df[col].dt.tz_localize(None)
        
    # Generate Excel in memory
    output = io.BytesIO()
    # Ensure openpyxl is installed. If not, fallback to CSV could be considered, but user asked for Excel.
    # Assuming openpyxl is present (standard with pandas in many envs, or implied).
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Alerts')
    
    output.seek(0)
    
    return StreamingResponse(
        output, 
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={"Content-Disposition": f"attachment; filename=simulation_results_{run_id}.xlsx"}
    )

@router.post("/preview")
async def preview_scenario(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Test scenario logic - returns sample alerts without saving to DB
    """
    try:
        user_id = current_user.get('sub')
        limit = payload.get('limit', 5)
        
        # Get active upload
        active_upload = db.query(DataUpload).filter(
            DataUpload.user_id == user_id,
            DataUpload.status == 'active',
            DataUpload.expires_at > datetime.now(timezone.utc)
        ).order_by(DataUpload.upload_timestamp.desc()).first()
        
        if not active_upload:
            return {
                "status": "no_data",
                "message": "No active data upload found"
            }
        
        # Initialize Service
        from services.simulation_service import SimulationService
        service = SimulationService(db)
        
        # Build theoretical scenario config
        scenario_config = {
            "scenario_id": payload.get('scenario_id', 'PREVIEW_TEST'),
            "scenario_name": payload.get('scenario_name', 'Preview Test'),
            "config_json": payload.get('config_json', {}),
            "priority": "MEDIUM",
            "is_active": True,
            "field_mappings": payload.get('field_mappings') # Pass mappings if any
        }
        
        # Get customer list for this user
        # 1. Try active upload first
        customers = db.query(Customer.customer_id).filter(
            Customer.upload_id == active_upload.upload_id
        ).distinct().all()
        
        # 2. Fallback: If no customers in active upload (e.g. it was transactions only),
        # Find the most recent upload that has customers
        if not customers:
            recent_cust_upload = db.query(DataUpload).filter(
                DataUpload.user_id == user_id,
                DataUpload.record_count_customers > 0,
                DataUpload.status == 'active'
            ).order_by(DataUpload.upload_timestamp.desc()).first()
            
            if recent_cust_upload:
                print(f"[PREVIEW] Fallback: Using customers from upload {recent_cust_upload.upload_id}")
                customers = db.query(Customer.customer_id).filter(
                    Customer.upload_id == recent_cust_upload.upload_id
                ).distinct().all()
        
        customer_ids = [c[0] for c in customers]
        
        if not customer_ids:
            return {
                "status": "no_data",
                "message": "No customers found in active upload or recent history"
            }
        
        # Run simulation in preview mode (dry run, no DB writes)
        # Limit to 20 customers for preview speed
        print(f"[PREVIEW] Running scenario for sample of {min(20, len(customer_ids))} customers")
        
        alerts_df = service._execute_single_scenario(
            scenario_config=scenario_config,
            customer_ids=customer_ids[:20],
            upload_id=active_upload.upload_id,
            run_id='preview_run',
            user_id=user_id
        )
        
        if alerts_df is None or alerts_df.empty:
            return {
                "status": "success",
                "alert_count": 0,
                "sample_alerts": [],
                "sample_size": len(customer_ids),
                "estimated_monthly_volume": 0,
                "message": "No alerts generated with current configuration"
            }
        
        # Convert to sample alerts
        sample_alerts = []
        for _, row in alerts_df.head(limit).iterrows():
            # Check if alert_date is a Timestamp or datetime object
            a_date = row.get('alert_date', datetime.now())
            if hasattr(a_date, 'isoformat'):
                a_date = a_date.isoformat()
            else:
                a_date = str(a_date)
                
            sample_alerts.append({
                "customer_id": str(row.get('customer_id')),
                "alert_date": a_date,
                "trigger_details": {
                    "aggregated_value": float(row.get('aggregated_value', 0)) if row.get('aggregated_value') else 0,
                    "transaction_count": int(row.get('transaction_count', 0)) if row.get('transaction_count') else 0
                }
            })
        
        # Estimate monthly volume
        alert_count = len(alerts_df)
        total_customers = len(customer_ids)
        
        # Simple extrapolation: (alerts_in_sample / customers_in_sample) * total_customers
        # Multiplied by 1.5 as a loose "monthly scaling" factor
        estimated_monthly = int((alert_count / min(20, total_customers)) * total_customers * 1.5)
        
        return {
            "status": "success",
            "alert_count": alert_count,
            "sample_alerts": sample_alerts,
            "sample_size": total_customers,
            "estimated_monthly_volume": estimated_monthly
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Preview failed: {str(e)}"
        }

def _apply_field_mappings(config: dict, mappings: dict) -> dict:
    """
    Recursively replaces field names in config JSON.
    Example: {"transaction_amount": "txn_amt"} replaces all occurrences.
    """
    import copy
    config = copy.deepcopy(config)
    
    def replace_in_obj(obj):
        if isinstance(obj, dict):
            for key, value in list(obj.items()):
                # Replace field references
                if key == 'field' and value in mappings:
                    obj[key] = mappings[value]
                elif key == 'group_by' and isinstance(value, list):
                    obj[key] = [mappings.get(v, v) for v in value]
                elif key == 'segment_field' and value in mappings:
                     obj[key] = mappings[value]
                else:
                    replace_in_obj(value)
        elif isinstance(obj, list):
            for item in obj:
                replace_in_obj(item)
    
    replace_in_obj(config)
    return config
