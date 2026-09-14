import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.billing_service import apply_subscription_event, entitlement_snapshot
from app.db import Base, SessionLocal, engine as app_engine
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


def test_provider_event_replay_rejects_another_workspace():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        first_workspace = Workspace(name="First billing tenant")
        second_workspace = Workspace(name="Second billing tenant")
        db.add_all([first_workspace, second_workspace])
        db.flush()
        db.add_all([
            Subscription(workspace_id=first_workspace.id, plan_code="trial", status=SubscriptionStatus.trial),
            Subscription(workspace_id=second_workspace.id, plan_code="trial", status=SubscriptionStatus.trial),
        ])
        db.commit()
        period_end = datetime.now(timezone.utc) + timedelta(days=30)
        args = dict(
            provider="test_provider",
            external_event_id="tenant-bound-event",
            event_type="subscription.activated",
            plan_code="pro",
            subscription_status=SubscriptionStatus.active,
            provider_customer_id="customer-1",
            provider_subscription_id="subscription-1",
            period_expires_at=period_end,
            payload={"safe": "metadata"},
        )
        apply_subscription_event(db, workspace_id=first_workspace.id, **args)

        with pytest.raises(ValueError, match="replay identity"):
            apply_subscription_event(db, workspace_id=second_workspace.id, **args)


@pytest.mark.parametrize(
    "changed",
    [
        {"event_type": "subscription.renewed"},
        {"plan_code": "business"},
        {"subscription_status": SubscriptionStatus.past_due},
        {"provider_customer_id": "customer-2"},
        {"provider_subscription_id": "subscription-2"},
        {"period_started_at": datetime(2026, 9, 2, tzinfo=timezone.utc)},
        {"period_expires_at": datetime(2026, 11, 1, tzinfo=timezone.utc)},
        {"cancel_at_period_end": True},
        {"payload": {"safe": "changed"}},
    ],
)
def test_provider_event_replay_rejects_changed_semantics(changed):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        workspace = Workspace(name="Immutable billing event")
        db.add(workspace)
        db.flush()
        db.add(Subscription(workspace_id=workspace.id, plan_code="trial", status=SubscriptionStatus.trial))
        db.commit()
        args = dict(
            provider="test_provider",
            external_event_id="immutable-event",
            event_type="subscription.activated",
            workspace_id=workspace.id,
            plan_code="pro",
            subscription_status=SubscriptionStatus.active,
            provider_customer_id="customer-1",
            provider_subscription_id="subscription-1",
            period_started_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            period_expires_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
            cancel_at_period_end=False,
            payload={"safe": "metadata"},
        )
        apply_subscription_event(db, **args)

        with pytest.raises(ValueError, match="replay identity"):
            apply_subscription_event(db, **(args | changed))


@pytest.mark.parametrize("payload", [[], "", 0, False])
def test_provider_event_payload_must_be_an_object(payload):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        workspace = Workspace(name="Billing payload validation")
        db.add(workspace)
        db.flush()
        db.add(Subscription(workspace_id=workspace.id, plan_code="trial", status=SubscriptionStatus.trial))
        db.commit()
        with pytest.raises(ValueError, match="payload must be an object"):
            apply_subscription_event(
                db,
                provider="test_provider",
                external_event_id="invalid-payload",
                event_type="subscription.activated",
                workspace_id=workspace.id,
                plan_code="pro",
                subscription_status=SubscriptionStatus.active,
                period_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                payload=payload,
            )


