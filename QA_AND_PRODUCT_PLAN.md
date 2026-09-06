# Marketplace AI Studio PRO — QA audit and ideal product plan

## QA policy

Every release must pass four gates before it is called stable:

1. **Static gate** — compile all Python sources and import every production module used by the current UI.
2. **Contract gate** — deterministic tests with mocked network calls for AI routing, WB/Ozon parsing, advertising guardrails, reviews, safety controls, publisher payloads and local AI resource logic.
3. **UI gate** — construct the current `Main` window and core pages in headless Qt mode.
4. **Live integration gate** — on a seller test account, verify read/write flows against official marketplace APIs. Live writes must use a sandbox/test SKU or explicit user confirmation and must never run from CI with production tokens.

CI currently covers gates 1–3. Gate 4 requires authorized marketplace credentials and is intentionally separated from public GitHub Actions.

## Bugs found during 3.4 audit

- Local model ranking used substring matching, so names such as `14b` / `32b` could be mis-ranked as smaller models. Fixed with exact numeric parameter parsing.
- Review classification called a private AI method whose arguments were incompatible with the new Local AI adapter. Fixed by adding a public `raw_text()` route that respects FREE / Economy / Premium policy.
- OpenAI cost refresh updated the status bar but not the visible credit label. Fixed in UI 3.4.
- WB catalog, ads, reviews and business refresh jobs did not consistently honor cancellation. Fixed so cancelled jobs do not save partial results.
- AI errors inherited from older UI layers could expose technical output. UI 3.4 maps AI errors to user-friendly messages.

## Ideal product principle

The product should not be a collection of separate tools. It should behave as an **AI operating system for a marketplace seller**:

`connect stores → collect data → detect opportunities/problems → propose actions → generate content → preview risky changes → execute allowed actions → measure result → roll back when worse`.

The user should spend time on exceptions and business decisions, not routine clicks.

## Ideal functional architecture

### 1. Marketplace Data Core

A single normalized data model for WB and Ozon:

- products / variants / media / characteristics;
- prices and discounts;
- stocks by warehouse;
- orders, sales, returns and cancellations;
- commissions, logistics, penalties and payouts;
- ad campaigns, bids, spend and attributed sales;
- reviews and questions;
- historical snapshots for every important metric.

API calls must pass through a central coordinator with endpoint-specific rate limits, short-lived caching, retries, error classification and last-success timestamps. UI pages should reuse cached responses rather than hit the same endpoint repeatedly.

### 2. Profit Engine

The main business metric should be **profit, not revenue**.

For each SKU calculate:

`revenue - marketplace commissions - logistics - ads - returns - COGS - other marketplace charges = operating profit`.

Show:

- profit and margin per SKU;
- break-even ad DRR/ACoS;
- break-even selling price;
- loss-making SKUs;
- stock-days and frozen capital;
- forecast for 7/30/60 days;
- what action has the largest expected profit impact.

### 3. AI Card Factory

One workflow from real product photo + confirmed facts to ready WB/Ozon package:

- title variants;
- descriptions per marketplace;
- SEO semantic core and exclusions;
- characteristics candidates with missing-fact warnings;
- benefits and FAQ;
- 6–10-slide infographic plan;
- local-first product visuals preserving product identity;
- exact local text overlay;
- per-slide regeneration;
- preview and edit;
- marketplace-specific validation before publish;
- version history and one-click rollback.

AI must never invent composition, certification, dimensions or promises. Unknown facts remain explicit blockers/warnings.

### 4. Growth Autopilot

Closed-loop optimization:

1. find weak SKU;
2. explain why it is weak;
3. estimate opportunity and risk;
4. create improved version;
5. request approval only if policy requires it;
6. publish;
7. measure before/after for a configured observation window;
8. keep improvement or roll back automatically under guardrails.

Priority score should combine expected profit impact, confidence, urgency and risk.

### 5. Advertising Autopilot

Per campaign and SKU:

- exact spend/sales/orders/DRR;
- target DRR derived from unit economics, not a universal number;
- bid recommendations with expected effect;
- search-cluster analysis;
- waste detection (spend without sales);
- scaling winners;
- daily budget guardrails;
- change history and rollback;
- approval / autopilot modes.

No automatic bid write is allowed without a known current bid and configured max delta.

### 6. Reviews & Reputation Center

Workflow:

`load unanswered → select → AI draft → edit/preview → send`.

Automation policy:

- 4–5 star, low-risk reviews can be auto-replied when explicitly enabled;
- negative, legal, health/safety, counterfeit, refund and ambiguous cases always require human approval;
- reusable brand tone templates;
- issue clustering to feed product/card improvements;
- response analytics and SLA.

### 7. Inventory & Supply Assistant

- stock days per SKU/warehouse;
- out-of-stock date forecast;
- reorder point;
- excess stock / dead stock;
- recommended shipment quantity;
- seasonality and sales velocity;
- alerts before stockout;
- supply task list.

### 8. Price Assistant

- current price / discount history;
- minimum profitable price;
- recommended price corridor;
- margin impact simulator;
- optional guarded price write only after official API verification;
- automatic protection from selling below configured contribution margin.

### 9. Daily AI Director

A single home screen should answer:

- What happened?
- What is losing money?
- What should I do today?
- What can AI safely do automatically?
- What needs my approval?
- What changed after yesterday's actions?

The user should see 5–10 prioritized actions, not dozens of raw dashboards.

### 10. FREE-FIRST AI

Default mode remains zero-cost:

- Ollama/local OpenAI-compatible text provider;
- local image provider;
- hardware-aware model selection;
- RAM/VRAM monitoring;
- automatic downgrade only to already-installed models;
- explicit paid fallback switch;
- explicit paid image switch;
- cost limits and visible provider badge on every AI action.

Premium cloud AI is an optional quality accelerator, never a hidden dependency.

### 11. Reliability and commercial readiness

Before commercial release:

- centralized typed API errors;
- endpoint-specific rate coordinator + cache;
- database migrations and backup/restore;
- crash recovery and resumable jobs;
- encrypted secret storage;
- role-based access for teams;
- audit trail for every external write;
- emergency STOP;
- daily write limits;
- signed installer and signed updates;
- diagnostic bundle that excludes secrets;
- automatic backup before app/database upgrade;
- first-run wizard and self-test;
- release channel Stable/Beta.

## Priority order

### P0 — before calling it commercially stable

- keep CI contract/UI tests green;
- endpoint-specific WB rate limiting + response cache;
- complete functional WB reviews workflow with editable draft/send;
- exact advertising attribution by SKU;
- reliable finance + COGS + profit per SKU;
- backup/migrations and recovery;
- full diagnostic/self-test page;
- live integration test checklist on a controlled WB seller account.

### P1 — makes the product materially better

- inventory/supply forecast;
- price assistant and margin simulator;
- daily AI Director with ranked actions;
- automatic image quality profile by VRAM;
- Ozon parity for all verified official read/write APIs;
- Excel bulk import/export and scheduled reports.

### P2 — scale/commercial features

- user roles and team accounts;
- licensing/activation without locking core seller data;
- Telegram/mobile notifications;
- remote optional worker for local AI on another PC;
- multi-store portfolio view;
- experiment/A-B history and statistical confidence.

## Definition of “ideal”

The ideal version is reached when a seller can install the app, connect WB/Ozon, enter COGS, choose FREE or Premium AI, and then mostly work from one queue of prioritized actions. The application should automatically perform safe routine work, request approval for risky writes, explain every recommendation in profit terms, and learn from measured before/after results while always retaining rollback and audit history.
