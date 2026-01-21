# Quick Start Guide

## 🚀 Run with Docker (Recommended)

```bash
# 1. Copy environment template
cp .env.example .env

# 2. (Optional) Edit .env to change passwords
nano .env

# 3. Start all services
docker-compose up -d

# 4. Check health
curl http://localhost:8000/health

# 5. Access application
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## 📊 What's Running?

| Service | Port | Purpose |
|---------|------|---------|
| Backend | 8000 | FastAPI server |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Celery queue |
| Celery Worker | - | Background tasks |

## 🛑 Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (deletes data!)
docker-compose down -v
```

## 📝 View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend

# Last 100 lines
docker-compose logs --tail=100 backend
```

## 🔧 Common Commands

```bash
# Rebuild after code changes
docker-compose up -d --build

# Restart specific service
docker-compose restart backend

# Access PostgreSQL
docker-compose exec postgres psql -U postgres -d sas_simulator

# Access backend shell
docker-compose exec backend bash

# Run tests
docker-compose exec backend pytest tests/ -v
```

## ⚙️ Configuration

### Required Settings
- `POSTGRES_PASSWORD` - Change in production!

### Optional Settings
- `SENTRY_DSN` - Error tracking (leave empty to disable)
- `ALLOWED_ORIGINS` - CORS origins for production

## 🐛 Troubleshooting

### "Port already in use"
```bash
# Find process using port
lsof -i :8000

# Kill process
kill -9 <PID>
```

### "Database connection failed"
```bash
# Check postgres is running
docker-compose ps postgres

# View postgres logs
docker-compose logs postgres
```

## 📈 Production Deployment

For production, use separate docker-compose.prod.yml:
- Remove volume mounts (no hot-reload)
- Use production Dockerfiles
- Set strong passwords
- Enable HTTPS
- Configure Sentry for error tracking

See [README.md](README.md) for full deployment guide.
