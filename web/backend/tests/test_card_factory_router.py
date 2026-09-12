import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.ai_card_factory import build_fact_set
from app.ai_generation_service import stable_hash
from app.card_factory_router import ConfirmPublicationRequest, GenerateCardRequest, PreparePublicationRequest, _find_card, _load_card, _media_verification_result, _photo_urls, _publication_payload, _verification_result, generate, generations, prepare_publication, publish_card, publish_media
from app.external_write_guard import require_external_write_allowed
from app.models import AutomationControl, OperationalAuditEvent, PublicationStatus


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


class StopAwareDb:
    def __init__(self, row, controls):
        self.row = row
        self.controls = iter(controls)
        self.current_control = None
        self.events = []
        self.commits = 0

    def query(self, model):
        if model is AutomationControl:
            self.current_control = next(self.controls)
            return PublicationQuery(self.current_control)
        return PublicationQuery(self.row)

    def expire_all(self): pass
    def get_bind(self): return SimpleNamespace(dialect=SimpleNamespace(name='sqlite'))
    def add(self, item): self.events.append(item)
    def commit(self): self.commits += 1
    def flush(self): pass


def _control(stopped, *, store_id='s1', workspace_id='w1'):
    return SimpleNamespace(
        id=f'control-{store_id}', workspace_id=workspace_id, store_id=store_id,
        marketplace='wildberries', stopped=stopped, reason='incident',
    )


