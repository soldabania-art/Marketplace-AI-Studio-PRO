# Backend scaling baseline

Marketplace AI Studio must be designed for at least 1,000 active client accounts and should avoid architectural limits that force a rewrite before 10,000 clients.

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

## Next scaling step

For heavier background workloads (catalog sync, ads, reviews, finance, Market Intelligence and AI jobs), introduce a durable queue with explicit job idempotency, retry/backoff, visibility/lease timeout and dead-letter handling. FBO account polling can continue to use database-coordinated leases until workload/latency data justifies moving scheduling to the queue.

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
