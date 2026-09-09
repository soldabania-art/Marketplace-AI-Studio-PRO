# TROVENDI — AI Commerce OS

> Living execution map: [`PRODUCT_ROADMAP.md`](./PRODUCT_ROADMAP.md). Every accepted product decision, integration and delivery gate must be recorded there before implementation is considered planned.
>
> Expansion architecture: [`EXPANSION_STRATEGY.md`](./EXPANSION_STRATEGY.md) records the discovery gates for cross-border CIS, Manufacturer OS, omnichannel wholesale and the professional network.

## Product direction
TROVENDI is a web-first AI operating system for marketplace sellers, starting with Wildberries and Ozon and designed for later expansion to Yandex Market, Megamarket, AliExpress and other verified integrations.

The product is designed around one loop:

`connect stores -> collect own + market data -> detect problems/opportunities -> calculate financial effect -> propose actions -> generate content -> approve risky changes -> execute -> measure -> rollback if worse`

The target UX is maximum automation: the seller connects stores, supplies product facts and business constraints, then AI Director continuously prioritizes work. AI creates card copy/SEO/visual concepts and, where generation is available, visual assets. Deterministic engines remain the source of business calculations.

The initial paying core is an owner-led small or medium seller/manufacturer with usable transaction history and fragmented operations. Beginner Studio remains the low-friction acquisition path; enterprise requirements are added after the core operating loop is proven.

## Beginner Launch Studio — «Старт с нуля»
This is a distinct product entry point for a person who has not sold on marketplaces before. It shares the same account, Store, Card Factory, Profit Center and AI Director architecture; it is not a disconnected second product.

Primary promise: `one product photo -> confirmed fact set -> marketplace-ready launch project -> approved publication -> ongoing store operations`.

Flow:
1. Upload one phone photo. Vision AI may identify only visibly supported properties and must label product/category identification as a confidence-scored guess.
2. Ask the smallest possible set of plain-language questions for non-visible facts: material, dimensions, composition, package contents, brand, certificates, supplier documents, COGS and available stock.
3. Build an immutable confirmed fact set. Unknown facts remain unknown; the system never fills them with plausible guesses.
4. Generate WB/Ozon-specific title, description, SEO, characteristics mapping and an infographic/image plan.
5. Check category requirements, marketplace constraints and unit economics before offering publication.
6. Show a complete preview/diff. Publishing, price changes and advertising spend require explicit confirmation unless the seller later configures bounded autopilot permissions.
7. After launch, hand the product to AI Director for stock risk, advertising, reviews, profit and content-performance monitoring.

Beginner language must avoid marketplace jargon or explain it at the point of use. The workspace shows one next action at a time and never exposes the full professional dashboard as a setup checklist.

## Product layers
1. Seller OS — daily operations for one or many stores.
2. Market Intelligence — competitors, search demand and niche discovery.
3. Smart Supply / Smart FBO — inventory forecasting and concrete replenishment plans.
4. Profit & Promo Economics — unit economics, reconciliation, taxes and promotion scenarios.
5. AI Growth — Card Factory, SEO, advertising, A/B experiments and external traffic creatives.
6. Claims & Disputes — penalties, deductions, lost goods and marketplace support claims.
7. Agency Mode — portfolio, RBAC, client portal, white-label reporting and bulk actions.
8. Notification layer — Web Push first, Telegram and native Android push later.
9. Self-service and scale layer — business profiles, activation, bounded AI capabilities, durable jobs and privacy-safe network insights.

## Primary navigation
1. AI Director
2. Dashboard
3. Profit Center
4. Products
5. AI Card Factory
6. Advertising
7. Reviews
8. Inventory / Smart Supply
9. SEO & Search
10. Market Intelligence
11. Claims & Disputes
12. Growth Lab
13. Automations
14. Reports
15. Integrations
16. Settings
17. Agency — visible for agency workspaces

