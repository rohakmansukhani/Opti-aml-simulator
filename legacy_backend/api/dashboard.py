from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import Transaction, Alert, SimulationRun, ScenarioConfig
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

class SimulationSummary(BaseModel):
    run_id: str
    run_type: str
    created_at: datetime
    total_alerts: int
    status: str

class DashboardStats(BaseModel):
    risk_score: str
    active_high_risk_alerts: int
    transactions_scanned: int
    system_coverage: str
    total_simulations: int
    recent_simulations: List[SimulationSummary]

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    user_payload: dict = Depends(get_current_user), # Secure endpoint
    db: Session = Depends(get_db)
):
    user_id = user_payload.get("sub")

    # 1. Transaction Count (Scoped to User)
    from models import DataUpload
    tx_count = db.query(Transaction).join(DataUpload).filter(DataUpload.user_id == user_id).count()
    
    # 2. High Risk Alerts (Scoped to User)
    high_risk_count = db.query(Alert).join(SimulationRun).filter(
        SimulationRun.user_id == user_id,
        Alert.risk_classification == 'HIGH', 
        Alert.alert_status == 'OPN'
    ).count()
    
    # 3. Recent Simulations (Scoped to User)
    total_simulations = db.query(SimulationRun).filter(SimulationRun.user_id == user_id).count()
    
    recent_runs_db = db.query(SimulationRun)\
        .filter(SimulationRun.user_id == user_id)\
        .order_by(SimulationRun.created_at.desc())\
        .limit(5)\
        .all()
        
    recent_runs = [
        SimulationSummary(
            run_id=run.run_id,
            run_type=run.run_type,
            created_at=run.created_at,
            total_alerts=run.total_alerts or 0,
            status=run.status
        ) for run in recent_runs_db
    ]
    
    # 4. Risk Score
    risk_level = "Low"
    if high_risk_count > 50:
        risk_level = "High"
    elif high_risk_count > 10:
        risk_level = "Medium"
        
    # 5. System Coverage (Scoped to User's Scenarios)
    total_scenarios = db.query(ScenarioConfig).filter(ScenarioConfig.user_id == user_id).count()
    enabled_scenarios = db.query(ScenarioConfig).filter(
        ScenarioConfig.user_id == user_id, 
        ScenarioConfig.enabled == True
    ).count()
    
    coverage = "0%"
    if total_scenarios > 0:
        pct = (enabled_scenarios / total_scenarios) * 100
        coverage = f"{pct:.1f}%"
    
    if total_scenarios == 0:
        coverage = "100%" 

    return DashboardStats(
        risk_score=risk_level,
        active_high_risk_alerts=high_risk_count,
        transactions_scanned=tx_count,
        system_coverage=coverage,
        total_simulations=total_simulations,
        recent_simulations=recent_runs
    )
