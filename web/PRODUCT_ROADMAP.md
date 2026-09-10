# TROVENDI — living product roadmap

Status: source of truth for product scope, priorities and delivery gates. Update this file whenever a product decision is accepted. A feature mentioned in chat but absent here is not yet scheduled.

Hierarchy view: [`PRODUCT_TREE.md`](./PRODUCT_TREE.md).

## 1. Product mission

Build an AI operating system for marketplace commerce in Russia and the CIS. It must work for three audiences without splitting into unrelated products:

1. **Beginner:** starts with one product photo and receives a safe, guided path from verified facts to publication and ongoing store management.
2. **Seller:** connects existing stores and receives profit visibility, operational alerts and measurable AI-assisted actions.
3. **Agency or team:** manages many stores with roles, approvals, client reporting and an audit trail.

The operating loop is:

`connect -> collect facts -> calculate -> recommend -> preview -> approve -> execute -> measure -> rollback if worse`

AI coordinates the work, but deterministic services remain authoritative for money, stock, limits, permissions and compliance rules.

## 2. Non-negotiable product rules

- Never invent a material, dimension, composition, certificate, package item or other product fact.
- An unknown fact stays unknown and is requested from the user.
- Publishing, price changes, advertising spend, responses to legal claims and destructive operations require explicit confirmation until the owner configures bounded autopilot permissions.
- Every AI result stores its input facts, model, cost, validation result and user decision.
- Every external write is idempotent, audited and reversible where the external system allows it.
- Store and organization data are tenant-isolated. Secrets are encrypted and never returned to the browser.
- Profit is calculated from source transactions and documented rules, not from an LLM estimate.
- We do not promise guaranteed income or replace legal, certification, tax or accounting professionals.

## 3. Beginner Launch Studio

### Core journey

1. Explain the next single action in plain language.
2. Accept one phone photo and optional SKU/name.
3. Let vision AI identify only visually supported facts and mark guesses with confidence.
4. Ask for missing non-visible facts, documents, cost price and available stock.
5. Freeze a confirmed fact set linked to the store and product project.
6. Generate marketplace-specific title, description, SEO, characteristic mapping and visual plan.
7. Generate and store visual assets when image generation is enabled.
8. Validate category requirements, restricted claims and unit economics.
9. Show a preview/diff and request publication confirmation.
10. Publish through the official marketplace API and hand the product to AI Director.

### Beginner trial — accepted decision

- Duration: **72 hours from the first successful AI photo analysis**, not from registration.
- Allowance: **5 successfully analysed cards**.
- Scope: one user and one connected store.
- Failed AI calls do not consume a card and do not start the clock.
- Existing projects remain readable after expiration; new AI work becomes read-only.
- No advertising autopilot, automatic price changes, automatic publication or bulk external writes.
- Trial includes photo analysis, grounded copy, SEO, visual plan and unit economics. AI image generation, marketplace publication and autonomous writes require a paid entitlement.
- Paid subscription removes trial limits according to the selected plan.

Current implementation includes the 72-hour clock, five-success quota, store-bound signed analysis, persisted projects, read-only enforcement and a central server entitlement snapshot. Durable public image storage is connected for paid Card Factory access; Beginner Studio reuse remains a delivery gate.

## 4. Seller and agency journeys

### Existing seller

1. Connect marketplace and accounting sources.
2. Import catalog, stock, orders, sales, returns, commissions and costs.
3. Reconcile data into a store profit view.
4. AI Director ranks issues by expected financial impact and confidence.
5. Seller reviews the evidence and proposed change.
6. The system executes only within granted permissions, then measures the result.

### Agency or team

- Organization, store and client portfolio hierarchy.
- Owner, administrator, manager, analyst and read-only roles.
- Per-client approval policies and spend limits.
- Bulk workflows with per-store validation and partial-failure reporting.
- White-label reports and client portal.
- Complete actor/action/result audit log.

## 5. AI Director and low-cost AI architecture

AI Director is the coordinator, not an unrestricted autonomous bot.

