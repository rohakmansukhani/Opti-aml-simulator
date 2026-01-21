"""
TTL Manager - Handles automatic data expiration and cleanup
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
import uuid
import json
import structlog

logger = structlog.get_logger("ttl_manager")


class TTLManager:
    """Manages Time-To-Live for uploaded data"""
    
    DEFAULT_TTL_HOURS = 48
    MAX_TTL_HOURS = 168  # 7 days
    
    @staticmethod
    def set_expiry(hours: int = DEFAULT_TTL_HOURS) -> datetime:
        """
        Calculate expiry timestamp (timezone-aware).
        
        Args:
            hours: Number of hours until expiration
            
        Returns:
            timezone-aware datetime object representing expiry time
        """
        return datetime.now(timezone.utc) + timedelta(hours=hours)
    
    @staticmethod
    def create_upload_record(
        db: Session,
        user_id: str,  # UUID as string from JWT
        filename: str,
        txn_count: int,
        cust_count: int,
        schema_snapshot: dict,
        ttl_hours: int = DEFAULT_TTL_HOURS
    ) -> uuid.UUID:
        """
        Create a new upload metadata record.
        
        Returns:
            upload_id (UUID object)
        """
        upload_id = uuid.uuid4()  # Native UUID object
        expires_at = TTLManager.set_expiry(ttl_hours)
        
        # Serialize schema to JSON string
        schema_json = json.dumps(schema_snapshot)
        
        # Insert into data_uploads table
        query = text("""
            INSERT INTO data_uploads 
            (upload_id, user_id, filename, record_count_transactions, 
             record_count_customers, schema_snapshot, expires_at, status)
            VALUES 
            (:upload_id, :user_id, :filename, :txn_count, 
             :cust_count, CAST(:schema AS jsonb), :expires_at, 'active')
        """)
        
        try:
            db.execute(query, {
                "upload_id": upload_id,
                "user_id": user_id,  # Pass as string, cast to UUID in SQL
                "filename": filename,
                "txn_count": txn_count,
                "cust_count": cust_count,
                "schema": schema_json,
                "expires_at": expires_at
            })
            logger.info("upload_record_created", upload_id=str(upload_id), user_id=user_id)
        except Exception as e:
            logger.error("upload_record_creation_failed", error=str(e), upload_id=str(upload_id))
            raise
        
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
        # Atomic Update to prevent race conditions
        # We update data_uploads first and get the new expiry, then sync other tables
        
        try:
            # Postgres: Update expires_at by adding interval
            update_query = text("""
                UPDATE data_uploads 
                SET expires_at = expires_at + (:hours * interval '1 hour')
                WHERE upload_id = :id
                RETURNING expires_at
            """)
            
            result = db.execute(update_query, {"hours": additional_hours, "id": upload_id}).fetchone()
            
            if not result:
                logger.warning("extend_ttl_failed_not_found", upload_id=upload_id)
                return False
                
            new_expiry = result[0]
            
            # Cap at Max TTL (if new_expiry exceeds limit, force update it back)
            now = datetime.now(timezone.utc)
            max_allowed = now + timedelta(hours=TTLManager.MAX_TTL_HOURS)
            
            if new_expiry.tzinfo is None:
                new_expiry = new_expiry.replace(tzinfo=timezone.utc)
                
            if new_expiry > max_allowed:
                new_expiry = max_allowed
                # Force update to cap
                db.execute(
                    text("UPDATE data_uploads SET expires_at = :cap WHERE upload_id = :id"),
                    {"cap": new_expiry, "id": upload_id}
                )
            
            # Sync child tables
            db.execute(
                text("""
                    UPDATE transactions SET expires_at = :new_expiry WHERE upload_id = :id;
                    UPDATE customers SET expires_at = :new_expiry WHERE upload_id = :id;
                """),
                {"new_expiry": new_expiry, "id": upload_id}
            )
            
            db.commit()
            logger.info("ttl_extended", upload_id=upload_id, new_expiry=new_expiry.isoformat())
            return True
            
        except Exception as e:
            db.rollback()
            logger.error("ttl_extension_error", error=str(e))
            raise e
    
    @staticmethod
    def cleanup_expired(db: Session, dry_run: bool = False) -> dict:
        """
        Delete expired PII data while preserving anonymized alerts.
        
        Critical Flow:
        1. Anonymize alerts BEFORE deleting customers (preserve customer_name)
        2. Delete transactions (raw PII)
        3. Delete customers (FK cascade sets alert.customer_id = NULL)
        4. Mark data_uploads as expired
        
        Args:
            db: Database session
            dry_run: If True, rollback instead of commit (for testing)
        
        Returns:
            dict with cleanup statistics including anonymized alert count
        """
        now = datetime.now(timezone.utc)
        
        logger.info("cleanup_started", timestamp=now.isoformat(), dry_run=dry_run)
        
        # Get expired upload IDs
        expired_uploads = db.execute(
            text("SELECT upload_id FROM data_uploads WHERE expires_at < :now AND status = 'active'"),
            {"now": now}
        ).fetchall()
        
        expired_ids = [str(row[0]) for row in expired_uploads]
        
        if not expired_ids:
            logger.info("cleanup_no_expired_data")
            return {
                "alerts_anonymized": 0,
                "transactions_deleted": 0,
                "customers_deleted": 0,
                "uploads_expired": 0,
                "timestamp": now.isoformat(),
                "dry_run": dry_run
            }
        
        # STEP 1: Anonymize alerts BEFORE deleting customers
        # This preserves customer_name while removing PII linkage
        anonymize_result = db.execute(
            text("""
                UPDATE alerts
                SET 
                    customer_name = 'ANONYMIZED-' || SUBSTRING(customer_id, 1, 8),
                    is_anonymized = true,
                    anonymized_at = :now,
                    trigger_details = jsonb_set(
                        COALESCE(trigger_details, '{}'::jsonb),
                        '{pii_removed}',
                        'true'::jsonb
                    )
                WHERE customer_id IN (
                    SELECT customer_id FROM customers WHERE upload_id = ANY(:ids::uuid[])
                )
                AND is_anonymized = false
            """),
            {"now": now, "ids": expired_ids}
        )
        alerts_anonymized = anonymize_result.rowcount
        
        # STEP 2: Delete transactions (raw PII)
        txn_result = db.execute(
            text("DELETE FROM transactions WHERE upload_id = ANY(:ids::uuid[])"),
            {"ids": expired_ids}
        )
        transactions_deleted = txn_result.rowcount
        
        # STEP 3: Delete customers (FK cascade sets alert.customer_id = NULL)
        cust_result = db.execute(
            text("DELETE FROM customers WHERE upload_id = ANY(:ids::uuid[])"),
            {"ids": expired_ids}
        )
        customers_deleted = cust_result.rowcount
        
        # STEP 4: Mark uploads as expired
        upload_result = db.execute(
            text("UPDATE data_uploads SET status = 'expired' WHERE upload_id = ANY(:ids::uuid[])"),
            {"ids": expired_ids}
        )
        uploads_expired = upload_result.rowcount
        
        result = {
            "alerts_anonymized": alerts_anonymized,
            "transactions_deleted": transactions_deleted,
            "customers_deleted": customers_deleted,
            "uploads_expired": uploads_expired,
            "upload_ids_processed": expired_ids,
            "timestamp": now.isoformat(),
            "dry_run": dry_run
        }
        
        if dry_run:
            db.rollback()
            logger.info("cleanup_dry_run_completed", **result)
        else:
            db.commit()
            logger.info("cleanup_completed", **result)
        
        return result

