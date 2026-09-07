# Backend staging / production deployment contract

Marketplace AI Studio Cloud uses one container image with separate process roles.

## Required services

1. **API service**
   - Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Health: `/health`
   - Readiness: `/ready`
   - Must not run the embedded FBO monitor in production: `MARKETPLACE_RUN_FBO_MONITOR_IN_API=false`.

2. **Worker service**
   - Command: `python -m app.worker`
   - Uses the same image/environment as API.
   - Runs the durable job consumers and lightweight FBO scheduler.

3. **PostgreSQL**
   - Shared by API + workers.
   - `MARKETPLACE_DATABASE_URL` must point to managed PostgreSQL in staging/production.

4. **Migration step**
   - Run once before deploying new API/worker revisions: `alembic upgrade head`.
   - Do not run migrations independently in every API replica.

## Required production environment

- `MARKETPLACE_ENVIRONMENT=production`
- `MARKETPLACE_DATABASE_URL`
- `MARKETPLACE_JWT_SECRET` — long random secret, never committed
- `MARKETPLACE_MARKETPLACE_TOKEN_KEY` — temporary Fernet provider key until managed SecretProvider/KMS rollout
- `MARKETPLACE_FRONTEND_URL`
- VAPID settings when Web Push is enabled

Frontend must set `MARKETPLACE_API_URL` to the externally reachable API base URL.

## Scaling policy

Start <=100 clients with one API service and one worker service. Scale worker replicas first when queue latency rises. API and worker replicas must remain stateless apart from PostgreSQL/external coordination. The current local marketplace limiter is not safe for multi-replica rate-limit coordination; distributed Redis/Upstash limiter is a launch gate before horizontally scaling marketplace workers.

## Deploy safety

Deployment order:

`backup/check -> alembic upgrade head -> deploy API -> verify /ready -> deploy worker -> verify queue/FBO logs -> frontend`

Rollback application images only when the database migration is backward compatible. Destructive migrations require an explicit expand/migrate/contract rollout and a backup/restore plan.
