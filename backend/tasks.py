"""
Celery Tasks - Background job processing for long-running simulations

Purpose:
    Run simulations asynchronously to avoid blocking HTTP requests
    
Why Celery?
    - Simulations take 10-45 seconds
    - HTTP requests would timeout
    - User gets instant response, simulation runs in background
    
Flow:
    1. User clicks "Run Simulation"
    2. API creates run record, returns run_id immediately
    3. Celery worker picks up task from Redis queue
    4. Simulation executes in background
    5. User polls /status endpoint for progress
"""

from celery import Celery
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import structlog

# Celery app configuration
app = Celery('sas_simulator')
app.conf.broker_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
app.conf.result_backend = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
app.conf.task_serializer = 'json'
app.conf.result_serializer = 'json'
app.conf.accept_content = ['json']
app.conf.timezone = 'UTC'
app.conf.enable_utc = True

logger = structlog.get_logger("celery_tasks")


# Global engine and sessionmaker for reuse across tasks
_engine = None
_SessionFactory = None

def get_db_session():
    """
    Create database session for Celery tasks.
    Reuses the global engine to prevent connection pool exhaustion.
    """
    global _engine, _SessionFactory
    
    if _engine is None:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is not set")
            
        # Create engine with production-ready settings
        _engine = create_engine(
            database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600
        )
        _SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
        
    return _SessionFactory()


@app.task(bind=True, name='tasks.run_simulation_background')
def run_simulation_background(
    self, 
    run_id: str, 
    scenarios: list, 
    date_range: dict = None,
    field_mappings: dict = None
):
    """
    Background task for running simulations.
    
    Args:
        self: Celery task instance (for progress updates)
        run_id: Simulation run ID
        scenarios: List of scenario IDs to execute
        date_range: Optional date filtering
        field_mappings: Optional field name mappings
        
    Returns:
        {
            "status": "completed" | "failed",
            "run_id": str,
            "total_alerts": int (if successful),
            "error": str (if failed)
        }
    """
    logger.info(
        "simulation_task_started",
        run_id=run_id,
        scenarios=scenarios,
        task_id=self.request.id
    )
    
    try:
        # Import here to avoid circular dependencies
        from services.simulation_service import SimulationService
        
        # Create database session
        db = get_db_session()
        
        try:
            # Update task state to STARTED
            self.update_state(
                state='STARTED',
                meta={'run_id': run_id, 'progress': 0}
            )
            
            # Execute simulation
            service = SimulationService(db)
            
            # Update progress: 25% - Loading data
            self.update_state(
                state='PROGRESS',
                meta={'run_id': run_id, 'progress': 25, 'stage': 'Loading data'}
            )
            
            # Execute simulation (this is the long-running part)
            result = service.execute_run(
                run_id=run_id,
                scenarios=scenarios,
                date_range=date_range,
                field_mappings=field_mappings
            )
            
            # Update progress: 100% - Complete
            self.update_state(
                state='SUCCESS',
                meta={'run_id': run_id, 'progress': 100, 'stage': 'Complete'}
            )
            
            logger.info(
                "simulation_task_completed",
                run_id=run_id,
                total_alerts=result.get('total_alerts', 0)
            )
            
            return {
                "status": "completed",
                "run_id": run_id,
                "total_alerts": result.get('total_alerts', 0),
                "total_transactions": result.get('total_transactions', 0)
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(
            "simulation_task_failed",
            run_id=run_id,
            error=str(e),
            exc_info=True
        )
        
        # Update task state to FAILURE
        self.update_state(
            state='FAILURE',
            meta={'run_id': run_id, 'error': str(e)}
        )
        
        return {
            "status": "failed",
            "run_id": run_id,
            "error": str(e)
        }


@app.task(name='tasks.cleanup_expired_data')
def cleanup_expired_data():
    """
    Periodic task to cleanup expired TTL data.
    
    Run this via Celery Beat (scheduler):
        celery -A tasks beat --schedule=/tmp/celerybeat-schedule
    """
    logger.info("cleanup_task_started")
    
    try:
        from core.ttl_manager import TTLManager
        
        db = get_db_session()
        
        try:
            result = TTLManager.cleanup_expired(db)
            
            logger.info(
                "cleanup_task_completed",
                transactions_deleted=result['transactions_deleted'],
                customers_deleted=result['customers_deleted']
            )
            
            return result
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error("cleanup_task_failed", error=str(e), exc_info=True)
        raise


# Celery Beat schedule (periodic tasks)
app.conf.beat_schedule = {
    'cleanup-expired-data-daily': {
        'task': 'tasks.cleanup_expired_data',
        'schedule': 86400.0,  # Run every 24 hours
    },
}
