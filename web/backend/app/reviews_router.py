import json

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .ai_generation_service import begin_generation, complete_generation, fail_generation, public_generation, stable_hash
from .billing_service import require_entitlement
from .config import get_settings
from .data_health import evaluate_source_snapshot, refresh_due
from .marketplace_sync import latest_snapshot
from .models import AIGeneration, GenerationStatus, MarketplaceConnection, User
from .review_ai import build_review_fact_set, generate_review_analysis
from .security import get_current_user
from .store_access import resolve_store
from .sync_scheduler import enqueue_sync_job

router = APIRouter(prefix="/reviews", tags=["reviews"])


def _queue(db: Session, store):
    job, _ = enqueue_sync_job(db, store=store, group="feedbacks", payload={"store_id": store.id, "origin": "reviews"}, priority=54)
    db.commit()
    return job


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
    health = evaluate_source_snapshot(snapshot, "feedbacks")
    age = health["age_seconds"]
    due = refresh_due(health, get_settings().sync_feedbacks_interval_seconds)
    refresh = _queue(db, store) if due else None
    ratings = [int(item.get("rating") or 0) for item in items]
    metrics = {
        "loaded": len(items),
        "unanswered": int((snapshot.payload or {}).get("unanswered_count") or sum(not item.get("answered") for item in items)),
        "low_rating": sum(rating <= 3 for rating in ratings),
        "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
    }
    return {"store_id": store.id, "store_name": store.name, "marketplace": "wildberries", "read_only": True, "sync_required": due, "refresh_job_id": refresh.id if refresh else None, "freshness": {"created_at": snapshot.created_at, "age_seconds": age, "status": health["status"]}, "metrics": metrics, "reviews": items[:200]}


@router.get("/analysis")
def review_analysis(store_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id)
    rows = db.query(AIGeneration).filter(AIGeneration.store_id == store.id, AIGeneration.feature == "review_analysis").order_by(AIGeneration.created_at.desc()).limit(20).all()
    return {"items": [public_generation(row) for row in rows], "automatic_reply_enabled": False}


@router.post("/analysis", status_code=201)
def create_review_analysis(store_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id)
    require_entitlement(db, store.workspace_id, "review_ai")
    snapshot = latest_snapshot(db, store_id=store.id, marketplace="wildberries", snapshot_type="feedbacks")
    if not snapshot:
        raise HTTPException(409, "Сначала синхронизируйте отзывы Wildberries.")
    fact_set = build_review_fact_set(list((snapshot.payload or {}).get("items") or []))
    input_payload = {"feedback_snapshot_id": snapshot.id, "fact_set": fact_set}
    input_hash = stable_hash(input_payload)
    previous = db.query(AIGeneration).filter(AIGeneration.store_id == store.id, AIGeneration.feature == "review_analysis", AIGeneration.input_hash == input_hash, AIGeneration.status == GenerationStatus.completed).order_by(AIGeneration.created_at.desc()).first()
    if previous:
        return {"generation": public_generation(previous), "cached": True, "automatic_reply_enabled": False}
    generation = begin_generation(db, store=store, user=user, feature="review_analysis", subject_id=snapshot.id, input_payload=input_payload, fact_set_sha256=fact_set["sha256"])
    try:
        result = generate_review_analysis(fact_set)
        metadata = result.pop("_generation_metadata", {})
        complete_generation(db, generation, result, metadata)
    except RuntimeError as exc:
        fail_generation(db, generation, exc); raise HTTPException(503, str(exc)) from exc
    except (ValueError, json.JSONDecodeError) as exc:
        fail_generation(db, generation, exc); raise HTTPException(502, f"AI-анализ не прошёл проверку доказательств: {exc}") from exc
    except httpx.HTTPError as exc:
        fail_generation(db, generation, exc); raise HTTPException(502, "AI-сервис временно не ответил.") from exc
    return {"generation": public_generation(generation), "cached": False, "automatic_reply_enabled": False}

