import asyncio
import base64
import hashlib
import inspect
from datetime import datetime, timedelta, timezone
from io import BytesIO
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from PIL import Image

from app.card_factory_router import (
    ConfirmPublicationRequest,
    FinalizeVisualRequest,
    GenerateVisualRequest,
    VerifyPublicationRequest,
    _media_verification_result,
    finalize_visual,
    generate_visual,
    publish_media,
    verify_media_publication,
)
from app.models import GenerationStatus, PublicationStatus


GENERATION_ID = "11111111-1111-1111-1111-111111111111"
OWN_HOST = "own.public.blob.vercel-storage.com"
PATHNAME = f"ai-assets/s1/42/{GENERATION_ID}.webp"
URL = f"https://{OWN_HOST}/{PATHNAME}"


class Query:
    def __init__(self, row):
        self.row = row

    def filter(self, *args):
        return self

    def with_for_update(self):
        return self

    def order_by(self, *args):
        return self

    def first(self):
        return self.row


class Db:
    def __init__(self, row):
        self.row = row
        self.commits = 0

    def query(self, *args):
        return Query(self.row)

    def commit(self):
        self.commits += 1

    def flush(self):
        pass

    def refresh(self, row):
        pass


class BlobClient:
    def __init__(self, raw):
        self.raw = raw

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url):
        return httpx.Response(
            200,
            content=self.raw,
            headers={"content-type": "image/webp"},
            request=httpx.Request("GET", url),
        )


def webp_bytes(color):
    stream = BytesIO()
    Image.new("RGB", (1024, 1024), color).save(stream, format="WEBP")
    return stream.getvalue()


