# Durable job transaction contract (T08B)

`enqueue(db, ...)` stages a BackgroundJob in the caller's PostgreSQL transaction.
It never commits or rolls back. The caller must commit before returning a durable
job ID or leaving its Session. Session close/rollback discards both pending domain
changes and the job. A successful enqueue return alone is not a durability claim.

BackgroundJob is the transactional outbox consumed directly from PostgreSQL.
There is no new external broker or dispatch step. Workers cannot claim an
uncommitted row. `ON CONFLICT (idempotency_key) DO NOTHING` resolves concurrent
inserts without rolling back unrelated caller writes. Other database errors still
fail the transaction; callers must roll back/close it and retry the logical unit.
Production uses PostgreSQL READ COMMITTED. SQLite is a development fallback and
does not establish concurrency guarantees.

## Transaction owners

| Path | Owner and atomic writes |
| --- | --- |
| Director execute | Action status, audit and all source jobs commit together in execute_action |
| Profit sync API | Both finance and advertising jobs commit together in start_profit_sync |
| Onboarding import | Three source jobs and onboarding audit commit together in start_import |
| Products / FBO / reviews / manual sync | API refresh boundary explicitly commits before returning job IDs |
| Finance / advertising worker page | Ledger inserts/updates/deletes, page checkpoint and continuation job commit together |
| Automatic source scheduler | Explicit commit of staged source jobs per store, after leaving store lease |
| FBO scheduler | Explicit commit of staged poll jobs for the cycle |

`enqueue_profit_sync` composes with Director and does not commit. `stage_snapshot`
composes with page import and does not commit. `save_snapshot` remains the owner
of independent snapshots and rejected-page diagnostics. Data-health incident
reconciliation/push is an existing independent operation; this change does not
claim atomic notification delivery. Session advisory-lock connection lifetime and
the shared Redis limiter remain T08C.

## Ownership and crash semantics

Attempt ownership is checked before enqueue flush and again at outer COMMIT.
The ownership row lock is held through COMMIT/ROLLBACK. Keep this transaction short:
perform provider reads first, then stage database changes and commit immediately;
do not hold the fence across a slow provider request. Independent heartbeat and
stale-worker fencing tests remain enabled.

Before COMMIT, a failure loses neither half selectively: domain writes and jobs
roll back together. After COMMIT but before an HTTP response or job acknowledgement,
the durable job remains and re-enqueue with the same logical key returns its ID.
Page replays upsert source lines and reuse continuation keys; snapshots may retain
multiple audit observations of the same replayed page.

This does not promise exactly-once external HTTP. STOP, immutable publication
assets, durable submitting state and read-only reconciliation of unknown provider
results retain their existing contracts. No real WB writes or paid AI are used in
the tests.

## Verification

`tests/test_job_transactions.py` checks close/rollback/fault boundaries, independent
PostgreSQL visibility, two concurrent writers with unrelated domain changes,
finance/advertising page continuation failures, and Director action/audit/jobs.
The full ownership, STOP and publication suites must remain green. Schema version
is unchanged from T08A (0028); run fresh and previous-to-head migration checks.
