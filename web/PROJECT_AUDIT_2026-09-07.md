# TROVENDI — full project audit

Date: 2026-09-07
Scope: web SaaS, FastAPI backend, background workers, marketplace integration foundation, security, billing, legal, CI/deployment, and legacy desktop code present in the repository.

## Executive conclusion

The repository is no longer a visual prototype only: it has a real authentication/session foundation, workspace/store isolation, encrypted WB connection storage, Alembic migrations, durable PostgreSQL-oriented jobs, an FBO watcher with Web Push, a per-token marketplace limiter abstraction, and the first live Smart FBO data path.

However, the product is **not production-launch ready yet**. The largest gap is not UI polish; it is the missing verified production runtime around the code: always-on FastAPI + worker hosting, production PostgreSQL/migrations, distributed rate limiting/cache, secrets provider, payment webhooks, transactional email, observability, and end-to-end tenant/security tests. A large part of the seller-facing UI still intentionally shows demo/static data.

The correct strategy remains: launch cheaply for the first <=100 clients, but keep the same architecture when scaling toward 1,000-10,000+ clients.

## What is already structurally strong

### Multi-tenant/store foundation
- `User -> Membership -> Workspace -> Store -> MarketplaceConnection` exists.
- Seller-facing backend operations can resolve and authorize an explicit store.
- WB connection is store-scoped.
- Smart FBO API is store-scoped and tests denial of inaccessible stores.
- This is the correct base for later Agency Mode.

### Authentication/security baseline
- Password hashing uses the recommended `pwdlib` password hash.
- Access JWT includes a database session ID and sessions can be revoked.
- Password/email action tokens are one-time/hash-based in the account subsystem.
- Marketplace tokens are encrypted before persistence and plaintext tokens are not returned to the browser.
- Session cookies are HttpOnly, Secure in production, and SameSite=Lax at the Next.js BFF layer.

### Background execution/scaling foundation
- A dedicated worker entrypoint exists separately from the HTTP API.
- Durable jobs persist in the database with status, retry, max attempts, lease, idempotency key, priority and dead state.
- PostgreSQL job claiming uses `FOR UPDATE SKIP LOCKED`.
- FBO polling is scheduled as durable `fbo.poll` jobs rather than doing all work in request handlers.
- Per-store FBO work also has a distributed PostgreSQL advisory lock.
- Queue priority aging prevents indefinite starvation of lower-priority clients.

### Database evolution
- Alembic is present.
- Store-scoping migration and background-job migration exist.
- Production API no longer relies on `create_all()` for schema evolution; local development still can.

### FBO / Smart FBO
- WB acceptance slot monitoring uses the current official acceptance-coefficients API path.
- Web Push infrastructure and subscription persistence exist.
- Smart FBO deterministic math calculates reorder point, target stock, days of cover and recommended quantity with provenance.
- `/api/v1/smart-fbo/live` now reads official WB Analytics current warehouse inventory plus the recent sales funnel and acceptance slots.
- Live v1 intentionally calculates replenishment quantity at **SKU / WB-network level**. It does **not** fake allocation of that quantity between warehouses. Warehouse allocation remains pending until regional/warehouse demand is sourced in a scalable, verified way.

### CI baseline
- GitHub Actions builds the Next.js frontend and runs backend pytest tests on pushes affecting `web/**`.

## P0 — must be completed before taking production money or connecting many live stores

### 1. Deploy and verify the real backend + worker
Current Vercel deployment is frontend-oriented. The FastAPI API and worker require an always-on runtime. Production must have:
- FastAPI service;
- separate worker service;
- production PostgreSQL;
- Alembic migration step before app rollout;
- `MARKETPLACE_API_URL` configured in the frontend environment;
- health/readiness checks;
- restart policy and monitoring.

Recommended start: Vercel for web + managed Postgres/Supabase + Railway/another always-on container runtime for FastAPI/workers. Provider choice must remain replaceable.

### 2. Replace in-process marketplace rate limiting for multi-replica production
`rate_limit.py` correctly scopes keys by marketplace + hashed token fingerprint + endpoint, but its state is currently process-local. With several worker replicas, each process can independently send requests and collectively exceed marketplace limits.

Before horizontal worker scaling, implement a distributed limiter backend (Redis/Upstash or equivalent), with endpoint-specific official limits and retry-after handling. Keep the current interface so WB/Ozon callers do not change.

### 3. Production secret provider
Marketplace tokens are encrypted with Fernet, which is better than plaintext, but the encryption key is still an application environment secret. Add a `SecretProvider` abstraction and production implementation backed by a managed KMS/Vault or equivalent. Requirements:
- key rotation;
- no raw token in logs/events/admin UI;
- least-privilege runtime access;
- audit secret operations;
- migration path from current Fernet ciphertext.