- Deterministic code handles arithmetic, reconciliation, permissions, quotas and marketplace rules.
- A low-cost model handles classification, extraction and routine rewriting.
- A stronger multimodal model is used only for ambiguous images, high-value generation and escalation.
- Structured outputs are schema-validated and grounded against the immutable fact set.
- Identical work is cached by input/version hash. Batches and asynchronous jobs reduce cost.
- Per-organization and per-feature budgets, model fallbacks and a kill switch are mandatory.
- Each recommendation contains evidence, expected effect, confidence, risk, required permission and expiry.
- Provider routing must allow managed models first and additional providers or customer keys later without changing product workflows.
- A deny-by-default agent registry now declares the Director and specialist capabilities. An independent Security Sentinel has veto power, all external writes remain disabled in registry version 1, and the authenticated control plane exposes the policy checksum. Owner/admin work orders are routed only through enumerated goals, redacted, idempotent and stored with that checksum.
- Agent feedback is stored only as a redacted, idempotent, store-scoped learning candidate. Review does not change production behavior; promotion requires separate offline evaluations and a versioned release.
- Daily AI Director also consumes the privacy-minimised WB feedback snapshot as a rules-only source: stale or missing reviews trigger a safe refresh, low ratings and unanswered reviews become human-only tasks with count-based measurements. It never infers causes or sends a reply.

## 6. Integration Hub: Russia and CIS accounting coverage

The promise is broad compatibility, delivered by a normalized Integration Hub rather than marketplace logic hard-coded for every accounting product.

### Canonical data model

- Products, variants, barcodes and bundles.
- Warehouses, stock, reservations and movements.
- Orders, shipments, sales, cancellations and returns.
- Prices, promotions and cost of goods.
- Marketplace fees, logistics, storage, penalties, payments and settlements.
- Counterparties, organizations, tax settings and source documents.
- Source identifiers, timestamps, currency, tax treatment and reconciliation status on every record.

### Connector contract

Every adapter must expose capabilities and use the same operational contract:

- scoped authentication and encrypted credentials;
- read-only connection test before write permissions;
- full import plus cursor/incremental synchronization;
- webhook events when supported and rate-limited polling otherwise;
- idempotency keys, retries, dead-letter handling and replay;
- mapping/version control for fields, units, taxes and warehouses;
- health, last success, lag, record counts and actionable error messages;
- reconciliation report before any system becomes an accounting source of truth;
- explicit approval and audit for write-back.

### Direct connectors — Wave 1

- **1C:** Enterprise Accounting, Trade Management, ERP, Small Business Management and Retail through published OData/HTTP services plus a documented 1C extension where standard publication is insufficient.
- **MoySklad:** JSON API, webhooks and incremental synchronization.
- **Saby/SBIS:** catalog, stock, documents and relevant accounting operations through supported APIs.
- **Kontur ecosystem:** Market plus Diadoc/Extern-related document flows where their APIs and customer permissions allow it.

**Implemented Integration Hub foundation:** an authenticated, store-scoped, versioned connector catalog now declares marketplace, accounting and logistics adapters with explicit capabilities, delivery stage and shared production gates. Connected status comes only from enabled server connection records. Wildberries is marked read beta, CSV cost import is available, and every unimplemented connector remains visibly planned or discovery-only.

### CIS and enterprise expansion — Wave 2

- BAS products through OData and supported integration interfaces.
- Localized 1C editions for Kazakhstan, Belarus, Uzbekistan and other priority markets.
- Odoo.
- SAP, Oracle and Microsoft Dynamics connectors based on signed customer demand.
- Regional systems selected from onboarding telemetry and paid integration requests.

### Universal coverage

Systems without a maintained direct adapter connect through:

- guided CSV/XLSX import and export with saved mappings;
- REST API and webhook connector;
- SFTP or approved object-storage exchange;
- connector SDK, test contract and reference adapter for partners;
- scheduled file exchange for legacy systems.

Marketing may say “works with any accounting system” only when one of these universal paths is usable for that customer's required data. The UI must distinguish certified direct, partner, beta and file/API connections.

## 7. Marketplace map

