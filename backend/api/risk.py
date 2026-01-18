from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from core.risk_engine import RiskEngine
from pydantic import BaseModel
from typing import List, Dict, Any

router = APIRouter(prefix="/api/risk", tags=["Risk Analysis"])

class RiskAnalysisRequest(BaseModel):
    baseline_run_id: str
    refinements: List[Dict[str, Any]] # e.g. [{"type": "event_based", "excluded_events": ["education"]}]

@router.post("/analyze")
async def analyze_risk(request: RiskAnalysisRequest, db: Session = Depends(get_db)):
    """
    Analyze the risk gap of proposed refinements BEFORE running a simulation.
    """
    engine = RiskEngine(db)
    
    try:
        report = engine.analyze_risk_gap(request.refinements, request.baseline_run_id)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
