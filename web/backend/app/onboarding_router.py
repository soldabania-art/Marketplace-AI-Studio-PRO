from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from .data_health import store_data_health
from .db import get_db
from .marketplace_sync import latest_snapshot
from .models import BusinessOperatingProfile, MarketplaceConnection, OperationalAuditEvent, User
from .security import get_current_user
from .store_access import require_store_admin, resolve_store

router = APIRouter(prefix='/onboarding', tags=['onboarding'])

OperatingModel = Literal['reseller', 'manufacturer', 'distributor', 'mixed']
MODEL_LABELS = {
    'reseller': 'Реселлер / импортёр',
    'manufacturer': 'Собственное производство',
    'distributor': 'Официальный дистрибьютор',
    'mixed': 'Смешанная модель',
}


class ProfileConfirmation(BaseModel):
    store_id: str = Field(min_length=1, max_length=36)
    operating_model: OperatingModel
    buys_finished_goods: bool
    makes_products: bool
    controls_rrp: bool

    @model_validator(mode='after')
    def consistent_model(self):
        if self.operating_model == 'reseller' and (not self.buys_finished_goods or self.makes_products or self.controls_rrp):
            raise ValueError('Профиль реселлера должен подтверждать закупку готовых товаров без производства и контроля РРЦ.')
        if self.operating_model == 'manufacturer' and not self.makes_products:
            raise ValueError('Для профиля производителя подтвердите собственное производство или сборку.')
        if self.operating_model == 'distributor' and (not self.buys_finished_goods or not self.controls_rrp):
            raise ValueError('Для профиля дистрибьютора подтвердите закупку готовых товаров и контроль РРЦ.')
        if self.operating_model == 'mixed' and sum((self.buys_finished_goods, self.makes_products, self.controls_rrp)) < 2:
            raise ValueError('Смешанный профиль должен включать минимум два рабочих сценария.')
        return self


def _metrics(db: Session, store_id: str) -> dict:
    catalog = latest_snapshot(db, store_id=store_id, marketplace='wildberries', snapshot_type='catalog')
    stocks = latest_snapshot(db, store_id=store_id, marketplace='wildberries', snapshot_type='stocks')
    sales = latest_snapshot(db, store_id=store_id, marketplace='wildberries', snapshot_type='sales_velocity_7d')
    cards = list((catalog.payload or {}).get('items') or []) if catalog else []
    stock_rows = list((stocks.payload or {}).get('rows') or []) if stocks else []
    sales_rows = list((sales.payload or {}).get('items') or []) if sales else []
    return {
        'catalog_cards': len(cards),
        'brands': len({str(item.get('brand') or '').strip().lower() for item in cards if str(item.get('brand') or '').strip()}),
        'without_description': sum(not str(item.get('description') or '').strip() for item in cards),
        'without_photos': sum(int(item.get('photo_count') or 0) == 0 for item in cards),
        'stock_rows': len(stock_rows),
        'stock_units': sum(max(0, int(item.get('quantity') or item.get('stock') or 0)) for item in stock_rows),
        'products_with_sales': sum(float(item.get('avg_daily_sales') or 0) > 0 for item in sales_rows),
    }


def _actions(*, connected: bool, health: dict, profile: BusinessOperatingProfile | None, metrics: dict) -> list[dict]:
    actions = []
    if not connected:
        actions.append({'key': 'connect-wb', 'title': 'Подключите Wildberries', 'reason': 'Без read-only импорта TROVENDI не видит факты магазина.', 'href': '/account', 'action': 'Подключить'})
    elif not health['safe_for_ai_decisions']:
        actions.append({'key': 'sync-wb', 'title': 'Дождитесь первой синхронизации', 'reason': 'AI Director начнёт анализ после загрузки каталога, остатков и продаж.', 'href': '/data-health', 'action': 'Проверить данные'})
    if profile is None:
        actions.append({'key': 'confirm-profile', 'title': 'Подтвердите модель бизнеса', 'reason': 'Это определяет будущий расчёт себестоимости, закупок и РРЦ.', 'href': '/onboarding#business-profile', 'action': 'Выбрать модель'})
    if health['safe_for_ai_decisions']:
        if metrics['without_description'] or metrics['without_photos']:
            actions.append({'key': 'fix-content', 'title': 'Усилите неполные карточки', 'reason': f"Без описания: {metrics['without_description']} · без фото: {metrics['without_photos']}.", 'href': '/products', 'action': 'Открыть товары'})
        if metrics['stock_units'] == 0 and metrics['catalog_cards']:
            actions.append({'key': 'check-stock', 'title': 'Проверьте нулевые остатки', 'reason': 'Каталог загружен, но доступный остаток не обнаружен.', 'href': '/products', 'action': 'Проверить остатки'})
    if connected and health['safe_for_ai_decisions'] and profile is not None and not actions:
        actions.append({'key': 'open-director', 'title': 'Откройте первый план AI Director', 'reason': 'Магазин, источники и бизнес-профиль готовы.', 'href': '/director', 'action': 'Получить план'})
    return actions[:3]