1. Wildberries: catalog, stock, orders/sales, economics, content publication, advertising, reviews and claims.
2. Ozon: equivalent seller loop after the WB vertical path is production-safe.
3. Yandex Market, Megamarket and other marketplaces: added through the same canonical entities and connector contract.
4. No integration is marked production-ready until read, reconciliation, permission, write-preview, rate-limit and failure-recovery tests pass.

## 8. Android and notification foundation

The web product and future Android app use the same versioned API, permissions and event model.

- Push topics: approval required, stock risk, sync failure, critical margin, advertising limit, review escalation and completed AI job.
- Every push deep-links to the exact store, entity and proposed action.
- Android priority flow: sign in, dashboard, alerts, camera upload, project review, approve/reject and emergency stop.
- Device tokens are per user/device, revocable and never used as authorization.
- Offline mode may cache read models and drafts but queues no external write without renewed authorization.
- Notification preferences, quiet hours, deduplication and delivery audit are shared across Web Push, Android and later channels.

## 9. Module map and status

| Area | Current status | Next production gate |
|---|---|---|
| Accounts, organizations, stores | Server sessions, TOTP MFA, recovery codes, admin MFA gate and ten-minute step-up authorization implemented | Passkeys, export gates, complete RBAC and audit coverage |
| Business profiles / onboarding | Store-scoped assessment, resumable first import, confirmed profile, evidence summary and profile-aware costing requirements implemented | Automatic source-specific document readers |
| WB snapshots | Catalog, stocks, sales velocity and store-scoped Data Health Center implemented | Automatic scheduling, freshness SLO telemetry and incident alerts |
| Products | Reads real WB catalog facts | Provenance and cross-source identity mapping |
| Beginner Studio | Photo analysis, confirmed facts, draft and saved project implemented | Durable image assets and publication |
| Trial and billing | Server entitlements, 3 days / 5 cards, store cap, paid-period lifecycle and idempotent provider-event core | Select RF/CIS payment provider and add its verified checkout/webhook adapter |
| Card Factory | Grounded copy, saved versions, confirmed WB text and append-only media submission, post-write live verification | Production observation and failure telemetry |
| Profit Center | WB ledgers, verified COGS components, guided CSV column mapping, immutable preview/commit and tax | Production reconciliation, XLSX and certified accounting adapters |
| AI Director | Evidence queue, durable decisions, audit, STOP, read-only executors and source-based measurement implemented | Bounded marketplace-write executors and verified rollback |
| Agent network and security | Director + five specialists, independent Security Sentinel, typed deny-by-default registry and reviewed-learning candidates implemented | Eval artefacts, signed policy versions, canary promotion and executor-level security gates |
| AI Support Agent | Architecture accepted | Incident intake, forced escalation and evidence bundle before general chat |
| Advertising | Read-only source data connected | Reconciliation and bounded, approved writes |
| Reviews | Read-only WB snapshot plus persisted grounded AI themes/drafts | Human review workflow; automatic replies remain disabled |
| Claims | Planned | Read-only insights before approved writes |
| Integration Hub | Architecture accepted | Canonical schema and 1C/MoySklad adapters |
| Ozon and other marketplaces | Planned | Start after WB write path is safe |
| Android and push | API/event foundation required now | Native approval and alert MVP |
| Cross-border CIS | Accepted for discovery | Validate Kazakhstan partner/API/legal route, then read-only economics MVP |
| Manufacturer OS | Planned P3 | Versioned BOM, production costing and accounting-source boundaries |
| Omnichannel / Wholesale | Planned P3 | Canonical offer, reservation-safe inventory and quote MVP |
| Professional community | Planned P4 | Launch only with verified users, moderation and privacy controls |
| Network insights | Planned P3 | Consent, cohort protection and contractual data-use review before pilot |

## 10. Delivery order

**Public entry experience:** `/` is session-aware. Anonymous visitors and the initial server render see a crawlable TROVENDI product surface with outcomes, marketplace/scenario choice, trial boundaries, pricing, security controls and clear register/login actions; authenticated users switch to the evidence-backed operating dashboard only after successful session verification. The internal dashboard is never the anonymous fallback. Conversion measurement and verified customer proof remain launch gates.

