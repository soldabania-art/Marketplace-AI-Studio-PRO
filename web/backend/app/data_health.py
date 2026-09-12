from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import BackgroundJob, DataHealthIncident, JobStatus, MarketplaceConnection, MarketplaceSnapshot


MARKETPLACE_TIMEZONE = "Europe/Moscow"

SOURCE_POLICIES = (
    {"key": "catalog", "label": "Каталог и карточки", "snapshot_type": "catalog", "job_type": "marketplace.wb.analytics.sync", "warn_after": 7200, "stale_after": 21600, "required_for": ["products", "card_factory"]},
    {"key": "stocks", "label": "Остатки", "snapshot_type": "stocks", "job_type": "marketplace.wb.analytics.sync", "warn_after": 1800, "stale_after": 7200, "required_for": ["products", "smart_fbo", "director"]},
    {"key": "sales", "label": "Продажи и скорость", "snapshot_type": "sales_velocity_7d", "job_type": "marketplace.wb.analytics.sync", "warn_after": 7200, "stale_after": 21600, "required_for": ["products", "smart_fbo", "director"]},
    {"key": "finance", "label": "Финансовый отчёт", "snapshot_type": "finance_realization_sync", "job_type": "marketplace.wb.finance.sync", "warn_after": 86400, "stale_after": 172800, "required_for": ["profit_center", "director"], "coverage_days": 30},
    {"key": "advertising", "label": "Реклама", "snapshot_type": "advertising_sync", "job_type": "marketplace.wb.advertising.sync", "warn_after": 86400, "stale_after": 172800, "required_for": ["profit_center", "director"], "coverage_days": 30},
    {"key": "feedbacks", "label": "Отзывы", "snapshot_type": "feedbacks", "job_type": "marketplace.wb.feedbacks.sync", "warn_after": 3600, "stale_after": 14400, "required_for": ["reviews", "director"]},
)

POLICY_BY_KEY = {policy["key"]: policy for policy in SOURCE_POLICIES}
POLICY_BY_SNAPSHOT_TYPE = {policy["snapshot_type"]: policy for policy in SOURCE_POLICIES}


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def source_policy(source: str) -> dict:
    policy = POLICY_BY_KEY.get(source) or POLICY_BY_SNAPSHOT_TYPE.get(source)
    if policy is None:
        raise ValueError(f"Unknown marketplace source: {source}")
    return policy


def expected_coverage(source: str, *, now: datetime | None = None, period_days: int | None = None) -> dict:
    """Return the marketplace-local inclusive period required for a covered source."""
    policy = source_policy(source)
    days = (period_days or policy.get("coverage_days")) if policy.get("coverage_days") else None
    if not days:
        return {}
    current = _aware(now or datetime.now(timezone.utc)).astimezone(ZoneInfo(MARKETPLACE_TIMEZONE))
    date_to = current.date()
    date_from = date_to - timedelta(days=max(1, int(days)) - 1)
    return {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()}


def evaluate_source_snapshot(
    snapshot: MarketplaceSnapshot | None,
    source: str,
    *,
    now: datetime | None = None,
    period_days: int | None = None,
) -> dict:
    """Apply the single freshness/completeness contract used by every module."""
    policy = source_policy(source)
    current = _aware(now or datetime.now(timezone.utc))
    expected = expected_coverage(policy["key"], now=current, period_days=period_days)
    if snapshot is None:
        return {
            "key": policy["key"], "snapshot_type": policy["snapshot_type"], "status": "missing",
            "age_seconds": None, "warn_after_seconds": policy["warn_after"],
            "stale_after_seconds": policy["stale_after"], "complete": False,
            "coverage_matches": False if expected else None, "coverage_expected": expected or None,
            "coverage_actual": None,
        }
    created = _aware(snapshot.created_at)
    age_seconds = max(0, int((current - created).total_seconds()))
    payload = dict(snapshot.payload or {})
    actual = ({"date_from": payload.get("date_from"), "date_to": payload.get("date_to")} if expected else None)
    coverage_matches = actual == expected if expected else None
    if expected:
        declared_complete = (
            payload.get("complete") is True
            and payload.get("schema_state") in {"valid", "documented_empty"}
            and type(payload.get("rejected_count")) is int
            and payload["rejected_count"] == 0
        )
    else:
        declared_complete = payload.get("complete") is not False
    complete = declared_complete and coverage_matches is not False
    if not complete:
        status = "incomplete"
    elif age_seconds > policy["stale_after"]:
        status = "stale"
    elif age_seconds > policy["warn_after"]:
        status = "delayed"
    else:
        status = "healthy"
    return {
        "key": policy["key"], "snapshot_type": policy["snapshot_type"], "status": status,
        "snapshot_created_at": snapshot.created_at, "source_updated_at": getattr(snapshot, "source_updated_at", None),
        "age_seconds": age_seconds, "warn_after_seconds": policy["warn_after"],
        "stale_after_seconds": policy["stale_after"], "complete": complete,
        "coverage_matches": coverage_matches, "coverage_expected": expected or None,
        "coverage_actual": actual,
    }


