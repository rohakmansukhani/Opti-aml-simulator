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
    db: Session = Depends(get_db)
):
    """
    Validates if the current DB has all columns required by the selected scenarios.
    Returns list of missing fields.
    """
    from models import ScenarioConfig, Transaction, Customer
    from sqlalchemy import inspect
    
    # 1. Collect all required fields from scenarios
    required_fields = set()
    
    scenarios = db.query(ScenarioConfig).filter(ScenarioConfig.scenario_id.in_(request.scenarios)).all()
    
    for sc in scenarios:
        config = sc.config_json
        if not config: continue
        
        # Filters
        if 'filters' in config:
            for f in config['filters']:
                if 'field' in f: required_fields.add(f['field'])
                
        # Aggregation
        if 'aggregation' in config and 'field' in config['aggregation']:
            required_fields.add(config['aggregation']['field'])
            
        # Threshold (Field based)
        if 'threshold' in config and 'field_based' in config['threshold']:
             required_fields.add(config['threshold']['field_based'].get('reference_field'))

    # 2. Collect available columns from key tables
    inspector = inspect(db.bind)
    available_columns = set()
    
    for table in [Transaction, Customer]:
        for col in inspector.get_columns(table.__tablename__):
            available_columns.add(col['name'])
            
    # 3. Determine missing
    # Remove 'virtual' or ignored fields if any
    missing = [f for f in required_fields if f not in available_columns]
    
    return {
        "status": "ok" if not missing else "missing_fields",
        "missing_fields": missing,
        "available_columns": list(available_columns)
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
    config: dict,
    user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Test a scenario configuration on a sample dataset WITHOUT saving it.
    """
    import pandas as pd
    from models import Transaction
    from core.universal_engine import UniversalScenarioEngine
    from core.config_models import ScenarioConfigModel

    try:
        from models import DataUpload
        user_id = user_data.get("sub")
        
        # Load last 1000 transactions via ORM (Scoped to User)
        txns = db.query(Transaction).join(DataUpload).filter(
            DataUpload.user_id == user_id
        ).order_by(
            Transaction.transaction_date.desc()
        ).limit(1000).all()
        
        if not txns:
             return {"status": "no_data", "message": "No transactions found for your account. Please upload data first."}
        
        # Convert to DataFrame
        df = pd.DataFrame([{
            'transaction_id': t.transaction_id,
            'customer_id': t.customer_id,
            'transaction_amount': float(t.transaction_amount),
            'transaction_date': t.transaction_date,
            'transaction_type': t.transaction_type,
            'channel': t.channel,
            'debit_credit_indicator': t.debit_credit_indicator
        } for t in txns])
        
        # Run engine
        engine = UniversalScenarioEngine(db)
        
        # Apply Field Mappings if provided in config
        if 'field_mappings' in config and config['field_mappings']:
            from core.field_mapper import apply_field_mappings_to_df
            df = apply_field_mappings_to_df(df, config['field_mappings'])
        
        # Convert config dict to ScenarioConfigModel
        # Handle simple vs full config structure
        config_data = config.get('config_json', config)
        
        # For preview mode, add default values for required fields if missing
        if 'scenario_id' not in config_data:
            import uuid
            config_data['scenario_id'] = 'preview-' + str(uuid.uuid4())[:8]
        if 'scenario_name' not in config_data:
            config_data['scenario_name'] = 'Preview Test'
        
        # Ensure we have a valid model even if partial config sent
        try:
            scenario = ScenarioConfigModel(**config_data)
        except Exception as e:
            # Fallback for manual construction if pydantic validation fails strictly
            # or if frontend sends partial data. 
            # Ideally we want strictly valid data, but for preview we can be lenient.
            # Reraise for now to catching validation errors.
            raise ValueError(f"Invalid Config: {e}")

        # Execute on sample (Empty customers DF for now, or fetch if needed)
        alerts = engine.execute(scenario, df, pd.DataFrame(), 'PREVIEW')
        
        estimated_monthly = int((len(alerts) / 30) * 30) # Rough estimate on 1000 rows? 
        # Better estimate: (alerts / days_in_sample) * 30
        days_in_sample = (df['transaction_date'].max() - df['transaction_date'].min()).days
        if days_in_sample > 0:
            estimated_monthly = int((len(alerts) / days_in_sample) * 30)
        
        return {
            "status": "success",
            "alert_count": len(alerts),
            "sample_alerts": alerts[:10],  # First 10
            "estimated_monthly_volume": estimated_monthly,
            "sample_size": len(df)
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
