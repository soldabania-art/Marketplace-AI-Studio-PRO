from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import FboWatch, PushSubscription, User
from .security import get_current_user
from .store_access import resolve_store

router = APIRouter()


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=20, max_length=512)
    auth: str = Field(min_length=8, max_length=512)


class PushBody(BaseModel):
    endpoint: str = Field(min_length=20, max_length=2048)
    keys: PushKeys


class WatchBody(BaseModel):
    marketplace: str = 'wildberries'
    store_id: str | None = None
    warehouse_filter: str = ''
    free_only: bool = False
    enabled: bool = True


def _validate_endpoint(endpoint: str) -> None:
    parsed = urlparse(endpoint)
    if parsed.scheme != 'https' or not parsed.netloc:
        raise HTTPException(400, 'Некорректный PUSH endpoint.')


@router.get('/push/config')
def push_config(user: User = Depends(get_current_user)):
    settings = get_settings()
    return {
        'enabled': bool(settings.vapid_public_key and settings.vapid_private_key and settings.vapid_subject),
        'public_key': settings.vapid_public_key,
    }


@router.post('/push/subscriptions')
def save_push(body: PushBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _validate_endpoint(body.endpoint)
    row = db.query(PushSubscription).filter(PushSubscription.endpoint == body.endpoint).first()
    if row and row.user_id != user.id:
        raise HTTPException(409, 'Эта PUSH-подписка уже принадлежит другому аккаунту.')
    if row:
        row.p256dh = body.keys.p256dh
        row.auth = body.keys.auth
    else:
        db.add(PushSubscription(user_id=user.id, endpoint=body.endpoint, p256dh=body.keys.p256dh, auth=body.keys.auth))
    db.commit()
    return {'ok': True}


@router.delete('/push/subscriptions')
def delete_push(body: PushBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(PushSubscription).filter(
        PushSubscription.endpoint == body.endpoint,
        PushSubscription.user_id == user.id,
    ).first()
    if row:
        db.delete(row)
        db.commit()
    return {'ok': True}


@router.get('/fbo/watch')
def get_watch(store_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id)
    row = db.query(FboWatch).filter(
        FboWatch.store_id == store.id,
        FboWatch.marketplace == 'wildberries',
    ).first()
    if not row:
        return {'enabled': False, 'store_id': store.id, 'scope': 'all_warehouses', 'coefficients': [0, 1]}
    return {
        'enabled': row.enabled,
        'watch_id': row.id,
        'store_id': store.id,
        'scope': 'all_warehouses' if not row.warehouse_filter else 'filtered',
        'warehouse_filter': row.warehouse_filter,
        'coefficients': [0] if row.free_only else [0, 1],
        'last_checked_at': row.last_checked_at,
    }


@router.post('/fbo/watch')
def save_watch(body: WatchBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.marketplace != 'wildberries':
        raise HTTPException(409, 'Серверный мониторинг складов сейчас доступен только для Wildberries.')
    store = resolve_store(db, user, body.store_id)
    row = db.query(FboWatch).filter(
        FboWatch.store_id == store.id,
        FboWatch.marketplace == body.marketplace,
    ).first()
    if not row:
        row = FboWatch(user_id=user.id, store_id=store.id, marketplace=body.marketplace)
        db.add(row)
    else:
        row.user_id = user.id
    row.warehouse_filter = body.warehouse_filter[:500]
    row.free_only = body.free_only
    row.enabled = body.enabled
    db.commit()
    return {
        'ok': True,
        'enabled': row.enabled,
        'watch_id': row.id,
        'store_id': store.id,
        'scope': 'all_warehouses' if not row.warehouse_filter else 'filtered',
        'coefficients': [0] if row.free_only else [0, 1],
    }
