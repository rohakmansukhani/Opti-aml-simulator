"""
Cleanup Cron Job - Automatically deletes expired data

This script should be run periodically (e.g., every hour) via cron or a task scheduler.
For Supabase, this is configured via pg_cron extension.
"""

import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_default_engine
from sqlalchemy.orm import sessionmaker
from core.ttl_manager import TTLManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_cleanup():
    """Execute cleanup of expired data"""
    logger.info("Starting TTL cleanup job...")
    
    SessionLocal = get_default_engine()
    db = SessionLocal()
    
    try:
        result = TTLManager.cleanup_expired(db)
        logger.info(f"Cleanup completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_cleanup()
