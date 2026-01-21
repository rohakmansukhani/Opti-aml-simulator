from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text, func, and_, or_, Numeric, String
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
    total_records = db.query(Transaction).filter(Transaction.upload_id == upload_id).count()
    
    # Debug Logging
    print(f"[VALIDATION] User: {user_id}, Upload: {upload_id}")
    print(f"[VALIDATION] Total records: {total_records}")
    print(f"[VALIDATION] Filters received: {filters}")
    
    # 2. Build Query for Filters
    # We primarily filter transactions since they are the core units being analyzed.
    # Note: If filters involve customer fields, this would need a join.
    query = db.query(Transaction).filter(Transaction.upload_id == upload_id)
    
    # 3. Apply Filters
    for idx, f in enumerate(filters):
        field = f.get('field')
        operator = f.get('operator')
        value = f.get('value')
        
        print(f"[FILTER {idx}] Field: {field}, Operator: {operator}, Value: {value}, Type: {type(value)}")
        
        if not field or not operator:
            continue
        
        # Try direct attribute first
        attr = getattr(Transaction, field, None)
        use_jsonb = False
        
        if attr is None:
            # Check if it's a customer field
            if hasattr(Customer, field):
                query = query.join(Customer, Transaction.customer_id == Customer.customer_id)
                attr = getattr(Customer, field)
            else:
                # Field not found as column - must be in raw_data JSONB
                print(f"[FILTER {idx}] Using JSONB field: transactions.raw_data->>'{field}'")
                use_jsonb = True
        
        # Determine if field is numeric (for type casting)
        is_numeric_field = field in [
            'transaction_amount', 'amount', 'balance', 'risk_score', 
            'annual_income', 'transaction_count', 'account_balance'
        ]
        
        # Apply filter based on JSONB or regular column
        if use_jsonb:
            # Use JSONB operator ->> for text extraction
            if operator == '==':
                query = query.filter(Transaction.raw_data[field].as_string() == str(value))
            elif operator == '!=':
                query = query.filter(Transaction.raw_data[field].as_string() != str(value))
            elif operator == '>':
                # Cast JSONB value to numeric for comparison
                query = query.filter(
                    func.cast(Transaction.raw_data[field].as_string(), Numeric) > float(value)
                )
            elif operator == '>=':
                query = query.filter(
                    func.cast(Transaction.raw_data[field].as_string(), Numeric) >= float(value)
                )
            elif operator == '<':
                query = query.filter(
                    func.cast(Transaction.raw_data[field].as_string(), Numeric) < float(value)
                )
            elif operator == '<=':
                query = query.filter(
                    func.cast(Transaction.raw_data[field].as_string(), Numeric) <= float(value)
                )
            elif operator == 'in':
                if isinstance(value, list):
                    query = query.filter(Transaction.raw_data[field].as_string().in_([str(v) for v in value]))
                elif isinstance(value, str):
                    vals = [v.strip() for v in value.split(',') if v.strip()]
                    query = query.filter(Transaction.raw_data[field].as_string().in_(vals))
        else:
            # Regular column access
            if operator == '==':
                query = query.filter(attr == value)
            elif operator == '!=':
                query = query.filter(attr != value)
            elif operator == '>':
                compare_value = float(value) if is_numeric_field else value
                query = query.filter(attr > compare_value)
            elif operator == '>=':
                compare_value = float(value) if is_numeric_field else value
                query = query.filter(attr >= compare_value)
            elif operator == '<':
                compare_value = float(value) if is_numeric_field else value
                query = query.filter(attr < compare_value)
            elif operator == '<=':
                compare_value = float(value) if is_numeric_field else value
                query = query.filter(attr <= compare_value)
            elif operator == 'in':
                if isinstance(value, list):
                    query = query.filter(attr.in_(value))
                elif isinstance(value, str):
                    vals = [v.strip() for v in value.split(',') if v.strip()]
                    query = query.filter(attr.in_(vals))

    print(f"[VALIDATION] Final query: {str(query)}")
    
    try:
        match_count = query.count()
        
        # Calculate distinct customers in the result set
        distinct_customers = query.with_entities(Transaction.customer_id).distinct().count()
        
        # --- ENHANCED STATS ---
        stats = {}
        distributions = {}
        
        if match_count > 0:
            # 1. Numeric Stats (Transaction Amount from JSONB)
            try:
                # Query raw_data->'transaction_amount' and cast to numeric
                num_stats = query.with_entities(
                    func.min(func.cast(Transaction.raw_data['transaction_amount'].as_string(), Numeric)),
                    func.max(func.cast(Transaction.raw_data['transaction_amount'].as_string(), Numeric)),
                    func.avg(func.cast(Transaction.raw_data['transaction_amount'].as_string(), Numeric))
                ).first()
                
                if num_stats and num_stats[0] is not None:
                    stats['transaction_amount'] = {
                        "min": float(num_stats[0]) if num_stats[0] else 0,
                        "max": float(num_stats[1]) if num_stats[1] else 0,
                        "avg": float(num_stats[2]) if num_stats[2] else 0
                    }
            except Exception as e:
                print(f"[STATS] Error calculating transaction_amount stats: {e}")

            # 2. Distributions (Categorical from JSONB)
            try:
                type_dist = query.with_entities(
                    Transaction.raw_data['transaction_type'].as_string(),
                    func.count(Transaction.transaction_id)
                ).group_by(Transaction.raw_data['transaction_type'].as_string()).limit(10).all()
                distributions['transaction_type'] = {k: v for k, v in type_dist if k}
            except Exception as e:
                print(f"[STATS] Error calculating transaction_type distribution: {e}")

            try:
                dc_dist = query.with_entities(
                    Transaction.raw_data['debit_credit_indicator'].as_string(),
                    func.count(Transaction.transaction_id)
                ).group_by(Transaction.raw_data['debit_credit_indicator'].as_string()).all()
                distributions['debit_credit_indicator'] = {k: v for k, v in dc_dist if k}
            except Exception as e:
                print(f"[STATS] Error calculating debit_credit_indicator distribution: {e}")

        return {
            "match_count": match_count,
            "match_count_customers": distinct_customers,
            "total_records": total_records,
            "stats": stats,
            "distributions": distributions,
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
            # Field is in JSONB raw_data
            try:
                # Query distinct values from JSONB field
                query = db.query(
                    Transaction.raw_data[field].as_string()
                ).filter(Transaction.upload_id == upload_id)
                
                if search:
                    query = query.filter(
                        Transaction.raw_data[field].as_string().ilike(f"%{search}%")
                    )
                
                values = [r[0] for r in query.distinct().limit(20).all() if r[0] is not None]
                return {"values": values}
            except Exception as e:
                print(f"[AUTOCOMPLETE] Error fetching values for {field}: {e}")
                return {"values": []}
            
    attr = getattr(model, field)
    query = db.query(attr).filter(model.upload_id == upload_id)
    
    if search:
        query = query.filter(attr.cast(text("TEXT")).ilike(f"%{search}%"))
    
    values = [r[0] for r in query.distinct().limit(20).all() if r[0] is not None]
    return {"values": values}