AI Support is available contextually from every module rather than occupying a primary operating-navigation slot. High-risk incident intake and emergency controls remain visually distinct from ordinary help chat.

## Global Store Context
All seller-facing modules operate against an explicit selected Store. A Store belongs to a Workspace/Organization and can have multiple marketplace connections.

Target hierarchy:
`User -> Membership/RBAC -> Workspace/Organization -> Client (agency mode) -> Store -> MarketplaceConnection -> business data`

The global store selector is foundational. Dashboard, Products, Card Factory, SEO, Ads, Reviews, Inventory, Smart FBO, Profit Center, Reports, Claims and Automations must never silently mix stores.

Every persisted business record, cache, job and external action must be scoped by workspace and store ID. Agency portfolio views are the explicit exception: they aggregate authorized stores and preserve drill-down provenance.

## Home dashboard
The first screen answers three questions:
1. How much did I earn?
2. What is going wrong?
3. What should I do next?

Top KPIs:
- revenue;
- net profit;
- orders;
- ad spend;
- DRR/ACoS;
- returns;
- stock risk;
- penalties/deductions;
- reconciliation variance.

Below the KPIs is the AI Director queue. Each item has severity, affected workspace/store/marketplace/SKU, financial impact, evidence, confidence/provenance and a safe action.

## AI Director
AI is not allowed to invent business facts. Deterministic engines calculate metrics, constraints and flags first; AI explains, summarizes, connects signals and helps choose an action.

Examples of cross-module reasoning:
- competitor price fell -> search position/CTR changed -> advertising economics deteriorated -> recommend a bounded response;
- competitor reviews repeatedly complain about packaging -> verify our product fact/advantage -> propose a Card Factory infographic message;
- regional demand + inventory + acceptance slots + logistics tariffs -> recommend replenishment by warehouse/date/quantity;
- promotion price -> recompute unit economics -> recommend only profitable SKUs with forecast ranges.

Action levels:
- Observe: read-only analysis.
- Recommend: prepare changes, never write externally.
- Assisted: execute after explicit confirmation.
- Autopilot: execute only pre-approved low-risk action classes within limits.

Every external write is audited. Money, pricing, publishing, support claims and destructive actions require safeguards and rollback where technically possible.

## Market Intelligence / Competitor Spy
The system must not optimize SEO and advertising using only the seller's own data.

Capabilities:
- competitor watchlists by SKU/category/search query;
- competitor price and availability history where legally and technically available;
- search position tracking;
- estimated share/visibility by tracked query with methodology and confidence shown;
- new-player detection in tracked niches;
- competitor review analysis, especially recurring negative themes;
- demand/category trend and seasonality analysis;
- niche/product opportunity discovery: growing/falling demand, competition, economics and supply risk.

Market data must include source, timestamp and confidence. Estimates must never be presented as exact marketplace facts.

## Smart Supply / Smart FBO/FBS
The existing warehouse acceptance-slot search is the foundation, not the final product.

Inputs:
- sales velocity and forecast;
- stock by warehouse/fulfilment scheme;
- regional order distribution where available;
- marketplace logistics/storage/acceptance tariffs;
- acceptance availability and coefficients;
- lead time and seller constraints;
- returns and seasonality;
- target safety stock and days of cover.

Output is a concrete supply plan: marketplace, warehouse, SKU, quantity, ship-by date, expected days of cover, expected logistics/localization effect and confidence.

Example UX: `Ship 300 units to Kazan and 150 to Shushary by <date>; estimated logistics saving <range>.`

Web Push alerts on newly matching WB acceptance slots remain part of this module. Server monitoring must only be described as 24/7 after an always-on backend/worker deployment is verified.

## Profit Center & financial reconciliation
Per SKU/store/marketplace:
`revenue -> marketplace payout/fees -> logistics/storage -> advertising -> penalties/deductions -> returns -> taxes -> COGS -> net profit`

