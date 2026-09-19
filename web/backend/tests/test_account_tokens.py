"""Account action tokens are private, transactional, and single-use."""
import hashlib
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from app.account_router import (
    _consume_account_token,
    _create_account_token,
    confirm_email_verification,
    confirm_password_reset,
)
from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import AccountActionToken, AccountTokenPurpose, User, UserSession
from app.schemas import PasswordResetConfirmRequest, TokenActionRequest
from app.security import hash_password, verify_password


Base.metadata.create_all(bind=engine)
client = TestClient(app)


def _user_and_token(purpose: AccountTokenPurpose) -> tuple[str, str]:
    with SessionLocal() as db:
        user = User(
            email=f"t09a-{uuid.uuid4().hex}@example.com",
            password_hash=hash_password("OldStrongPass123!"),
        )
        db.add(user)
        db.commit()
        raw_token = _create_account_token(db, user, purpose, timedelta(minutes=30))
        db.commit()
        return user.id, raw_token


def test_password_reset_production_response_does_not_disclose_account(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")
    email = f"known-{uuid.uuid4().hex}@example.com"
    with SessionLocal() as db:
        db.add(User(email=email, password_hash=hash_password("StrongPass123!")))
        db.commit()

    known = client.post(
        "/api/v1/auth/password-reset/request",
        headers={"x-forwarded-for": "2001:db8:9::1"},
        json={"email": email},
    )
    unknown = client.post(
        "/api/v1/auth/password-reset/request",
        headers={"x-forwarded-for": "2001:db8:9::2"},
        json={"email": f"missing-{uuid.uuid4().hex}@example.com"},
    )

    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert "development_token" not in known.json()
    assert known.json()["delivery"] == "request_accepted"


def test_consume_marks_token_in_callers_transaction_and_rollback_restores_it():
    _, raw_token = _user_and_token(AccountTokenPurpose.verify_email)
    with SessionLocal() as db:
        token, _ = _consume_account_token(db, raw_token, AccountTokenPurpose.verify_email)
        assert token.used_at is not None
        db.rollback()

    with SessionLocal() as db:
        token, _ = _consume_account_token(db, raw_token, AccountTokenPurpose.verify_email)
        db.commit()
        assert token.used_at is not None


def test_tokens_reject_wrong_purpose_expiry_and_replay():
    _, raw_token = _user_and_token(AccountTokenPurpose.verify_email)
    with SessionLocal() as db:
        with pytest.raises(HTTPException) as wrong:
            _consume_account_token(db, raw_token, AccountTokenPurpose.reset_password)
        assert wrong.value.status_code == 400
        db.rollback()

    with SessionLocal() as db:
        confirm_email_verification(TokenActionRequest(token=raw_token), db=db)
    with SessionLocal() as db:
        with pytest.raises(HTTPException) as replay:
            _consume_account_token(db, raw_token, AccountTokenPurpose.verify_email)
        assert replay.value.status_code == 400

    _, expired_raw = _user_and_token(AccountTokenPurpose.reset_password)
    with SessionLocal() as db:
        row = db.scalar(select(AccountActionToken).where(
            AccountActionToken.token_hash == hashlib.sha256(expired_raw.encode()).hexdigest(),
        ))
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    with SessionLocal() as db:
        with pytest.raises(HTTPException) as expired:
            _consume_account_token(db, expired_raw, AccountTokenPurpose.reset_password)
        assert expired.value.status_code == 400


def test_inactive_account_failure_rolls_back_token_use():
    user_id, raw_token = _user_and_token(AccountTokenPurpose.verify_email)
    with SessionLocal() as db:
        db.get(User, user_id).is_active = False
        db.commit()
    with SessionLocal() as db:
        with pytest.raises(HTTPException) as unavailable:
            _consume_account_token(db, raw_token, AccountTokenPurpose.verify_email)
        assert unavailable.value.status_code == 400
        db.rollback()
    with SessionLocal() as db:
        token = db.scalar(select(AccountActionToken).where(
            AccountActionToken.token_hash == hashlib.sha256(raw_token.encode()).hexdigest(),
        ))
        assert token.used_at is None
        db.get(User, user_id).is_active = True
        db.commit()
    with SessionLocal() as db:
        _consume_account_token(db, raw_token, AccountTokenPurpose.verify_email)
        db.commit()


def test_password_reset_commit_is_atomic_with_password_and_session_revocation():
    user_id, raw_token = _user_and_token(AccountTokenPurpose.reset_password)
    with SessionLocal() as db:
        session = UserSession(
            user_id=user_id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        db.add(session)
        db.commit()
        session_id = session.id

    class InjectedFailure(RuntimeError):
        pass

    failing = SessionLocal()
    event.listen(failing, "before_commit", lambda _: (_ for _ in ()).throw(InjectedFailure()))
    try:
        with pytest.raises(InjectedFailure):
            confirm_password_reset(
                PasswordResetConfirmRequest(token=raw_token, new_password="NewStrongPass456!"),
                db=failing,
            )
        failing.rollback()
    finally:
        failing.close()

    with SessionLocal() as db:
        assert verify_password("OldStrongPass123!", db.get(User, user_id).password_hash)
        assert db.get(UserSession, session_id).revoked_at is None
        assert db.scalar(select(AccountActionToken.used_at).where(
            AccountActionToken.token_hash == hashlib.sha256(raw_token.encode()).hexdigest()
        )) is None

    with SessionLocal() as db:
        confirm_password_reset(
            PasswordResetConfirmRequest(token=raw_token, new_password="NewStrongPass456!"),
            db=db,
        )
    with SessionLocal() as db:
        assert verify_password("NewStrongPass456!", db.get(User, user_id).password_hash)
        assert db.get(UserSession, session_id).revoked_at is not None


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="two independent PostgreSQL transactions")
@pytest.mark.parametrize("purpose", [AccountTokenPurpose.verify_email, AccountTokenPurpose.reset_password])
def test_actual_confirmation_endpoint_allows_only_one_concurrent_consumer(purpose):
    _, raw_token = _user_and_token(purpose)
    start = threading.Barrier(2)
    selected = threading.Barrier(2)

    def hold_legacy_select(execute_state):
        statement = str(execute_state.statement).lower()
        if execute_state.is_select and "account_action_tokens" in statement:
            result = execute_state.invoke_statement()
            selected.wait(timeout=10)
            return result
        return execute_state.invoke_statement()

    event.listen(Session, "do_orm_execute", hold_legacy_select, retval=True)
    try:
        def consume():
            with SessionLocal() as db:
                # Pin both sessions to different live PostgreSQL connections before release.
                backend_pid = db.scalar(text("select pg_backend_pid()"))
                start.wait(timeout=10)
                try:
                    if purpose == AccountTokenPurpose.verify_email:
                        confirm_email_verification(TokenActionRequest(token=raw_token), db=db)
                    else:
                        confirm_password_reset(
                            PasswordResetConfirmRequest(token=raw_token, new_password="ConcurrentPass456!"),
                            db=db,
                        )
                    return backend_pid, 200
                except HTTPException as exc:
                    db.rollback()
                    return backend_pid, exc.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: consume(), range(2)))
    finally:
        event.remove(Session, "do_orm_execute", hold_legacy_select)

    assert len({pid for pid, _ in results}) == 2
    assert sorted(code for _, code in results) == [200, 400]
