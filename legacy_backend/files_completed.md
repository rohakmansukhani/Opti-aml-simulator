# Backend Migration Status

Legend:
- [x] : Fully Migrated / Ported
- [/] : Partially Migrated / In Progress
- [ ] : Pending
- [-] : Deprecated / Not Needed

## Root
- [x] `models.py` -> `simulation/models.py`
- [-] `main.py` (Replaced by Django `manage.py` + `config.wsgi`)
- [-] `database.py` (Replaced by `settings.py` + Django ORM)
- [-] `auth.py` (Replaced by Django Auth)
- [-] `Dockerfile` (Using local dev / Oracle Docker)

## API (`api/`)
- [x] `admin.py` -> `api/api.py` (Merged)
- [x] `comparison.py` -> `api/api.py` (Comparison Endpoints)
- [x] `dashboard.py` -> `api/api.py` (Dashboard Stats)
- [x] `data.py` -> `api/api.py` (Upload Endpoints)
- [x] `fields.py` -> `api/api.py` (Field Discovery Endpoints)
- [x] `investigation.py` -> `api/api.py` (Investigation Enpdoints)
- [x] `risk.py` -> `api/api.py` (Verification Endpoint)
- [x] `rules.py` -> `api/api.py` (Scenario CRUD Endpoints)
- [x] `simulation.py` -> `api/api.py` (Simulation Endpoints)
- [x] `validation.py` -> `api/api.py` (Filter Validation Endpoint)

## Core (`core/`)
- [x] `config_models.py` -> `core/config_models.py`
- [-] `data_quality.py` (Not critical for MVP)
- [x] `field_mapper.py` -> `core/field_mapper.py`
- [-] `rate_limiting.py` (Use Django middleware)
- [-] `redis_client.py` (Optional caching)
- [x] `risk_engine.py` -> `simulation/engines/risk_engine.py`
- [x] `smart_layer.py` -> `simulation/engines/smart_layer.py`
- [x] `ttl_manager.py` -> `simulation/services/ttl_manager.py`
- [x] `universal_engine.py` -> `simulation/engines/universal_engine.py`
- [x] `upload_validator.py` -> `core/upload_validator.py`

## Services (`services/`)
- [x] `comparison_service.py` -> `simulation/engines/comparison_engine.py`
- [x] `data_ingestion.py` -> `simulation/services/data_ingestion.py`
- [x] `simulation_service.py` -> `simulation/services/simulation_service.py`

## Tasks (`tasks/`)
- [-] `cleanup_cron.py` (Use Django management commands)
- [-] `tasks.py` (Use Celery for async tasks)
