import sys
import os
import logging
import random
from datetime import datetime

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, '..', 'backend')
sys.path.append(backend_dir)

from database import SessionLocal, engine
from models import Base, VerifiedEntity, CustomerRiskProfile, Customer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_risk_data():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    try:
        # 1. Seed Verified Entities
        logger.info("Seeding Verified Entities...")
        
        universities = [
            "University of Oxford", "University of Cambridge", "Imperial College London",
            "UCL", "University of Edinburgh", "King's College London",
            "University of Manchester", "University of Bristol"
        ]
        
        crypto_exchanges = [
            "Coinbase", "Binance", "Kraken", "Gemini", "Bitstamp", "eToro"
        ]
        
        for name in universities:
            if not db.query(VerifiedEntity).filter_by(entity_name=name).first():
                ve = VerifiedEntity(
                    entity_name=name,
                    entity_type="University",
                    country="UK",
                    risk_category="LOW",
                    is_active=True
                )
                db.add(ve)

        for name in crypto_exchanges:
            if not db.query(VerifiedEntity).filter_by(entity_name=name).first():
                ve = VerifiedEntity(
                    entity_name=name,
                    entity_type="CryptoExchange",
                    country="Global",
                    risk_category="MEDIUM",
                    is_active=True
                )
                db.add(ve)
        
        db.commit()
        
        # 2. Seed Customer Risk Profiles
        logger.info("Seeding Customer Risk Profiles...")
        customers = db.query(Customer).all()
        
        for cust in customers:
            if not db.query(CustomerRiskProfile).filter_by(customer_id=cust.customer_id).first():
                # Randomly assign risk
                is_high_risk = random.random() < 0.05 # 5% high risk
                
                profile = CustomerRiskProfile(
                    customer_id=cust.customer_id,
                    risk_rating="HIGH" if is_high_risk else "LOW",
                    is_pep=is_high_risk and random.random() < 0.3, # 30% of high risk are PEP
                    has_adverse_media=is_high_risk and random.random() < 0.4,
                    high_risk_occupation=cust.occupation in ["Politician", "Unknown", "Consultant"],
                    previous_sar_count=random.randint(1,3) if is_high_risk else 0,
                    last_updated=datetime.utcnow()
                )
                db.add(profile)
                
        db.commit()
        logger.info("Seeding complete.")
        
    except Exception as e:
        logger.error(f"Error seeding data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_risk_data()
