# SAS Simulator Architecture

## System Overview

**SAS Sandbox Simulator** is an enterprise-grade AML/CFT (Anti-Money Laundering / Counter-Terrorist Financing) scenario testing platform that allows financial institutions to simulate transaction monitoring rules against historical data.

### Technology Stack

- **Backend**: FastAPI + Python 3.13 + SQLAlchemy
- **Database**: PostgreSQL (Supabase) with Row-Level Security (RLS)
- **Background Jobs**: Celery + Redis (Upstash)
- **Authentication**: Supabase Auth (JWT with ES256)
- **Deployment**: Docker Containers

---

## Core Architecture

### Multi-Tenancy Model

All data is scoped to `user_id` (UUID from Supabase Auth):
- **Data Uploads**: Each user's transaction/customer data is isolated
- **Scenarios**: Users can only access their own rule configurations
- **Simulation Runs**: Results are user-specific
- **TTL Management**: Data expires after 48 hours (configurable)

### Data Flow

```
┌─────────────┐
│   Client    │
│  (API/CLI)  │
└──────┬──────┘
       │ REST API (Bearer Token)
       ▼
┌─────────────────┐
│   FastAPI API   │
│  (Auth Layer)   │
└──────┬──────────┘
       │
       ├─► /api/data/upload → DataIngestionService
       ├─► /api/simulation → SimulationService → Celery Worker
       ├─► /api/comparison → ComparisonEngine
       └─► /api/dashboard → Stats Aggregation
              │
              ▼
       ┌──────────────┐
       │  PostgreSQL  │
       │  (Supabase)  │
       └──────────────┘
```

---

## Key Components

### Backend (`/backend`)

#### 1. **API Layer** (`/api`)
- **`data.py`**: File upload, schema validation, TTL management
- **`simulation.py`**: Scenario execution orchestration
- **`comparison.py`**: Side-by-side rule comparison
- **`dashboard.py`**: User statistics and metrics
- **`scenario_config.py`**: Rule CRUD operations
- **`risk.py`**: Risk scoring engine

#### 2. **Core Services** (`/services`)
- **`DataIngestionService`**: Flexible CSV/Excel parsing with schema mapping
- **`SimulationService`**: Orchestrates scenario execution
- **`ComparisonService`**: Compares baseline vs. refined rules

#### 3. **Business Logic** (`/core`)
- **`UniversalScenarioEngine`**: Executes AML scenarios (filters → aggregation → thresholds)
- **`RiskEngine`**: Calculates customer risk scores
- **`ComparisonEngine`**: Analyzes alert differences between runs
- **`TTLManager`**: Handles data expiration and cleanup
- **`SmartLayerProcessor`**: Applies intelligent exclusions

#### 4. **Models** (`models.py`)
- **Transaction**: Financial transaction records
- **Customer**: Customer profile data
- **Alert**: Generated AML alerts
- **ScenarioConfig**: Rule definitions
- **SimulationRun**: Execution metadata
- **DataUpload**: TTL-managed upload tracking

#### 5. **Authentication** (`auth.py`)
- JWT validation using Supabase JWKS
- ES256 algorithm support
- User context extraction

---

## Critical Workflows

### 1. **Data Upload Flow**

```
Client uploads CSV/Excel
    ↓
API reads file bytes
    ↓
POST /api/data/upload/customers
POST /api/data/upload/transactions
    ↓
DataIngestionService:
  - Parses file (pandas)
  - Maps headers to schema
  - Stores unmapped fields in raw_data (JSONB)
  - Creates DataUpload record with TTL
    ↓
Returns upload_id + expires_at
```

### 2. **Simulation Execution Flow**

```
Client defines rules
    ↓
POST /api/simulation/run
    ↓
SimulationService.create_run():
  - Creates SimulationRun record
  - Queues Celery task
    ↓
Celery Worker:
  - Loads transaction/customer data
  - For each scenario:
      UniversalScenarioEngine.execute_scenario():
        1. Apply filters (transaction_type, channel, amount range)
        2. Aggregate (group by customer, time window)
        3. Evaluate thresholds (count > X, sum > Y)
        4. Generate alerts
  - Save alerts to database
  - Update run status
    ↓
Client polls GET /api/simulation/status/{run_id}
```

