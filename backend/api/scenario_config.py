from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import ScenarioConfig
from core.config_models import ScenarioConfigModel
from auth import get_current_user

router = APIRouter(prefix="/api/config", tags=["Scenario Configuration"])

@router.post("/scenarios", response_model=ScenarioConfigModel)
def create_scenario(config: ScenarioConfigModel, db: Session = Depends(get_db)):
    existing = db.query(ScenarioConfig).filter(ScenarioConfig.scenario_id == config.scenario_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Scenario ID already exists")
        
    db_config = ScenarioConfig(
        scenario_id=config.scenario_id,
        scenario_name=config.scenario_name,
        frequency=config.frequency,
        config_json=config.dict(),
        thresholds=config.threshold.dict() if config.threshold else None,
        enabled=True
    )
    db.add(db_config)
    db.commit()
    return config

from pydantic import BaseModel
from typing import Optional

class ScenarioSummary(BaseModel):
    scenario_id: str
    scenario_name: str
    enabled: bool = True
    description: Optional[str] = None

@router.get("/scenarios", response_model=List[ScenarioSummary])
def list_scenarios(
    user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    configs = db.query(ScenarioConfig).all()
    results = []
    for c in configs:
        results.append(ScenarioSummary(
            scenario_id=c.scenario_id,
            scenario_name=c.scenario_name,
            enabled=c.enabled if c.enabled is not None else True,
            description=c.description
        ))
    return results

@router.get("/scenarios/{scenario_id}", response_model=ScenarioConfigModel)
def get_scenario(
    scenario_id: str,
    user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    c = db.query(ScenarioConfig).filter(ScenarioConfig.scenario_id == scenario_id).first()
    if not c or not c.config_json:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return ScenarioConfigModel(**c.config_json)

@router.put("/scenarios/{scenario_id}", response_model=ScenarioConfigModel)
def update_scenario(
    scenario_id: str,
    config: ScenarioConfigModel,
    user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    c = db.query(ScenarioConfig).filter(ScenarioConfig.scenario_id == scenario_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Scenario not found")
        
    c.scenario_name = config.scenario_name
    c.frequency = config.frequency
    c.config_json = config.dict()
    c.thresholds = config.threshold.dict() if config.threshold else None
    c.field_mappings = config.field_mappings  # Persist field mappings
    
    db.commit()
    return config

@router.delete("/scenarios/{scenario_id}")
def delete_scenario(scenario_id: str, db: Session = Depends(get_db)):
    c = db.query(ScenarioConfig).filter(ScenarioConfig.scenario_id == scenario_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Scenario not found")
    