def generation(raw, **overrides):
    values = dict(
        id=GENERATION_ID,
        store_id="s1",
        subject_type="product_card",
        subject_id="42",
        feature="card_factory_visual",
        fact_set_sha256="facts",
        model="fake",
        status=GenerationStatus.completed,
        token_usage={},
        estimated_cost_microusd=0,
        created_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        error="",
        result_payload={
            "storage_status": "awaiting_blob",
            "generated_sha256": hashlib.sha256(raw).hexdigest(),
            "generated_bytes": len(raw),
        },
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def media_publication(raw, **overrides):
    digest = hashlib.sha256(raw).hexdigest()
    values = dict(
        id="publication-1",
        generation_id=GENERATION_ID,
        store_id="s1",
        workspace_id="w1",
        subject_id="42",
        marketplace="wildberries",
        status=PublicationStatus.prepared,
        payload_sha256="a" * 64,
        diff_payload={"target_position": 2},
        source_payload={"vendor_code": "SKU", "photo_urls": ["https://old.example/1.webp"]},
        asset_payload={
            "url": URL,
            "pathname": PATHNAME,
            "trusted_host": OWN_HOST,
            "object_id": f"{OWN_HOST}/{PATHNAME}",
            "store_id": "s1",
            "generation_id": GENERATION_ID,
            "subject_id": "42",
            "sha256": digest,
            "bytes": len(raw),
            "content_type": "image/webp",
        },
        attempt_count=0,
        provider_response={},
        error="",
        verification_status="not_checked",
        verification_payload={},
        verification_attempt_count=0,
        last_verified_at=None,
        verified_at=None,
        approved_at=None,
        submitted_at=None,
        created_at=datetime.now(timezone.utc),
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def finalize_payload(**overrides):
    values = dict(
        store_id="s1",
        generation_id=GENERATION_ID,
        url=URL,
        pathname=PATHNAME,
        content_type="image/webp",
        bytes=10,
        sha256="0" * 64,
    )
    values.update(overrides)
    return FinalizeVisualRequest(**values)


def run_finalize(payload, row, monkeypatch, raw):
    monkeypatch.setattr(
        "app.card_factory_router.resolve_store",
        lambda *args: SimpleNamespace(id="s1"),
    )
    monkeypatch.setattr(
        "app.card_factory_router.get_settings",
        lambda: SimpleNamespace(
            asset_blob_host_set={OWN_HOST},
            media_submitting_recovery_seconds=0,
        ),
    )
    monkeypatch.setattr(
        "app.card_factory_router.httpx.AsyncClient",
        lambda *args, **kwargs: BlobClient(raw),
    )
    result = finalize_visual(payload, user=SimpleNamespace(id="u1"), db=Db(row))
    return asyncio.run(result) if inspect.isawaitable(result) else result


def patch_media_dependencies(monkeypatch, store):
    monkeypatch.setattr("app.card_factory_router._resolve_connected_store", lambda *args: store)
    monkeypatch.setattr("app.card_factory_router.require_entitlement", lambda *args: None)
    monkeypatch.setattr("app.card_factory_router.require_store_admin", lambda *args: None)
    monkeypatch.setattr("app.card_factory_router.require_external_write_allowed", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.card_factory_router._connection", lambda *args: SimpleNamespace())
    monkeypatch.setattr("app.card_factory_router.decrypt_connection", lambda *args: "token")


def test_finalize_rejects_foreign_blob_store(monkeypatch):
    raw = webp_bytes("green")
    row = generation(raw)
    payload = finalize_payload(
        url=f"https://foreign.public.blob.vercel-storage.com/{PATHNAME}",
    )
    with pytest.raises(HTTPException, match="хранилищ"):
        run_finalize(payload, row, monkeypatch, raw)


def test_finalize_rejects_url_pathname_mismatch(monkeypatch):
    raw = webp_bytes("green")
    row = generation(raw)
    payload = finalize_payload(url=f"https://{OWN_HOST}/ai-assets/s1/42/other.webp")
    with pytest.raises(HTTPException, match="объект|путь"):
        run_finalize(payload, row, monkeypatch, raw)


def test_finalize_binds_exact_generation_object(monkeypatch):
    raw = webp_bytes("green")
    row = generation(raw)
    wrong = f"ai-assets/s1/42/22222222-2222-2222-2222-222222222222.webp"
    payload = finalize_payload(pathname=wrong, url=f"https://{OWN_HOST}/{wrong}")
    with pytest.raises(HTTPException, match="генерац|объект|путь"):
        run_finalize(payload, row, monkeypatch, raw)


def test_finalize_rejects_blob_different_from_generated_checksum(monkeypatch):
    generated = webp_bytes("green")
    substituted = webp_bytes("red")
    row = generation(generated)
    with pytest.raises(HTTPException, match="контрольн|измен"):
        run_finalize(finalize_payload(), row, monkeypatch, substituted)


def test_finalize_computes_checksum_server_side(monkeypatch):
    raw = webp_bytes("green")
    row = generation(raw)
    run_finalize(finalize_payload(sha256="f" * 64, bytes=1), row, monkeypatch, raw)
    assert row.result_payload["sha256"] == hashlib.sha256(raw).hexdigest()
    assert row.result_payload["bytes"] == len(raw)


def test_repeated_finalize_cannot_replace_stored_asset(monkeypatch):
    raw = webp_bytes("green")
    digest = hashlib.sha256(raw).hexdigest()
    stored = generation(raw)
    stored.result_payload.update({
        "storage_status": "stored",
        "url": URL,
        "pathname": PATHNAME,
        "trusted_host": OWN_HOST,
        "object_id": f"{OWN_HOST}/{PATHNAME}",
        "store_id": "s1",
        "generation_id": GENERATION_ID,
        "subject_id": "42",
        "sha256": digest,
        "bytes": len(raw),
        "content_type": "image/webp",
    })
    run_finalize(finalize_payload(sha256="f" * 64, bytes=1), stored, monkeypatch, raw)
    assert stored.result_payload["sha256"] == digest
    assert stored.result_payload["bytes"] == len(raw)


def test_unrelated_added_photo_is_not_proof_of_our_asset():
    row = media_publication(webp_bytes("green"))
    status, evidence = _media_verification_result(
        row,
        {"photos": [
            {"big": "https://old.example/1.webp"},
            {"big": "https://wb.example/unrelated.webp"},
        ]},
    )
    assert status == "unverified"
    assert evidence["outcome"] == "not_confirmed"
    assert evidence["identity_confirmed"] is False


def test_timeout_after_accept_reconciles_before_any_retry(monkeypatch):
    raw = webp_bytes("green")
    row = media_publication(raw)
    db = Db(row)
    store = SimpleNamespace(id="s1", workspace_id="w1")
    patch_media_dependencies(monkeypatch, store)
    live = iter([
        {"photos": [{"big": "https://old.example/1.webp"}]},
        {"photos": [
            {"big": "https://old.example/1.webp"},
            {"big": "https://wb.example/transformed.webp"},
        ]},
    ])
    reads = []
    uploads = []

    async def fetch(*args, **kwargs):
        reads.append("read")
        return next(live)

    async def upload(*args, **kwargs):
        kwargs["before_send"]()
        assert db.commits >= 1, "submission intent must survive a process crash before HTTP"
        assert row.status == PublicationStatus.submitting
        uploads.append("upload")
        raise httpx.ReadTimeout("outcome unknown", request=httpx.Request("POST", "https://wb.test"))

    monkeypatch.setattr("app.card_factory_router.fetch_wb_card", fetch)
    monkeypatch.setattr("app.card_factory_router.upload_wb_media_file", upload)
    monkeypatch.setattr(
        "app.card_factory_router._download_and_validate_asset",
        lambda *args: asyncio.sleep(0, result=(raw, "image/webp", {"width": 1024, "height": 1024})),
    )

    result = asyncio.run(publish_media(
        row.id,
        ConfirmPublicationRequest(
            store_id="s1", payload_sha256=row.payload_sha256, confirmation="ОПУБЛИКОВАТЬ ФОТО",
        ),
        user=SimpleNamespace(id="u1"),
        db=db,
    ))

    assert uploads == ["upload"]
    assert reads == ["read", "read"]
    assert result["status"] == PublicationStatus.submitted.value
    assert result["verification_status"] == "unverified"


def test_stuck_submitting_recovers_by_reading_without_write(monkeypatch):
    raw = webp_bytes("green")
    row = media_publication(
        raw,
        status=PublicationStatus.submitting,
        attempt_count=1,
        approved_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        verification_status="pending",
    )
    db = Db(row)
    store = SimpleNamespace(id="s1", workspace_id="w1")
    patch_media_dependencies(monkeypatch, store)
    uploads = []

    async def fetch(*args, **kwargs):
        return {"photos": [{"big": "https://old.example/1.webp"}]}

    monkeypatch.setattr("app.card_factory_router.fetch_wb_card", fetch)
    monkeypatch.setattr("app.card_factory_router.upload_wb_media_file", lambda *args, **kwargs: uploads.append("write"))
    monkeypatch.setattr(
        "app.card_factory_router.get_settings",
        lambda: SimpleNamespace(media_submitting_recovery_seconds=0, asset_blob_host_set={OWN_HOST}),
    )

    result = asyncio.run(verify_media_publication(
        row.id,
        VerifyPublicationRequest(store_id="s1"),
        user=SimpleNamespace(id="u1"),
        db=db,
    ))

    assert uploads == []
    assert result["status"] == PublicationStatus.submitting.value
    assert result["verification_status"] == "not_confirmed"
    assert result["verification"]["retry_blocked"] is True


def test_visual_generation_records_digest_before_blob_finalize(monkeypatch):
    raw = webp_bytes("green")
    copy = SimpleNamespace(result_payload={"visual_plan": ["Честный слайд"]})
    pending = generation(raw)
    pending.result_payload = {}
    captured = {}
    store = SimpleNamespace(id="s1", workspace_id="w1")

    monkeypatch.setattr("app.card_factory_router._resolve_connected_store", lambda *args: store)
    monkeypatch.setattr("app.card_factory_router.require_entitlement", lambda *args: None)
    monkeypatch.setattr(
        "app.card_factory_router._load_card",
        lambda *args: ({"nm_id": 42}, SimpleNamespace(created_at=None)),
    )
    monkeypatch.setattr(
        "app.card_factory_router.build_fact_set",
        lambda source: {"sha256": "facts"},
    )
    monkeypatch.setattr("app.card_factory_router.begin_generation", lambda *args, **kwargs: pending)
    monkeypatch.setattr(
        "app.card_factory_router.generate_product_visual",
        lambda *args: (
            base64.b64encode(raw).decode(),
            {},
            {"storage_status": "awaiting_blob"},
        ),
    )

    def complete(db, row, result, metadata):
        captured.update(result)
        row.result_payload = result

    monkeypatch.setattr("app.card_factory_router.complete_generation", complete)
    result = generate_visual(
        GenerateVisualRequest(store_id="s1", nm_id=42, visual_index=0),
        user=SimpleNamespace(id="u1"),
        db=Db(copy),
    )

    assert result["generation_id"] == GENERATION_ID
    assert captured["generated_sha256"] == hashlib.sha256(raw).hexdigest()
    assert captured["generated_bytes"] == len(raw)
