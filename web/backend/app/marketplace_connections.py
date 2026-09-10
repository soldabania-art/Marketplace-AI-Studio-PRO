import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .db import get_db
from .fbo_service import fetch_wb_slots
from .models import MarketplaceConnection, User, UserSession
from .secret_provider import SecretProviderError, get_secret_provider
from .security import get_current_user, require_step_up_session
from .store_access import require_store_admin, resolve_store

router = APIRouter()


class WbTokenBody(BaseModel):
    token: str = Field(min_length=20, max_length=4096)
    store_id: str | None = None


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


@router.post('/integrations/wildberries')
async def connect_wb(body: WbTokenBody, user: User = Depends(get_current_user), _: UserSession = Depends(require_step_up_session), db: Session = Depends(get_db)):
    store = resolve_store(db, user, body.store_id)
    require_store_admin(db, user, store)
    provider = secret_provider()
    token = body.token.strip()
    try:
        await fetch_wb_slots(token)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else 502
        if status in {401, 403}:
            raise HTTPException(400, 'WB отклонил токен или у него недостаточно прав.')
        if status == 429:
            raise HTTPException(429, 'WB временно ограничил частоту проверки токена. Повторите позже.')
        raise HTTPException(502, 'WB временно недоступен. Повторите позже.')
    except httpx.RequestError:
        raise HTTPException(503, 'Не удалось связаться с WB для проверки токена.')

    row = db.query(MarketplaceConnection).filter(
        MarketplaceConnection.store_id == store.id,
        MarketplaceConnection.marketplace == 'wildberries',
    ).first()
    encrypted = provider.encrypt(token)
    if not row:
        row = MarketplaceConnection(user_id=user.id, store_id=store.id, marketplace='wildberries', encrypted_token=encrypted)
        db.add(row)
    else:
        row.user_id = user.id
        row.encrypted_token = encrypted
        row.enabled = True
    row.token_hint = ('…' + token[-4:]) if len(token) >= 4 else 'configured'
    db.commit()
    return {'ok': True, 'marketplace': 'wildberries', 'store_id': store.id, 'token_hint': row.token_hint}


@router.get('/integrations/wildberries')
def wb_status(store_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id)
    row = db.query(MarketplaceConnection).filter(MarketplaceConnection.store_id == store.id, MarketplaceConnection.marketplace == 'wildberries', MarketplaceConnection.enabled.is_(True)).first()
    return {'connected': bool(row), 'store_id': store.id, 'store_name': store.name, 'token_hint': row.token_hint if row else ''}


@router.delete('/integrations/wildberries')
def disconnect_wb(store_id: str | None = None, user: User = Depends(get_current_user), _: UserSession = Depends(require_step_up_session), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id)
    require_store_admin(db, user, store)
    row = db.query(MarketplaceConnection).filter(MarketplaceConnection.store_id == store.id, MarketplaceConnection.marketplace == 'wildberries').first()
    if row:
        row.enabled = False
        row.encrypted_token = ''
        row.token_hint = ''
        db.commit()
    return {'ok': True, 'store_id': store.id, 'connected': False}
