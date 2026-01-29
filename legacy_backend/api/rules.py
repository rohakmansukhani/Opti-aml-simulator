from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import ScenarioConfig
from auth import get_current_user
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import datetime
import uuid


router = APIRouter(prefix="/api/rules", tags=["Rules"])


class ScenarioUpdate(BaseModel):
    scenario_name: Optional[str] = None
    enabled: Optional[bool] = None
    config_json: Optional[Dict[str, Any]] = None
    thresholds: Optional[Dict[str, float]] = None
    refinements: Optional[List[Dict[str, Any]]] = None


class CreateScenarioRequest(BaseModel):
    scenario_id: Optional[str] = None
    scenario_name: str
    priority: str
    is_active: bool
    config_json: Dict[str, Any]  # ✅ This should contain filters, aggregation, threshold
    description: Optional[str] = None
    field_mappings: Optional[Dict[str, str]] = None


@router.post("/scenarios")
async def create_scenario(
    request: CreateScenarioRequest,
    user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Creates a new scenario configuration."""
    try:
        user_id = user_data.get("sub")
        scenario_id = request.scenario_id or str(uuid.uuid4())[:8]
        
        # Check if scenario already exists
        existing = db.query(ScenarioConfig).filter(ScenarioConfig.scenario_id == scenario_id).first()
        if existing:
            raise HTTPException(400, f"Scenario ID '{scenario_id}' already exists")
        
        # Build config_json
        config_json = request.config_json.copy()
        config_json['scenario_id'] = scenario_id
        config_json['scenario_name'] = request.scenario_name
        config_json['description'] = request.description
        
        new_scenario = ScenarioConfig(
            scenario_id=scenario_id,
            user_id=user_id,
            scenario_name=request.scenario_name,
            description=request.description,
            priority=request.priority,
            enabled=request.is_active,
            config_json=config_json,
            field_mappings=request.field_mappings,
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
        
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
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
        raise HTTPException(404, "Scenario not found")
    
    if update.scenario_name is not None:
        scenario.scenario_name = update.scenario_name
    if update.enabled is not None:
        scenario.enabled = update.enabled
    if update.config_json is not None:
        # ✅ Merge with existing config_json
        existing_config = scenario.config_json or {}
        existing_config.update(update.config_json)
        scenario.config_json = existing_config
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
