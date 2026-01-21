# Production Deployment Checklist & Guide

This document outlines the steps and best practices for deploying the SAS Sandbox Simulator to a production environment.

## 1. Environment Configuration

Ensure your `.env` (or environment variables in your deployment platform) is fully populated:

| Variable | Description | Requirement |
|----------|-------------|-------------|
| `DATABASE_URL` | PostgreSQL connection string | **Required** |
| `REDIS_URL` | Upstash Redis URL (redis://:pw@host:port) | **Required** |
| `SUPABASE_URL` | Your Supabase Project URL | **Required** |
| `SUPABASE_KEY` | Supabase Service Key (for backend) | **Required** |
| `ENVIRONMENT` | Set to `production` | **Required** |
| `ALLOWED_ORIGINS`| CORS allowed domains (e.g. client app) | **Optional** |

## 2. Security Hardening

- **Rate Limiting**: The API has built-in rate limiting (200 requests/min). Monitor logs for any unexpected 429 errors.
- **Auth**: Ensure `SUPABASE_URL` corresponds to your production project with correct RLS policies.
- **Health Checks**: Use `/health` for Kubernetes liveness/readiness or UptimeRobot monitoring. Returns `503` if dependent services (DB/Redis) are down.

## 3. Worker Strategy

For production, it is critical to have the Celery worker running. 

- **Memory**: Ensure the worker has at least 1GB of RAM for large DataFrame operations.
- **Concurrency**: Use `--concurrency=2` or higher depending on expected simultaneous users.
- **Order of Cleanup**: TTL cleanup is managed by Celery Beat. Ensure a single instance of `celery beat` is running to avoid duplicate cleanup jobs.

## 4. Monitoring & Observability

- **Prometheus/Grafana**: Scrape the `/metrics` endpoint to monitor alert volume, processing times, and memory usage.
- **Structured Logs**: Logs are output in JSON format, making them ready for ingestion by ELK stack or New Relic.

## 5. Known Limitations

- **Dataset Size**: Large datasets (>100k records) should use an external PostgreSQL connection via the dashboard for better performance.
- **TTL**: Data uploaded via CSV is automatically deleted after 48 hours unless extended.
