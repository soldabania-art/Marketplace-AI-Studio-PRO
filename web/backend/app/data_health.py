from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import BackgroundJob, JobStatus, MarketplaceConnection, MarketplaceSnapshot


SOURCE_POLICIES = (
    {"key": "catalog", "label": "Каталог и карточки", "snapshot_type": "catalog", "job_type": "marketplace.wb.analytics.sync", "warn_after": 7200, "stale_after": 21600, "required_for": ["products", "card_factory"]},
    {"key": "stocks", "label": "Остатки", "snapshot_type": "stocks", "job_type": "marketplace.wb.analytics.sync", "warn_after": 1800, "stale_after": 7200, "required_for": ["smart_fbo", "director"]},
    {"key": "sales", "label": "Продажи и скорость", "snapshot_type": "sales_velocity_7d", "job_type": "marketplace.wb.analytics.sync", "warn_after": 7200, "stale_after": 21600, "required_for": ["smart_fbo", "director"]},
    {"key": "finance", "label": "Финансовый отчёт", "snapshot_type": "finance_realization_sync", "job_type": "marketplace.wb.finance.sync", "warn_after": 86400, "stale_after": 172800, "required_for": ["profit_center"]},
    {"key": "advertising", "label": "Реклама", "snapshot_type": "advertising_sync", "job_type": "marketplace.wb.advertising.sync", "warn_after": 86400, "stale_after": 172800, "required_for": ["profit_center", "director"]},
)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


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
        if not connection:
            status = "disconnected"
            age_seconds = None
        elif snapshot is None:
            status = "missing"
            age_seconds = None
        else:
            age_seconds = max(0, int((now - _aware(snapshot.created_at)).total_seconds()))
            incomplete = policy["key"] in {"finance", "advertising"} and (snapshot.payload or {}).get("complete") is False
            if incomplete:
                status = "syncing"
            elif age_seconds > policy["stale_after"]:
                status = "stale"
            elif age_seconds > policy["warn_after"]:
                status = "delayed"
            else:
                status = "healthy"
        job_type = policy["job_type"]
        if job_type not in job_cache:
            job_cache[job_type] = _latest_job(db, store_id, job_type)
        job = job_cache[job_type]
        job_state = job.status.value if job else None
        issue = None
        if job and job.status in {JobStatus.queued, JobStatus.running} and status in {"missing", "delayed", "stale"}:
            status = "syncing"
        if job and job.status in {JobStatus.retry, JobStatus.dead}:
            issue = "Последняя синхронизация завершилась ошибкой; подробности доступны в защищённом журнале."
            if status in {"healthy", "delayed", "syncing"}:
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
            "record_count": payload.get("count", payload.get("page_rows")) if snapshot else None,
            "required_for": policy["required_for"],
            "job": {"id": job.id, "status": job_state, "attempts": job.attempts, "updated_at": job.updated_at} if job else None,
            "issue": issue,
        })
    priority = {"error": 6, "disconnected": 5, "stale": 4, "missing": 3, "delayed": 2, "syncing": 1, "healthy": 0}
    worst = max(sources, key=lambda item: priority[item["status"]])["status"] if sources else "missing"
    counts = {status: sum(item["status"] == status for item in sources) for status in priority}
    return {
        "marketplace": "wildberries",
        "connected": bool(connection),
        "overall_status": worst,
        "checked_at": now,
        "counts": counts,
        "sources": sources,
        "safe_for_ai_decisions": bool(connection) and all(item["status"] == "healthy" for item in sources if item["key"] in {"catalog", "stocks", "sales"}),
    }
