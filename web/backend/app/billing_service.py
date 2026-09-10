import hashlib
import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import BillingEvent, Subscription, SubscriptionStatus


PLAN_CATALOG = {
    "trial": {
        "code": "trial",
        "name": "Пробный запуск",
        "price_monthly_rub": 0,
        "duration_days": 3,
        "entitlements": {
            "stores_limit": 1,
            "users_limit": 1,
            "beginner_ai_cards_limit": 5,
            "card_copy_generation": True,
            "card_visual_generation": False,
            "marketplace_publication": False,
            "profit_center": True,
            "community_access": False,
            "autopilot_level": "disabled",
        },
    },
    "pro": {
        "code": "pro",
        "name": "PRO",
        "price_monthly_rub": 4990,
        "entitlements": {
            "stores_limit": 3,
            "users_limit": 3,
            "beginner_ai_cards_limit": None,
            "card_copy_generation": True,
            "card_visual_generation": True,
            "marketplace_publication": True,
            "profit_center": True,
            "community_access": True,
            "autopilot_level": "assisted",
        },
    },
    "business": {
        "code": "business",
        "name": "Business",
        "price_monthly_rub": 12990,
        "entitlements": {
            "stores_limit": 10,
            "users_limit": 10,
            "beginner_ai_cards_limit": None,
            "card_copy_generation": True,
            "card_visual_generation": True,
            "marketplace_publication": True,
            "profit_center": True,
            "community_access": True,
            "autopilot_level": "advanced",
        },
    },
}


READ_ONLY_ENTITLEMENTS = {
    "stores_limit": 0,
    "users_limit": 0,
    "beginner_ai_cards_limit": 0,
    "card_copy_generation": False,
    "card_visual_generation": False,
    "marketplace_publication": False,
    "profit_center": True,
    "community_access": False,
    "autopilot_level": "disabled",
}


def utc(value):
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def latest_subscription(db: Session, workspace_id: str, lock: bool = False) -> Subscription:
    statement = select(Subscription).where(Subscription.workspace_id == workspace_id).order_by(Subscription.created_at.desc())
    if lock:
        statement = statement.with_for_update()
    subscription = db.scalar(statement)
    if subscription is None:
        raise HTTPException(402, "Для рабочего пространства не найден тариф.")
    return subscription


def paid_access_is_active(subscription: Subscription, now: datetime | None = None) -> bool:
    if subscription.plan_code == "trial" or subscription.status != SubscriptionStatus.active:
        return False
    expires_at = utc(subscription.current_period_expires_at)
    return expires_at is None or expires_at > (now or datetime.now(timezone.utc))


def entitlement_snapshot(subscription: Subscription, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    plan = PLAN_CATALOG.get(subscription.plan_code, PLAN_CATALOG["trial"])
    if subscription.plan_code == "trial":
        started = utc(subscription.trial_started_at)
        expires = utc(subscription.trial_expires_at)
        used = subscription.trial_ai_cards_used or 0
        limit = subscription.trial_ai_cards_limit or 5
        access_status = "not_started"
        if started:
            access_status = "expired" if expires and expires <= now else "active"
        if used >= limit and access_status != "expired":
            access_status = "exhausted"
        entitlements = dict(plan["entitlements"])
        entitlements["beginner_ai_cards_limit"] = limit
        if access_status in {"expired", "exhausted"}:
            entitlements.update(READ_ONLY_ENTITLEMENTS)
        return {
            "plan": "trial",
            "subscription_status": subscription.status.value,
            "access_status": access_status,
            "read_only": access_status in {"expired", "exhausted"},
            "started_at": started,
            "expires_at": expires,
            "cards_used": used,
            "cards_limit": limit,
            "cards_remaining": max(0, limit - used),
            "duration_days": plan["duration_days"],
            "cancel_at_period_end": False,
            "entitlements": entitlements,
        }
    active = paid_access_is_active(subscription, now)
    return {
        "plan": subscription.plan_code,
        "subscription_status": subscription.status.value,
        "access_status": "active" if active else "read_only",
        "read_only": not active,
        "started_at": utc(subscription.current_period_started_at),
        "expires_at": utc(subscription.current_period_expires_at),
        "cards_used": None,
        "cards_limit": None,
        "cards_remaining": None,
        "duration_days": None,
        "cancel_at_period_end": bool(subscription.cancel_at_period_end),
        "entitlements": dict(plan["entitlements"] if active else READ_ONLY_ENTITLEMENTS),
    }


def require_entitlement(db: Session, workspace_id: str, entitlement: str) -> dict:
    snapshot = entitlement_snapshot(latest_subscription(db, workspace_id))
    if not snapshot["entitlements"].get(entitlement):
        if snapshot["read_only"]:
            raise HTTPException(402, "Тариф завершён. Данные сохранены в режиме просмотра.")
        raise HTTPException(403, "Функция недоступна на текущем тарифе.")
    return snapshot


def public_plans() -> list[dict]:
    return [PLAN_CATALOG[code] for code in ("trial", "pro", "business")]


def apply_subscription_event(
    db: Session,
    *,
    provider: str,
    external_event_id: str,
    event_type: str,
    workspace_id: str,
    plan_code: str,
    subscription_status: SubscriptionStatus,
    provider_customer_id: str = "",
    provider_subscription_id: str = "",
    period_started_at: datetime | None = None,
    period_expires_at: datetime | None = None,
    cancel_at_period_end: bool = False,
    payload: dict | None = None,
) -> tuple[Subscription, bool]:
    """Apply one already verified provider event exactly once.

    Provider adapters must verify their native webhook signature before calling
    this function. No browser redirect or checkout query can activate access.
    """
    provider = provider.strip().lower()
    external_event_id = external_event_id.strip()
    if not provider or provider == "not_configured" or not external_event_id:
        raise ValueError("Verified billing provider and event id are required")
    if plan_code not in {"pro", "business"}:
        raise ValueError("Only paid plans can be activated by a provider event")
    if subscription_status == SubscriptionStatus.active and period_expires_at is None:
        raise ValueError("Active paid access requires a verified billing period end")
    existing = db.scalar(select(BillingEvent).where(BillingEvent.provider == provider, BillingEvent.external_event_id == external_event_id))
    if existing:
        return latest_subscription(db, existing.workspace_id), False
    source_payload = payload or {}
    encoded = json.dumps(source_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    event = BillingEvent(
        workspace_id=workspace_id,
        subscription_id=latest_subscription(db, workspace_id).id,
        provider=provider,
        external_event_id=external_event_id,
        event_type=event_type[:80],
        payload_sha256=hashlib.sha256(encoded).hexdigest(),
        payload=source_payload,
    )
    db.add(event)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(BillingEvent).where(BillingEvent.provider == provider, BillingEvent.external_event_id == external_event_id))
        if existing is None:
            raise
        return latest_subscription(db, existing.workspace_id), False
    subscription = latest_subscription(db, workspace_id, lock=True)
    subscription.plan_code = plan_code
    subscription.status = subscription_status
    subscription.provider = provider
    subscription.provider_customer_id = provider_customer_id or subscription.provider_customer_id
    subscription.provider_subscription_id = provider_subscription_id or subscription.provider_subscription_id
    subscription.current_period_started_at = period_started_at
    subscription.current_period_expires_at = period_expires_at
    subscription.cancel_at_period_end = cancel_at_period_end
    subscription.canceled_at = datetime.now(timezone.utc) if subscription_status == SubscriptionStatus.canceled else None
    db.commit()
    db.refresh(subscription)
    return subscription, True
