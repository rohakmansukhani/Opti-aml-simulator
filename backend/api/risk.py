from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import SimulationRun
from core.risk_engine import RiskEngine
from auth import get_current_user
from pydantic import BaseModel
from typing import List, Dict, Any

router = APIRouter(prefix="/api/risk", tags=["Risk Analysis"])

class RiskAnalysisRequest(BaseModel):
    baseline_run_id: str
    refinements: List[Dict[str, Any]] # e.g. [{"type": "event_based", "excluded_events": ["education"]}]

@router.post("/analyze")
async def analyze_risk(
    request: RiskAnalysisRequest, 
    user_payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyze the risk gap of proposed refinements BEFORE running a simulation.
    """
    user_id = user_payload.get("sub")
    
    # 1. Verify Baseline Run Ownership
    run = db.query(SimulationRun).filter(
        SimulationRun.run_id == request.baseline_run_id,
        SimulationRun.user_id == user_id
    ).first()
    
    if not run:
        raise HTTPException(404, "Baseline run not found or access denied")

    engine = RiskEngine(db)
    
    try:
        # 2. Pass user_id to engine for scoped analysis
        report = engine.analyze_risk_gap(request.refinements, request.baseline_run_id, user_id=user_id)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
