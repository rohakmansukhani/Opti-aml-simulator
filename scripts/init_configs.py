import sys
import os
import logging

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, '..', 'backend')
sys.path.append(backend_dir)

from database import SessionLocal, engine
from models import ScenarioConfig, Base
from core.migrated_configs import ALL_UNIVERSAL_CONFIGS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_configs():
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        logger.info("Initializing Universal Scenario Configs...")
        for config in ALL_UNIVERSAL_CONFIGS:
            existing = db.query(ScenarioConfig).filter(ScenarioConfig.scenario_id == config.scenario_id).first()
            if existing:
                logger.info(f"Updating existing config: {config.scenario_id}")
                existing.config_json = config.dict()
                existing.scenario_name = config.scenario_name
                # Update other fields if needed
            else:
                logger.info(f"Creating new config: {config.scenario_id}")
                db_config = ScenarioConfig(
                    scenario_id=config.scenario_id,
                    scenario_name=config.scenario_name,
                    frequency=config.frequency,
                    config_json=config.dict(),
                    thresholds=config.threshold.dict() if config.threshold else None,
                    enabled=True
                )
                db.add(db_config)
        
        db.commit()
        logger.info("Initialization complete.")
    except Exception as e:
        logger.error(f"Error initializing configs: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_configs()