Capabilities:
- loss makers and margin leaders;
- advertising efficiency;
- return impact;
- inventory-at-risk;
- promotion economics;
- reconciliation of marketplace reports against actual payouts;
- discrepancy detection;
- export for accounting/1C-compatible workflows where format requirements are verified;
- configurable tax calculation, including relevant simplified-tax and VAT scenarios, with legal/accounting assumptions explicit.

No hidden estimates: every derived metric carries its data source and confidence/provenance.

## Promo Economics
Before a seller joins a marketplace promotion, recompute unit economics per SKU and scenario.

Show:
- normal vs promo price;
- fees/logistics/ads/tax/COGS;
- profit per unit and margin;
- break-even price/volume;
- forecast range for total profit and confidence.

Algorithmic boost or demand uplift must be labelled as a forecast, never a guaranteed fact. AI Director can recommend a subset of SKUs rather than all-or-nothing participation.

## AI Card Factory
Input:
- product photos;
- confirmed product facts;
- marketplace/category constraints;
- optional brand style;
- verified market/competitor insights.

Pipeline:
1. validate facts;
2. analyze existing listing/performance;
3. create positioning;
4. generate marketplace-specific title and copy;
5. generate SEO/search phrases and negative keywords where applicable;
6. create visual concept and infographic plan;
7. generate/edit image assets;
8. marketplace compliance checks;
9. preview diff;
10. publish only through verified official API capabilities.

AI must never fabricate material, dimensions, certifications, composition or other product facts. Competitor weaknesses can inspire positioning only when the corresponding advantage of our product is a confirmed fact.

## Growth Lab / A-B measurement
Track controlled listing and advertising changes and measure business impact.

Initial experiments:
- main image/cover;
- title/SEO;
- price/promotion strategy;
- advertising strategy.

Measure CTR, conversion, orders and profit. Never declare a winner from a tiny sample; show sample size, observation window and statistical/decision confidence.

## External Traffic Studio
Generate marketplace-card-derived creative briefs and promotional copy for legitimate external channels such as Telegram/VK when configured. Support campaign attribution/UTM where possible and measure traffic, conversions and profit.

The product must not provide tooling for fake purchases, rating manipulation or deceptive marketplace activity.

## Claims & Disputes
Track marketplace penalties, deductions and operational disputes:
- damaged/substituted goods;
- packaging violations;
- lost inventory;
- incorrect dimensions;
- incorrect commissions/logistics charges;
- other supported marketplace deductions.

AI can prepare a support ticket/claim using the actual case evidence and the current applicable marketplace terms. Legal/offer references must come from a versioned, current source; models must not invent clause numbers. Track status, deadlines, amount disputed and amount recovered.

## Notifications
Event engine feeds:
- in-app notifications;
- Web Push;
- Telegram bot later;
- native Android push after the web product is stable.

Examples: competitor price move, stockout risk, ad-spend anomaly, new acceptance slot, financial discrepancy, claim deadline and critical AI Director action. Notifications must be deduplicated and configurable per store/event/severity.

## Agency Mode
Agency Mode is a layer over the same Store/Workspace architecture, not a separate product.

Capabilities:
- multi-client/store selector without separate logins;
- RBAC for agency owner/admin/account manager/analyst/client viewer;
- employee access limited to assigned clients/stores;
- portfolio dashboard with authorized aggregate revenue/profit/risk;
- client portal exposing only the client's stores/reports/work performed;
- white-label PDF/weekly reporting with agency branding;
- bulk actions across explicitly selected authorized stores, with preview and safeguards;
- billing/plan limits by connected stores/SKU where commercially configured;
- employee audit log: actor, store, action, before/after, timestamp, result;
- encrypted client marketplace credentials with rotation; ordinary employees never receive plaintext keys.

## AI Router
Do not hard-wire product modules to one AI vendor. Route tasks by capability, context size, cost, privacy and availability.

Policy:
- deterministic code for financial/business calculations;
- local/free mode never silently calls paid APIs;
- paid cloud AI is explicit/plan-controlled;
- provider adapters can support OpenAI and other approved providers without changing product workflows;
- no model may invent marketplace/business facts;
- store prompts/results only according to configured privacy/retention rules.

