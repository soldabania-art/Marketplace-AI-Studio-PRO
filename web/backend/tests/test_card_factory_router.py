from datetime import datetime, timezone
from types import SimpleNamespace

from app.card_factory_router import _load_card


def test_load_card_selects_nm_id_only_inside_requested_store_snapshot(monkeypatch):
    snapshot = SimpleNamespace(
        created_at=datetime.now(timezone.utc),
        payload={"items": [{"nm_id": 41, "title": "First"}, {"nm_id": 42, "title": "Second"}]},
    )
    calls = []

    def latest(db, store_id, marketplace, snapshot_type):
        calls.append((store_id, marketplace, snapshot_type))
        return snapshot

    monkeypatch.setattr("app.card_factory_router.latest_snapshot", latest)
    card, selected_snapshot = _load_card(SimpleNamespace(), "store-7", 42)
    assert card["title"] == "Second"
    assert selected_snapshot is snapshot
    assert calls == [("store-7", "wildberries", "catalog")]
