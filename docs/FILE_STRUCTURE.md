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
├── frontend/                         # Next.js React frontend
│   ├── src/
│   │   ├── app/                      # Next.js 13+ App Router
│   │   │   ├── page.tsx              # Landing & auth page
│   │   │   ├── layout.tsx            # Root layout
│   │   │   └── dashboard/            # Dashboard pages
│   │   │       ├── page.tsx          # Dashboard home
│   │   │       └── reports/          # Simulation reports
│   │   │           └── page.tsx
│   │   │
│   │   ├── components/               # Reusable components
│   │   │   └── TTLCountdown.tsx      # Data expiry countdown
│   │   │
│   │   ├── lib/                      # Utilities
│   │   │   └── api.ts                # Axios API client
│   │   │
│   │   └── store/                    # State management
│   │       └── useSessionStore.ts    # Zustand session store
│   │
│   ├── public/                       # Static assets
│   ├── README.md                     # Frontend documentation
│   ├── package.json                  # Node dependencies
│   ├── next.config.js                # Next.js configuration
│   ├── tailwind.config.ts            # Tailwind CSS config
│   └── Dockerfile                    # Production build
│
├── docs/                             # Documentation
│   └── mermaid_flowchart.md          # System architecture diagrams
│
├── docker-compose.yml                # Full stack orchestration
├── .env.example                      # Environment template
├── README.md                         # Main project README
└── mermaid_flowchart.md              # Flowcharts & diagrams
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

### Frontend (TypeScript/React)
- **PascalCase** for components: `TTLCountdown.tsx`
- **camelCase** for utilities: `api.ts`
- **kebab-case** for routes: `dashboard/reports/`

## 🔍 Finding Code

### "Where is the simulation logic?"
→ `backend/core/universal_engine.py`

### "Where are the API endpoints?"
→ `backend/api/` (organized by domain)

### "Where is the frontend dashboard?"
→ `frontend/src/app/dashboard/page.tsx`

### "Where are the tests?"
→ `backend/tests/`

### "Where is the Docker setup?"
→ `docker-compose.yml` + `Dockerfile` in backend/frontend

## 🚀 Quick Start Paths

### Run Full Stack:
```bash
docker-compose up -d
```

### Run Backend Only:
```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload
```

### Run Frontend Only:
```bash
cd frontend
npm run dev
```

### Run Tests:
```bash
cd backend
pytest tests/ -v
```

## 📊 Data Flow Through Files

```
1. User uploads CSV
   → frontend/src/app/dashboard/page.tsx
   → backend/api/data.py (upload_transactions)
   → backend/services/data_ingestion_service.py
   → backend/core/ttl_manager.py
   → backend/models.py (Transaction, DataUploads)

2. User runs simulation
   → frontend/src/app/dashboard/page.tsx
   → backend/api/simulation.py (start_simulation)
   → backend/services/simulation_service.py
   → backend/core/universal_engine.py
   → backend/core/smart_layer.py
   → backend/core/risk_engine.py
   → backend/models.py (Alert, SimulationRun)

3. User views results
   → frontend/src/app/dashboard/reports/page.tsx
   → backend/api/dashboard.py (get_dashboard_stats)
   → backend/models.py (queries)
```

## 🔧 Configuration Files

| File | Purpose |
|------|---------|
| `backend/requirements.txt` | Python dependencies |
| `backend/pyproject.toml` | Pytest & coverage config |
| `frontend/package.json` | Node dependencies |
| `frontend/next.config.js` | Next.js configuration |
| `frontend/tailwind.config.ts` | Tailwind CSS setup |
| `docker-compose.yml` | Multi-service orchestration |
| `.env.example` | Environment variables template |

## 📚 Documentation Files

| File | Content |
|------|---------|
| `README.md` (root) | Project overview & quick start |
| `backend/core/README.md` | Core modules documentation |
| `backend/api/README.md` | API endpoints documentation |
| `frontend/README.md` | Frontend structure & components |
| `mermaid_flowchart.md` | System architecture diagrams |
| `docs/ARCHITECTURE.md` | (TODO) Detailed architecture |

## 🎨 Asset Organization

### Backend
- No static assets (API only)
- Logs → `logs/` (gitignored)
- Uploads → Database (TTL managed)

### Frontend
- Images → `frontend/public/images/`
- Icons → Lucide React (no files)
- Styles → Tailwind (utility classes)

## 🔐 Security Files

| File | Purpose | Gitignored? |
|------|---------|-------------|
| `.env` | Environment secrets | ✅ Yes |
| `.env.example` | Template (no secrets) | ❌ No |
| `backend/auth.py` | JWT validation | ❌ No |
| `frontend/src/lib/api.ts` | API client | ❌ No |
