# Backend staging / production deployment contract

TROVENDI uses one container image with separate process roles.

## Required services

1. **API service**
   - Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Health: `/health`
   - Readiness: `/ready`
   - Must not run the embedded FBO monitor in production: `MARKETPLACE_RUN_FBO_MONITOR_IN_API=false`.

2. **Worker service**
   - Command: `python -m app.worker`
   - Uses the same image/environment as API.
   - Runs durable job consumers, the lightweight FBO scheduler and automatic marketplace sync scheduler.
   - Automatic sync defaults: core WB analytics every 30 minutes when due; finance and advertising daily. Override only through the documented `MARKETPLACE_SYNC_*` environment settings after checking provider quotas.

3. **PostgreSQL**
   - Shared by API + workers.
   - `MARKETPLACE_DATABASE_URL` must point to managed PostgreSQL and require TLS in staging/production; certificate verification with `sslmode=verify-full` is preferred.
   - Public database ingress must be disabled or temporarily restricted to a narrow provider/IP allowlist.
   - Runtime credentials must use a non-owner, non-DDL role. See `../DATABASE_SECURITY_RUNBOOK.md`.

4. **Migration step**
   - Run once before deploying new API/worker revisions: `alembic upgrade head`.
   - Do not run migrations independently in every API replica.

## Required production environment

- `MARKETPLACE_ENVIRONMENT=production`
- `MARKETPLACE_DATABASE_URL`
- `MARKETPLACE_JWT_SECRET` — long random secret, never committed
- `MARKETPLACE_MARKETPLACE_TOKEN_KEY` — temporary Fernet provider key until managed SecretProvider/KMS rollout
- `MARKETPLACE_MFA_ENCRYPTION_KEY` — a separate Fernet key for TOTP secrets; never reuse the marketplace-token key
- `MARKETPLACE_FRONTEND_URL`
- `MARKETPLACE_MARKETPLACE_LIMITER_BACKEND=redis` — обязателен в production; memory разрешён только для локальной разработки
- `MARKETPLACE_REDIS_URL` — единый Redis для API и workers, использующих один provider account
- `MARKETPLACE_MARKETPLACE_LIMITER_MAX_WAIT_SECONDS` — максимальное ожидание общей квоты до контролируемого 429/retry (по умолчанию 65 секунд)
- `MARKETPLACE_BILLING_PROVIDER` — remains `not_configured` until a contracted RF/CIS provider adapter verifies checkout and webhook events server-side
- `MARKETPLACE_OPENAI_API_KEY` — server-only key for AI Card Factory; never expose it to the frontend
- `MARKETPLACE_OPENAI_MODEL` — optional model override (defaults to `gpt-5.6-terra`)
- `MARKETPLACE_OPENAI_IMAGE_MODEL` — image editor (defaults to economical `gpt-image-1-mini`)
- `MARKETPLACE_OPENAI_IMAGE_QUALITY`, `MARKETPLACE_OPENAI_IMAGE_SIZE` — trial defaults are `low` and `1024x1024`
- `MARKETPLACE_OPENAI_IMAGE_ESTIMATED_COST_MICROUSD` — current provider estimate used for budgets and audit
- `MARKETPLACE_ASSET_BLOB_HOSTS` — comma-separated exact hostnames of the dedicated public Vercel Blob store; wildcards and generic `*.blob.vercel-storage.com` trust are forbidden
- `MARKETPLACE_MEDIA_SUBMITTING_RECOVERY_SECONDS` — legacy compatibility setting; elapsed time never authorizes a retry of an uncertain upload. Read-only reconciliation preserves the blocked state until the outcome is established.
- `MARKETPLACE_DOCUMENT_SCAN_WEBHOOK_SECRET` — long independent secret used to authenticate malware scan results
- Frontend: `DOCUMENT_BLOB_READ_WRITE_TOKEN` must belong to a dedicated **private** Blob store used only for document evidence
- VAPID settings when Web Push is enabled

The API intentionally refuses production startup when PostgreSQL, TLS, HTTPS, the JWT secret, the marketplace credential-encryption key or the separate MFA-encryption key is missing. Do not weaken these checks to make a deployment pass.

Frontend must set `MARKETPLACE_API_URL` to the externally reachable API base URL. Connect a public Vercel Blob store to the frontend project; Vercel supplies `BLOB_STORE_ID` + rotating `VERCEL_OIDC_TOKEN`, or `BLOB_READ_WRITE_TOKEN` only for a non-OIDC/manual setup. Generated marketplace visuals use exact immutable paths `ai-assets/{store}/{nm_id}/{generation_id}.webp` and are never written when Blob credentials are absent. The backend downloads the object, computes its digest and accepts it only when its exact hostname is listed in `MARKETPLACE_ASSET_BLOB_HOSTS`.

## Scaling policy

Start <=100 clients with one API service and one worker service. Scale worker replicas first when queue latency rises. API and worker replicas must remain stateless apart from PostgreSQL/external coordination. The implemented Redis limiter must be configured for all API and worker processes that share provider quotas. Memory limiting is process-local and is not sufficient across API/worker boundaries. Verify queue heartbeat/fencing and scheduler locking under T08 before horizontal worker scaling.

`MARKETPLACE_JOB_HEARTBEAT_SECONDS` must remain materially lower than `MARKETPLACE_JOB_LEASE_SECONDS` (defaults: 30 and 300 seconds). Heartbeat runs outside the handler event loop. Every claim receives a new attempt ID; only that attempt may commit handler state, enqueue child jobs, finish or enter retry. This fencing prevents stale database results, but it does not promise exactly-once external HTTP. A timed-out marketplace write remains subject to the existing STOP gate and read-before-retry reconciliation.

## Deploy safety

Deployment order:

`backup/check -> stop old job claims and schedulers -> drain/stop old handlers -> alembic upgrade head -> deploy API -> verify /ready -> deploy worker -> verify heartbeat/recovery and queue/FBO logs -> frontend`

For the attempt-ownership migration, confirm every old worker has exited before enabling new consumers. Do not mix workers without fencing with the new version. Disable automatic restarts of the old revision during rollout. If a handler cannot drain, stop it and preserve its durable state for recovery; stopping the process does not establish whether a provider accepted an in-flight HTTP write. Reconcile uncertain writes read-only before any retry. A backward-compatible schema alone does not make rollback to unfenced workers safe. This is a deployment requirement, not a claim that production rollout has been verified.

Rollback application images only when the database migration is backward compatible. Destructive migrations require an explicit expand/migrate/contract rollout and a backup/restore plan.
