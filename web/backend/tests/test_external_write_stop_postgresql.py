import asyncio
import threading
import uuid

import pytest
from fastapi import HTTPException

from app.db import SessionLocal, engine
from app.external_write_guard import lock_external_write_scope, require_external_write_allowed
from app.models import AutomationControl, Store, User, Workspace
from app.wb_content import update_wb_card, upload_wb_media_file


pytestmark = pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="STOP/dispatch serialization requires PostgreSQL advisory locks",
)


class _Response:
    content = b'{"error":false}'
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {"error": False}


class _Client:
    def __init__(self, http_started):
        self.http_started = http_started

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, *args, **kwargs):
        self.http_started.set()
        return _Response()


@pytest.mark.parametrize("control_exists", [False, True])
@pytest.mark.parametrize("publication_kind", ["text", "photo"])
def test_stop_saved_during_rate_wait_prevents_new_http_request(
    monkeypatch, control_exists, publication_kind,
):
    suffix = uuid.uuid4().hex
    user_id = str(uuid.uuid4())
    workspace_id = str(uuid.uuid4())
    store_id = str(uuid.uuid4())
    with SessionLocal() as setup:
        setup.add(User(id=user_id, email=f"stop-{suffix}@example.com", password_hash="test"))
        setup.add(Workspace(id=workspace_id, name=f"STOP {suffix}"))
        setup.flush()
        setup.add(Store(id=store_id, workspace_id=workspace_id, name=f"Store {suffix}"))
        setup.flush()
        if control_exists:
            setup.add(AutomationControl(
                workspace_id=workspace_id,
                store_id=store_id,
                marketplace="wildberries",
                stopped=False,
                reason="running",
                changed_by_user_id=user_id,
            ))
        setup.commit()

    limiter_waiting = threading.Event()
    release_limiter = threading.Event()
    http_started = threading.Event()
    errors = []

    async def controlled_wait(*args, **kwargs):
        limiter_waiting.set()
        await asyncio.to_thread(release_limiter.wait, 5)

    monkeypatch.setattr("app.wb_content.wait_marketplace_slot", controlled_wait)
    monkeypatch.setattr("app.wb_content.httpx.AsyncClient", lambda **kwargs: _Client(http_started))

    def publish():
        try:
            with SessionLocal() as dispatch_db:
                def admit():
                    require_external_write_allowed(
                        dispatch_db,
                        workspace_id=workspace_id,
                        store_id=store_id,
                        marketplace="wildberries",
                        user_id=user_id,
                        operation=f"{publication_kind}.publish",
                        entity_type=f"{publication_kind}_publication",
                        entity_id=str(uuid.uuid4()),
                        lock=True,
                    )

                if publication_kind == "text":
                    asyncio.run(update_wb_card("token", {"nmID": 42}, before_send=admit))
                else:
                    asyncio.run(upload_wb_media_file(
                        "token", nm_id=42, photo_number=1, raw=b"webp",
                        content_type="image/webp", before_send=admit,
                    ))
                dispatch_db.commit()
        except Exception as exc:  # asserted below, across the thread boundary
            errors.append(exc)

    thread = threading.Thread(target=publish)
    thread.start()
    try:
        assert limiter_waiting.wait(5), "publisher did not enter the controlled rate-limit wait"

        # A second database session can save STOP while the publisher is still waiting.
        with SessionLocal() as stop_db:
            lock_external_write_scope(
                stop_db,
                workspace_id=workspace_id,
                store_id=store_id,
                marketplace="wildberries",
            )
            control = stop_db.query(AutomationControl).filter(
                AutomationControl.store_id == store_id,
                AutomationControl.marketplace == "wildberries",
            ).with_for_update().first()
            if control is None:
                control = AutomationControl(
                    workspace_id=workspace_id,
                    store_id=store_id,
                    marketplace="wildberries",
                    changed_by_user_id=user_id,
                )
                stop_db.add(control)
            control.stopped = True
            control.reason = "controlled regression"
            stop_db.commit()
    finally:
        release_limiter.set()
        thread.join(10)

    assert not thread.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], HTTPException)
    assert errors[0].status_code == 423
    assert not http_started.is_set()
