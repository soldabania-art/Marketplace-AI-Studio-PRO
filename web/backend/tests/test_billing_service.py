from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.billing_service import apply_subscription_event, entitlement_snapshot
from app.db import Base
from app.models import BillingEvent, PurchaseIntent, Subscription, SubscriptionStatus, User, Workspace
from app.trial_service import _require_ai_generation, refund_trial_card, reserve_trial_card, trial_snapshot


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
    assert result["entitlements"]["community_access"] is False


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
    assert active["entitlements"]["community_access"] is True
    assert expired["read_only"] is True
    assert expired["entitlements"]["community_access"] is False


def test_every_inactive_paid_status_blocks_new_ai_generation():
    now = datetime.now(timezone.utc)
    rows = [
        subscription(plan_code="pro", status=SubscriptionStatus.active, current_period_expires_at=now - timedelta(seconds=1)),
        subscription(plan_code="pro", status=SubscriptionStatus.past_due, current_period_expires_at=now + timedelta(days=2)),
        subscription(plan_code="pro", status=SubscriptionStatus.canceled, current_period_expires_at=now + timedelta(days=2)),
    ]
    for row in rows:
        snapshot = trial_snapshot(row)
        with pytest.raises(HTTPException) as error:
            _require_ai_generation(snapshot)
        assert error.value.status_code == 402


def test_active_paid_snapshot_allows_new_ai_generation():
    row = subscription(
        plan_code="pro", status=SubscriptionStatus.active,
        current_period_expires_at=datetime.now(timezone.utc) + timedelta(days=2),
    )
    assert _require_ai_generation(trial_snapshot(row))["unlimited"] is True


def test_trial_reservations_lock_and_never_exceed_five(monkeypatch):
    row = subscription()
    locks = []
    monkeypatch.setattr("app.trial_service.workspace_subscription", lambda db, workspace_id, lock=False: locks.append(lock) or row)
    db = type("Db", (), {"commit": lambda self: None, "refresh": lambda self, value: None})()
    for expected_used in range(1, 6):
        reserve_trial_card(db, "w1")
        assert row.trial_ai_cards_used == expected_used
    with pytest.raises(HTTPException) as error:
        reserve_trial_card(db, "w1")
    assert error.value.status_code == 402
    assert locks == [True] * 6


def test_failed_first_reservation_does_not_reset_another_success(monkeypatch):
    started = datetime.now(timezone.utc)
    row = subscription(trial_started_at=started, trial_expires_at=started + timedelta(days=3), trial_ai_cards_used=2)
    monkeypatch.setattr("app.trial_service.workspace_subscription", lambda db, workspace_id, lock=False: row)
    db = type("Db", (), {"commit": lambda self: None})()
    refund_trial_card(db, "w1", started_now=True)
    assert row.trial_ai_cards_used == 1
    assert row.trial_started_at == started


def test_verified_provider_event_is_idempotent():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        workspace = Workspace(name="Billing QA")
        user = User(email="billing@example.com", password_hash="not-used")
        db.add_all([workspace, user])
        db.flush()
        db.add(Subscription(workspace_id=workspace.id, plan_code="trial", status=SubscriptionStatus.trial))
        db.add(PurchaseIntent(workspace_id=workspace.id, created_by_user_id=user.id, requested_plan="pro", active_channel="wb", requested_stores=3, requested_modules=["profit"]))
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
        intent = db.scalar(select(PurchaseIntent).where(PurchaseIntent.workspace_id == workspace.id))
        assert intent.status == "fulfilled"
        assert intent.fulfilled_at is not None
