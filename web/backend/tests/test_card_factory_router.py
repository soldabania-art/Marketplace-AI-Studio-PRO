import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.card_factory_router import ConfirmPublicationRequest, _find_card, _load_card, _media_verification_result, _photo_urls, _publication_payload, _verification_result, publish_card, publish_media
from app.models import PublicationStatus


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


def test_publication_payload_exposes_diff_and_hash_but_not_full_wb_payload():
    row=SimpleNamespace(
        id='p1',generation_id='g1',store_id='s1',subject_id='42',marketplace='wildberries',
        status=PublicationStatus.prepared,payload_sha256='a'*64,diff_payload={'title':{'before':'A','after':'B'}},
        attempt_count=0,error='',approved_at=None,submitted_at=None,created_at=datetime.now(timezone.utc),
        source_payload={'sizes':[{'skus':['secret-ish-barcode']}]},proposed_payload={'description':'full payload'},
    )
    result=_publication_payload(row)
    assert result['payload_sha256']=='a'*64
    assert result['diff']['title']['after']=='B'
    assert 'source_payload' not in result
    assert 'proposed_payload' not in result


def test_find_card_uses_exact_nm_id():
    assert _find_card([{'nm_id':41},{'nm_id':42,'title':'Right'}],42)['title']=='Right'
    assert _find_card([{'nm_id':41}],42) is None


@pytest.mark.parametrize(
    ("live", "expected"),
    [
        ({"title": "New", "description": "New description"}, "applied"),
        ({"title": "Old", "description": "Old description"}, "pending"),
        ({"title": "Third party", "description": "Changed elsewhere"}, "mismatch"),
    ],
)
def test_verification_result_distinguishes_applied_pending_and_mismatch(live, expected):
    publication = SimpleNamespace(
        proposed_payload={"title": "New", "description": "New description"},
        source_payload={"title": "Old", "description": "Old description"},
    )
    status, result = _verification_result(publication, live)
    assert status == expected
    assert result["fields"]["title"]["actual"] == live["title"]
    assert result["fields"]["description"]["matches"] is (expected == "applied")


def test_photo_urls_use_original_big_images_in_order():
    card = {"photos": [{"big": "https://wb/1.webp", "square": "small"}, {}, {"big": "https://wb/2.webp"}]}
    assert _photo_urls(card) == ["https://wb/1.webp", "https://wb/2.webp"]


@pytest.mark.parametrize(
    ("photos", "expected"),
    [
        ([{"big": "old-1"}, {"big": "old-2"}, {"big": "new-3"}], "applied"),
        ([{"big": "old-1"}, {"big": "old-2"}], "pending"),
        ([{"big": "changed"}, {"big": "old-2"}, {"big": "new-3"}], "mismatch"),
    ],
)
def test_media_verification_preserves_existing_photo_order(photos, expected):
    publication = SimpleNamespace(
        source_payload={"photo_urls": ["old-1", "old-2"]},
        diff_payload={"target_position": 3},
    )
    status, result = _media_verification_result(publication, {"photos": photos})
    assert status == expected
    assert result["target_position"] == 3
    assert result["existing_photos_unchanged"] is (expected != "mismatch")


class PublicationQuery:
    def __init__(self,row): self.row=row
    def filter(self,*args): return self
    def with_for_update(self): return self
    def first(self): return self.row


class PublicationDb:
    def __init__(self,row): self.row=row
    def query(self,*args): return PublicationQuery(self.row)


def test_publish_requires_exact_confirmation_before_any_wb_call(monkeypatch):
    row=SimpleNamespace(
        id='p1',generation_id='g1',store_id='s1',subject_id='42',marketplace='wildberries',
        status=PublicationStatus.prepared,payload_sha256='a'*64,diff_payload={},
        attempt_count=0,error='',approved_at=None,submitted_at=None,created_at=datetime.now(timezone.utc),
    )
    store=SimpleNamespace(id='s1',workspace_id='w1')
    monkeypatch.setattr('app.card_factory_router._resolve_connected_store',lambda db,user,store_id:store)
    monkeypatch.setattr('app.card_factory_router.require_store_admin',lambda db,user,store:None)
    with pytest.raises(HTTPException) as error:
        asyncio.run(publish_card(
            'p1',
            ConfirmPublicationRequest(store_id='s1',payload_sha256='a'*64,confirmation='да'),
            user=SimpleNamespace(id='u1'),
            db=PublicationDb(row),
        ))
    assert error.value.status_code==422
    assert row.status==PublicationStatus.prepared
    assert row.attempt_count==0


def test_media_publish_requires_separate_exact_confirmation(monkeypatch):
    row=SimpleNamespace(
        id='p2',generation_id='g2',store_id='s1',subject_id='42',marketplace='wildberries',
        status=PublicationStatus.prepared,payload_sha256='b'*64,diff_payload={},asset_payload={},source_payload={},
        attempt_count=0,error='',approved_at=None,submitted_at=None,created_at=datetime.now(timezone.utc),
    )
    store=SimpleNamespace(id='s1',workspace_id='w1')
    monkeypatch.setattr('app.card_factory_router._resolve_connected_store',lambda db,user,store_id:store)
    monkeypatch.setattr('app.card_factory_router.require_store_admin',lambda db,user,store:None)
    with pytest.raises(HTTPException) as error:
        asyncio.run(publish_media(
            'p2',
            ConfirmPublicationRequest(store_id='s1',payload_sha256='b'*64,confirmation='ОПУБЛИКОВАТЬ'),
            user=SimpleNamespace(id='u1'),
            db=PublicationDb(row),
        ))
    assert error.value.status_code==422
    assert row.status==PublicationStatus.prepared
    assert row.attempt_count==0