### 4. Payments are not a real subscription system yet
The checkout page only redirects to optional `NEXT_PUBLIC_PAYMENT_*_URL` values. Production needs:
- server-created checkout/payment session;
- signed webhook verification;
- idempotent webhook processing;
- subscription state transitions;
- failed payment/grace-period handling;
- receipts/invoices required by target jurisdiction/provider;
- cancellation/renewal handling;
- admin payment history and reconciliation;
- plan/usage enforcement on backend, not only UI.

### 5. Real email delivery
Verification/password-recovery logic exists, but production transactional email delivery must be connected and monitored. Add delivery provider abstraction, retry, bounce handling and rate limits.

### 6. Finish tenant isolation/RBAC for Agency Mode
Current membership grants workspace-wide access. Agency employees eventually need assignment to specific client stores. Add `StoreAccess` / assignment entities and enforce them inside store resolution. Then add tests proving:
- cross-workspace store access denied;
- agency employee sees only assigned stores;
- client viewer cannot reach admin/token/payment actions;
- bulk actions only operate on explicitly authorized stores.

### 7. External-write audit log
Marketplace connect/disconnect and every future write to price/card/ads/reviews/claims must create an immutable audit record with actor, workspace, store, action, before/after, result and correlation/job ID. Sensitive values must be redacted.

### 8. Production observability
Need structured logs, request/job correlation IDs, exception tracking, metrics and alerts for:
- API latency/error rate;
- queue depth/oldest job/dead jobs;
- WB/Ozon 401/403/429/5xx;
- worker heartbeat;
- push failures;
- DB pool pressure;
- AI cost/quota use;
- payment webhook failures.

### 9. Repository/deployment protection
`main` is currently unprotected. Before commercial launch enable protected main, required CI checks, dependency/security scanning, secret scanning and controlled production deploys.

## P1 — product functionality required for a sellable first release

### Dashboard
The current dashboard KPI values and several AI priorities remain static demo data. Replace them with store-scoped backend aggregates and clear freshness timestamps.

### Products
Product UX exists, but real marketplace catalog import/sync is still incomplete. Implement WB first:
- content/cards;
- SKU/nmId mapping;
- stocks;
- prices/discounts where permitted;
- sync timestamps and errors.

### Smart FBO next step
Current live v1 is deliberately conservative. Next phase:
1. persist normalized WB stock and sales snapshots instead of fetching large reports interactively every time;
2. sync them through durable jobs;
3. derive SKU velocity from persisted snapshots;
4. add scalable regional/warehouse demand inputs;
5. allocate recommended quantity across warehouses only when supported by actual demand facts;
6. intersect allocation with acceptance slots/tariffs;
7. create watch automatically when a recommended destination has no acceptable slot;
8. Push/Telegram/Android notification when the needed slot appears.

### Ozon
Ozon store connection, products, inventory, finance, ads and FBO slot workflows are not yet verified/implemented to the same level as WB. Do not label Ozon modules live until each official API capability is verified.

### Profit Center
Calculator exists, but a commercial Profit Center needs actual marketplace payout/commission/logistics/storage/ads/returns/penalties + seller COGS + tax assumptions and reconciliation to marketplace settlements.

### Commission auto-load
Current contract intentionally fails closed until real tariff integration. Implement marketplace/category-specific tariff data with source timestamp and cache.

### Ads / SEO / Reviews / Reports / Autopilot
Most of these sections are currently store-aware UX shells. Each should move from `StudioSection` placeholder behavior to live data/actions one module at a time. Do not make visible buttons that only look functional.

### AI Card Factory
The web Card Factory currently has deterministic/local copy behavior rather than the final AI service. Production design should use AI Router + quotas + provenance:
- confirmed product facts only;
- separate marketplace prompts/rules;
- image generation/editing jobs;
- cost limits;
- cache;
- moderation/compliance checks;
- diff/approval before publish.

### AI Director
Build it on deterministic module outputs and evidence. It should prioritize by expected financial impact, confidence and urgency, but must not invent marketplace facts.

## P2 — scale and margin work after first commercial release

### AI cost control
Implement workspace/store usage ledger and plan budgets before enabling heavy generation at scale:
- request token/context caps;
- task-based AI Router;
- cheap/local model preference when quality allows;
- semantic/result cache;
- circuit breaker;
- daily/monthly workspace limits;
- cost per feature/store/client;
- admin margin dashboard.

### Redis/cache
Add distributed cache/coordination only where needed first: marketplace rate limiting, short-lived API cache, idempotency/locks if DB becomes a bottleneck, and AI cache. Avoid making Redis a mandatory dependency for local development.

### OLTP vs analytics
PostgreSQL is appropriate for the first release. Do not add ClickHouse/BigQuery prematurely. Instead:
- use append-only normalized facts/snapshots;
- pre-aggregate expensive reports in jobs;
- keep analytical access behind repository/service interfaces;
- move high-volume history to OLAP later without changing product contracts.

