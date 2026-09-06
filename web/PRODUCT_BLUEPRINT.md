# Marketplace AI Studio Cloud

## Product direction
Marketplace AI Studio Cloud is a web-first AI operating system for Wildberries and Ozon sellers.

The product is designed around one loop:

`connect stores -> collect data -> detect problems/opportunities -> propose actions -> generate content -> approve risky changes -> execute -> measure -> rollback if worse`

## UX benchmark
We intentionally combine the strongest ideas of modern seller SaaS rather than cloning one product:
- centralized KPI dashboard and actionable insights;
- product-level profit/unit economics;
- AI commerce director as the primary interaction layer;
- one-click transition from insight to safe action;
- WB + Ozon unified operations;
- AI Card Factory for text, SEO and visuals.

## Primary navigation
1. AI Director
2. Dashboard
3. Profit Center
4. Products
5. AI Card Factory
6. Advertising
7. Reviews
8. Inventory
9. SEO & Search
10. Competitors
11. Automations
12. Reports
13. Integrations
14. Settings

## Home dashboard
The first screen answers three questions:
1. How much did I earn?
2. What is going wrong?
3. What should I do next?

Top KPIs:
- revenue
- net profit
- orders
- ad spend
- DRR/ACoS
- returns
- stock risk

Below the KPIs is the AI Director queue. Each item has severity, affected SKU/store, financial impact, explanation and a safe action.

Example actions:
- reduce an inefficient ad bid;
- regenerate weak SEO;
- create a new card visual pack;
- prepare a review reply;
- warn about profitable SKU stockout;
- recommend replenishment;
- flag a loss-making SKU.

## AI Director
AI is not allowed to invent business facts. Deterministic engines calculate metrics and flags first; AI explains, summarizes and helps choose an action.

Action levels:
- Observe: read-only analysis.
- Recommend: prepare changes, never write externally.
- Assisted: execute after explicit confirmation.
- Autopilot: execute only pre-approved low-risk action classes within limits.

Every external write is audited. Money, pricing, publishing and destructive actions require explicit safeguards and rollback where technically possible.

## Profit Center
Per SKU and per marketplace:
`revenue -> marketplace payout/fees -> advertising -> COGS -> net profit`

Views:
- loss makers first;
- margin leaders;
- advertising efficiency;
- return impact;
- inventory-at-risk;
- exact-vs-estimated data provenance.

No hidden estimates: every derived metric carries its data source and confidence/provenance.

## AI Card Factory
Input:
- product photos;
- confirmed product facts;
- marketplace/category constraints;
- optional brand style.

Pipeline:
1. validate facts;
2. analyze existing listing/performance;
3. create positioning;
4. generate WB/Ozon-specific title and copy;
5. generate SEO/search phrases;
6. create visual concept and infographic plan;
7. generate/edit image assets;
8. marketplace compliance checks;
9. preview diff;
10. publish only through verified official API capabilities.

AI must never fabricate material, dimensions, certifications, composition or other product facts.

## Web architecture
Frontend: Next.js + TypeScript.
Backend: FastAPI/Python.
Database: PostgreSQL.
Queue/workers: Redis-backed background jobs.
Storage: S3-compatible object storage for generated assets.
Authentication: server-side accounts/sessions with organization/workspace isolation.
Secrets: encrypted server-side marketplace credentials; never expose marketplace tokens to the browser after connection.
Observability: structured logs, audit events, job status and diagnostics.

Existing Python marketplace/business modules should be extracted behind backend service interfaces instead of rewritten unnecessarily.

## Multi-tenant safety
Every persisted business record must be scoped by organization/workspace and store ID. API caches and rate-limit coordinators must also be seller-scoped. Raw tokens must never be cache keys or logs; use non-reversible fingerprints internally when required.

## Free-first AI
AI routing policy remains explicit:
- local/free mode never silently calls paid APIs;
- paid cloud AI is opt-in;
- image generation can remain pending if no free/local image engine is available;
- no silent model downloads or model switching.

For a pure cloud deployment, local AI is an optional later desktop agent, not a prerequisite for the web dashboard.

## Migration phases
### Phase 1 — Cloud foundation
- web shell and responsive design;
- authentication/workspaces;
- WB connection flow;
- Dashboard;
- Profit Center;
- AI Director read-only recommendations;
- background synchronization and job status.

### Phase 2 — Operations
- Products;
- Reviews;
- Advertising;
- Inventory;
- task/action queue;
- audited assisted actions.

### Phase 3 — AI factory
- Card Factory;
- SEO;
- generated assets;
- preview/diff;
- controlled publishing.

### Phase 4 — Commercial SaaS
- Ozon parity where official endpoints are verified;
- organizations/roles;
- plans/limits;
- notifications;
- backups/recovery;
- onboarding and support diagnostics;
- production deployment.

## Definition of success
The user should be able to open one browser tab and understand the business in under a minute. The system should prioritize what matters financially and turn analysis into safe, measurable actions instead of forcing the seller to navigate dozens of reports.
