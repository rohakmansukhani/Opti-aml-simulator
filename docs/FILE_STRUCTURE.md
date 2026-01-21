# File Structure Guide

## 📂 Project Organization

```
sas simulator/
│
├── backend/                          # Python FastAPI backend
│   ├── api/                          # API route handlers
│   │   ├── README.md                 # API documentation
│   │   ├── data.py                   # Data upload & TTL endpoints
│   │   ├── simulation.py             # Simulation execution endpoints
│   │   ├── rules.py                  # Scenario management
│   │   ├── scenario_config.py        # Advanced config endpoints
│   │   ├── dashboard.py              # Dashboard statistics
│   │   ├── comparison.py             # Simulation comparison
│   │   └── risk.py                   # Risk analysis endpoints
│   │
│   ├── core/                         # Business logic & engines
│   │   ├── README.md                 # Core modules documentation
│   │   ├── universal_engine.py       # Main scenario execution engine
│   │   ├── smart_layer.py            # Alert refinement (vectorized)
│   │   ├── risk_engine.py            # Risk scoring & gap analysis
│   │   ├── event_detector.py         # Transaction context detection
│   │   ├── ttl_manager.py            # Data lifecycle management
│   │   └── config_models.py          # Pydantic schemas
│   │
│   ├── services/                     # Orchestration services
│   │   ├── simulation_service.py     # Simulation orchestration
│   │   └── data_ingestion_service.py # CSV/Excel processing
│   │
│   ├── tests/                        # Pytest test suite
│   │   ├── conftest.py               # Test fixtures & config
│   │   ├── test_simulation.py        # Simulation endpoint tests
│   │   ├── test_data.py              # Data upload tests
│   │   └── test_auth.py              # Authentication tests
│   │
│   ├── main.py                       # FastAPI app entry point
│   ├── database.py                   # SQLAlchemy setup
│   ├── models.py                     # Database models
│   ├── auth.py                       # Supabase authentication
│   ├── requirements.txt              # Python dependencies
│   ├── Dockerfile                    # Multi-stage production build
│   ├── .dockerignore                 # Docker ignore patterns
│   └── pyproject.toml                # Pytest & coverage config
│
├── docs/                             # Documentation
│   ├── ARCHITECTURE.md               # System Architecture
│   ├── PRD.md                        # Product Requirements
│   ├── API_TESTING.md                # API Curl Tests
│   └── ...
│
├── docker-compose.yml                # Full stack orchestration
├── .env.example                      # Environment template
└── README.md                         # Main project README
```

## 🎯 Key Principles

### 1. Separation of Concerns
- **API Layer** (`api/`): HTTP request/response handling
- **Business Logic** (`core/`): Pure business logic, no HTTP
- **Services** (`services/`): Orchestration between layers
- **Models** (`models.py`): Database schema only

### 2. Modularity
- Each module has single responsibility
- Clear interfaces between modules
- Easy to test in isolation

### 3. Documentation
- README in each major directory
- Inline comments for complex logic
- Mermaid diagrams for visual understanding

## 📝 File Naming Conventions

### Backend (Python)
- **snake_case** for files: `simulation_service.py`
- **PascalCase** for classes: `UniversalScenarioEngine`
- **snake_case** for functions: `execute_scenarios()`

## 🔍 Finding Code

### "Where is the simulation logic?"
→ `backend/core/universal_engine.py`

### "Where are the API endpoints?"
→ `backend/api/` (organized by domain)

### "Where are the tests?"
→ `backend/tests/`

### "Where is the Docker setup?"
→ `docker-compose.yml` + `Dockerfile` in backend

## 🚀 Quick Start Paths

### Run Backend:
```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload
```

### Run Tests:
```bash
cd backend
pytest tests/ -v
```

## 🔧 Configuration Files

| File | Purpose |
|------|---------|
| `backend/requirements.txt` | Backend Python dependencies |
| `backend/pyproject.toml` | Pytest & coverage config |
| `docker-compose.yml` | Multi-service orchestration |
| `.env.example` | Environment variables template |

## 🎨 Asset Organization

### Backend
- No static assets (API only)
- Logs → `logs/` (gitignored)
- Uploads → Database (TTL managed)

## 🔐 Security Files

| File | Purpose | Gitignored? |
|------|---------|-------------|
| `.env` | Environment secrets | ✅ Yes |
| `.env.example` | Template (no secrets) | ❌ No |
| `backend/auth.py` | JWT validation | ❌ No |