## Multimarketplace strategy
Priority order is product-driven, but architecture must not assume only two marketplaces.

Initial: Wildberries, Ozon.
Planned expansion after official API/capability verification: Yandex Market, Megamarket, AliExpress and other commercially relevant marketplaces.

Each capability is feature-gated per marketplace. Never simulate API support that has not been verified.

## Web architecture
Frontend: Next.js + React/TypeScript target.
Backend: FastAPI/Python.
Database: PostgreSQL target.
Queue/workers: Redis-backed background jobs target.
Storage: S3-compatible object storage for generated assets.
Authentication: server-side accounts/sessions with organization/workspace/store isolation.
Secrets: encrypted server-side marketplace credentials; never expose marketplace tokens to the browser after connection.
Observability: structured logs, audit events, job status and diagnostics.

Existing Python marketplace/business modules should be extracted behind backend service interfaces instead of rewritten unnecessarily.

## Security, admin and compliance are P0
Commercial launch requires:
- secure passwords/sessions and email verification/recovery;
- rate limits/brute-force controls;
- RBAC and tenant/store isolation tests;
- encrypted marketplace/API secrets and key rotation path;
- audit logs for admin/agency/external writes;
- protected admin console;
- webhook signature verification/idempotency for payments;
- backups/recovery, migrations, monitoring and dependency/secret scanning;
- privacy/personal-data documents, terms/public offer, consent evidence/versioning and cookie controls;
- subscription/autorenew/cancellation/refund disclosures;
- retention/deletion and AI-processing disclosures;
- Russia-first legal/commercial baseline with CIS expansion profiles.

Admins must never see plaintext marketplace tokens.

## Admin console
Platform administrators need operational control over users, workspaces/stores, plans/limits, subscriptions/payments, AI quotas/providers, promotions, support, security/audit events, errors/jobs, legal document versions and service configuration. Sensitive actions require elevated authorization and audit.

## Android later
After the web product is stable, build an Android client on the same backend/account/store model. Primary early value is native push for critical events, including FBO slots, with deep links to the affected store/warehouse/action. Do not create a second business-logic stack in the mobile app.

## Delivery order
### Phase 1 — Safe multi-store foundation
- global Store Context/selector across the entire UI;
- store-scoped APIs/jobs/caches/actions;
- WB connection flow per store;
- real backend deployment + worker;
- auth/security/audit/migrations baseline.

### Phase 2 — Seller core
- Dashboard and AI Director on real store data;
- Products, Reviews, Ads, SEO;
- Profit Center with real provenance;
- Inventory + current FBO slot monitoring;
- notifications.

### Phase 3 — Smart operations
- Smart Supply/FBO/FBS forecasting and replenishment plan;
- Promo Economics;
- financial reconciliation;
- Claims & Disputes;
- Telegram alerts.

### Phase 4 — Market & growth intelligence
- Market Intelligence/Competitor Spy;
- competitor review pain mining -> Card Factory suggestions;
- niche/product discovery and seasonality;
- Growth Lab/A-B measurement;
- External Traffic Studio.

### Phase 5 — Agency & scale
- Agency Mode/RBAC assignments;
- portfolio analytics;
- client portal;
- white-label reports;
- bulk actions/audit;
- agency billing.

### Phase 6 — Marketplace/mobile expansion
- Ozon parity where official endpoints are verified;
- Yandex Market and additional marketplaces after capability verification;
- Android app/native push.

## Definition of success
The user should be able to open one browser tab and understand the business in under a minute. The system should prioritize what matters financially and turn own-store data plus verified market intelligence into safe, measurable actions instead of forcing the seller to navigate dozens of reports.

The seller should increasingly operate by exceptions: connect stores, set constraints, review high-risk decisions, while the platform continuously detects, calculates, drafts and executes pre-approved low-risk work.
