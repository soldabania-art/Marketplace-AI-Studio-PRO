# WB first useful pilot

**Status:** planned implementation; no real WB token or provider call is used in development or tests.

## What already works

- A store-scoped Wildberries connection is encrypted server-side and can be changed only by a workspace owner/admin with MFA and step-up.
- Read import jobs, Redis provider limiting, job fencing, source health and the Director queue already exist.
- Data Health marks incomplete or stale sources; Director is read-only when its evidence is insufficient.

## Gaps that block a useful first connection

1. Connection preflight now proves importer-source access, but import and scheduler still need to consume that matrix.
2. A partial result must distinguish forbidden, unchecked and temporary access failures without retrying unavailable sources.
3. Director must keep connection diagnostics visible while withholding evidence-dependent operational and monetary conclusions.

## Minimal change

1. Reuse WB01's store-scoped, version- and generation-fenced read-only capability matrix.
2. Gate first import and scheduled read jobs: enqueue only groups whose required sources are `available`; keep `forbidden`/`unchecked` blocked and `transient_error` deferred until explicit recheck.
3. Show partial/deferred/blocked states in existing onboarding; preserve WB02's explicit dead-job recovery namespace.
4. Director shows missing-source recovery actions without a conclusion; money conclusions require live finance evidence.

## Acceptance criteria

- A partial connection imports independent available groups only; unavailable groups create no automatic retry job.
- Recheck and credentials rotation remain fenced by exact credentials version and check generation.
- No WB write endpoint, response body or secret enters diagnostics.
- Director keeps connection diagnosis visible when sales are missing and reports no money conclusion without finance.
- Targeted tests/build pass locally; PostgreSQL migration/concurrency and remote CI remain required before independent acceptance.

## Explicit limits

Read-only WB pilot only: no publication, promotion spend, paid AI generation, real token or external request. It does not certify worker deployment, billing or production readiness.
