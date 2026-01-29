from datetime import datetime, timedelta, timezone
from django.db import transaction, connection
from simulation.models import DataUpload, Customer, Transaction, Alert, AlertTransaction
from django.utils import timezone as django_timezone
import uuid
import logging

logger = logging.getLogger(__name__)

class TTLManager:
    """Manages Time-To-Live for uploaded data (Django Version)"""
    
    DEFAULT_TTL_HOURS = 48
    MAX_TTL_HOURS = 168  # 7 days
    
    @staticmethod
    def set_expiry(hours: int = DEFAULT_TTL_HOURS) -> datetime:
        return django_timezone.now() + timedelta(hours=hours)

    @staticmethod
    def cleanup_expired(dry_run: bool = False) -> dict:
        """
        Delete expired PII data while preserving anonymized alerts.
        """
        now = django_timezone.now()
        logger.info(f"Starting cleanup (dry_run={dry_run})")
        
        # 1. Find expired uploads
        expired_uploads = DataUpload.objects.filter(
            expires_at__lt=now,
            status='active'
        ).values_list('upload_id', flat=True)
        
        expired_ids = list(str(uid) for uid in expired_uploads)
        
        if not expired_ids:
            return {
                "alerts_anonymized": 0,
                "transactions_deleted": 0,
                "customers_deleted": 0,
                "uploads_expired": 0,
                "message": "No expired data found"
            }

        stats = {
            "alerts_anonymized": 0,
            "transactions_deleted": 0,
            "customers_deleted": 0,
            "uploads_expired": 0
        }

        try:
            with transaction.atomic():
                # STEP 1: Anonymize Alerts
                # We update alerts linked to these uploads via Customer
                # In Django ORM or Raw SQL? Raw SQL is safer for bulk updates involving JSONB manipulation
                with connection.cursor() as cursor:
                    # Anonymize linked alerts
                    cursor.execute("""
                        UPDATE alerts
                        SET 
                            customer_name = 'ANONYMIZED-' || SUBSTR(customer_id, 1, 8),
                            is_anonymized = true,
                            anonymized_at = %s,
                            trigger_details = jsonb_set(
                                COALESCE(trigger_details, '{}'::jsonb),
                                '{pii_removed}',
                                'true'::jsonb
                            )
                        WHERE customer_id IN (
                            SELECT customer_id FROM customers WHERE upload_id = ANY(%s::uuid[])
                        )
                        AND is_anonymized = false
                    """, [now, expired_ids])
                    stats["alerts_anonymized"] = cursor.rowcount

                    # STEP 2: Delete Transactions (Raw PII)
                    cursor.execute("DELETE FROM transactions WHERE upload_id = ANY(%s::uuid[])", [expired_ids])
                    stats["transactions_deleted"] = cursor.rowcount

                    # STEP 3: Delete Customers
                    cursor.execute("DELETE FROM customers WHERE upload_id = ANY(%s::uuid[])", [expired_ids])
                    stats["customers_deleted"] = cursor.rowcount

                    # STEP 4: Mark Uploads as Expired
                    cursor.execute("UPDATE data_uploads SET status = 'expired' WHERE upload_id = ANY(%s::uuid[])", [expired_ids])
                    stats["uploads_expired"] = cursor.rowcount
            
                if dry_run:
                    # Rollback manually by raising exception if verified, 
                    # but atomic() block commits at end. 
                    # To support dry_run efficiently without actual rollback exception hack:
                    # We should probably just COUNT above instead of executing if dry_run.
                    # BUT legacy code did rollback.
                    # For simplicity in this port, we'll raise an error to rollback.
                    raise RuntimeError("DRY RUN ROLLBACK")
                    
        except RuntimeError as e:
            if str(e) == "DRY RUN ROLLBACK":
                logger.info("Dry run rollback successful")
                stats["message"] = "Dry run completed - no data modified"
                return stats
            raise e
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            raise e

        stats["message"] = "Cleanup completed successfully"
        return stats

    @staticmethod
    def get_status_stats():
        """Returns statistics for Admin Dashboard"""
        now = django_timezone.now()
        
        active_uploads = DataUpload.objects.filter(status='active').count()
        expired_pending = DataUpload.objects.filter(status='active', expires_at__lt=now).count()
        
        anonymized = Alert.objects.filter(is_anonymized=True).count()
        active_alerts = Alert.objects.filter(is_anonymized=False).count()
        
        return {
            "active_uploads": active_uploads,
            "expired_uploads_pending_cleanup": expired_pending,
            "anonymized_alerts": anonymized,
            "active_alerts": active_alerts,
            "total_alerts": anonymized + active_alerts,
            "timestamp": now.isoformat()
        }