### 3. **Rule Comparison Flow**

```
Client selects baseline + refined scenarios
    ↓
POST /api/comparison/compare
    ↓
ComparisonEngine:
  - Run both scenarios
  - Diff alerts (new, removed, modified)
  - Calculate risk impact
    ↓
Return comparison metrics
```

---

## Database Schema

### Core Tables

**`data_uploads`** (TTL tracking)
- `upload_id` (UUID, PK)
- `user_id` (UUID, FK → profiles)
- `expires_at` (timestamp with timezone)
- `status` ('active' | 'expired')

**`transactions`**
- `transaction_id` (String, PK)
- `customer_id` (String, FK → customers)
- `transaction_date` (timestamp)
- `transaction_amount` (decimal)
- `raw_data` (JSONB) - unmapped fields
- `upload_id` (UUID, FK → data_uploads)
- `expires_at` (timestamp with timezone)

**`customers`**
- `customer_id` (String, PK)
- `customer_name`, `occupation`, `annual_income`
- `raw_data` (JSONB)
- `upload_id` (UUID, FK → data_uploads)
- `expires_at` (timestamp with timezone)

**`scenarios_config`**
- `scenario_id` (String, PK)
- `user_id` (UUID, FK → profiles)
- `scenario_name`, `description`
- `config_json` (JSONB) - full scenario definition
- `enabled` (boolean)

**`simulation_runs`**
- `run_id` (String, PK)
- `user_id` (UUID, FK → profiles)
- `upload_id` (UUID, FK → data_uploads)
- `scenarios_run` (JSONB)
- `status` ('pending' | 'running' | 'completed' | 'failed')

**`alerts`**
- `alert_id` (UUID, PK)
- `customer_id` (String, FK → customers)
- `scenario_id` (String, FK → scenarios_config)
- `run_id` (String, FK → simulation_runs)
- `alert_date` (timestamp)
- `risk_classification` ('LOW' | 'MEDIUM' | 'HIGH')
- `trigger_details` (JSONB)

---

## Security Model

### Authentication
- **JWT Tokens**: Issued by Supabase Auth
- **Algorithm**: ES256 (Elliptic Curve)
- **Validation**: JWKS-based public key verification
- **Expiry**: Tokens expire after 1 hour

### Authorization
- **Row-Level Security (RLS)**: Enforced at database level
- **User Scoping**: All queries filtered by `user_id`
- **Service Role**: Background tasks use elevated permissions

### Data Protection
- **TTL**: All uploaded data expires after 48 hours
- **Cleanup Job**: Celery cron task runs hourly
- **Encryption**: TLS in transit, Supabase encryption at rest

---

## Performance Considerations

### Database Indexes
```sql
-- TTL cleanup optimization
CREATE INDEX idx_transactions_upload_expires ON transactions(upload_id, expires_at);
CREATE INDEX idx_customers_upload_expires ON customers(upload_id, expires_at);
CREATE INDEX idx_data_uploads_expires_status ON data_uploads(expires_at, status);

-- Query optimization
CREATE INDEX idx_transactions_customer_date ON transactions(customer_id, transaction_date);
CREATE INDEX idx_alerts_run_id ON alerts(run_id);
```

### Connection Pooling
```python
# PostgreSQL connection pool
pool_size=10          # Persistent connections
max_overflow=20       # Burst capacity
pool_recycle=3600     # Recycle hourly
```

---

## Deployment

### Backend (Docker/Cloud)
```bash
# Start command
uvicorn main:app --host 0.0.0.0 --port $PORT

# Environment variables
DATABASE_URL=postgresql://...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=xxx
REDIS_URL=rediss://...
```

### Background Workers
```bash
# Start command
celery -A tasks worker --loglevel=info
```

---

## Monitoring & Observability

### Logging
- **Structured Logging**: `structlog` with JSON output
- **Log Levels**: INFO (production), DEBUG (development)
- **Context**: `user_id`, `run_id`, `upload_id` in all logs

### Health Checks
```bash
GET /health
{
  "status": "healthy",
  "checks": {
    "database": "healthy",
    "redis": "healthy",
    "auth": "healthy"
  }
}
```