**Start-page channel control:** the channel selector is a permanent product branch, not a temporary landing-page decoration. Guests can inspect the sequenced roadmap for Wildberries, Ozon, Yandex Market, Kaspi.kz and Uzum Market. Authenticated users receive store-scoped connection flags from `/stores`; the response exposes only marketplace code and enabled state, never credentials or token hints. A channel is labelled `connected` only when a real connection record exists and is enabled. Integration Hub will extend this catalog without redesigning the start page.

**Public purchase journey:** the anonymous start page also owns an allowlisted bundle configurator for channel, modules and store count. It recommends PRO or Business, then carries only non-sensitive routing intent through registration. **Implemented foundation:** registration validates the plan/channel/store/module allowlists, persists one tenant-scoped purchase intent and still creates only a Trial subscription. The authenticated activation router derives the next allowlisted step from server state: paid users must verify email before checkout, receive rights only from a matching verified provider event, then enable/verify MFA before connecting Wildberries and entering onboarding. Trial bypasses payment but never the MFA requirement for marketplace credentials. Browser parameters and return URLs never grant rights. Future marketplaces are recorded as interest and transparently route the first usable setup through Wildberries; they cannot be purchased as active connectors before their release gate.

**Community access:** the forum/professional community is included in every active paid PRO and Business subscription and denied to Trial, unpaid, expired and canceled/read-only workspaces. The server entitlement key is `community_access`; every future forum API must enforce it in addition to authentication, tenant scope and moderation/privacy controls. The public page may advertise the benefit, but the forum remains planned until those controls are implemented.

### P0 — complete the safe vertical product

0. Complete the production security perimeter: private PostgreSQL connectivity, least-privilege runtime role, encrypted PITR/backups with restore drill, passkeys, export authorization gates, observed Vercel WAF rules, and PostgreSQL RLS rollout. **Application baseline implemented:** production fails closed without PostgreSQL/TLS/HTTPS/secrets, API docs are disabled, auth/recovery limits and anti-cache headers are active, cross-tenant exfiltration probes run in tests, TOTP MFA with single-use recovery codes protects accounts, and a ten-minute server-side step-up window gates marketplace credentials, marketplace publications and administrative mutations. Marketplace credential connect/disconnect additionally requires an MFA-verified current session; credential hints are no longer returned to the browser. Infrastructure controls remain launch gates until verified in the providers.
1. Finish one store-scoped Card Factory using real catalog facts.
2. Persist generated images and generation metadata. **Implemented for Card Factory; Beginner Studio reuse remains.**
3. Add validation preview and confirmed WB publication. **Implemented for title/description and separately approved image upload, each with post-write verification and no automatic retry.**
4. Complete source-based Profit Center reconciliation. **Implemented foundation: WB finance and advertising lines, deduplication, confirmed COGS and tax profile, double-charge protection and completeness-gated profit. Per-SKU COGS now uses allowlisted components for reseller, manufacturer or distributor models; each non-zero component requires a user-confirmed source, the server calculates integer kopecks, stores a canonical checksum and writes an audit event. Existing confirmed totals remain readable through a legacy-compatible record. Production reconciliation and automated accounting imports remain observation gates.**
   **Accounting import boundary:** 1C, MoySklad, Saby, Kontur, CSV and partner adapters can now submit up to 500 normalized cost rows to an immutable 24-hour preview. TROVENDI rejects duplicate or foreign `nmId`, reports validation errors by source row, binds the preview to its creator and SHA-256, and applies it only after a separate owner/admin confirmation. Commit is transactional, idempotent and audited. The store-scoped import journal shows bounded metadata and effective preview expiry without exposing row-level financial payloads. Certified source-specific readers and XLSX remain delivery gates.
   **Guided CSV mapping:** Profit Center accepts a local CSV file up to 2 MB / 500 rows, handles comma, semicolon or tab delimiters and quoted cells, suggests only known header mappings and lets the user explicitly map `nmId`, SKU model, cost components and row source. The browser performs a first validation, the backend repeats authoritative validation, and the UI exposes row-level errors and the immutable preview checksum before a separate confirmation. Files are parsed locally and are not uploaded as raw documents. Store-scoped mapping presets can be saved, reapplied only when all named columns exist, deleted and audited; the server allowlists their shape and component keys. XLSX remains a delivery gate.
