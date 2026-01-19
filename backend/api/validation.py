from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text, func, and_, or_
from typing import List, Any, Dict
from database import get_db
from models import Transaction, Customer, DataUpload
from auth import get_current_user
from datetime import datetime, timezone
import pandas as pd

router = APIRouter(prefix="/api/validation", tags=["Validation"])

@router.post("/filters")
async def validate_filters(
    filters: List[Dict[str, Any]],
    user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Validates a set of filters against the user's active dataset.
    Returns the match count and total record count.
    """
    user_id = user_data.get("sub")
    
    # 1. Get the latest active upload for this user
    active_upload = db.query(DataUpload).filter(
        DataUpload.user_id == user_id,
        DataUpload.status == 'active',
        DataUpload.expires_at > datetime.now(timezone.utc)
    ).order_by(DataUpload.upload_timestamp.desc()).first()
    
    if not active_upload:
        return {
            "match_count": 0,
            "total_records": 0,
            "status": "no_active_upload"
        }
    
    upload_id = active_upload.upload_id
    
    # 2. Get Real-time Total Count
    # We query the actual table count to ensure it matches the user's perception 
    # and ignores any stale metadata in DataUpload record_count
    total_records = db.query(Transaction).filter(Transaction.upload_id == upload_id).count()
    
    # 3. Build Query for Filters
    # We primarily filter transactions since they are the core units being analyzed.
    # Note: If filters involve customer fields, this would need a join.
    query = db.query(Transaction).filter(Transaction.upload_id == upload_id)
    
    # 3. Apply Filters
    for f in filters:
        field = f.get('field')
        operator = f.get('operator')
        value = f.get('value')
        
        if not field or not operator:
            continue
            
        # Basic mapping of symbols to SQLAlchemy operators
        # In a real enterprise app, we'd use a more robust mapper (like smart_layer.py)
        attr = getattr(Transaction, field, None)
        if attr is None:
            # Check if it's a customer field (simple join check)
            if hasattr(Customer, field):
                query = query.join(Customer, Transaction.customer_id == Customer.customer_id)
                attr = getattr(Customer, field)
            else:
                continue
        
        if operator == '==':
            query = query.filter(attr == value)
        elif operator == '!=':
            query = query.filter(attr != value)
        elif operator == '>':
            query = query.filter(attr > value)
        elif operator == '<':
            query = query.filter(attr < value)
        elif operator == 'in':
            if isinstance(value, list):
                query = query.filter(attr.in_(value))
            elif isinstance(value, str):
                vals = [v.strip() for v in value.split(',') if v.strip()]
                query = query.filter(attr.in_(vals))
    
    try:
        match_count = query.count()
        
        # Calculate distinct customers in the result set
        # This helps clarify "20 transactions vs 4 customers" confusion
        distinct_customers = query.with_entities(Transaction.customer_id).distinct().count()
        
        return {
            "match_count": match_count,
            "match_count_customers": distinct_customers,
            "total_records": total_records,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid filter combination: {str(e)}")

@router.get("/values")
async def get_field_values(
    field: str,
    search: str = "",
    user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns unique values for autocomplete."""
    user_id = user_data.get("sub")
    
    active_upload = db.query(DataUpload).filter(
        DataUpload.user_id == user_id,
        DataUpload.status == 'active',
        DataUpload.expires_at > datetime.now(timezone.utc)
    ).order_by(DataUpload.upload_timestamp.desc()).first()
    
    if not active_upload:
        return {"values": []}
        
    upload_id = active_upload.upload_id
    
    # Try Transaction first, then Customer
    model = Transaction
    if not hasattr(Transaction, field):
        if hasattr(Customer, field):
            model = Customer
        else:
            return {"values": []}
            
    attr = getattr(model, field)
    query = db.query(attr).filter(model.upload_id == upload_id)
    
    if search:
        query = query.filter(attr.cast(text("TEXT")).ilike(f"%{search}%"))
    
    values = [r[0] for r in query.distinct().limit(20).all() if r[0] is not None]
    return {"values": values}
