from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Dict, Any, List
from database import get_db
from models import SimulationRun
from services.comparison_service import ComparisonEngine
from auth import get_current_user
import structlog

logger = structlog.get_logger("comparison_api")

router = APIRouter(prefix="/api/comparison", tags=["Comparison"])


class ComparisonRequest(BaseModel):
    """Request model for run comparison (accepts Run IDs or Scenario IDs)"""
    baseline_run_id: str
    refined_run_id: str


def resolve_to_run_id(db: Session, user_id: str, identifier: str) -> str:
    """
    Resolves an identifier to an actual SimulationRun ID.
    Supports: 
    1. Direct Run ID (UUID)
    2. Scenario ID (Resolves to latest completed run containing this scenario)
    """
    # 1. Try as direct Run ID
    run = db.query(SimulationRun).filter(
        SimulationRun.run_id == identifier,
        SimulationRun.user_id == user_id
    ).first()
    if run:
        return run.run_id
    
    # 2. Try as Scenario ID (latest completed run for this user)
    latest_run = db.query(SimulationRun).filter(
        SimulationRun.user_id == user_id,
        SimulationRun.status == 'completed'
    ).order_by(SimulationRun.created_at.desc()).all()
    
    for r in latest_run:
        if r.scenarios_run and identifier in r.scenarios_run:
            return r.run_id
            
    raise HTTPException(
        status_code=404, 
        detail=f"No completed simulation run found for rule: {identifier}"
    )


@router.post("/compare")
async def compare_runs(
    request: ComparisonRequest,
    user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Compare two simulation runs or rules. Resolves IDs automatically.
    """
    user_id = user_data.get("sub")
    
    try:
        baseline_run_id = resolve_to_run_id(db, user_id, request.baseline_run_id)
        refined_run_id = resolve_to_run_id(db, user_id, request.refined_run_id)
        
        logger.info(
            "comparison_requested",
            raw_baseline=request.baseline_run_id,
            resolved_baseline=baseline_run_id,
            raw_refined=request.refined_run_id,
            resolved_refined=refined_run_id
        )
        
        engine = ComparisonEngine(db)
        return engine.compare_runs(baseline_run_id, refined_run_id)
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error("comparison_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")


@router.get("/runs/{run_id}/metadata")
async def get_run_metadata(
    run_id: str,
    user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get metadata for a simulation run.
    """
    user_id = user_data.get("sub")
    
    # Verify ownership
    run = db.query(SimulationRun).filter(
        SimulationRun.run_id == run_id,
        SimulationRun.user_id == user_id
    ).first()
    
    if not run:
         raise HTTPException(
                status_code=404,
                detail=f"Run {run_id} not found or access denied"
            )

    try:
        engine = ComparisonEngine(db)
        metadata = engine.get_run_metadata(run_id)
        
        if not metadata:
            raise HTTPException(
                status_code=404,
                detail=f"Run {run_id} metadata not found"
            )
        
        return metadata
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("metadata_fetch_failed", error=str(e), run_id=run_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch metadata: {str(e)}"
        )


@router.get("/diff")
async def compare_runs_legacy(
    baseline_id: str,
    refined_id: str,
    user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Legacy endpoint - use POST /compare instead.
    """
    request = ComparisonRequest(
        baseline_run_id=baseline_id,
        refined_run_id=refined_id
    )
    return await compare_runs(request, user_data, db)