5. Add billing entitlements and trial-to-paid transition. **Implemented provider-neutral foundation: server capabilities, trial/paid/read-only states, period end, cancellation intent, store cap and idempotent verified-event application. Provider checkout/webhook adapter remains blocked until the RF/CIS provider is selected and contracted.**

### P1 — make AI Director operational

1. Freshness/health monitoring for all data sources. **Implemented foundation:** the authenticated Data Health Center reports bounded freshness, expected intervals, record counts and redacted job failures for catalog, stocks, sales, finance and advertising. Core-data safety gates are exposed to AI consumers. The dedicated worker now schedules due read-only WB updates, retries through the durable queue, sanitizes persisted failures and maintains deduplicated incidents with optional Web Push delivery to owners/admins.
2. Ranked profit, stock, content and operational recommendations.
   **Implemented foundation:** store-scoped queue of up to ten actions, transparent priority formula, source freshness, observed-loss labelling, zero-cost rules provider and proposal-only safety mode.
3. Approval inbox, bounded policies, audit and rollback measurement.
   **Implemented foundation:** immutable recommendation runs, owner/admin approve-or-reject decisions, operational audit events and store-level emergency STOP. Approval is deliberately separated from execution. Marketplace-write executors and verified rollback remain the next gate.
   **Implemented safe executor:** only allowlisted WB read synchronizations can run from Director. Profit, stock and content recommendations expose structured baselines and can be measured again only against fresh compatible sources. Marketplace writes remain blocked; a missing recommendation is reported as “no longer detected” without inventing a numeric result.
4. Reviews, marketplace-condition changes, penalties and claims in read-only mode first. **Penalty foundation implemented:** Profit Center now derives a store/period-scoped read-only register of penalties and non-advertising deductions from normalized WB finance lines. It exposes only allowlisted evidence fields, separates incomplete coverage, caps the visible list, ranks the eight largest reason groups by deterministic totals and never creates or submits a claim. Reviews, condition changes and claim workflow remain delivery gates.
5. Incident-safe AI Support Agent: deterministic escalation, idempotent ticket, redacted evidence and authenticated emergency STOP entry point before product-help RAG.
6. Self-service onboarding: read-only capability test, resumable source import, user-confirmed business profile, completeness gate and first three evidence-backed actions. **Implemented foundation:** the setup master verifies store/WB/data readiness, summarizes only latest snapshot evidence, persists an owner-confirmed operating profile with audit and returns up to three grounded next actions. One action now starts all three read-only import groups, reuses active jobs, restores progress after reload and verifies current complete finance/advertising coverage. Confirmed business profiles expose their own costing-source checklist without inventing monetary values.
7. Typed AI capability registry is implemented as a deny-by-default foundation; add eval artefacts and transactional outbox promotion before more autonomous executors.

### P2 — expand the operating system

1. Integration Hub canonical model, connector runtime and health center.
2. 1C and MoySklad certified adapters; Saby/SBIS and Kontur follow.
3. Ozon complete seller loop.
4. Push service and Android approval/alert MVP.
5. Agency portfolio and client permissions.

### P3 — expansion pilots

1. Kazakhstan cross-border discovery and read-only multi-currency economics pilot.
2. Manufacturer BOM and production-cost foundation over canonical products.
3. Reservation-safe omnichannel inventory and wholesale quote MVP.
4. BAS/localized 1C and demand-led CIS connectors.

### P4 — network and enterprise scale

1. Additional verified cross-border routes and marketplaces.
2. Universal connector SDK and partner certification.
3. Verified manufacturer/distributor network and moderated professional community.
4. Advanced experiments, external traffic, white-label and enterprise accounting systems.

## 11. Definition of done