def test_provider_event_freezes_the_caller_payload():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        workspace = Workspace(name="Frozen billing payload")
        db.add(workspace)
        db.flush()
        db.add(Subscription(workspace_id=workspace.id, plan_code="trial", status=SubscriptionStatus.trial))
        db.commit()
        payload = {"nested": {"value": "original"}}
        args = dict(
            provider="test_provider",
            external_event_id="frozen-payload",
            event_type="subscription.activated",
            workspace_id=workspace.id,
            plan_code="pro",
            subscription_status=SubscriptionStatus.active,
            period_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        apply_subscription_event(db, payload=payload, **args)
        payload["nested"]["value"] = "mutated"
        _, applied = apply_subscription_event(db, payload={"nested": {"value": "original"}}, **args)
        assert applied is False


@pytest.mark.parametrize("transaction_end", ["rollback", "close"])
def test_provider_event_stays_in_caller_transaction(transaction_end):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as setup:
        workspace = Workspace(name="Caller-owned billing")
        setup.add(workspace)
        setup.flush()
        workspace_id = workspace.id
        setup.add(Subscription(workspace_id=workspace_id, plan_code="trial", status=SubscriptionStatus.trial))
        setup.commit()

    db = Session(engine)
    db.add(User(email=f"pending-{transaction_end}@example.com", password_hash="not-used"))
    apply_subscription_event(
        db,
        provider="test_provider",
        external_event_id=f"caller-{transaction_end}",
        event_type="subscription.activated",
        workspace_id=workspace_id,
        plan_code="pro",
        subscription_status=SubscriptionStatus.active,
        period_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        payload={"safe": "metadata"},
    )
    getattr(db, transaction_end)()

    with Session(engine) as check:
        assert check.scalar(select(User).where(User.email == f"pending-{transaction_end}@example.com")) is None
        assert check.scalar(select(BillingEvent).where(BillingEvent.external_event_id == f"caller-{transaction_end}")) is None
        current = check.scalar(select(Subscription).where(Subscription.workspace_id == workspace_id))
        assert current.plan_code == "trial"
        assert current.status == SubscriptionStatus.trial


@pytest.mark.skipif(app_engine.dialect.name != "postgresql", reason="two real PostgreSQL billing transactions")
def test_concurrent_provider_event_preserves_both_callers_pending_rows():
    with SessionLocal() as setup:
        workspace = Workspace(name=f"Concurrent billing {uuid.uuid4().hex}")
        setup.add(workspace)
        setup.flush()
        workspace_id = workspace.id
        setup.add(Subscription(workspace_id=workspace_id, plan_code="trial", status=SubscriptionStatus.trial))
        setup.commit()

    barrier = threading.Barrier(2)
    event_id = f"concurrent-{uuid.uuid4().hex}"
    period_end = datetime(2026, 10, 1, tzinfo=timezone.utc)

    def apply(number):
        email = f"billing-pending-{number}-{uuid.uuid4().hex}@example.com"
        with SessionLocal() as db:
            backend_pid = db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            db.add(User(email=email, password_hash="not-used"))
            barrier.wait(timeout=5)
            subscription, applied = apply_subscription_event(
                db,
                provider="test_provider",
                external_event_id=event_id,
                event_type="subscription.activated",
                workspace_id=workspace_id,
                plan_code="pro",
                subscription_status=SubscriptionStatus.active,
                provider_customer_id="customer-1",
                provider_subscription_id="subscription-1",
                period_expires_at=period_end,
                payload={"safe": "metadata"},
            )
            with SessionLocal() as observer:
                assert observer.scalar(select(User).where(User.email == email)) is None
            db.commit()
            return subscription.id, applied, email, backend_pid

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(apply, [1, 2]))

    assert results[0][0] == results[1][0]
    assert sorted(result[1] for result in results) == [False, True]
    assert results[0][3] != results[1][3]
    with SessionLocal() as check:
        assert check.query(BillingEvent).filter_by(provider="test_provider", external_event_id=event_id).count() == 1
        assert all(check.scalar(select(User).where(User.email == result[2])) is not None for result in results)


@pytest.mark.skipif(app_engine.dialect.name != "postgresql", reason="two real PostgreSQL billing transactions")
def test_cross_workspace_insert_conflict_preserves_loser_pending_row():
    with SessionLocal() as setup:
        workspaces = [Workspace(name=f"Billing conflict {uuid.uuid4().hex}") for _ in range(2)]
        setup.add_all(workspaces)
        setup.flush()
        workspace_ids = [workspace.id for workspace in workspaces]
        setup.add_all([
            Subscription(workspace_id=workspace_id, plan_code="trial", status=SubscriptionStatus.trial)
            for workspace_id in workspace_ids
        ])
        setup.commit()

    first_miss = threading.Barrier(2)
    event_id = f"cross-workspace-{uuid.uuid4().hex}"

    def apply(workspace_id):
        email = f"billing-conflict-{uuid.uuid4().hex}@example.com"
        with SessionLocal() as db:
            backend_pid = db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            db.add(User(email=email, password_hash="not-used"))
            original_scalar = db.scalar
            synchronized = False

            def scalar(statement, *args, **kwargs):
                nonlocal synchronized
                result = original_scalar(statement, *args, **kwargs)
                entities = {
                    description.get("entity")
                    for description in getattr(statement, "column_descriptions", ())
                }
                if not synchronized and BillingEvent in entities:
                    assert result is None
                    synchronized = True
                    first_miss.wait(timeout=5)
                return result

            db.scalar = scalar
            applied = None
            try:
                _, applied = apply_subscription_event(
                    db,
                    provider="test_provider",
                    external_event_id=event_id,
                    event_type="subscription.activated",
                    workspace_id=workspace_id,
                    plan_code="pro",
                    subscription_status=SubscriptionStatus.active,
                    provider_customer_id="customer-1",
                    provider_subscription_id="subscription-1",
                    period_expires_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
                    payload={"safe": "metadata"},
                )
            except ValueError as error:
                assert "replay identity" in str(error)
            db.commit()
            return applied, email, backend_pid

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(apply, workspace_ids))

    assert sorted(result[0] for result in results if result[0] is not None) == [True]
    assert results[0][2] != results[1][2]
    with SessionLocal() as check:
        assert check.query(BillingEvent).filter_by(provider="test_provider", external_event_id=event_id).count() == 1
        assert all(check.scalar(select(User).where(User.email == result[1])) is not None for result in results)
        assert sorted(
            check.scalar(select(Subscription).where(Subscription.workspace_id == workspace_id)).plan_code
            for workspace_id in workspace_ids
        ) == ["pro", "trial"]
