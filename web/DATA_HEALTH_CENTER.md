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

`safe_for_ai_decisions` becomes true only when the connected store has healthy catalog, stock and sales snapshots. Profit recommendations continue to use their own stricter completeness gates for finance, advertising, confirmed COGS and tax.

## Status contract

- `healthy`: source is inside its warning interval.
- `delayed`: warning interval exceeded, but the stale boundary has not been crossed.
- `stale`: source is too old for confident use.
- `syncing`: a paginated source is incomplete or a relevant job is queued/running while data is missing or late.
- `error`: the latest relevant job is retrying or dead. The browser receives a generic explanation; raw worker errors stay in protected operations logs.
- `missing`: the connection exists but no snapshot has been stored.
- `disconnected`: the marketplace connection is not active.

The worker now schedules read-only WB analytics every 30 minutes when due and finance/advertising refreshes daily. Jobs keep unique time-bucket keys, database leases and bounded exponential retry. A dead daily job can enter a separate hourly recovery window without creating an unbounded retry loop. Stale or failed sources open one deduplicated incident, limit AI Director decisions and optionally notify workspace owners/admins through Web Push. Incidents close only after a healthy snapshot is observed. Raw provider exceptions and credentials never enter incident payloads; persisted job errors are sanitized before storage.

Freshness SLO aggregation and external incident correlation remain later production gates.
