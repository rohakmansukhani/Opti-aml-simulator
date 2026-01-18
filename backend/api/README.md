# Backend API Endpoints

This directory contains all FastAPI route handlers organized by domain.

## 📁 API Structure

```
api/
├── data.py              # Data upload & TTL management
├── simulation.py        # Simulation execution & status
├── rules.py             # Scenario configuration
├── scenario_config.py   # Advanced scenario management
├── dashboard.py         # Dashboard statistics
├── comparison.py        # Simulation comparison
└── risk.py              # Risk analysis endpoints
```

## 🌐 API Endpoints Overview

### 1. Data API (`/api/data`)
**File:** `data.py`

**Endpoints:**
- `POST /upload/transactions` - Upload transaction CSV/Excel
- `POST /upload/customers` - Upload customer CSV/Excel
- `POST /ttl/extend` - Extend data TTL by 24 hours
- `GET /field-values` - Get unique field values for filtering

**Features:**
- File validation (CSV/Excel only)
- Size limits (10k transactions, 5k customers)
- TTL management (48h default)
- Bulk insert optimization
- Error handling with rollback

**Example:**
```bash
curl -X POST http://localhost:8000/api/data/upload/transactions \
  -F "file=@transactions.csv"
```

**Response:**
```json
{
    "status": "success",
    "records_uploaded": 1523,
    "upload_id": "uuid-here",
    "expires_at": "2024-01-20T15:30:00Z"
}
```

---

### 2. Simulation API (`/api/simulation`)
**File:** `simulation.py`

**Endpoints:**
- `POST /check-schema` - Validate scenario requirements
- `POST /run` - Start simulation (background task)
- `GET /{run_id}/status` - Get simulation status
- `GET /{run_id}/results` - Get simulation results
- `GET /{run_id}/download` - Download Excel report

**Features:**
- Schema validation before execution
- Background task execution
- Field mapping support
- Date range filtering
- Real-time status updates

**Example:**
```bash
curl -X POST http://localhost:8000/api/simulation/run \
  -H "Content-Type: application/json" \
  -d '{
    "scenarios": ["ICICI_01", "ICICI_44"],
    "run_type": "baseline",
    "field_mappings": {"amount": "transaction_amount"}
  }'
```

**Response:**
```json
{
    "run_id": "uuid-here",
    "status": "pending"
}
```

---

### 3. Rules API (`/api/rules`)
**File:** `rules.py`

**Endpoints:**
- `GET /scenarios` - List all scenarios
- `GET /scenarios/{id}` - Get scenario details
- `PUT /scenarios/{id}` - Update scenario
- `POST /refinements` - Apply refinements to run

**Features:**
- User-scoped scenarios
- Enable/disable scenarios
- Refinement rule management
- Default scenario fallback

---

### 4. Dashboard API (`/api/dashboard`)
**File:** `dashboard.py`

**Endpoints:**
- `GET /stats` - Get dashboard statistics

**Returns:**
```json
{
    "risk_score": "72.5",
    "active_high_risk_alerts": 45,
    "transactions_scanned": 15234,
    "system_coverage": "95%",
    "total_simulations": 127,
    "recent_simulations": [...]
}
```

---

## 🔐 Security

### Authentication
All endpoints (except `/health`, `/metrics`) require JWT authentication:
```python
user_data: dict = Depends(get_current_user)
```

### Rate Limiting
Default: 200 requests/minute per IP
```python
@limiter.limit("5/minute")  # Override for specific endpoint
async def sensitive_endpoint():
    ...
```

### CORS
Production origins configured via environment:
```bash
ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

---

## 📊 Request/Response Flow

```
Client Request
    ↓
Rate Limiter (200/min)
    ↓
CORS Validation
    ↓
JWT Authentication
    ↓
Request Logging (structlog)
    ↓
Endpoint Handler
    ↓
Database Operations
    ↓
Response Logging
    ↓
Client Response
```

---

## 🧪 Testing

Each API module has tests in `backend/tests/`:
```bash
pytest tests/test_simulation.py -v
pytest tests/test_data.py -v
pytest tests/test_auth.py -v
```

---

## 📝 API Documentation

Interactive docs available at:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

---

## 🔧 Error Handling

All endpoints return consistent error format:
```json
{
    "detail": "Error message",
    "code": "ERROR_CODE"
}
```

**Common Status Codes:**
- `200` - Success
- `400` - Bad Request (validation error)
- `401` - Unauthorized (missing/invalid token)
- `403` - Forbidden (insufficient permissions)
- `413` - Payload Too Large (dataset limits)
- `422` - Unprocessable Entity (Pydantic validation)
- `429` - Too Many Requests (rate limit)
- `500` - Internal Server Error (logged to Sentry)

---

## 📈 Monitoring

### Metrics Endpoint
```bash
curl http://localhost:8000/metrics
```

Returns Prometheus metrics:
- Request count by endpoint
- Request duration histogram
- Error rates
- Active connections

### Health Check
```bash
curl http://localhost:8000/health
```

Returns:
```json
{
    "status": "healthy",
    "service": "sas-sandbox-simulator",
    "version": "1.0.0",
    "environment": "production"
}
```

---

## 🚀 Performance

### Optimization Techniques:
1. **Bulk Operations:** Use `bulk_insert_mappings` for data uploads
2. **Background Tasks:** Long-running simulations run async
3. **Database Indexing:** Indexed on customer_id, transaction_date
4. **Connection Pooling:** SQLAlchemy pool (size=20)

### Response Times (P95):
- Data upload (1k rows): < 500ms
- Simulation start: < 200ms
- Status check: < 50ms
- Dashboard stats: < 300ms
