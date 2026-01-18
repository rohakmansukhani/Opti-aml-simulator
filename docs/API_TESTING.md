# Backend API Testing Guide - Complete curl Scenarios

## Prerequisites

```bash
# Set base URL
export API_URL="http://localhost:8000"

# Get auth token (replace with your Supabase token)
export AUTH_TOKEN="your_jwt_token_here"
```

## 1. Health & Status Checks

### Comprehensive Health Check
```bash
curl -X GET "$API_URL/health" | jq

# Expected Response:
# {
#   "status": "healthy",
#   "service": "sas-sandbox-simulator",
#   "version": "1.0.0",
#   "environment": "development",
#   "checks": {
#     "redis": {
#       "status": "healthy",
#       "message": "Connected to Redis",
#       "url": "your-db.upstash.io:6379"
#     },
#     "database": {
#       "status": "healthy",
#       "message": "Database connected",
#       "type": "PostgreSQL"
#     },
#     "auth": {
#       "status": "healthy",
#       "message": "Supabase Auth configured",
#       "url": "https://xxx.supabase.co"
#     }
#   }
# }
```

### Root Endpoint
```bash
curl -X GET "$API_URL/" | jq
```

### Prometheus Metrics
```bash
curl -X GET "$API_URL/metrics"
```

---

## 2. Data Upload Endpoints

### Upload Transactions CSV
```bash
curl -X POST "$API_URL/api/data/upload/transactions" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -F "file=@transactions.csv" | jq

# Expected Response:
# {
#   "status": "success",
#   "records_uploaded": 1523,
#   "upload_id": "uuid-here",
#   "expires_at": "2024-01-20T15:30:00Z"
# }
```

### Upload Customers CSV
```bash
curl -X POST "$API_URL/api/data/upload/customers" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -F "file=@customers.csv" | jq
```

### Extend TTL
```bash
curl -X POST "$API_URL/api/data/ttl/extend?upload_id=YOUR_UPLOAD_ID&additional_hours=24" \
  -H "Authorization: Bearer $AUTH_TOKEN" | jq

# Expected Response:
# {
#   "status": "success",
#   "new_expires_at": "2024-01-21T15:30:00Z"
# }
```

### Get Field Values
```bash
curl -X GET "$API_URL/api/data/field-values?field=customer_type" \
  -H "Authorization: Bearer $AUTH_TOKEN" | jq
```

---

## 3. Simulation Endpoints

### Check Schema
```bash
curl -X POST "$API_URL/api/simulation/check-schema" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "scenarios": ["ICICI_01", "ICICI_44"],
    "run_type": "baseline"
  }' | jq

# Expected Response:
# {
#   "status": "valid",
#   "missing_fields": [],
#   "required_fields": ["customer_id", "transaction_date", ...]
# }
```

### Run Simulation
```bash
curl -X POST "$API_URL/api/simulation/run" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "scenarios": ["ICICI_01"],
    "run_type": "baseline",
    "date_range": {
      "start": "2024-01-01",
      "end": "2024-12-31"
    },
    "field_mappings": {
      "amount": "transaction_amount"
    }
  }' | jq

# Expected Response:
# {
#   "run_id": "uuid-here",
#   "status": "pending",
#   "message": "Simulation started"
# }
```

### Get Simulation Status
```bash
RUN_ID="your-run-id-here"
curl -X GET "$API_URL/api/simulation/$RUN_ID/status" \
  -H "Authorization: Bearer $AUTH_TOKEN" | jq

# Expected Response:
# {
#   "run_id": "uuid-here",
#   "status": "running",
#   "progress": 65,
#   "stage": "Applying refinements"
# }
```

### Get Simulation Results
```bash
curl -X GET "$API_URL/api/simulation/$RUN_ID/results" \
  -H "Authorization: Bearer $AUTH_TOKEN" | jq

# Expected Response:
# {
#   "run_id": "uuid-here",
#   "status": "completed",
#   "total_alerts": 850,
#   "alerts": [...]
# }
```

### Download Excel Report
```bash
curl -X GET "$API_URL/api/simulation/$RUN_ID/download" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -o "simulation_report.xlsx"
```

---

## 4. Scenario Configuration

### List Scenarios
```bash
curl -X GET "$API_URL/api/rules/scenarios" \
  -H "Authorization: Bearer $AUTH_TOKEN" | jq

# Expected Response:
# [
#   {
#     "scenario_id": "ICICI_01",
#     "scenario_name": "High Value Transactions",
#     "enabled": true
#   }
# ]
```

### Get Scenario Details
```bash
curl -X GET "$API_URL/api/rules/scenarios/ICICI_01" \
  -H "Authorization: Bearer $AUTH_TOKEN" | jq
```

### Update Scenario
```bash
curl -X PUT "$API_URL/api/rules/scenarios/ICICI_01" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "config_json": {...}
  }' | jq
```

---

## 5. Comparison Engine

