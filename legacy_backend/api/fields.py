from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Optional, Any
import json

from database import get_db
from auth import get_current_user
from models import FieldMetadata, FieldValueIndex, DataUpload
from core.redis_client import get_redis_client

router = APIRouter(prefix="/api/fields", tags=["Fields & Intelligence"])

@router.get("/discover")
async def discover_fields(
    table: str = Query(..., regex="^(transactions|customers)$"),
    user_payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all discoverable fields and their metadata for the user's active data.
    """
    user_id = user_payload.get("sub")
    
    # 1. Get latest active upload
    upload = db.query(DataUpload).filter(
        DataUpload.user_id == user_id,
        DataUpload.status == 'active'
    ).order_by(DataUpload.upload_timestamp.desc()).first()
    
    if not upload:
        return {"fields": []}
        
    # 2. Get Metadata
    metadata_records = db.query(FieldMetadata).filter(
        FieldMetadata.upload_id == upload.upload_id,
        FieldMetadata.table_name == table
    ).all()
    
    results = []
    for m in metadata_records:
        results.append({
            "name": m.field_name,
            "type": m.field_type,
            "label": m.field_name.replace('_', ' ').title(),
            "stats": {
                "total": m.total_records,
                "distinct": m.distinct_count,
                "nulls": m.null_count
            },
            "operators": m.recommended_operators,
            "sample_values": m.sample_values
        })
        
    return {"fields": results}

@router.get("/{field_name}/values")
async def get_field_values(
    field_name: str,
    table: str = Query(..., regex="^(transactions|customers)$"),
    search: str = "",
    user_payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get autocomplete values for a field.
    Uses Redis caching (1 hour TTL).
    """
    user_id = user_payload.get("sub")
    redis_client = get_redis_client()
    
    # 1. Get Upload ID
    upload = db.query(DataUpload).filter(
        DataUpload.user_id == user_id,
        DataUpload.status == 'active'
    ).order_by(DataUpload.upload_timestamp.desc()).first()
    
    if not upload:
        return {"values": []}
    
    # 2. Redis Cache Key
    # Key format: fields:{upload_id}:{table}:{field_name}:values
    cache_key = f"fields:{upload.upload_id}:{table}:{field_name}:values"
    
    # 3. Check Cache (if no search term, or handle search filtering in memory if list small?)
    # For now, we cache the FULL list of values for the field, then filter in application
    # This avoids caching every search permutation.
    
    cached_data = None
    try:
        cached_data = redis_client.get(cache_key)
    except Exception as e:
        print(f"Redis error: {e}")
        
    if cached_data:
        all_values = json.loads(cached_data)
    else:
        # 4. Cache Miss - Query DB
        # Query FieldValueIndex table
        index_records = db.query(FieldValueIndex).filter(
            FieldValueIndex.upload_id == upload.upload_id,
            FieldValueIndex.table_name == table,
            FieldValueIndex.field_name == field_name
        ).order_by(FieldValueIndex.value_count.desc()).limit(100).all() # Cap at 100 for autocomplete
        
        all_values = [
            {
                "value": r.field_value, 
                "count": r.value_count, 
                "percentage": float(r.value_percentage) if r.value_percentage else 0
            } 
            for r in index_records
        ]
        
        # 5. Set Cache (TTL 1 hour = 3600 seconds)
        try:
            if all_values:
                redis_client.setex(cache_key, 3600, json.dumps(all_values))
        except Exception as e:
            print(f"Redis set error: {e}")

    # 6. Apply Search Filter
    if search:
        search_lower = search.lower()
        filtered = [v for v in all_values if search_lower in str(v['value']).lower()]
        return {"values": filtered[:20]} # Return top 20 matches
        
    return {"values": all_values[:20]} # Return top 20 by default

@router.get("/{field_name}/operators")
async def get_field_operators(
    field_name: str,
    table: str = Query(..., regex="^(transactions|customers)$"),
    user_payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get compatible operators for a field based on its type.
    """
    user_id = user_payload.get("sub")
    
    upload = db.query(DataUpload).filter(
        DataUpload.user_id == user_id,
        DataUpload.status == 'active'
    ).order_by(DataUpload.upload_timestamp.desc()).first()
    
    if not upload:
        return {"operators": ["equals"]} # Fallback
        
    metadata = db.query(FieldMetadata).filter(
        FieldMetadata.upload_id == upload.upload_id,
        FieldMetadata.table_name == table,
        FieldMetadata.field_name == field_name
    ).first()
    
    if metadata and metadata.recommended_operators:
        return {"operators": metadata.recommended_operators, "type": metadata.field_type}
        
    return {"operators": ["equals", "not_equals", "in"]} # Default fallback
