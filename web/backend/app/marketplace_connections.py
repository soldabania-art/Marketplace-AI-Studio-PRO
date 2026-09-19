from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import get_db
from .models import MarketplaceConnection, User, UserSession
from .secret_provider import SecretProviderError, get_secret_provider
from .security import get_current_user, require_mfa_session, require_step_up_session
from .store_access import require_store_admin, resolve_store
from .wb_capability_preflight import check_wb_capabilities, unchecked_capabilities

router = APIRouter()


class WbTokenBody(BaseModel):
    token: str = Field(min_length=20, max_length=4096)
    store_id: str | None = None
    accept_partial: bool = False


def secret_provider():
    try:
        return get_secret_provider()
    except SecretProviderError:
        raise HTTPException(503, 'Защищённое хранилище токенов маркетплейса не настроено на сервере.')


def decrypt_connection(row: MarketplaceConnection) -> str:
    try:
        return secret_provider().decrypt(row.encrypted_token)
    except SecretProviderError:
        raise HTTPException(503, 'Не удалось расшифровать токен магазина.')


def _checked_at(result: dict):
    from datetime import datetime
    value = result.get('checked_at')
    return datetime.fromisoformat(value) if value else None


def _connection_payload(row: MarketplaceConnection | None, store) -> dict:
    connected = bool(row and row.enabled and row.encrypted_token)
    verification = row.capability_results if connected and row.capability_results else unchecked_capabilities()
    return {
        'connected': connected,
        'token_saved': connected,
        'sources_verified': bool(connected and row.capabilities_checked_at),
        'credentials_version': row.credentials_version if connected else None,
        'store_id': store.id,
        'store_name': store.name,
        'verification': verification,
    }


def _candidate_error(result: dict, message: str, *, confirmation_required: bool = False) -> dict:
    return {
        'message': message,
        'candidate_saved': False,
        'confirmation_required': confirmation_required,
        'verification': result,
    }


def _claim_capability_check(db: Session, row: MarketplaceConnection, expected_version: int) -> int:
    """Allocate a monotonically increasing check generation atomically."""
    generation = db.execute(
        update(MarketplaceConnection)
        .where(
            MarketplaceConnection.id == row.id,
            MarketplaceConnection.credentials_version == expected_version,
            MarketplaceConnection.enabled.is_(True),
        )
        .values(capability_check_generation=MarketplaceConnection.capability_check_generation + 1)
        .returning(MarketplaceConnection.capability_check_generation)
    ).scalar_one_or_none()
    if generation is None:
        db.rollback()
        raise HTTPException(409, 'Подключение изменилось до начала проверки. Обновите текущее состояние.')
    db.commit()
    return generation


def _apply_capability_check(
    db: Session,
    *,
    connection_id: str,
    expected_version: int,
    check_generation: int,
    result: dict,
) -> bool:
    changed = db.execute(
        update(MarketplaceConnection)
        .where(
            MarketplaceConnection.id == connection_id,
            MarketplaceConnection.credentials_version == expected_version,
            MarketplaceConnection.capability_check_generation == check_generation,
            MarketplaceConnection.enabled.is_(True),
        )
        .values(
            capability_results=result,
            capabilities_checked_at=_checked_at(result),
        )
    )
    if changed.rowcount != 1:
        db.rollback()
        return False
    db.commit()
    return True