### Compare Runs
```bash
curl -X POST "$API_URL/api/comparison/compare" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "baseline_run_id": "run-123",
    "refined_run_id": "run-456"
  }' | jq

# Expected Response:
# {
#   "summary": {
#     "baseline_alerts": 1200,
#     "refined_alerts": 850,
#     "net_change": 350,
#     "percent_reduction": 29.17
#   },
#   "granular_diff": [...],
#   "risk_analysis": {
#     "risk_score": 45.2,
#     "risk_level": "CAUTION"
#   }
# }
```

### Get Run Metadata
```bash
curl -X GET "$API_URL/api/comparison/runs/$RUN_ID/metadata" \
  -H "Authorization: Bearer $AUTH_TOKEN" | jq
```

---

## 6. Dashboard Endpoints

### Get Dashboard Stats
```bash
curl -X GET "$API_URL/api/dashboard/stats" \
  -H "Authorization: Bearer $AUTH_TOKEN" | jq

# Expected Response:
# {
#   "risk_score": "72.5",
#   "active_high_risk_alerts": 45,
#   "transactions_scanned": 15234,
#   "system_coverage": "95%",
#   "total_simulations": 127
# }
```

---

## 7. Database Connection Test

### Test PostgreSQL Connection
```bash
curl -X POST "$API_URL/api/connect" \
  -H "Content-Type: application/json" \
  -d '{
    "db_url": "postgresql://user:pass@host:5432/dbname"
  }' | jq

# Expected Response:
# {
#   "status": "connected",
#   "message": "Connection Successful"
# }
```

---

## 8. Error Testing

### Test Rate Limiting
```bash
# Send 250 requests rapidly (limit is 200/min)
for i in {1..250}; do
  curl -X GET "$API_URL/health" &
done
wait

# Should get 429 Too Many Requests after 200
```

### Test Invalid Auth
```bash
curl -X GET "$API_URL/api/rules/scenarios" \
  -H "Authorization: Bearer invalid_token" | jq

# Expected: 401 Unauthorized
```

### Test Missing Required Fields
```bash
curl -X POST "$API_URL/api/simulation/run" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "scenarios": []
  }' | jq

# Expected: 422 Validation Error
```

---

## 9. Complete Test Script

Save as `test_api.sh`:

```bash
#!/bin/bash

# Configuration
API_URL="http://localhost:8000"
AUTH_TOKEN="your_token_here"

echo "🧪 Testing SAS Sandbox Simulator API"
echo "======================================"

# 1. Health Check
echo -e "\n✅ 1. Health Check"
curl -s -X GET "$API_URL/health" | jq '.status'

# 2. Root Endpoint
echo -e "\n✅ 2. Root Endpoint"
curl -s -X GET "$API_URL/" | jq '.message'

# 3. Metrics
echo -e "\n✅ 3. Metrics Endpoint"
curl -s -X GET "$API_URL/metrics" | head -n 5

# 4. List Scenarios (requires auth)
echo -e "\n✅ 4. List Scenarios"
curl -s -X GET "$API_URL/api/rules/scenarios" \
  -H "Authorization: Bearer $AUTH_TOKEN" | jq 'length'

# 5. Dashboard Stats
echo -e "\n✅ 5. Dashboard Stats"
curl -s -X GET "$API_URL/api/dashboard/stats" \
  -H "Authorization: Bearer $AUTH_TOKEN" | jq '.total_simulations'

# 6. Schema Check
echo -e "\n✅ 6. Schema Check"
curl -s -X POST "$API_URL/api/simulation/check-schema" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"scenarios": ["ICICI_01"], "run_type": "baseline"}' | jq '.status'

echo -e "\n✅ All tests completed!"
```

Run with:
```bash
chmod +x test_api.sh
./test_api.sh
```

---

## 10. Expected Status Codes

| Endpoint | Success | Auth Error | Validation Error | Rate Limit |
|----------|---------|------------|------------------|------------|
| `/health` | 200 | - | - | 429 |
| `/api/data/upload/*` | 200 | 401 | 400/422 | 429 |
| `/api/simulation/run` | 200 | 401 | 422 | 429 |
| `/api/rules/scenarios` | 200 | 401 | - | 429 |
| `/api/comparison/compare` | 200 | 401 | 422 | 429 |

---

## 11. Performance Testing

### Load Test with Apache Bench
```bash
# 1000 requests, 50 concurrent
ab -n 1000 -c 50 -H "Authorization: Bearer $AUTH_TOKEN" \
  "$API_URL/health"
```

### Load Test with hey
```bash
# Install: brew install hey
hey -n 1000 -c 50 -H "Authorization: Bearer $AUTH_TOKEN" \
  "$API_URL/api/dashboard/stats"
```

---

## 12. Monitoring

### Watch Health Status
```bash
watch -n 5 'curl -s http://localhost:8000/health | jq ".checks"'
```

### Monitor Logs
```bash
docker-compose logs -f backend
```

### Monitor Celery Tasks
```bash
docker-compose logs -f celery
```
