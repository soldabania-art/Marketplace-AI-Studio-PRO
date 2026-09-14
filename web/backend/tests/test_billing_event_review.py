"""Independent T10A review: immutable identity and caller-owned transactions."""
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.billing_service import apply_subscription_event
from app.db import Base, SessionLocal, engine
from app.models import BillingEvent, PurchaseIntent, Subscription, SubscriptionStatus, User, Workspace

Base.metadata.create_all(bind=engine)


def seed():
    with SessionLocal() as db:
        workspace = Workspace(name='Independent billing review')
        user = User(email=f'billing-review-{uuid.uuid4().hex}@example.com', password_hash='not-used')
        db.add_all([workspace, user])
        db.flush()
        subscription = Subscription(workspace_id=workspace.id, plan_code='trial', status=SubscriptionStatus.trial,
                                    created_at=datetime.now(timezone.utc)-timedelta(days=1))
        intent = PurchaseIntent(workspace_id=workspace.id, created_by_user_id=user.id, requested_plan='pro',
                                active_channel='wb', requested_stores=3, requested_modules=['profit'])
        db.add_all([subscription, intent])
        db.commit()
        return workspace.id, subscription.id, intent.id, intent.status


def args(workspace_id):
    now = datetime.now(timezone.utc)
    return dict(provider='review-provider', external_event_id=uuid.uuid4().hex,
                event_type='subscription.activated', workspace_id=workspace_id, plan_code='pro',
                subscription_status=SubscriptionStatus.active, provider_customer_id='customer-review',
                provider_subscription_id='subscription-review', period_started_at=now,
                period_expires_at=now+timedelta(days=30), cancel_at_period_end=False,
                payload={'reference': 'review', 'nested': {'b': 2, 'a': 1}})


def test_duplicate_returns_original_subscription_after_a_newer_one_exists():
    workspace_id, original_id, _, _ = seed()
    request = args(workspace_id)
    with SessionLocal() as db:
        _, applied = apply_subscription_event(db, **request)
        assert applied
        db.commit()
        newer = Subscription(workspace_id=workspace_id, plan_code='trial', status=SubscriptionStatus.trial,
                             created_at=datetime.now(timezone.utc)+timedelta(hours=1))
        db.add(newer)
        db.commit()
        duplicate, applied = apply_subscription_event(db, **request)
        assert not applied
        assert duplicate.id == original_id
        assert db.get(Subscription, newer.id).plan_code == 'trial'


def test_timezone_equivalent_replay_is_the_same_immutable_event():
    workspace_id, subscription_id, _, _ = seed()
    request = args(workspace_id)
    with SessionLocal() as db:
        apply_subscription_event(db, **request)
        db.commit()
    equivalent = dict(request, period_started_at=request['period_started_at'].astimezone(timezone(timedelta(hours=4))),
                      period_expires_at=request['period_expires_at'].astimezone(timezone(timedelta(hours=-5))),
                      payload={'nested': {'a': 1, 'b': 2}, 'reference': 'review'})
    with SessionLocal() as db:
        result, applied = apply_subscription_event(db, **equivalent)
        assert not applied
        assert result.id == subscription_id


@pytest.mark.parametrize('field,value', [
    ('plan_code', 'business'),
    ('provider_customer_id', 'other-customer'),
    ('provider_subscription_id', 'other-subscription'),
    ('event_type', 'subscription.changed'),
    ('cancel_at_period_end', True),
])
def test_changed_semantics_with_same_provider_payload_are_rejected_without_rollback(field, value):
    workspace_id, subscription_id, _, _ = seed()
    request = args(workspace_id)
    with SessionLocal() as db:
        apply_subscription_event(db, **request)
        db.commit()
    email = f'caller-pending-{uuid.uuid4().hex}@example.com'
    with SessionLocal() as db:
        db.add(User(email=email, password_hash='not-used'))
        with pytest.raises(ValueError):
            apply_subscription_event(db, **dict(request, **{field: value}))
        db.commit()
    with SessionLocal() as db:
        assert db.scalar(select(User.id).where(User.email == email)) is not None
        assert db.get(Subscription, subscription_id).plan_code == 'pro'


def test_session_close_discards_event_subscription_intent_and_unrelated_pending_user():
    workspace_id, subscription_id, intent_id, initial_intent_status = seed()
    request = args(workspace_id)
    email = f'caller-rollback-{uuid.uuid4().hex}@example.com'
    with SessionLocal() as db:
        db.add(User(email=email, password_hash='not-used'))
        _, applied = apply_subscription_event(db, **request)
        assert applied
        # No commit: a caller failure must undo the entire operation.
    with SessionLocal() as db:
        assert db.scalar(select(BillingEvent.id).where(BillingEvent.external_event_id == request['external_event_id'])) is None
        assert db.get(Subscription, subscription_id).plan_code == 'trial'
        assert db.get(PurchaseIntent, intent_id).status == initial_intent_status
        assert db.scalar(select(User.id).where(User.email == email)) is None


def test_legacy_event_without_immutable_snapshot_is_not_acknowledged_as_identical():
    workspace_id, subscription_id, _, _ = seed()
    request = args(workspace_id)
    encoded = json.dumps(request['payload'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    with SessionLocal() as db:
        db.add(BillingEvent(workspace_id=workspace_id, subscription_id=subscription_id,
                            provider=request['provider'], external_event_id=request['external_event_id'],
                            event_type=request['event_type'], payload=request['payload'],
                            payload_sha256=hashlib.sha256(encoded).hexdigest()))
        db.commit()
    with SessionLocal() as db:
        with pytest.raises(ValueError):
            apply_subscription_event(db, **request)
        assert db.get(Subscription, subscription_id).plan_code == 'trial'