def _publication(**overrides):
    proposed = {'title': 'New', 'description': 'New'}
    payload_sha256 = stable_hash(proposed)
    values = dict(
        id='p1', generation_id='g1', store_id='s1', subject_id='42', marketplace='wildberries',
        status=PublicationStatus.prepared, payload_sha256=payload_sha256,
        diff_payload={'grounding': {
            'status': 'verified', 'publish_ready': True, 'fact_set_sha256': 'facts',
            'payload_sha256': payload_sha256,
        }},
        attempt_count=0, error='', approved_at=None, submitted_at=None,
        created_at=datetime.now(timezone.utc), source_payload={'title':'Old','description':'Old'},
        proposed_payload=proposed, fact_set_sha256='facts', source_card_sha256='source',
        provider_response={}, verification_status='not_checked', verification_payload={},
        verification_attempt_count=0, last_verified_at=None, verified_at=None, asset_payload={},
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _patch_publish_dependencies(monkeypatch, store):
    monkeypatch.setattr('app.card_factory_router._resolve_connected_store',lambda db,user,store_id:store)
    monkeypatch.setattr('app.card_factory_router.require_store_admin',lambda db,user,store:None)
    monkeypatch.setattr('app.card_factory_router.require_entitlement',lambda db,workspace_id,entitlement:None)


@pytest.mark.parametrize(('endpoint','confirmation'), [(publish_card,'ОПУБЛИКОВАТЬ'), (publish_media,'ОПУБЛИКОВАТЬ ФОТО')])
def test_emergency_stop_blocks_direct_publish_api_before_any_wb_call(monkeypatch, endpoint, confirmation):
    row = _publication(id='p2' if endpoint is publish_media else 'p1', asset_payload={})
    store = SimpleNamespace(id='s1', workspace_id='w1')
    db = StopAwareDb(row, [_control(True)])
    calls = []
    _patch_publish_dependencies(monkeypatch, store)
    monkeypatch.setattr('app.card_factory_router._connection',lambda db,store_id: calls.append('connection'))
    monkeypatch.setattr('app.card_factory_router.update_wb_card',lambda *args,**kwargs: calls.append('card-write'))
    monkeypatch.setattr('app.card_factory_router.upload_wb_media_file',lambda *args,**kwargs: calls.append('media-write'))

    with pytest.raises(HTTPException) as error:
        asyncio.run(endpoint(row.id, ConfirmPublicationRequest(
            store_id='s1', payload_sha256=row.payload_sha256, confirmation=confirmation,
        ), user=SimpleNamespace(id='u1'), db=db))

    assert error.value.status_code == 423
    assert calls == []
    assert row.attempt_count == 0
    audit = next(item for item in db.events if isinstance(item, OperationalAuditEvent))
    assert audit.event_type == 'external_write.refused'
    assert audit.payload['provider_request_started'] is False
    assert audit.payload['stop_scope'] == {
        'type':'store_marketplace', 'workspace_id':'w1', 'store_id':'s1',
        'marketplace':'wildberries', 'automation_control_id':'control-s1',
    }


@pytest.mark.parametrize('initial_status', [PublicationStatus.prepared, PublicationStatus.failed])
def test_stop_enabled_during_long_card_preflight_blocks_writer_and_retry(monkeypatch, initial_status):
    row = _publication(status=initial_status)
    store = SimpleNamespace(id='s1', workspace_id='w1')
    db = StopAwareDb(row, [_control(False), _control(True)])
    writes = []
    _patch_publish_dependencies(monkeypatch, store)
    monkeypatch.setattr('app.card_factory_router._connection',lambda db,store_id:SimpleNamespace())
    monkeypatch.setattr('app.card_factory_router.decrypt_connection',lambda connection:'token')
    async def fetch(*args, **kwargs): return {'title':'Old','description':'Old'}
    async def write(*args, **kwargs):
        kwargs['before_send']()
        writes.append('write')
        return {}
    monkeypatch.setattr('app.card_factory_router.fetch_wb_card',fetch)
    monkeypatch.setattr('app.card_factory_router.update_wb_card',write)
    monkeypatch.setattr('app.card_factory_router.build_card_update',lambda card,**kwargs:{'title':card['title'],'description':card['description']})
    monkeypatch.setattr('app.card_factory_router.build_fact_set',lambda card:{'sha256':'facts'})
    monkeypatch.setattr('app.card_factory_router.stable_hash', lambda card: row.payload_sha256 if card.get('title') == 'New' else 'source')

    with pytest.raises(HTTPException) as error:
        asyncio.run(publish_card('p1', ConfirmPublicationRequest(
            store_id='s1', payload_sha256=row.payload_sha256, confirmation='ОПУБЛИКОВАТЬ',
        ), user=SimpleNamespace(id='u1'), db=db))

    assert error.value.status_code == 423
    assert writes == []
    assert row.status == initial_status


def test_explicit_resume_allows_card_writer(monkeypatch):
    row = _publication()
    store = SimpleNamespace(id='s1', workspace_id='w1')
    db = StopAwareDb(row, [_control(False), _control(False)])
    writes = []
    _patch_publish_dependencies(monkeypatch, store)
    monkeypatch.setattr('app.card_factory_router._connection',lambda db,store_id:SimpleNamespace())
    monkeypatch.setattr('app.card_factory_router.decrypt_connection',lambda connection:'token')
    async def fetch(*args, **kwargs): return {'title':'Old','description':'Old'}
    async def write(*args, **kwargs):
        kwargs['before_send']()
        writes.append('write')
        return {'accepted':True}
    monkeypatch.setattr('app.card_factory_router.fetch_wb_card',fetch)
    monkeypatch.setattr('app.card_factory_router.update_wb_card',write)
    monkeypatch.setattr('app.card_factory_router.build_card_update',lambda card,**kwargs:{'title':card['title'],'description':card['description']})
    monkeypatch.setattr('app.card_factory_router.build_fact_set',lambda card:{'sha256':'facts'})
    monkeypatch.setattr('app.card_factory_router.stable_hash', lambda card: row.payload_sha256 if card.get('title') == 'New' else 'source')

    result = asyncio.run(publish_card('p1', ConfirmPublicationRequest(
        store_id='s1', payload_sha256=row.payload_sha256, confirmation='ОПУБЛИКОВАТЬ',
    ), user=SimpleNamespace(id='u1'), db=db))

    assert writes == ['write']
    assert result['status'] == PublicationStatus.submitted.value


def test_regeneration_cannot_bypass_exhausted_trial(monkeypatch):
    provider_calls = []
    store = SimpleNamespace(id='s1', workspace_id='w1')
    monkeypatch.setattr('app.card_factory_router._resolve_connected_store', lambda db,user,store_id: store)
    monkeypatch.setattr('app.card_factory_router._load_card', lambda db,store_id,nm_id: ({'nm_id':nm_id}, SimpleNamespace()))
    monkeypatch.setattr('app.card_factory_router.build_fact_set', lambda source: {'sha256':'facts'})
    monkeypatch.setattr('app.card_factory_router.reserve_trial_card', lambda db,workspace_id: (_ for _ in ()).throw(HTTPException(402, 'exhausted')))
    monkeypatch.setattr('app.card_factory_router.generate_grounded_copy', lambda facts: provider_calls.append('generate'))
    with pytest.raises(HTTPException) as error:
        generate(GenerateCardRequest(store_id='s1', nm_id=42), user=SimpleNamespace(id='u1'), db=SimpleNamespace())
    assert error.value.status_code == 402
    assert provider_calls == []


def test_saved_generation_history_remains_readable_without_ai_entitlement(monkeypatch):
    saved = SimpleNamespace(id='g-saved')
    class HistoryQuery:
        def filter(self, *args): return self
        def order_by(self, *args): return self
        def limit(self, value): return self
        def all(self): return [saved]
    db = SimpleNamespace(query=lambda model: HistoryQuery())
    monkeypatch.setattr('app.card_factory_router.resolve_store', lambda db,user,store_id: SimpleNamespace(id='s1'))
    monkeypatch.setattr('app.card_factory_router.public_generation', lambda row: {'id':row.id})
    assert generations(store_id='s1', user=SimpleNamespace(id='u1'), db=db) == {'items':[{'id':'g-saved'}]}


def test_stop_from_another_tenant_does_not_match_current_scope():
    class TenantQuery(PublicationQuery):
        def filter(self, *criteria):
            requested = {str(item.left).rsplit('.', 1)[-1]: item.right.value for item in criteria}
            if any(getattr(self.row, key) != value for key, value in requested.items()):
                self.row = None
            return self

    class TenantDb(StopAwareDb):
        def query(self, model):
            assert model is AutomationControl
            return TenantQuery(_control(True, store_id='other-store', workspace_id='other-workspace'))

    db = TenantDb(_publication(), [])
    require_external_write_allowed(
        db, workspace_id='w1', store_id='s1', marketplace='wildberries', user_id='u1',
        operation='card.publish', entity_type='card_publication', entity_id='p1',
    )
    assert db.events == []


def test_publish_requires_exact_confirmation_before_any_wb_call(monkeypatch):
    row=SimpleNamespace(
        id='p1',generation_id='g1',store_id='s1',subject_id='42',marketplace='wildberries',
        status=PublicationStatus.prepared,payload_sha256='a'*64,diff_payload={},
        attempt_count=0,error='',approved_at=None,submitted_at=None,created_at=datetime.now(timezone.utc),
    )
    store=SimpleNamespace(id='s1',workspace_id='w1')
    monkeypatch.setattr('app.card_factory_router._resolve_connected_store',lambda db,user,store_id:store)
    monkeypatch.setattr('app.card_factory_router.require_store_admin',lambda db,user,store:None)
    monkeypatch.setattr('app.card_factory_router.require_entitlement',lambda db,workspace_id,entitlement:None)
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
    monkeypatch.setattr('app.card_factory_router.require_entitlement',lambda db,workspace_id,entitlement:None)
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


def test_direct_publish_rejects_legacy_or_edited_payload_without_grounding_proof(monkeypatch):
    row = _publication(diff_payload={})
    store = SimpleNamespace(id="s1", workspace_id="w1")
    calls = []
    _patch_publish_dependencies(monkeypatch, store)
    monkeypatch.setattr("app.card_factory_router.require_external_write_allowed", lambda *args, **kwargs: calls.append("guard"))
    monkeypatch.setattr(
        "app.card_factory_router._connection",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("WB access must not begin")),
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(publish_card(
            row.id,
            ConfirmPublicationRequest(
                store_id="s1", payload_sha256=row.payload_sha256, confirmation="ОПУБЛИКОВАТЬ",
            ),
            user=SimpleNamespace(id="u1"),
            db=PublicationDb(row),
        ))
    assert error.value.status_code == 409
    assert calls == []


def test_prepare_publication_revalidates_saved_generation_before_creating_diff(monkeypatch):
    source = {"nm_id": 42, "title": "Сумка", "description": "Сумка"}
    fact_set = build_fact_set(source)
    invented = "Сумка из натуральной кожи"
    generation = SimpleNamespace(
        id="11111111-1111-1111-1111-111111111111", fact_set_sha256=fact_set["sha256"],
        result_payload={
            "wb_title": invented, "ozon_title": invented, "description": invented,
            "seo_phrases": [], "visual_plan": ["Preview"], "used_fact_ids": ["card.title"],
            "claims": [{"field": "description", "text": invented, "fact_id": "card.title"}],
        },
    )
    store = SimpleNamespace(id="s1", workspace_id="w1")
    snapshot = SimpleNamespace(created_at=datetime.now(timezone.utc))
    monkeypatch.setattr("app.card_factory_router._resolve_connected_store", lambda *args: store)
    monkeypatch.setattr("app.card_factory_router.require_entitlement", lambda *args: None)
    monkeypatch.setattr("app.card_factory_router._load_card", lambda *args: (source, snapshot))

    with pytest.raises(HTTPException) as error:
        prepare_publication(
            PreparePublicationRequest(store_id="s1", nm_id=42, generation_id="11111111-1111-1111-1111-111111111111"),
            user=SimpleNamespace(id="u1"),
            db=PublicationDb(generation),
        )

    assert error.value.status_code == 422
    assert error.value.detail["code"] == "AI_GROUNDING_REVIEW_REQUIRED"
    assert error.value.detail["human_preview_available"] is True


def test_direct_publish_rejects_proposed_payload_changed_after_grounding(monkeypatch):
    row = _publication()
    row.proposed_payload = {"title": "Сумка из кожи", "description": "Изменено после проверки"}
    store = SimpleNamespace(id="s1", workspace_id="w1")
    calls = []
    _patch_publish_dependencies(monkeypatch, store)
    monkeypatch.setattr(
        "app.card_factory_router.require_external_write_allowed",
        lambda *args, **kwargs: calls.append("guard"),
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(publish_card(
            row.id,
            ConfirmPublicationRequest(
                store_id="s1", payload_sha256=row.payload_sha256, confirmation="ОПУБЛИКОВАТЬ",
            ),
            user=SimpleNamespace(id="u1"),
            db=PublicationDb(row),
        ))

    assert error.value.status_code == 409
    assert calls == []