def refresh_due(health: dict, interval_seconds: int) -> bool:
    if health["status"] in {"missing", "stale", "incomplete", "error"}:
        return True
    return health["status"] == "delayed" and int(health.get("age_seconds") or 0) >= interval_seconds


def _latest_by_type(db: Session, store_id: str) -> dict[str, MarketplaceSnapshot]:
    result = {}
    for snapshot_type in {policy["snapshot_type"] for policy in SOURCE_POLICIES}:
        row = db.scalar(select(MarketplaceSnapshot).where(
            MarketplaceSnapshot.store_id == store_id,
            MarketplaceSnapshot.marketplace == "wildberries",
            MarketplaceSnapshot.snapshot_type == snapshot_type,
        ).order_by(MarketplaceSnapshot.created_at.desc()).limit(1))
        if row is not None:
            result[snapshot_type] = row
    return result


def _latest_job(db: Session, store_id: str, job_type: str) -> BackgroundJob | None:
    return db.scalar(select(BackgroundJob).where(
        BackgroundJob.store_id == store_id,
        BackgroundJob.job_type == job_type,
    ).order_by(BackgroundJob.created_at.desc()))


def store_data_health(db: Session, store_id: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    connection = db.scalar(select(MarketplaceConnection).where(
        MarketplaceConnection.store_id == store_id,
        MarketplaceConnection.marketplace == "wildberries",
        MarketplaceConnection.enabled.is_(True),
    ))
    snapshots = _latest_by_type(db, store_id)
    job_cache = {}
    sources = []
    for policy in SOURCE_POLICIES:
        snapshot = snapshots.get(policy["snapshot_type"])
        health = evaluate_source_snapshot(snapshot, policy["key"], now=now)
        status = "disconnected" if not connection else health["status"]
        age_seconds = health["age_seconds"]
        job_type = policy["job_type"]
        if job_type not in job_cache:
            job_cache[job_type] = _latest_job(db, store_id, job_type)
        job = job_cache[job_type]
        job_state = job.status.value if job else None
        issue = None
        refresh_in_progress = bool(job and job.status in {JobStatus.queued, JobStatus.running, JobStatus.retry})
        if job and job.status in {JobStatus.retry, JobStatus.dead}:
            issue = "Последняя синхронизация завершилась ошибкой; подробности доступны в защищённом журнале."
            if status != "disconnected":
                status = "error"
        payload = snapshot.payload or {} if snapshot else {}
        sources.append({
            "key": policy["key"],
            "label": policy["label"],
            "status": status,
            "snapshot_created_at": snapshot.created_at if snapshot else None,
            "source_updated_at": snapshot.source_updated_at if snapshot else None,
            "age_seconds": age_seconds,
            "warn_after_seconds": policy["warn_after"],
            "stale_after_seconds": policy["stale_after"],
            "complete": health["complete"],
            "coverage_matches": health["coverage_matches"],
            "coverage_expected": health["coverage_expected"],
            "coverage_actual": health["coverage_actual"],
            "record_count": payload.get("count", payload.get("page_rows")) if snapshot else None,
            "required_for": policy["required_for"],
            "job": {"id": job.id, "status": job_state, "attempts": job.attempts, "updated_at": job.updated_at} if job else None,
            "refresh_in_progress": refresh_in_progress,
            "issue": issue,
        })
    priority = {"error": 7, "disconnected": 6, "incomplete": 5, "stale": 4, "missing": 3, "delayed": 2, "syncing": 1, "healthy": 0}
    worst = max(sources, key=lambda item: priority[item["status"]])["status"] if sources else "missing"
    counts = {status: sum(item["status"] == status for item in sources) for status in priority}
    incidents = db.scalars(select(DataHealthIncident).where(
        DataHealthIncident.store_id == store_id,
        DataHealthIncident.status == "open",
    ).order_by(DataHealthIncident.opened_at.desc()).limit(20)).all()
    return {
        "marketplace": "wildberries",
        "connected": bool(connection),
        "overall_status": worst,
        "checked_at": now,
        "counts": counts,
        "sources": sources,
        "active_incidents": [{
            "id": row.id,
            "source_key": row.source_key,
            "severity": row.severity,
            "message": row.public_message,
            "opened_at": row.opened_at,
            "last_seen_at": row.last_seen_at,
        } for row in incidents],
        "safe_for_ai_decisions": bool(connection) and all(item["status"] == "healthy" for item in sources if item["key"] in {"catalog", "stocks", "sales"}),
    }
