# Backend Core Modules

This directory contains the core business logic and processing engines for the SAS Sandbox Simulator.

## 📁 Module Structure

```
core/
├── universal_engine.py    # Main scenario execution engine
├── smart_layer.py          # Alert refinement & exclusion logic
├── risk_engine.py          # Risk scoring & gap analysis
├── event_detector.py       # Transaction context detection
├── ttl_manager.py          # Data lifecycle management
└── config_models.py        # Pydantic configuration schemas
```

## 🔧 Core Components

### 1. Universal Scenario Engine
**File:** `universal_engine.py`

**Purpose:** Executes AML/CFT scenarios against transaction data to generate alerts.

**Key Features:**
- Config-driven execution (no hardcoded rules)
- Supports multiple aggregation types (SUM, COUNT, MAX)
- Dynamic threshold evaluation
- Rolling window calculations (daily, monthly)
- Generates structured alert objects

**Main Class:** `UniversalScenarioEngine`

**Key Methods:**
```python
execute_scenarios(
    scenarios: List[Dict],
    transactions_df: pd.DataFrame,
    customers_df: pd.DataFrame
) -> pd.DataFrame
```

**Flow:**
1. Load scenario configurations
2. Apply filters to transactions
3. Aggregate by customer/time window
4. Evaluate thresholds
5. Generate alerts with metadata

---

### 2. Smart Layer Processor
**File:** `smart_layer.py`

**Purpose:** Refines raw alerts by applying exclusion rules and context checks.

**Key Features:**
- **Vectorized processing** (85% faster than iterrows)
- Trigger window filtering (only relevant transactions)
- Event context detection (education, crypto, loans)
- Beneficiary verification against whitelist
- Audit logging (AlertExclusionLog)

**Main Class:** `SmartLayerProcessor`

**Key Methods:**
```python
apply_refinements(
    alerts: pd.DataFrame,
    transactions: pd.DataFrame,
    refinement_rules: List[Dict],
    lookback_days: int = 30
) -> pd.DataFrame
```

**Optimization:**
- Uses `str.contains()` with regex for bulk filtering
- Processes only matched customer subset
- Avoids nested loops where possible

---

### 3. Risk Engine
**File:** `risk_engine.py`

**Purpose:** Analyzes excluded alerts to quantify security risk ("Red Teaming").

**Key Features:**
- Scores excluded alerts (0-100 scale)
- Uses CustomerRiskProfile (PEP, adverse media, SAR count)
- Validates against VerifiedEntity whitelist
- Generates exploit scenarios for UI

**Main Class:** `RiskEngine`

**Key Methods:**
```python
analyze_excluded_alerts(
    excluded_alerts: List[Dict]
) -> Dict[str, Any]
```

**Returns:**
```python
{
    "risk_score": 45.2,
    "risk_level": "CAUTION",  # SAFE | CAUTION | DANGEROUS | CRITICAL
    "excluded_count": 12,
    "sample_exploits": [...]
}
```

**Scoring Factors:**
- Amount reasonability (education > $50k = suspicious)
- Beneficiary verification status
- Customer risk profile (PEP, adverse media)
- Previous SAR filings

---

### 4. Event Detector
**File:** `event_detector.py`

**Purpose:** Detects transaction context (education, crypto, loans) and validates legitimacy.

**Key Features:**
- Keyword-based event classification
- Beneficiary verification lookup
- Amount reasonability checks
- Returns structured context object

**Main Class:** `EventDetector`

**Key Methods:**
```python
detect_event_context(
    narrative: str,
    amount: float,
    beneficiary: str
) -> Dict | None
```

**Returns:**
```python
{
    "type": "education",
    "is_verified": True,
    "amount_reasonable": True,
    "confidence": 0.95
}
```

---

### 5. TTL Manager
**File:** `ttl_manager.py`

**Purpose:** Manages time-to-live for uploaded data (auto-deletion after 48h).

**Key Features:**
- Creates upload metadata records
- Sets expiry timestamps
- Extends TTL (max 168h)
- Cleanup expired data (cron job)

**Main Class:** `TTLManager`

**Key Methods:**
```python
create_upload_record(db, user_id, filename, txn_count, ...) -> str
extend_ttl(db, upload_id, additional_hours=24) -> bool
cleanup_expired(db) -> Dict[str, int]
```

**TTL Lifecycle:**
1. Upload → `expires_at = now + 48h`
2. User extends → `expires_at += 24h` (max 168h)
3. Expiry reached → Cleanup job deletes records

---

## 🔄 Data Flow

```
Transactions (CSV) 
    ↓
UniversalEngine.execute_scenarios()
    ↓
Raw Alerts DataFrame
    ↓
SmartLayerProcessor.apply_refinements()
    ↓
EventDetector.detect_event_context()
    ↓
Refined Alerts (excluded flagged)
    ↓
RiskEngine.analyze_excluded_alerts()
    ↓
Risk Analysis + Exploit Scenarios
```

## 🎯 Performance Optimizations

### Vectorization (SmartLayer)
- **Before:** O(n) iterrows loop → 18s for 10k alerts
- **After:** Vectorized filtering → 2.7s (**85% faster**)

### Key Techniques:
1. Bulk keyword matching with `str.contains()`
2. Filter to matched customers first
3. Process only relevant subset
4. Avoid nested transaction loops

## 🧪 Testing

Each module has corresponding tests in `backend/tests/`:
- `test_simulation.py` - UniversalEngine tests
- `test_smart_layer.py` - SmartLayer tests (TODO)
- `test_risk_engine.py` - RiskEngine tests (TODO)

## 📊 Monitoring

All modules log to structured JSON via `structlog`:
```python
logger.info("scenario_executed", 
    scenario_id=scenario_id, 
    alerts_generated=len(alerts),
    duration_ms=duration
)
```

## 🔗 Dependencies

- `pandas` - DataFrame operations
- `sqlalchemy` - Database ORM
- `pydantic` - Configuration validation
- `simpleeval` - Safe expression evaluation

## 📝 Configuration

Scenarios are defined in `ScenarioConfig` table with JSON structure:
```json
{
    "filters": [...],
    "aggregation": {...},
    "threshold": {...},
    "alert_condition": {...}
}
```

See `config_models.py` for Pydantic schemas.
