# Celery Background Tasks Guide

The SAS Sandbox Simulator uses **Celery** to process long-running simulations (10-45 seconds) in the background. This prevents HTTP timeouts and ensures a smooth user experience.

## Infrastructure

- **Broker/Backend**: Upstash Redis (Serverless)
- **Framework**: Celery 5.x
- **Worker**: Python-based worker using the backend logic

## Configuration

The Celery configuration is located in `backend/tasks.py`. It uses the `REDIS_URL` environment variable for both the message broker and the result backend.

```python
app = Celery('sas_simulator')
app.conf.broker_url = os.getenv('REDIS_URL')
app.conf.result_backend = os.getenv('REDIS_URL')
```

## Running the Worker

To execute simulations in the background, you must start at least one Celery worker.

### Local Development (Virtual Env)
```bash
cd backend
source venv/bin/activate
# Start the worker
celery -A tasks worker --loglevel=info
```

### via Docker Compose
The worker is already defined in `docker-compose.yml` as the `celery` service.
```bash
docker-compose up -d celery
```

## Running the Scheduler (Beat)

The scheduler is responsible for periodic tasks, such as cleaning up expired TTL data every 24 hours.

```bash
cd backend
celery -A tasks beat --loglevel=info
```

## Task Progress Tracking

The frontend can track simulation progress by polling the Celery task ID. Note that we also update the `SimulationRun` status in the database for persistence.

- **STARTED**: Simulation has been picked up by a worker.
- **PROGRESS**: Simulation is currently calculating metrics.
- **SUCCESS**: Simulation completed successfully.
- **FAILURE**: Simulation failed (error details in task metadata).
