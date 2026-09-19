import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai_generation_service import GenerationAdmissionConflict, begin_generation, stable_hash
from app.db import Base, SessionLocal, engine
from app.models import AIGeneration, GenerationStatus, Membership, MembershipRole, Store, User, Workspace


def test_generation_input_hash_is_stable_and_order_independent():
    assert stable_hash({"b": 2, "a": 1}) == stable_hash({"a": 1, "b": 2})
    assert stable_hash({"a": 1}) != stable_hash({"a": 2})


def test_unrelated_integrity_error_is_not_reported_as_duplicate_admission():
    db = Mock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.commit.side_effect = IntegrityError("INSERT", {}, Exception("FOREIGN KEY constraint failed"))

    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        begin_generation(
            db,
            store=SimpleNamespace(id="store", workspace_id="workspace"),
            user=SimpleNamespace(id="user"),
            feature="review_analysis",
            subject_id="snapshot",
            input_payload={"facts": "hash"},
        )

    db.rollback.assert_called_once()


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="requires two real PostgreSQL transactions")
def test_concurrent_pending_admission_allows_only_one_generation_postgresql():
    Base.metadata.create_all(bind=engine)
    suffix = uuid.uuid4().hex
    with SessionLocal() as db:
        user = User(email=f"generation-concurrency-{suffix}@example.com", password_hash="test")
        workspace = Workspace(name=f"Generation concurrency {suffix}")
        db.add_all([user, workspace]); db.flush()
        db.add(Membership(user_id=user.id, workspace_id=workspace.id, role=MembershipRole.owner))
        store = Store(workspace_id=workspace.id, name=f"Store {suffix}")
        db.add(store); db.commit()
        user_id, store_id = user.id, store.id

    flush_barrier = Barrier(2)
    backend_ids = []

    def hold_both_after_lookup(session, _flush_context, _instances):
        if not session.info.get("t15a_hold_pending_generation_flush"):
            return
        backend_ids.append(session.execute(text("SELECT pg_backend_pid()")).scalar_one())
        flush_barrier.wait(timeout=5)

    event.listen(Session, "before_flush", hold_both_after_lookup)

    def admit():
        with SessionLocal() as db:
            store = db.get(Store, store_id)
            user = db.get(User, user_id)
            db.info["t15a_hold_pending_generation_flush"] = True
            try:
                return begin_generation(
                    db,
                    store=store,
                    user=user,
                    feature="review_analysis",
                    subject_id="snapshot-1",
                    input_payload={"fact_set": "same"},
                    fact_set_sha256="a" * 64,
                ).id
            except GenerationAdmissionConflict:
                return "duplicate"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: admit(), range(2)))
    finally:
        event.remove(Session, "before_flush", hold_both_after_lookup)

    assert results.count("duplicate") == 1
    assert len(set(backend_ids)) == 2
    with SessionLocal() as db:
        active = db.query(AIGeneration).filter(
            AIGeneration.store_id == store_id,
            AIGeneration.feature == "review_analysis",
            AIGeneration.status == GenerationStatus.pending,
        ).all()
        assert len(active) == 1
