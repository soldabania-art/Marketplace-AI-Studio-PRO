# TROVENDI Data Health Center

Status: implemented foundation for the Wildberries vertical path.

The Data Health Center is the freshness gate between marketplace ingestion and AI decisions. It is not a generic uptime badge. Every result is resolved through the authenticated user's store access and returns only bounded operational metadata, never raw marketplace payloads, credentials or worker exception text.

## Current source policies

| Source | Warning age | Stale age | Main consumers |
|---|---:|---:|---|
| Catalog | 2 hours | 6 hours | Products, Card Factory |
| Stocks | 30 minutes | 2 hours | Smart FBO, AI Director |
| Seven-day sales velocity | 2 hours | 6 hours | Smart FBO, AI Director |
| Finance realization sync | 24 hours | 48 hours | Profit Center |
| Advertising sync | 24 hours | 48 hours | Profit Center, AI Director |
| Feedbacks | 1 hour | 4 hours | Reviews, AI Director |

`safe_for_ai_decisions` becomes true only when the connected store has healthy catalog, stock and sales snapshots. Profit recommendations continue to use their own stricter completeness gates for finance, advertising, confirmed COGS and tax.

All backend modules consume this registry rather than defining their own 15-minute thresholds. Finance and advertising use an inclusive rolling period based on the Wildberries operating date in `Europe/Moscow`. At the marketplace-local date boundary, yesterday's otherwise complete period no longer satisfies today's coverage. A latest snapshot with `complete=false`, missing coverage fields, or a different period is `incomplete`; it is never promoted to complete from its age alone.

## Status contract

- `healthy`: source is inside its warning interval.
- `delayed`: warning interval exceeded, but the stale boundary has not been crossed.
- `stale`: source is too old for confident use.
- `incomplete`: the latest paginated snapshot has not completed the required current period.
- `syncing`: reserved for explicit sync progress presentation; a queued/running job is exposed separately as `refresh_in_progress` and does not hide the source's freshness status.
- `error`: the latest relevant job is retrying or dead. The browser receives a generic explanation; raw worker errors stay in protected operations logs.
- `missing`: the connection exists but no snapshot has been stored.
- `disconnected`: the marketplace connection is not active.

The worker schedules read-only WB analytics when due, feedbacks hourly when due, and finance/advertising daily. It does not increase every source to a 15-minute poll. Scheduler, Director and browser endpoints use one root-job admission path: a queued, running or retrying job for the same store/source is reused. PostgreSQL serializes concurrent root admission per store/job type. Recovery runs receive a new run namespace which is also included in every paginated child key, so keys from an earlier failed run cannot swallow later pages. Jobs retain bounded exponential retry. Stale, incomplete or failed sources open one deduplicated incident, limit AI Director decisions and optionally notify workspace owners/admins through Web Push. Incidents close only after a healthy snapshot is observed. Raw provider exceptions and credentials never enter incident payloads; persisted job errors are sanitized before storage.

Freshness SLO aggregation and external incident correlation remain later production gates.
