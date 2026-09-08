from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Subscription, SubscriptionStatus

TRIAL_DAYS = 3


def _utc(value):
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def workspace_subscription(db: Session, workspace_id: str, lock: bool = False) -> Subscription:
    statement = select(Subscription).where(Subscription.workspace_id == workspace_id).order_by(Subscription.created_at.desc())
    if lock:
        statement = statement.with_for_update()
    subscription = db.scalar(statement)
    if subscription is None:
        raise HTTPException(402, "Для рабочего пространства не найден тариф.")
    return subscription


def trial_snapshot(subscription: Subscription) -> dict:
    if subscription.status == SubscriptionStatus.active and subscription.plan_code != "trial":
        return {"plan": subscription.plan_code, "status": "active", "unlimited": True}
    now = datetime.now(timezone.utc)
    started = _utc(subscription.trial_started_at)
    expires = _utc(subscription.trial_expires_at)
    used = subscription.trial_ai_cards_used or 0
    limit = subscription.trial_ai_cards_limit or 5
    status = "not_started"
    if started:
        status = "expired" if expires and expires <= now else "active"
    if used >= limit and status != "expired":
        status = "exhausted"
    return {
        "plan": "trial",
        "status": status,
        "unlimited": False,
        "started_at": started,
        "expires_at": expires,
        "cards_used": used,
        "cards_limit": limit,
        "cards_remaining": max(0, limit - used),
        "duration_days": TRIAL_DAYS,
        "read_only": status in {"expired", "exhausted"},
    }


def ensure_ai_access(db: Session, workspace_id: str, allow_exhausted: bool = False) -> dict:
    snapshot = trial_snapshot(workspace_subscription(db, workspace_id))
    if snapshot.get("unlimited"):
        return snapshot
    if snapshot["status"] == "expired":
        raise HTTPException(402, "Пробный период завершён. Проекты сохранены в режиме просмотра.")
    if snapshot["status"] == "exhausted" and not allow_exhausted:
        raise HTTPException(402, "Пять пробных карточек использованы. Проекты сохранены в режиме просмотра.")
    return snapshot


def reserve_trial_card(db: Session, workspace_id: str) -> tuple[dict, bool]:
    subscription = workspace_subscription(db, workspace_id, lock=True)
    current = trial_snapshot(subscription)
    if current.get("unlimited"):
        return current, False
    ensure_ai_access(db, workspace_id)
    now = datetime.now(timezone.utc)
    started_now = subscription.trial_started_at is None
    if started_now:
        subscription.trial_started_at = now
        subscription.trial_expires_at = now + timedelta(days=TRIAL_DAYS)
    subscription.trial_ai_cards_used = (subscription.trial_ai_cards_used or 0) + 1
    db.commit()
    db.refresh(subscription)
    return trial_snapshot(subscription), started_now


def refund_trial_card(db: Session, workspace_id: str, started_now: bool) -> None:
    subscription = workspace_subscription(db, workspace_id, lock=True)
    subscription.trial_ai_cards_used = max(0, (subscription.trial_ai_cards_used or 0) - 1)
    if started_now and subscription.trial_ai_cards_used == 0:
        subscription.trial_started_at = None
        subscription.trial_expires_at = None
    db.commit()
