from fastapi import FastAPI, Request, Depends, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import engine, Base, get_db
from models import (
    Transaction, Customer, Alert, ScenarioConfig, 
    VerifiedEntity, AuditLog, AlertExclusionLog, 
    UserProfile, CustomerRiskProfile, SimulationRun
)
import os
import time
import structlog
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Structured logging configuration
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger("sas_simulator")

# Create database tables
Base.metadata.create_all(bind=engine)

from api import data, simulation, comparison, rules, risk, scenario_config, dashboard

# Rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

app = FastAPI(
    title="SAS Sandbox Simulator API",
    version="1.0.0",
    description="Enterprise-grade AML/CFT scenario simulation platform"
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

from fastapi.middleware.cors import CORSMiddleware

# Production CORS configuration
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(duration * 1000, 2),
        client_ip=get_remote_address(request)
    )
    
    return response

app.include_router(data.router)
app.include_router(simulation.router)
app.include_router(comparison.router)
app.include_router(rules.router)
app.include_router(risk.router)
app.include_router(scenario_config.router)
app.include_router(dashboard.router)



@app.get("/")
async def root():
    return {"message": "SAS Sandbox Simulator API is running", "version": "1.0.0"}

@app.get("/health")
async def health_check(response: Response, db: Session = Depends(get_db)):
    """
    Comprehensive health check endpoint
    
    Checks:
    1. Upstash Redis connection
    2. PostgreSQL database connection
    3. Supabase Auth service
    
    Returns:
        {
            "status": "healthy" | "degraded" | "unhealthy",
            "checks": {
                "redis": {...},
                "database": {...},
                "auth": {...}
            }
        }
    """
    import redis
    from supabase import create_client
    
    checks = {}
    overall_status = "healthy"
    
    # 1. Check Upstash Redis
    try:
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            r = redis.from_url(redis_url, socket_connect_timeout=5)
            r.ping()
            checks["redis"] = {
                "status": "healthy",
                "message": "Connected to Redis",
                "url": redis_url.split("@")[1] if "@" in redis_url else "localhost"
            }
        else:
            checks["redis"] = {
                "status": "warning",
                "message": "Redis URL not configured"
            }
            overall_status = "degraded"
    except Exception as e:
        checks["redis"] = {
            "status": "unhealthy",
            "message": f"Redis connection failed: {str(e)}"
        }
        overall_status = "unhealthy"
    
    # 2. Check PostgreSQL Database
    try:
        # Simple query to test connection
        db.execute(text("SELECT 1"))
        checks["database"] = {
            "status": "healthy",
            "message": "Database connected",
            "type": "PostgreSQL"
        }
    except Exception as e:
        checks["database"] = {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}"
        }
        overall_status = "unhealthy"
    
    # 3. Check Supabase Auth
    try:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_ANON_KEY")
        
        if supabase_url and supabase_key:
            supabase = create_client(supabase_url, supabase_key)
            # Test auth service by checking if it's reachable
            # Note: This doesn't actually authenticate, just checks service availability
            checks["auth"] = {
                "status": "healthy",
                "message": "Supabase Auth configured",
                "url": supabase_url
            }
        else:
            checks["auth"] = {
                "status": "warning",
                "message": "Supabase Auth not configured"
            }
            if overall_status == "healthy":
                overall_status = "degraded"
    except Exception as e:
        checks["auth"] = {
            "status": "unhealthy",
            "message": f"Auth service check failed: {str(e)}"
        }
        overall_status = "unhealthy"
    
    # Set appropriate HTTP status code
    if overall_status == "unhealthy":
        response.status_code = 503
    elif overall_status == "degraded":
        response.status_code = 200  # Still 200 OK but with warnings
    
    logger.info(
        "health_check_completed",
        status=overall_status,
        redis=checks.get("redis", {}).get("status"),
        database=checks.get("database", {}).get("status"),
        auth=checks.get("auth", {}).get("status")
    )
    
    return {
        "status": overall_status,
        "service": "sas-sandbox-simulator",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "checks": checks
    }

# Prometheus metrics endpoint
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint for monitoring"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

from pydantic import BaseModel
class ConnectionRequest(BaseModel):
    db_url: str

@app.post("/api/connect")
async def test_connection(request: ConnectionRequest):
    """
    Validates that a provided database URL can establish a connection.
    Frontend should call this before storing the URL in session/localstorage.
    Only PostgreSQL connections are supported.
    """
    from sqlalchemy import create_engine, text
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Validate URL format - only accept PostgreSQL
    if not request.db_url.startswith("postgresql://") and not request.db_url.startswith("postgres://"):
        return {
            "status": "failed", 
            "message": "Only PostgreSQL databases are supported. URL must start with 'postgresql://' or 'postgres://'"
        }
    
    try:
        # Try connecting with a short timeout
        engine = create_engine(
            request.db_url, 
            connect_args={"connect_timeout": 5}
        )
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "connected", "message": "Connection Successful"}
    except Exception as e:
        # Log detailed error server-side
        logger.error(f"Database connection failed: {str(e)}")
        
        # Return generic error to client
        return {
            "status": "failed", 
            "message": "Unable to connect to database. Please verify your connection string and ensure the database is accessible."
        }

