"""
TTL Manager - Handles automatic data expiration and cleanup
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
import uuid


class TTLManager:
    """Manages Time-To-Live for uploaded data"""
    
    DEFAULT_TTL_HOURS = 48
    MAX_TTL_HOURS = 168  # 7 days
    
    @staticmethod
    def set_expiry(hours: int = DEFAULT_TTL_HOURS) -> datetime:
        """
        Calculate expiry timestamp.
        
        Args:
            hours: Number of hours until expiration
            
        Returns:
            datetime object representing expiry time
        """
        return datetime.utcnow() + timedelta(hours=hours)
    
    @staticmethod
    def create_upload_record(
        db: Session,
        user_id: str,
        filename: str,
        txn_count: int,
        cust_count: int,
        schema_snapshot: dict,
        ttl_hours: int = DEFAULT_TTL_HOURS
    ) -> str:
        """
        Create a new upload metadata record.
        
        Returns:
            upload_id (str)
        """
        import json
        from models import Base
        
        upload_id = str(uuid.uuid4())
        expires_at = TTLManager.set_expiry(ttl_hours)
        
        # Insert into data_uploads table
        query = text("""
            INSERT INTO data_uploads 
            (upload_id, user_id, filename, record_count_transactions, 
             record_count_customers, schema_snapshot, expires_at, status)
            VALUES 
            (:upload_id, :user_id, :filename, :txn_count, 
             :cust_count, CAST(:schema AS jsonb), :expires_at, 'active')
        """)
        
        db.execute(query, {
            "upload_id": upload_id,
            "user_id": user_id,
            "filename": filename,
            "txn_count": txn_count,
            "cust_count": cust_count,
            "schema": json.dumps(schema_snapshot),  # Proper JSON serialization
            "expires_at": expires_at
        })
        # REMOVED: db.commit() - Let the calling function handle the transaction
        
        return upload_id
    
    @staticmethod
    def extend_ttl(db: Session, upload_id: str, additional_hours: int = 24) -> bool:
        """
        Extend TTL for an existing upload.
        
        Args:
            db: Database session
            upload_id: Upload to extend
            additional_hours: Hours to add
            
        Returns:
            bool indicating success
        """
        # Get current expiry
        result = db.execute(
            text("SELECT expires_at FROM data_uploads WHERE upload_id = :id"),
            {"id": upload_id}
        ).fetchone()
        
        if not result:
            return False
        
        current_expiry = result[0]
        new_expiry = current_expiry + timedelta(hours=additional_hours)
        
        # Cap at MAX_TTL_HOURS from now
        # Ensure max_allowed is timezone-aware if new_expiry is
        from datetime import timezone
        now = datetime.now(timezone.utc)
        max_allowed = now + timedelta(hours=TTLManager.MAX_TTL_HOURS)
        
        # Make new_expiry aware if it's naive, or max_allowed naive if needed
        if new_expiry.tzinfo is None:
            new_expiry = new_expiry.replace(tzinfo=timezone.utc)
            
        if new_expiry > max_allowed:
            new_expiry = max_allowed
        
        # Update expiry
        db.execute(
            text("""
                UPDATE data_uploads SET expires_at = :new_expiry WHERE upload_id = :id;
                UPDATE transactions SET expires_at = :new_expiry WHERE upload_id = :id;
                UPDATE customers SET expires_at = :new_expiry WHERE upload_id = :id;
            """),
            {"new_expiry": new_expiry, "id": upload_id}
        )
        db.commit()
        
        return True
    
    @staticmethod
    def cleanup_expired(db: Session) -> dict:
        """
        Delete expired data (called by cron job).
        
        Deletes in correct order to avoid foreign key violations:
        1. Alerts (references customers)
        2. Transactions
        3. Customers
        
        Returns:
            dict with cleanup statistics
        """
        now = datetime.utcnow()
        
        # Count before deletion
        alert_count = db.execute(
            text("""
                SELECT COUNT(*) FROM alerts a
                JOIN data_uploads du ON a.run_id IN (
                    SELECT run_id FROM simulation_run WHERE upload_id = du.upload_id
                )
                WHERE du.expires_at < :now
            """),
            {"now": now}
        ).scalar() or 0
        
        txn_count = db.execute(
            text("SELECT COUNT(*) FROM transactions WHERE expires_at < :now"),
            {"now": now}
        ).scalar() or 0
        
        cust_count = db.execute(
            text("SELECT COUNT(*) FROM customers WHERE expires_at < :now"),
            {"now": now}
        ).scalar() or 0
        
        # Delete in correct order to avoid foreign key violations
        
        # 1. Delete alerts first (they reference customers)
        db.execute(text("""
            DELETE FROM alerts
            WHERE run_id IN (
                SELECT sr.run_id 
                FROM simulation_run sr
                JOIN data_uploads du ON sr.upload_id = du.upload_id
                WHERE du.expires_at < :now
            )
        """), {"now": now})
        
        # 2. Delete transactions
        db.execute(
            text("DELETE FROM transactions WHERE expires_at < :now"),
            {"now": now}
        )
        
        # 3. Delete customers (no longer referenced by alerts)
        db.execute(
            text("DELETE FROM customers WHERE expires_at < :now"),
            {"now": now}
        )
        
        # 4. Update upload status
        db.execute(
            text("""
                UPDATE data_uploads 
                SET status = 'expired' 
                WHERE expires_at < :now AND status = 'active'
            """),
            {"now": now}
        )
        
        db.commit()
        
        return {
            "alerts_deleted": alert_count,
            "transactions_deleted": txn_count,
            "customers_deleted": cust_count,
            "timestamp": datetime.utcnow().isoformat()
        }

