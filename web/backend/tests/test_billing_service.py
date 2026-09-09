from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.billing_service import apply_subscription_event, entitlement_snapshot
from app.db import Base
from app.models import BillingEvent, Subscription, SubscriptionStatus, Workspace


def subscription(**values):
    defaults = {"workspace_id": "w1", "plan_code": "trial", "status": SubscriptionStatus.trial, "trial_ai_cards_limit": 5}
    defaults.update(values)
    return Subscription(**defaults)


def test_trial_entitlements_are_limited_before_first_success():
    result = entitlement_snapshot(subscription())
    assert result["access_status"] == "not_started"
    assert result["entitlements"]["stores_limit"] == 1
    assert result["entitlements"]["card_copy_generation"] is True
    assert result["entitlements"]["card_visual_generation"] is False
    assert result["entitlements"]["marketplace_publication"] is False


def test_expired_trial_keeps_read_only_access():
    now = datetime.now(timezone.utc)
    result = entitlement_snapshot(subscription(trial_started_at=now - timedelta(days=4), trial_expires_at=now - timedelta(days=1)), now=now)
    assert result["read_only"] is True
    assert result["entitlements"]["profit_center"] is True
    assert result["entitlements"]["card_copy_generation"] is False
    assert result["entitlements"]["stores_limit"] == 0


def test_paid_access_honors_status_and_period_end():
    now = datetime.now(timezone.utc)
    active = entitlement_snapshot(subscription(plan_code="pro", status=SubscriptionStatus.active, current_period_expires_at=now + timedelta(days=2), cancel_at_period_end=True), now=now)
    expired = entitlement_snapshot(subscription(plan_code="pro", status=SubscriptionStatus.active, current_period_expires_at=now - timedelta(seconds=1)), now=now)
    assert active["read_only"] is False
    assert active["cancel_at_period_end"] is True
    assert active["entitlements"]["marketplace_publication"] is True
    assert expired["read_only"] is True


def test_verified_provider_event_is_idempotent():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        workspace = Workspace(name="Billing QA")
        db.add(workspace)
        db.flush()
        db.add(Subscription(workspace_id=workspace.id, plan_code="trial", status=SubscriptionStatus.trial))
        db.commit()
        args = dict(
            provider="test_provider",
            external_event_id="event-1",
            event_type="subscription.activated",
            workspace_id=workspace.id,
            plan_code="pro",
            subscription_status=SubscriptionStatus.active,
            provider_customer_id="customer-1",
            provider_subscription_id="subscription-1",
            period_started_at=datetime.now(timezone.utc),
            period_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            payload={"safe": "metadata"},
        )
        first, applied = apply_subscription_event(db, **args)
        second, duplicated = apply_subscription_event(db, **args)
        assert applied is True
        assert duplicated is False
        assert first.plan_code == second.plan_code == "pro"
        assert db.scalar(select(BillingEvent).where(BillingEvent.external_event_id == "event-1")) is not None
