import os
import sys

# Add backend to path to import database utils
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))

from database import get_service_engine
from sqlalchemy import text

def list_indexes():
    db = get_service_engine()()
    try:
        print("\n=== 🔍 Database Indexes Report ===\n")
        
        # 1. List All Physical Indexes in Postgres
        result = db.execute(text("""
            SELECT 
                tablename, 
                indexname, 
                indexdef 
            FROM pg_indexes 
            WHERE schemaname = 'public' 
            ORDER BY tablename, indexname;
        """)).fetchall()
        
        print(f"{'Table':<30} | {'Index Name':<50}")
        print("-" * 80)
        
        for row in result:
            table = row[0]
            idx = row[1]
            print(f"{table:<30} | {idx:<50}")
            
        print("\n" + "="*80 + "\n")
        
        # 2. Check Application Data Index (FieldValueIndex) Stats
        count = db.execute(text("SELECT count(*) FROM field_value_index")).scalar()
        print(f"📊 Application Data Index (Autocomplete Values): {count} records")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    list_indexes()