## Frontend/UX issues found

1. Global Store Context is the correct concept, but store switching in Account still writes `localStorage` directly in some paths rather than always using the shared store event helper; this can produce temporary selector/page desynchronization.
2. The global selector is rendered as a fixed overlay and should be visually rechecked across desktop/mobile headers for overlap.
3. Dashboard greeting is now personalized and deterministic without spending AI tokens; this is good. Later the daily advice can use AI Director facts, not a paid model call on every page load.
4. Many routes still contain demo values. Every live-looking number needs a `demo` label until sourced from backend.
5. Checkout must not say/appear fully operational until server-side payment integration is present.

## Backend/code issues found

1. The Wildberries Next.js BFF had an off-by-one relative import for `lib/backend`; fixed during this audit.
2. `get_current_session()` updates and commits `last_seen_at` on every authenticated request. At scale this creates unnecessary DB write amplification. Throttle last-seen writes (for example once every several minutes).
3. WB connection validation currently proves the token can call acceptance coefficients, but does not prove Analytics permission required by Smart FBO. Add permission/capability checks during onboarding and show a capability matrix.
4. Smart FBO live endpoint currently performs multiple marketplace calls in an interactive request. Move live data refresh to jobs + persisted snapshots; API should normally read the latest successful snapshot and optionally enqueue refresh.
5. Large stock responses can be very large. Persist/stream/process pages incrementally and avoid returning raw warehouse rows unnecessarily to the browser.
6. Durable queue needs an admin/developer view for queued/running/retry/dead jobs and a safe replay action.
7. Add retention/cleanup policy for finished jobs, security events, old sessions and snapshots.

## Legacy desktop code

The repository still contains the mature `studio/` desktop lineage with AI routing, connectors, automation, rollback/safety and many historical UI versions. Treat it as a source of proven domain logic, not as the deployment architecture for Cloud. New SaaS business logic should be moved deliberately into backend services with tenant/store scoping, tests and explicit API contracts instead of importing desktop UI/state directly.

The large number of historical `ui_v*.py` files is useful as history but increases maintenance/search noise. After Cloud reaches feature parity, archive or remove obsolete UI versions in a controlled cleanup branch.

## CI/testing gaps

Current CI builds frontend and runs backend tests. Add before production:
- frontend lint/type checking (or migrate critical frontend to TypeScript);
- lockfile-based install (`npm ci`) once lockfile is stable;
- Python formatting/lint/static checks;
- Alembic upgrade test against PostgreSQL, not SQLite only;
- tenant isolation tests;
- marketplace rate-limit/retry tests;
- queue concurrency/idempotency tests on PostgreSQL;
- security regression tests;
- payment webhook tests;
- browser smoke tests for all visible navigation/actions;
- load tests for 100, 1,000 and projected 10,000-client job patterns.

## Recommended execution order from this audit

### Phase A — production skeleton
1. Fix remaining frontend Store Context sync/overlap issues.
2. Deploy managed PostgreSQL and run Alembic in staging.
3. Deploy FastAPI and worker separately.
4. Wire `MARKETPLACE_API_URL` and verify auth end-to-end.
5. Add distributed marketplace limiter/cache abstraction implementation.
6. Add secret provider abstraction and production secret backend.
7. Add monitoring/structured logs/dead-job visibility.

### Phase B — first sellable WB product
1. WB catalog sync.
2. Persisted stock + sales snapshots.
3. Smart FBO live recommendations + automatic slot watch.
4. Profit Center real data baseline.
5. Dashboard real KPIs.
6. Card Factory AI Router baseline.
7. Ads/SEO/Reviews one by one, with no fake buttons.

### Phase C — commercial system
1. Production email.
2. Payment provider + signed webhooks + subscription limits.
3. legal consent evidence/versioning finalization.
4. admin payments/usage/audit/health.
5. onboarding capability checks for WB permissions.

### Phase D — expansion
1. Ozon verified integration.
2. Market Intelligence.
3. Promo Economics.
4. Claims & Disputes.
5. Growth Lab.
6. External Traffic Studio.
7. Agency store assignments/client portal.
8. Telegram and Android native push.

## Launch gates

Do not call the product production-ready until all are true:
- staging and production backend/worker are always-on and monitored;
- PostgreSQL migrations are verified and backed up;
- tenant isolation tests pass;
- secrets are production-grade and rotatable;
- payments/webhooks are server-side and idempotent;
- email verification/reset delivery works;
- no critical UI action is a decorative stub;
- core WB data sync is live and freshness is displayed;
- queue/dead jobs/429 handling are observable;
- dependency/security scans have no unresolved critical/high launch blockers;
- legal documents and consent evidence match the actual service/payment behavior.