def _assessment(db: Session, store, profile: BusinessOperatingProfile | None) -> dict:
    connection = db.query(MarketplaceConnection).filter(
        MarketplaceConnection.store_id == store.id,
        MarketplaceConnection.marketplace == 'wildberries',
        MarketplaceConnection.enabled.is_(True),
    ).first()
    health = store_data_health(db, store.id)
    metrics = _metrics(db, store.id)
    steps = [
        {'key': 'store', 'label': 'Магазин создан', 'complete': True},
        {'key': 'connection', 'label': 'Wildberries подключён', 'complete': bool(connection)},
        {'key': 'data', 'label': 'Основные данные загружены', 'complete': health['safe_for_ai_decisions']},
        {'key': 'profile', 'label': 'Модель бизнеса подтверждена', 'complete': profile is not None},
    ]
    return {
        'store_id': store.id,
        'store_name': store.name,
        'status': 'ready' if all(item['complete'] for item in steps) else 'setup',
        'completion_percent': int(sum(item['complete'] for item in steps) / len(steps) * 100),
        'steps': steps,
        'data_health': {'overall_status': health['overall_status'], 'safe_for_ai_decisions': health['safe_for_ai_decisions']},
        'evidence': metrics,
        'profile': ({'operating_model': profile.operating_model, 'label': MODEL_LABELS[profile.operating_model], 'answers': profile.answers, 'confirmed_at': profile.confirmed_at} if profile else None),
        'profile_decision': {'state': 'confirmation_required' if profile is None else 'confirmed', 'reason': 'Юридическую и операционную модель нельзя надёжно определить только по карточкам WB.'},
        'actions': _actions(connected=bool(connection), health=health, profile=profile, metrics=metrics),
    }


@router.get('')
def onboarding(store_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id)
    profile = db.query(BusinessOperatingProfile).filter(
        BusinessOperatingProfile.store_id == store.id,
        BusinessOperatingProfile.marketplace == 'wildberries',
    ).first()
    return _assessment(db, store, profile)


@router.put('/profile')
def confirm_profile(payload: ProfileConfirmation, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, payload.store_id); require_store_admin(db, user, store)
    profile = db.query(BusinessOperatingProfile).filter(
        BusinessOperatingProfile.store_id == store.id,
        BusinessOperatingProfile.marketplace == 'wildberries',
    ).with_for_update().first()
    answers = {'buys_finished_goods': payload.buys_finished_goods, 'makes_products': payload.makes_products, 'controls_rrp': payload.controls_rrp}
    if profile is not None and profile.operating_model == payload.operating_model and profile.answers == answers and profile.status == 'confirmed':
        return _assessment(db, store, profile)
    now = datetime.now(timezone.utc)
    if profile is None:
        profile = BusinessOperatingProfile(workspace_id=store.workspace_id, store_id=store.id, operating_model=payload.operating_model, confirmed_by_user_id=user.id)
        db.add(profile)
    profile.operating_model = payload.operating_model
    profile.answers = answers
    profile.status = 'confirmed'; profile.confirmed_by_user_id = user.id; profile.confirmed_at = now
    db.flush()
    db.add(OperationalAuditEvent(workspace_id=store.workspace_id, store_id=store.id, user_id=user.id,
        event_type='onboarding.business_profile.confirmed', entity_type='business_profile', entity_id=profile.id,
        payload={'operating_model': payload.operating_model, 'marketplace': 'wildberries'}))
    db.commit(); db.refresh(profile)
    return _assessment(db, store, profile)
