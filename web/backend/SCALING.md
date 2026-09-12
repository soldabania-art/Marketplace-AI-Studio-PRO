# Backend scaling baseline

TROVENDI must be designed for at least 1,000 active client accounts and should avoid architectural limits that force a rewrite before 10,000 clients.

## Tenant isolation

Every business record, background job, cache key, marketplace connection and external action must remain scoped to an authorized workspace/store. Frontend-selected store IDs are never trusted as authorization; backend membership/store access checks remain authoritative.

## FBO monitoring

Production FBO monitoring runs in dedicated worker processes, not inside HTTP request handlers. Multiple replicas are allowed.

The current coordinator:
- snapshots only enabled FBO account/store identifiers;
- uses bounded concurrency instead of creating unbounded external requests;
- polls Wildberries once per store/account and fans results out to watches;
- uses PostgreSQL advisory locks so two worker replicas do not poll the same store concurrently;
- enforces a minimum per-account polling interval after the lock is acquired;
- adds cycle jitter to reduce synchronized bursts after deploy/restart;
- reports cycle counters for checked accounts, watches, pushes, lock skips, pacing skips, missing connections and failures.

SQLite is development-only for distributed scheduling. Its lock fallback is process-local and must not be treated as multi-host coordination.

## Database

Production target is PostgreSQL with connection pooling and Alembic migrations. API and workers use independent processes and can be scaled horizontally. Pool sizing must be configured together with process/replica counts so the aggregate connection count remains below the database service limit.

## Implemented queue and next scaling gate

The PostgreSQL BackgroundJob queue and separate worker are already implemented. Redis-backed marketplace rate limiting also exists in app/rate_limit.py. Their presence is not evidence that production uses the right settings.

Before scaling, close T08 in ../DEVELOPER_BACKLOG.md: renewable job leases, attempt fencing, transactionally coupled state/events/jobs, safe advisory-lock connection ownership, bounded retries and replay. A running job is currently reclaimable after the configured lease without heartbeat; multi-worker safety is not certified by SQLite tests.

Configure the shared limiter for API and worker processes, even when there is only one worker replica. Validate behavior on Redis failure and provider 429 without silently falling back to independent memory buckets. Measure queue age and source freshness before adding replicas.

## Capacity testing before commercial launch

Load tests must cover at minimum:
- 1,000+ authenticated client accounts;
- multiple stores per workspace;
- concurrent dashboard reads;
- scheduled marketplace sync jobs;
- FBO monitoring with multiple worker replicas;
- Web Push fan-out;
- database pool exhaustion behavior;
- one-tenant-cannot-read-another-tenant tests;
- retry storms and marketplace 429/5xx behavior.

No production capacity claim is made until these tests run against the actual hosted backend/database/worker stack.
