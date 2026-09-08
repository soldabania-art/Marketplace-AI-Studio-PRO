# Marketplace AI Studio PRO — living product roadmap

Status: source of truth for product scope, priorities and delivery gates. Update this file whenever a product decision is accepted. A feature mentioned in chat but absent here is not yet scheduled.

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
- Target package: one complete showcase card with an image pack plus four standard cards. Image-pack entitlement activates only when durable generated-image storage is ready.
- Paid subscription removes trial limits according to the selected plan.

Current implementation includes the 72-hour clock, five-success quota, store-bound signed analysis, persisted projects and read-only enforcement. Generated-image storage and official publication remain delivery gates.

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
| Accounts, organizations, stores | Implemented foundation | Complete RBAC and audit coverage |
| WB snapshots | Catalog, stocks and sales velocity implemented | Reconciliation, freshness SLO and failure UI |
| Products | Reads real WB catalog facts | Provenance and cross-source identity mapping |
| Beginner Studio | Photo analysis, confirmed facts, draft and saved project implemented | Durable image assets and publication |
| Trial | 3 days / 5 successful cards enforced server-side | Billing transition and entitlement tests |
| Card Factory | Store-scoped grounded generation, addressable history and cost records implemented | Version comparison and approved publication |
| Profit Center | Product shell/foundation | Full settlement and cost reconciliation |
| AI Director | Product architecture defined | Evidence-backed recommendation queue |
| Advertising, reviews, claims | Planned | Read-only insights before approved writes |
| Integration Hub | Architecture accepted | Canonical schema and 1C/MoySklad adapters |
| Ozon and other marketplaces | Planned | Start after WB write path is safe |
| Android and push | API/event foundation required now | Native approval and alert MVP |

## 10. Delivery order

### P0 — complete the safe vertical product

1. Finish one store-scoped Card Factory using real catalog facts.
2. Persist generated images and generation metadata.
3. Add validation preview and confirmed WB publication.
4. Complete source-based Profit Center reconciliation.
5. Add billing entitlements and trial-to-paid transition.

### P1 — make AI Director operational

1. Freshness/health monitoring for all data sources.
2. Ranked profit, stock, content and operational recommendations.
3. Approval inbox, bounded policies, audit and rollback measurement.
4. Reviews, marketplace-condition changes, penalties and claims in read-only mode first.

### P2 — expand the operating system

1. Integration Hub canonical model, connector runtime and health center.
2. 1C and MoySklad certified adapters; Saby/SBIS and Kontur follow.
3. Ozon complete seller loop.
4. Push service and Android approval/alert MVP.
5. Agency portfolio and client permissions.

### P3 — broad coverage and scale

1. BAS/localized 1C and demand-led CIS connectors.
2. Universal connector SDK and partner certification.
3. Additional marketplaces and enterprise accounting systems.
4. Advanced experiments, external traffic and white-label automation.

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
- After every GitHub upload, Vercel deployment status is checked, changed routes are opened, and failures are corrected before the work is reported complete.

## 12. Product decision log

- Beginner mode is a first-class entry point, not a separate disposable landing page.
- Trial is 72 hours from first successful AI analysis and limited to five successful cards.
- AI controls orchestration while deterministic services control facts, money and permissions.
- Android is a shared-platform client; API, events and permissions must be mobile-ready now.
- Russia/CIS accounting compatibility is implemented through Integration Hub: direct priority adapters plus universal file/API/SDK paths.
- WB remains the first complete production vertical; breadth must not weaken correctness of the write path.