@router.post('/integrations/wildberries')
async def connect_wb(body: WbTokenBody, user: User = Depends(get_current_user), _: UserSession = Depends(require_step_up_session), __: UserSession = Depends(require_mfa_session), db: Session = Depends(get_db)):
    store = resolve_store(db, user, body.store_id)
    require_store_admin(db, user, store)
    provider = secret_provider()
    token = body.token.strip()
    row = db.query(MarketplaceConnection).filter(
        MarketplaceConnection.store_id == store.id,
        MarketplaceConnection.marketplace == 'wildberries',
    ).first()
    expected_version = row.credentials_version if row else None
    result = await check_wb_capabilities(token)
    summary = result['summary']
    has_transient = any(
        endpoint.get('status') == 'transient_error'
        for source in result.get('sources', [])
        for endpoint in source.get('endpoints', [])
    )
    if summary == 'temporary_failure' or has_transient:
        raise HTTPException(503, _candidate_error(
            result,
            'Проверка временно не завершена. Сохранённый токен не изменён.',
        ))
    if summary in {'rejected', 'unchecked'}:
        raise HTTPException(400, _candidate_error(
            result,
            'WB не подтвердил доступ ни к одному источнику. Сохранённый токен не изменён.',
        ))
    if summary == 'partial' and not body.accept_partial:
        raise HTTPException(409, _candidate_error(
            result,
            'Доступ подтверждён только частично. Проверьте матрицу перед заменой токена.',
            confirmation_required=True,
        ))

    encrypted = provider.encrypt(token)
    if not row:
        row = MarketplaceConnection(
            user_id=user.id,
            store_id=store.id,
            marketplace='wildberries',
            encrypted_token=encrypted,
            credentials_version=1,
            capability_check_generation=1,
            capability_results=result,
            capabilities_checked_at=_checked_at(result),
        )
        db.add(row)
    else:
        changed = db.execute(
            update(MarketplaceConnection)
            .where(
                MarketplaceConnection.id == row.id,
                MarketplaceConnection.credentials_version == expected_version,
            )
            .values(
                user_id=user.id,
                encrypted_token=encrypted,
                token_hint=('…' + token[-4:]) if len(token) >= 4 else 'configured',
                enabled=True,
                credentials_version=expected_version + 1,
                capability_check_generation=MarketplaceConnection.capability_check_generation + 1,
                capability_results=result,
                capabilities_checked_at=_checked_at(result),
            )
        )
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(409, 'Подключение изменилось во время проверки. Результат старого токена проигнорирован.')
    if not row.token_hint:
        row.token_hint = ('…' + token[-4:]) if len(token) >= 4 else 'configured'
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Подключение изменилось во время проверки. Повторите проверку текущего состояния.')
    db.expire_all()
    saved = db.query(MarketplaceConnection).filter(
        MarketplaceConnection.store_id == store.id,
        MarketplaceConnection.marketplace == 'wildberries',
    ).one()
    return {
        'ok': True,
        'marketplace': 'wildberries',
        'candidate_saved': True,
        **_connection_payload(saved, store),
    }


@router.get('/integrations/wildberries')
def wb_status(store_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id)
    row = db.query(MarketplaceConnection).filter(MarketplaceConnection.store_id == store.id, MarketplaceConnection.marketplace == 'wildberries').first()
    return _connection_payload(row, store)


@router.post('/integrations/wildberries/check')
async def check_saved_wb(
    store_id: str | None = None,
    user: User = Depends(get_current_user),
    _: UserSession = Depends(require_step_up_session),
    __: UserSession = Depends(require_mfa_session),
    db: Session = Depends(get_db),
):
    store = resolve_store(db, user, store_id)
    require_store_admin(db, user, store)
    row = db.query(MarketplaceConnection).filter(
        MarketplaceConnection.store_id == store.id,
        MarketplaceConnection.marketplace == 'wildberries',
        MarketplaceConnection.enabled.is_(True),
    ).first()
    if not row or not row.encrypted_token:
        raise HTTPException(412, 'Сначала сохраните токен Wildberries для выбранного магазина.')
    expected_version = row.credentials_version
    token = decrypt_connection(row)
    check_generation = _claim_capability_check(db, row, expected_version)
    result = await check_wb_capabilities(token)
    if not _apply_capability_check(
        db,
        connection_id=row.id,
        expected_version=expected_version,
        check_generation=check_generation,
        result=result,
    ):
        raise HTTPException(409, 'Подключение изменилось во время проверки. Результат старого токена проигнорирован.')
    db.expire_all()
    saved = db.query(MarketplaceConnection).filter(MarketplaceConnection.id == row.id).one()
    return {'ok': True, 'marketplace': 'wildberries', **_connection_payload(saved, store)}


@router.delete('/integrations/wildberries')
def disconnect_wb(store_id: str | None = None, user: User = Depends(get_current_user), _: UserSession = Depends(require_step_up_session), __: UserSession = Depends(require_mfa_session), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id)
    require_store_admin(db, user, store)
    row = db.query(MarketplaceConnection).filter(MarketplaceConnection.store_id == store.id, MarketplaceConnection.marketplace == 'wildberries').first()
    if row:
        db.execute(
            update(MarketplaceConnection)
            .where(MarketplaceConnection.id == row.id)
            .values(
                enabled=False,
                encrypted_token='',
                token_hint='',
                credentials_version=MarketplaceConnection.credentials_version + 1,
                capability_check_generation=MarketplaceConnection.capability_check_generation + 1,
                capability_results=None,
                capabilities_checked_at=None,
            )
        )
        db.commit()
        db.expire_all()
        row = db.query(MarketplaceConnection).filter(MarketplaceConnection.id == row.id).one()
    return {'ok': True, **_connection_payload(row, store)}
