from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .billing_service import entitlement_snapshot, latest_subscription
from .models import Subscription

TRIAL_DAYS = 3


def _utc(value):
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def workspace_subscription(db: Session, workspace_id: str, lock: bool = False) -> Subscription:
    return latest_subscription(db, workspace_id, lock=lock)


def trial_snapshot(subscription: Subscription) -> dict:
    snapshot = entitlement_snapshot(subscription)
    return {
        **snapshot,
        "status": snapshot["access_status"],
        "unlimited": snapshot["plan"] != "trial" and not snapshot["read_only"],
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
