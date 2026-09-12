from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.data_health import evaluate_source_snapshot, expected_coverage
from app.director_router import _source
from app.seller_data_router import products
from app.smart_fbo_router import snapshot_plan


class Query:
    def __init__(self, row):
        self.row = row

    def filter(self, *args):
        return self

    def first(self):
        return self.row


class Db:
    def __init__(self, connection):
        self.connection = connection

    def query(self, *args):
        return Query(self.connection)


def snapshot(created_at, payload, snapshot_id="snapshot-1"):
    return SimpleNamespace(id=snapshot_id, created_at=created_at, source_updated_at=created_at, payload=payload)


def test_finance_twenty_minutes_old_is_healthy_under_daily_policy():
    now = datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc)
    coverage = expected_coverage("finance", now=now, period_days=30)
    row = snapshot(now - timedelta(minutes=20), {**coverage, "complete": True})

    result = evaluate_source_snapshot(row, "finance", now=now, period_days=30)

    assert result["status"] == "healthy"
    assert result["age_seconds"] == 1200
    assert result["complete"] is True


def test_expired_stocks_are_stale_in_policy_director_seller_and_fbo(monkeypatch):
    now = datetime.now(timezone.utc)
    old = now - timedelta(hours=3)
    stocks = snapshot(old, {"rows": [{"nm_id": 1, "warehouse_id": 10, "warehouse_name": "A", "quantity": 5}]}, "stocks-1")
    sales = snapshot(now, {"items": [{"nm_id": 1, "vendor_code": "SKU", "title": "Item", "orders": 14, "period_days": 7, "avg_daily_orders": 2}]}, "sales-1")
    catalog = snapshot(now, {"items": [{"nm_id": 1, "vendor_code": "SKU", "title": "Item"}], "count": 1}, "catalog-1")
    store = SimpleNamespace(id="s1", name="Store", workspace_id="w1")

    assert evaluate_source_snapshot(stocks, "stocks", now=now)["status"] == "stale"
    assert _source(stocks, "stocks", now=now)["state"] == "stale"

    monkeypatch.setattr("app.seller_data_router.resolve_store", lambda *args: store)
    monkeypatch.setattr("app.seller_data_router._refresh", lambda *args, **kwargs: SimpleNamespace(id="analytics-job"))
    monkeypatch.setattr(
        "app.seller_data_router.latest_snapshot",
        lambda db, store_id, marketplace, snapshot_type: {"stocks": stocks, "sales_velocity_7d": sales, "catalog": catalog}[snapshot_type],
    )
    seller = products(store_id="s1", user=SimpleNamespace(id="u1"), db=Db(SimpleNamespace(enabled=True)))
    assert seller["source_health"]["stocks"]["status"] == "stale"
    assert seller["sync_required"] is True

    monkeypatch.setattr("app.smart_fbo_router.resolve_store", lambda *args: store)
    monkeypatch.setattr("app.smart_fbo_router._queue_refresh", lambda *args, **kwargs: SimpleNamespace(id="analytics-job"))
    monkeypatch.setattr(
        "app.smart_fbo_router.latest_snapshot",
        lambda db, store_id, marketplace, snapshot_type: stocks if snapshot_type == "stocks" else sales,
    )
    fbo = snapshot_plan(store_id="s1", current_user=SimpleNamespace(id="u1"), db=Db(SimpleNamespace(enabled=True)))
    assert fbo["source_health"]["stocks"]["status"] == "stale"
    assert fbo["sync_required"] is True


def test_midnight_period_rollover_and_partial_import_are_never_complete():
    # 21:05 UTC is 00:05 on the next marketplace day in Europe/Moscow.
    now = datetime(2026, 9, 11, 21, 5, tzinfo=timezone.utc)
    expected = expected_coverage("finance", now=now, period_days=30)
    yesterday = (datetime.fromisoformat(expected["date_to"]) - timedelta(days=1)).date().isoformat()
    old_period = snapshot(
        now - timedelta(minutes=10),
        {"date_from": "2026-08-12", "date_to": yesterday, "complete": True},
    )
    partial_current = snapshot(now - timedelta(minutes=1), {**expected, "complete": False})

    rollover = evaluate_source_snapshot(old_period, "finance", now=now, period_days=30)
    partial = evaluate_source_snapshot(partial_current, "finance", now=now, period_days=30)

    assert rollover["status"] == "incomplete"
    assert rollover["complete"] is False
    assert rollover["coverage_matches"] is False
    assert partial["status"] == "incomplete"
    assert partial["complete"] is False
