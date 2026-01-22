from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, Numeric, String
from typing import List, Any, Union
from database import get_db
from models import Transaction, Customer, DataUpload
from auth import get_current_user
from pydantic import BaseModel, validator


router = APIRouter(prefix="/api/validation", tags=["Validation"])


class FilterItem(BaseModel):
    field: str
    operator: str
    value: Union[str, int, float, List[str], List[int], List[float], None]
    
    @validator('value', pre=True)
    def normalize_value(cls, v, values):
        """Normalize value based on operator."""
        operator = values.get('operator')
        
        # For 'in' and 'not_in', ensure value is a list
        if operator in ['in', 'not_in']:
            if isinstance(v, str):
                return [v]
            elif isinstance(v, list):
                return v
            else:
                return [str(v)] if v is not None else []
        
        # For other operators, ensure single value
        if isinstance(v, list):
            return v[0] if v else None
        
        return v


class FilterValidationRequest(BaseModel):
    filters: List[FilterItem]


@router.post("/filters")
async def validate_filters(
    request: FilterValidationRequest,
    user_payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = user_payload.get("sub")
    
    # Get user's active upload
    upload = db.query(DataUpload).filter(
        DataUpload.user_id == user_id,
        DataUpload.status == 'active'
    ).order_by(DataUpload.upload_timestamp.desc()).first()
    
    if not upload:
        raise HTTPException(404, "No active data upload found")
    
    print(f"[VALIDATION] User: {user_id}, Upload: {upload.upload_id}")
    
    # Start with transactions query
    query = db.query(Transaction).filter(Transaction.upload_id == upload.upload_id)
    
    # DETECT CUSTOMER FIELDS AND JOIN
    customer_fields = {'occupation', 'customer_type', 'annual_income', 'account_type', 'risk_score', 'customer_name'}
    needs_customer_join = False
    
    for filter_item in request.filters:
        if filter_item.field in customer_fields:
            needs_customer_join = True
            break
    
    # JOIN customers table if needed
    if needs_customer_join:
        query = query.join(Customer, Transaction.customer_id == Customer.customer_id)
    
    total_before_filter = query.count()
    print(f"[VALIDATION] Total records: {total_before_filter}")
    print(f"[VALIDATION] Filters: {[f.dict() for f in request.filters]}")
    
    # Apply filters
    for idx, filter_item in enumerate(request.filters):
        field = filter_item.field
        operator = filter_item.operator
        value = filter_item.value
        
        # ✅ USE ->> FOR TEXT EXTRACTION (not ->)
        if field in customer_fields:
            # PostgreSQL: raw_data ->> 'field' returns TEXT (no quotes)
            jsonb_field = func.cast(
                func.jsonb_extract_path_text(Customer.raw_data, field),
                String
            )
            print(f"[FILTER {idx}] Customer field: {field} = {value}")
        else:
            jsonb_field = func.cast(
                func.jsonb_extract_path_text(Transaction.raw_data, field),
                String
            )
            print(f"[FILTER {idx}] Transaction field: {field} = {value}")
        
        # Normalize operator
        operator = operator.lower().replace(' ', '_')
        if operator in ['==', 'equals']: operator = '=='
        elif operator in ['!=', 'not_equals']: operator = '!='
        elif operator in ['in', 'in_list']: operator = 'in'
        elif operator in ['not_in', 'not_in_list']: operator = 'not_in'
        elif operator in ['>', 'greater_than']: operator = '>'
        elif operator in ['<', 'less_than']: operator = '<'
        elif operator in ['>=', 'greater_then_equal']: operator = '>='
        elif operator in ['<=', 'less_than_equal']: operator = '<='

        # Apply operator
        if operator == "==":
            query = query.filter(jsonb_field == str(value))
        elif operator == "!=":
            query = query.filter(jsonb_field != str(value))
        elif operator == "in":
            if isinstance(value, list):
                query = query.filter(jsonb_field.in_([str(v) for v in value]))
            else:
                query = query.filter(jsonb_field == str(value))
        elif operator == "not_in":
            if isinstance(value, list):
                query = query.filter(~jsonb_field.in_([str(v) for v in value]))
            else:
                query = query.filter(jsonb_field != str(value))
        elif operator == ">":
            numeric_field = func.cast(
                func.jsonb_extract_path_text(
                    Customer.raw_data if field in customer_fields else Transaction.raw_data,
                    field
                ),
                Numeric
            )
            query = query.filter(numeric_field > float(value))
        elif operator == "<":
            numeric_field = func.cast(
                func.jsonb_extract_path_text(
                    Customer.raw_data if field in customer_fields else Transaction.raw_data,
                    field
                ),
                Numeric
            )
            query = query.filter(numeric_field < float(value))
        elif operator == ">=":
            numeric_field = func.cast(
                func.jsonb_extract_path_text(
                    Customer.raw_data if field in customer_fields else Transaction.raw_data,
                    field
                ),
                Numeric
            )
            query = query.filter(numeric_field >= float(value))
        elif operator == "<=":
            numeric_field = func.cast(
                func.jsonb_extract_path_text(
                    Customer.raw_data if field in customer_fields else Transaction.raw_data,
                    field
                ),
                Numeric
            )
            query = query.filter(numeric_field <= float(value))
        elif operator == "contains":
            query = query.filter(jsonb_field.ilike(f"%{value}%"))
    
    # ✅ PRINT THE ACTUAL SQL QUERY
    try:
        from sqlalchemy.dialects import postgresql
        compiled_query = query.statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        print(f"[DEBUG] SQL Query:\n{compiled_query}")
    except Exception as e:
        print(f"[DEBUG] Could not compile query: {e}")
    
    # Execute query
    matched_transactions = query.all()
    
    # Count distinct customers
    distinct_customers = len(set(txn.customer_id for txn in matched_transactions if txn.customer_id))
    
    # Get total counts
    total_txns = db.query(Transaction).filter(Transaction.upload_id == upload.upload_id).count()
    total_customers = db.query(Customer).filter(Customer.upload_id == upload.upload_id).count()
    
    print(f"[VALIDATION] Matched: {len(matched_transactions)} txns from {distinct_customers} customers")
    
    return {
        "matched_transactions": len(matched_transactions),
        "matched_customers": distinct_customers,
        "total_transactions": total_txns,
        "total_customers": total_customers,
        "match_percentage": round((len(matched_transactions) / total_txns * 100), 2) if total_txns > 0 else 0
    }
