from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .job_queue import enqueue
from .marketplace_sync import latest_snapshot
from .models import MarketplaceConnection, User
from .security import get_current_user
from .store_access import resolve_store

router = APIRouter(prefix="/reviews", tags=["reviews"])


def _queue(db: Session, store):
    bucket = int(datetime.now(timezone.utc).timestamp() // 900)
    return enqueue(db, job_type="marketplace.wb.feedbacks.sync", idempotency_key=f"wb-feedbacks:{store.id}:{bucket}", payload={"store_id": store.id}, workspace_id=store.workspace_id, store_id=store.id, priority=54, max_attempts=5)


@router.get("")
def reviews(store_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id)
    connection = db.query(MarketplaceConnection).filter(MarketplaceConnection.store_id == store.id, MarketplaceConnection.marketplace == "wildberries", MarketplaceConnection.enabled.is_(True)).first()
    if not connection:
        raise HTTPException(409, "Wildberries не подключён к выбранному магазину.")
    snapshot = latest_snapshot(db, store_id=store.id, marketplace="wildberries", snapshot_type="feedbacks")
    if not snapshot:
        job = _queue(db, store)
        return {"store_id": store.id, "store_name": store.name, "sync_required": True, "refresh_job_id": job.id, "freshness": None, "metrics": None, "reviews": []}
    items = list((snapshot.payload or {}).get("items") or [])
    age = max(0, int((datetime.now(timezone.utc) - (snapshot.created_at if snapshot.created_at.tzinfo else snapshot.created_at.replace(tzinfo=timezone.utc))).total_seconds()))
    refresh = _queue(db, store) if age > 3600 else None
    ratings = [int(item.get("rating") or 0) for item in items]
    metrics = {
        "loaded": len(items),
        "unanswered": int((snapshot.payload or {}).get("unanswered_count") or sum(not item.get("answered") for item in items)),
        "low_rating": sum(rating <= 3 for rating in ratings),
        "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
    }
    return {"store_id": store.id, "store_name": store.name, "marketplace": "wildberries", "read_only": True, "sync_required": age > 3600, "refresh_job_id": refresh.id if refresh else None, "freshness": {"created_at": snapshot.created_at, "age_seconds": age}, "metrics": metrics, "reviews": items[:200]}
