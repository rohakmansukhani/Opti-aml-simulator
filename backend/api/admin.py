"""
Admin API endpoints for manual operations

Provides endpoints for:
- Manual TTL cleanup trigger
- System health checks
- Administrative operations
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_service_engine
from core.ttl_manager import TTLManager
from auth import get_current_user
from typing import Dict, Any

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.post("/cleanup-ttl")
async def manual_cleanup(
    dry_run: bool = True,  # Default to dry-run for safety
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Manual TTL cleanup trigger.
    
    Allows administrators to manually trigger the TTL cleanup process
    instead of waiting for the scheduled Celery task.
    
    Args:
        dry_run: If True, simulates cleanup without making changes (default: True)
        current_user: Authenticated user (from JWT token)
        
    Returns:
        Cleanup results including counts of anonymized/deleted records
        
    Raises:
        HTTPException: If cleanup fails
        
    Example:
        # Dry run (safe)
        POST /api/admin/cleanup-ttl?dry_run=true
        
        # Actual cleanup (use with caution)
        POST /api/admin/cleanup-ttl?dry_run=false
    """
    
    # Optional: Add admin role check
    # if current_user.get("role") != "admin":
    #     raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_service_engine()()
    
    try:
        result = TTLManager.cleanup_expired(db, dry_run=dry_run)
        
        return {
            "status": "success",
            "dry_run": dry_run,
            "result": result,
            "message": "Dry run completed - no data modified" if dry_run else "Cleanup completed successfully"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Cleanup failed: {str(e)}"
        )
        
    finally:
        db.close()


@router.get("/ttl-status")
async def get_ttl_status(
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get current TTL status and statistics.
    
    Returns information about:
    - Active uploads and their expiry times
    - Anonymized alert counts
    - Expired data counts
    
    Returns:
        TTL status statistics
    """
    from sqlalchemy import text
    from datetime import datetime, timezone
    
    db = get_service_engine()()
    
    try:
        now = datetime.now(timezone.utc)
        
        # Count active uploads
        active_uploads = db.execute(
            text("SELECT COUNT(*) FROM data_uploads WHERE status = 'active'")
        ).scalar()
        
        # Count expired uploads
        expired_uploads = db.execute(
            text("SELECT COUNT(*) FROM data_uploads WHERE expires_at < :now AND status = 'active'"),
            {"now": now}
        ).scalar()
        
        # Count anonymized alerts
        anonymized_alerts = db.execute(
            text("SELECT COUNT(*) FROM alerts WHERE is_anonymized = true")
        ).scalar()
        
        # Count active alerts
        active_alerts = db.execute(
            text("SELECT COUNT(*) FROM alerts WHERE is_anonymized = false")
        ).scalar()
        
        return {
            "status": "success",
            "timestamp": now.isoformat(),
            "statistics": {
                "active_uploads": active_uploads,
                "expired_uploads_pending_cleanup": expired_uploads,
                "anonymized_alerts": anonymized_alerts,
                "active_alerts": active_alerts,
                "total_alerts": anonymized_alerts + active_alerts
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get TTL status: {str(e)}"
        )
        
    finally:
        db.close()
