from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

# Use the full connection string from .env directly or hardcode if needed for script
DB_URL = os.getenv("DATABASE_URL")

def apply_rls():
    if not DB_URL or "sqlite" in DB_URL:
        print("Skipping RLS: Not connected to Supabase PostgreSQL.")
        return

    print(f"Applying RLS policies to {DB_URL.split('@')[1]}...")
    
    engine = create_engine(DB_URL)
    
    statements = [
        "ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;",
        "ALTER TABLE customers ENABLE ROW LEVEL SECURITY;",
        "ALTER TABLE scenarios_config ENABLE ROW LEVEL SECURITY;",
        "ALTER TABLE simulation_runs ENABLE ROW LEVEL SECURITY;",
        "ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;",
        
        # Scenarios Policies
        """
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_policies WHERE tablename = 'scenarios_config' AND policyname = 'Users can view own scenarios') THEN
                CREATE POLICY "Users can view own scenarios" ON scenarios_config FOR SELECT USING (auth.uid()::text = user_id::text);
            END IF;
        END $$;
        """,
        """
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_policies WHERE tablename = 'scenarios_config' AND policyname = 'Users can create own scenarios') THEN
                CREATE POLICY "Users can create own scenarios" ON scenarios_config FOR INSERT WITH CHECK (auth.uid()::text = user_id::text);
            END IF;
        END $$;
        """,
        
        # Simulation Runs Policies
        """
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_policies WHERE tablename = 'simulation_runs' AND policyname = 'Users can view own runs') THEN
                CREATE POLICY "Users can view own runs" ON simulation_runs FOR SELECT USING (auth.uid()::text = user_id::text);
            END IF;
        END $$;
        """,
        """
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_policies WHERE tablename = 'simulation_runs' AND policyname = 'Users can create own runs') THEN
                CREATE POLICY "Users can create own runs" ON simulation_runs FOR INSERT WITH CHECK (auth.uid()::text = user_id::text);
            END IF;
        END $$;
        """
    ]
    
    with engine.connect() as conn:
        for stmt in statements:
            try:
                # Wrap each in a sub-transaction savepoint logic or just raw execute if autocommit
                # Simplest for script: Try/Except with rollback on failure
                conn.execute(text(stmt))
                conn.commit()
                print(f"Executed: {stmt[:50].strip()}...")
            except Exception as e:
                print(f"Error executing stmt: {e}")
                conn.rollback() # Important: Reset transaction state so next stmt works

if __name__ == "__main__":
    apply_rls()
