from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

from database import get_db
from models import Alert, AlertTransaction, Transaction, Customer
from auth import get_current_user

router = APIRouter(prefix="/api/investigation", tags=["Investigation"])

# --- Schemas ---

class AlertWorkflowUpdate(BaseModel):
    assigned_to: Optional[str] = None
    investigation_status: Optional[str] = None # New, In Progress, Closed
    outcome: Optional[str] = None # False Positive, True Positive, Suspicious
    sar_reference: Optional[str] = None
    investigation_notes: Optional[str] = None

class TraceabilityItem(BaseModel):
    transaction_id: str
    contribution_percentage: float
    amount: float
    date: datetime
    beneficiary: Optional[str]
    description: Optional[str]

class AlertDetailResponse(BaseModel):
    alert_id: str
    scenario_name: str
    risk_score: int
    alert_date: datetime
    customer_name: str
    customer_id: str
    status: str
    # Investigation Fields
    assigned_to: Optional[str]
    investigation_status: str
    outcome: Optional[str]
    sar_reference: Optional[str]
    investigation_notes: Optional[str]
    
    # Traceability
    contributing_transactions: List[TraceabilityItem]
    
    # Raw Metadata
    trigger_details: dict

# --- Endpoints ---

@router.get("/alerts/{alert_id}", response_model=AlertDetailResponse)
async def get_alert_details(
    alert_id: str,
    user_payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive details for a specific alert, including:
    - Contributing transactions (Traceability)
    - Investigation status & notes
    - Customer context
    """
    alert = db.query(Alert).options(
        joinedload(Alert.alert_transactions).joinedload(AlertTransaction.transaction),
        joinedload(Alert.customer)
    ).filter(Alert.alert_id == alert_id).first()
    
    if not alert:
        raise HTTPException(404, "Alert not found")
        
    # Build Traceability List
    trace_items = []
    # Optimized Traceability Fetch (Avoids N+1 JSON deserialization)
    from sqlalchemy import text
    
    # Fetch specifics directly via DB to minimize Python overhead
    trace_rows = db.query(
        AlertTransaction.transaction_id,
        AlertTransaction.contribution_percentage,
        Transaction.created_at,
        Transaction.transaction_amount,
        text("transactions.raw_data ->> 'transaction_amount'"),
        text("transactions.raw_data ->> 'beneficiary_name'"),
        text("transactions.raw_data ->> 'transaction_narrative'")
    ).select_from(AlertTransaction)\
     .join(AlertTransaction.transaction)\
     .filter(AlertTransaction.alert_id == alert_id)\
     .all()

    for r in trace_rows:
        # Unpack
        tid, contrib, tdate, amt_col, amt_json, ben_json, narr_json = r
        
        # Logic: Use JSON value if present, else Column
        final_amount = float(amt_json) if amt_json else (float(amt_col) if amt_col else 0.0)
        
        trace_items.append({
            "transaction_id": tid,
            "contribution_percentage": float(contrib) if contrib else 0,
            "amount": final_amount,
            "date": tdate,
            "beneficiary": ben_json or "Unknown",
            "description": narr_json or "N/A"
        })
    
    # sort by contribution desc
    trace_items.sort(key=lambda x: x['contribution_percentage'], reverse=True)

    return {
        "alert_id": alert.alert_id,
        "scenario_name": alert.scenario_name,
        "risk_score": alert.risk_score,
        "alert_date": alert.alert_date,
        "customer_name": alert.customer_name or "Unknown",
        "customer_id": alert.customer_id,
        "status": alert.alert_status,
        
        "assigned_to": alert.assigned_to,
        "investigation_status": alert.investigation_status or "New",
        "outcome": alert.outcome,
        "sar_reference": alert.sar_reference,
        "investigation_notes": alert.investigation_notes,
        
        "contributing_transactions": trace_items,
        "trigger_details": alert.trigger_details or {}
    }

@router.post("/alerts/{alert_id}/workflow")
async def update_investigation_workflow(
    alert_id: str,
    update: AlertWorkflowUpdate,
    user_payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update the investigation state of an alert.
    """
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Alert not found")
        
    # Apply updates
    if update.assigned_to is not None:
        alert.assigned_to = update.assigned_to
    
    if update.investigation_status:
        alert.investigation_status = update.investigation_status
        # Sync to main status?
        if update.investigation_status == 'Closed':
            alert.alert_status = 'CLS'
        elif update.investigation_status == 'In Progress':
            alert.alert_status = 'WIP'
            
    if update.outcome:
        alert.outcome = update.outcome
        
    if update.sar_reference:
        alert.sar_reference = update.sar_reference
        
    if update.investigation_notes:
        # Append or Replace? Let's Replace for atomic updates, or append with timestamp
        # Ideally, separate Note model. For now, simple text field.
        # Let's append if existing
        if alert.investigation_notes:
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
            alert.investigation_notes += f"\n[{timestamp}] {update.investigation_notes}"
        else:
            alert.investigation_notes = update.investigation_notes
            
    # Touch updated_at is automatic via onupdate
    
    db.commit()
    db.refresh(alert)
    
    return {"status": "success", "message": "Workflow updated", "current_status": alert.investigation_status}
