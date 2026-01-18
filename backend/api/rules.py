from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import ScenarioConfig
from auth import get_current_user
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import datetime

router = APIRouter(prefix="/api/rules", tags=["Rules"])

class RefinementRule(BaseModel):
    type: str # 'event_based' or 'behavioral'
    excluded_events: Optional[List[str]] = None

class ScenarioUpdate(BaseModel):
    scenario_name: Optional[str] = None
    enabled: Optional[bool] = None
    config_json: Optional[Dict[str, Any]] = None
    thresholds: Optional[Dict[str, float]] = None
    refinements: Optional[List[Dict[str, Any]]] = None

class CreateScenarioRequest(BaseModel):
    scenario_name: str
    priority: str
    is_active: bool
    config_json: Dict[str, Any]
    description: Optional[str] = None
    field_mappings: Optional[Dict[str, str]] = None

@router.post("/scenarios")
async def create_scenario(
    request: CreateScenarioRequest,
    user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Creates a new scenario configuration."""
    import uuid
    try:
        scenario_id = str(uuid.uuid4())[:8]
        user_id = user_data.get("sub")
        
        new_scenario = ScenarioConfig(
            scenario_id=scenario_id,
            user_id=user_id,
            scenario_name=request.scenario_name,
            enabled=request.is_active,
            config_json=request.config_json,
            frequency="daily",
            updated_at=datetime.datetime.utcnow()
        )
        
        db.add(new_scenario)
        db.commit()
        db.refresh(new_scenario)
        
        return {
            "status": "success",
            "scenario_id": scenario_id,
            "message": f"Scenario '{request.scenario_name}' created successfully"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Failed to create scenario: {str(e)}")

@router.get("/scenarios")
async def list_scenarios(
    user_data: dict = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """List all scenarios for the current user."""
    user_id = user_data.get("sub")
    scenarios = db.query(ScenarioConfig).filter(ScenarioConfig.user_id == user_id).all()
    return scenarios

@router.get("/scenarios/{scenario_id}")
async def get_scenario(
    scenario_id: str, 
    user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific scenario by ID."""
    user_id = user_data.get("sub")
    scenario = db.query(ScenarioConfig).filter(
        ScenarioConfig.scenario_id == scenario_id,
        ScenarioConfig.user_id == user_id
    ).first()
    if not scenario:
        if scenario_id in ['ICICI_01', 'ICICI_44']:
            return {"scenario_id": scenario_id, "status": "default_not_configured"}
        raise HTTPException(404, "Scenario not found")
    return scenario

@router.put("/scenarios/{scenario_id}")
async def update_scenario(
    scenario_id: str, 
    update: ScenarioUpdate, 
    user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an existing scenario."""
    user_id = user_data.get("sub")
    scenario = db.query(ScenarioConfig).filter(
        ScenarioConfig.scenario_id == scenario_id,
        ScenarioConfig.user_id == user_id
    ).first()
    
    if not scenario:
        # If upsert is intended, ensure we have minimal required fields.
        # But for 'edit', it should ideally exist. 
        # For robustness, we can keep creation logic if minimal fields provided,
        # but update mostly implies modification.
        if not update.scenario_name:
             raise HTTPException(404, "Scenario not found")
             
        scenario = ScenarioConfig(
            scenario_id=scenario_id,
            user_id=user_id,
            scenario_name=update.scenario_name or scenario_id,
        )
        db.add(scenario)
    
    if update.scenario_name is not None:
        scenario.scenario_name = update.scenario_name
    if update.enabled is not None:
        scenario.enabled = update.enabled
    if update.config_json is not None:
        scenario.config_json = update.config_json
    if update.thresholds is not None:
        scenario.thresholds = update.thresholds
    if update.refinements is not None:
        scenario.refinements = update.refinements
        
    scenario.updated_at = datetime.datetime.utcnow()
        
    db.commit()
    db.refresh(scenario)
    return scenario

@router.delete("/scenarios/{scenario_id}")
async def delete_scenario(
    scenario_id: str,
    user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a scenario."""
    user_id = user_data.get("sub")
    scenario = db.query(ScenarioConfig).filter(
        ScenarioConfig.scenario_id == scenario_id,
        ScenarioConfig.user_id == user_id
    ).first()
    
    if not scenario:
        raise HTTPException(404, "Scenario not found")
    
    db.delete(scenario)
    db.commit()
    
    return {"status": "success", "message": f"Scenario '{scenario.scenario_name}' deleted"}

@router.patch("/scenarios/{scenario_id}/toggle")
async def toggle_scenario(
    scenario_id: str,
    user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Toggle scenario active/inactive status."""
    user_id = user_data.get("sub")
    scenario = db.query(ScenarioConfig).filter(
        ScenarioConfig.scenario_id == scenario_id,
        ScenarioConfig.user_id == user_id
    ).first()
    
    if not scenario:
        raise HTTPException(404, "Scenario not found")
    
    scenario.enabled = not scenario.enabled
    db.commit()
    db.refresh(scenario)
    
    return {
        "status": "success",
        "enabled": scenario.enabled,
        "message": f"Scenario '{scenario.scenario_name}' {'enabled' if scenario.enabled else 'disabled'}"
    }
