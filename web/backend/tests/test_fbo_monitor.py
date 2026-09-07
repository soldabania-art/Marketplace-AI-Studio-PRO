from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.fbo_monitor import _advisory_key, _group_key, _recently_checked


def test_group_key_is_store_scoped_when_store_exists():
    assert _group_key('store-123', 'user-1') == ('store', 'store-123')


def test_group_key_keeps_legacy_user_fallback():
    assert _group_key(None, 'user-1') == ('legacy-user', 'user-1')


def test_advisory_key_is_stable_signed_bigint():
    key = _advisory_key('fbo:wildberries:store:store-123')
    assert key == _advisory_key('fbo:wildberries:store:store-123')
    assert -(2**63) <= key < 2**63
    assert key != _advisory_key('fbo:wildberries:store:store-456')


def test_recently_checked_enforces_account_pacing():
    recent = SimpleNamespace(last_checked_at=datetime.now(timezone.utc) - timedelta(seconds=4))
    old = SimpleNamespace(last_checked_at=datetime.now(timezone.utc) - timedelta(seconds=30))
    assert _recently_checked([recent], 10) is True
    assert _recently_checked([old], 10) is False


def test_recently_checked_accepts_sqlite_naive_timestamps():
    recent_naive = SimpleNamespace(last_checked_at=datetime.utcnow() - timedelta(seconds=2))
    assert _recently_checked([recent_naive], 10) is True
