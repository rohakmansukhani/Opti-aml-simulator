from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from fastapi import Header, HTTPException
import os
from tempfile import mkdtemp
from dotenv import load_dotenv

load_dotenv()

# Global cache for engines
# Key: db_url, Value: sessionmaker
_engine_cache = {}

Base = declarative_base()

# Default to Env Var (Supabase), remove SQLite fallback
DEFAULT_DB_URL = os.getenv("DATABASE_URL", "").strip()
if not DEFAULT_DB_URL:
    # Fallback only if truly unset, but prefer crashing or logging warning in production
    # ideally we want to fail fast if no DB is configured
    DEFAULT_DB_URL = "sqlite:///./sas_simulator.db"

# For initial boot/migrations where no request context exists
def get_default_engine():
    return _get_engine(DEFAULT_DB_URL)

def _get_engine(db_url: str):
    if not db_url:
         raise HTTPException(status_code=500, detail="Database URL not configured.")

    if db_url not in _engine_cache:
        connect_args = {}
        if "sqlite" in db_url:
            connect_args = {"check_same_thread": False}
        
        try:
            # Add pool_pre_ping for resilience with Supabase
            engine = create_engine(db_url, connect_args=connect_args, pool_pre_ping=True)
            _engine_cache[db_url] = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid Database Connection String: {str(e)}")
            
    return _engine_cache[db_url]

# Service Role support for background tasks (Bypass RLS)
SERVICE_ROLE_URL = os.getenv("DATABASE_URL_SERVICE_ROLE")

def get_service_engine():
    """Returns engine with SERVICE ROLE key - bypasses RLS for system operations."""
    # Fallback to standard URL if service role not set (e.g. dev/local sqlite)
    target_url = SERVICE_ROLE_URL or DEFAULT_DB_URL
    
    if "service_engine" not in _engine_cache:
        try:
            # Create a separate engine for service role tasks
            # If using postgresql, this connection should use the service_role credentials
            engine = create_engine(target_url, pool_pre_ping=True)
            _engine_cache["service_engine"] = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        except Exception as e:
             # Fallback
             print(f"Service role engine init failed: {e}")
             return get_default_engine()

    return _engine_cache["service_engine"]

def resolve_db_url(url_or_alias: str) -> str:
    """Helper to resolve 'local' alias to actual path."""
    if not url_or_alias or url_or_alias == "default":
        return DEFAULT_DB_URL # Default to Supabase
    if url_or_alias == "local":
        return DEFAULT_DB_URL # Redirect 'local' requests to Supabase
    if url_or_alias.startswith("sqlite") and "sas_simulator.db" in url_or_alias:
        return DEFAULT_DB_URL # Redirect old file paths to Supabase
    return url_or_alias

def get_db(x_db_url: str = Header(None)):
    """
    Dependency that gets DB session based on header.
    """
    if x_db_url is None:
        x_db_url = "local"
        
    target_url = resolve_db_url(x_db_url)
    
    SessionLocal = _get_engine(target_url)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Expose global engine/SessionLocal for scripts that import them directly
# ensuring they use the default fallback
engine = get_default_engine().kw['bind']
SessionLocal = get_default_engine()