A feature is done only when all applicable gates pass:

- Server authorization and tenant isolation are tested.
- Happy path, invalid input, quota, timeout and external failure are tested.
- External calls obey documented rate limits and retry/idempotency rules.
- UI shows loading, empty, error, stale and success states in plain language.
- AI output is schema-validated, fact-grounded and cost-attributed.
- Risky writes have preview, confirmation, audit and recovery behavior.
- Database migration works from the previous production schema.
- Production build and automated tests pass.
- Vercel deployment status is checked after every fifth GitHub upload as one controlled batch, then changed routes are opened and failures are corrected before that batch is reported complete. Local tests and a production build remain mandatory before every upload.
- CI uses current Node.js 24-compatible official GitHub Actions. The active delivery target is the TROVENDI web/backend product; Windows installer builds are disabled.

## 12. Product decision log

- The public product name is **TROVENDI**, the primary domain is **trovendi.ru**, and the descriptor is **AI Commerce OS**.
- The TROVENDI mark combines the letter T with an upward arrow: product launch, controlled growth and one direction of management.
- Legacy technical identifiers (`marketplace-ai-studio-pro`, `marketplace-ai-studio-api`, `mai_session`, `mai_store_id`) remain temporarily unchanged for deployment, session and data migration safety. They are not customer-facing brand names.
- Beginner mode is a first-class entry point, not a separate disposable landing page.
- Trial is 72 hours from first successful AI analysis and limited to five successful cards.
- AI controls orchestration while deterministic services control facts, money and permissions.
- Android is a shared-platform client; API, events and permissions must be mobile-ready now.
- Russia/CIS accounting compatibility is implemented through Integration Hub: direct priority adapters plus universal file/API/SDK paths.
- WB remains the first complete production vertical; breadth must not weaken correctness of the write path.
- A public FRA1 Vercel Blob store is connected to `marketplace-ai-studio-pro` through rotating OIDC credentials; no long-lived read-write token is enabled.
- WB text publication is bound to one saved AI generation and payload hash, requires an owner/admin confirmation, re-reads the live card before writing, and records the provider response without claiming moderation is complete.
- Post-write WB verification is a separate read action with persisted `pending`, `applied`, `mismatch` or `error` state; TROVENDI never retries a write merely because WB moderation is delayed.
- WB image publication is isolated from text publication, bound to one stored AI asset and SHA-256, and requires the separate phrase `ОПУБЛИКОВАТЬ ФОТО`. TROVENDI uses direct upload to the next free position so the existing photo set is not replaced, validates WB file requirements, blocks on concurrent media changes and verifies the resulting count/order without automatic retry.
- Profit Center imports the current WB Finance detailed realization report into an auditable, store-scoped ledger. Cursor pages run through the WB one-request-per-minute limiter and source lines are deduplicated by WB `rrdId`.
- Profit Center labels the available result as contribution before tax and advertising. Final profit remains unavailable until WB finance coverage is complete and confirmed COGS, advertising and tax sources are connected; missing values are never replaced by AI guesses or demo money.
- WB advertising costs use the current read-only `GET /adv/v3/fullstats` path. Campaigns are processed in batches of up to 50 and date ranges in chunks of up to 31 days through the shared per-token limiter; every stored daily SKU line retains source evidence.
- A tax value enters Profit Center only after an owner/admin confirms the rate and whether its base is gross WB sales or WB payout. It is labelled a management reserve and never presented as a filed tax calculation.
- Profit Center reconciles advertising costs against finance-report deductions marked as advertising so the store total does not subtract the same WB promotion charge twice. A complete profit is exposed only when finance, advertising, COGS and tax gates are all complete.
- Trial grants one store and five successful grounded text cards for 72 hours from the first successful analysis. It excludes AI image generation, marketplace publication and autonomous writes. Expired projects and reports remain readable.
- All capabilities are resolved by the backend from the latest subscription and period status. A browser redirect never activates paid access; only a signature-verified provider adapter or explicit platform-admin override may apply a paid transition. Provider events must be idempotent and auditable.
- TROVENDI visual direction is deep graphite plus brand emerald. Gold is reserved for Premium, green/red/amber remain semantic, and AI glow is subtle and separate from the brand. The operating workspace is dark; beginner onboarding may use a lighter surface; Android follows the shared tokens and system theme.
- Daily AI Director starts with a deterministic `Rules · Free` layer: it ranks only evidence present in WB snapshots and Profit Center, attributes zero AI cost, never invents expected revenue and never performs a marketplace write. Each action exposes urgency, confidence, risk, source and whether owner approval will be required. LLM interpretation is a later, budget-controlled layer over the same immutable evidence.
- Director recommendations are persisted by source-and-action fingerprint so refreshing the screen does not create duplicate decisions. An owner/admin decision is append-only for that recommendation run and records an audit event; it never starts an external write. Store-level STOP is immediate and reversible only with an explicit `ВОЗОБНОВИТЬ TROVENDI` confirmation. Every future executor must re-check this control before writing.
- The first Director executor is intentionally read-only and allowlisted to WB analytics, finance and advertising synchronization jobs. It records job IDs and audit evidence. Outcome measurement compares the original structured metric with a fresh metric of the same type; incompatible or stale sources block measurement. No rollback is offered for read-only work because no marketplace state was changed.
- Windows installer CI is removed because the desktop application is not an active TROVENDI delivery target. Existing desktop source remains as recoverable legacy code and must not consume CI minutes or create releases unless a separate product decision explicitly reactivates it.
- Cross-border CIS, Manufacturer OS, omnichannel wholesale and professional community are accepted expansion directions, not current production claims. Their architecture and validation gates are recorded in `EXPANSION_STRATEGY.md`; the safe WB vertical and Integration Hub remain prerequisites.
- Kazakhstan read-only economics is the first cross-border candidate. It becomes an MVP commitment only after seller eligibility, partner contracts, official/contracted data access, tax/customs treatment and reconciliation documents are verified. AI never authors legal or tax rules.
- The partner seller-of-record network, wholesale sales Hub and professional community are separate security domains and products. Store economics or matching data may enter community features only through granular opt-in and protected aggregation.
- AI Support Agent is separate from Daily AI Director and receives no marketplace-write permissions. Financial-loss, unexpected-write, security, personal-data, refund and legal cases are forced into an idempotent human-review ticket; an LLM may never downgrade this route.
- Support answers use approved, versioned and expiring knowledge with visible citations. Conversations do not automatically train a model or become shared knowledge, and the product never invents an SLA, marketplace rule or currently unavailable TROVENDI capability.
- The first paying ICP is an owner-led small or medium seller/manufacturer with usable sales history, operational pain and fast decision access. Beginner Studio remains the acquisition path; enterprise depth follows after stronger RBAC, audit, SLA and connector gates.
- Reseller/importer, manufacturer and distributor are versioned business operating profiles, not tenants. Profiles can differ by SKU and are proposed by AI but confirmed by a user before affecting financial calculations.
- TROVENDI uses bounded AI capabilities behind typed domain services. Finance AI has no arbitrary production SQL, vector retrieval is not financial memory, and Guided mode never weakens approval or money-safety rules.
- The near-term scale path is a modular application, PostgreSQL, transactional outbox, durable idempotent jobs, workload-specific workers and rate-limit backpressure. Kafka, ClickHouse or service extraction require measured workload evidence.
- Security is a launch gate, not a marketing label. Current application controls do not make a stolen logical database dump harmless; private networking, minimal database roles, independent encrypted backups, monitored key access, PostgreSQL RLS and selective per-tenant envelope encryption follow `DATABASE_SECURITY_RUNBOOK.md` and must be verified before broad onboarding.
- To conserve Vercel build quota, deployments are verified in batches after every five GitHub uploads. A failed fifth-build gate blocks the next batch until corrected; security-critical emergency fixes may be verified immediately.
- Cross-customer benchmarks and logistics radar require separate consent, contractual data-use rights, comparable cohorts, minimum cohort protection, uncertainty disclosure and access audit. Raw tenant data is never shared across retrieval contexts.
