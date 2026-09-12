from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from .data_health import expected_coverage, store_data_health
from .db import get_db
from .marketplace_sync import latest_snapshot
from .models import BackgroundJob, BusinessOperatingProfile, JobStatus, MarketplaceConnection, OperationalAuditEvent, User
from .security import get_current_user
from .store_access import require_store_admin, resolve_store
from .sync_scheduler import enqueue_sync_job

router = APIRouter(prefix='/onboarding', tags=['onboarding'])

OperatingModel = Literal['reseller', 'manufacturer', 'distributor', 'mixed']
MODEL_LABELS = {
    'reseller': 'Реселлер / импортёр',
    'manufacturer': 'Собственное производство',
    'distributor': 'Официальный дистрибьютор',
    'mixed': 'Смешанная модель',
}
COSTING_QUESTIONS = {
    'reseller': [
        {'key': 'purchase_price', 'label': 'Закупочная цена единицы', 'source': 'Накладная или счёт поставщика'},
        {'key': 'purchase_currency', 'label': 'Валюта и подтверждённый курс партии', 'source': 'Банк или платёжный документ'},
        {'key': 'inbound_logistics', 'label': 'Карго, таможня и доставка до фулфилмента', 'source': 'Документы перевозчика'},
        {'key': 'fulfillment_unit', 'label': 'Упаковка и обработка одной единицы', 'source': 'Тариф фулфилмента'},
    ],
    'manufacturer': [
        {'key': 'materials', 'label': 'Сырьё и комплектующие на единицу', 'source': 'Технологическая карта'},
        {'key': 'direct_labor', 'label': 'Сдельная работа на единицу', 'source': 'Наряд или норматив'},
        {'key': 'packaging', 'label': 'Упаковка и маркировка', 'source': 'Спецификация упаковки'},
        {'key': 'equipment', 'label': 'Амортизация оборудования и энергия', 'source': 'Подтверждённая методика распределения'},
        {'key': 'overhead', 'label': 'Доля аренды и цеховых расходов', 'source': 'Подтверждённая база распределения'},
    ],
    'distributor': [
        {'key': 'net_purchase', 'label': 'Закупочная цена после бонусов', 'source': 'Договор и закрывающие документы'},
        {'key': 'rrp', 'label': 'РРЦ и допустимый диапазон цены', 'source': 'Политика правообладателя'},
        {'key': 'brand_rebate', 'label': 'Маркетинговые компенсации', 'source': 'Отчёт или акт бренда'},
        {'key': 'fulfillment_unit', 'label': 'Логистика и обработка единицы', 'source': 'Тарифы партнёров'},
    ],
    'mixed': [
        {'key': 'sku_model', 'label': 'Модель себестоимости для каждого SKU', 'source': 'Решение владельца'},
        {'key': 'purchase_or_materials', 'label': 'Закупка или материалы на единицу', 'source': 'Накладная или техкарта'},
        {'key': 'labor_and_fulfillment', 'label': 'Производство, упаковка и фулфилмент', 'source': 'Нормативы и тарифы'},
        {'key': 'allocation', 'label': 'Правило распределения общих расходов', 'source': 'Подтверждённая методика'},
    ],
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


def _latest_job(db: Session, store_id: str, job_type: str) -> BackgroundJob | None:
    return db.query(BackgroundJob).filter(
        BackgroundJob.store_id == store_id,
        BackgroundJob.job_type == job_type,
    ).order_by(BackgroundJob.created_at.desc()).first()


def _import_progress(db: Session, store_id: str, health: dict) -> dict:
    source_map = {item['key']: item for item in health['sources']}
    groups = []
    specs = (
        ('core', 'Каталог, остатки и продажи', ('catalog', 'stocks', 'sales'), 'marketplace.wb.analytics.sync', 50),
        ('finance', 'Финансовый отчёт', ('finance',), 'marketplace.wb.finance.sync', 25),
        ('advertising', 'Рекламная статистика', ('advertising',), 'marketplace.wb.advertising.sync', 25),
    )
    total = 0
    for key, label, source_keys, job_type, weight in specs:
        sources = [source_map[item] for item in source_keys]
        job = _latest_job(db, store_id, job_type)
        complete = all(item['status'] in {'healthy', 'delayed'} for item in sources)
        if complete:
            state = 'complete'; total += weight
        elif job and job.status == JobStatus.dead:
            state = 'error'
        elif job and job.status == JobStatus.retry:
            state = 'retrying'
        elif job and job.status in {JobStatus.queued, JobStatus.running} or any(item['status'] == 'syncing' for item in sources):
            state = 'syncing'
        else:
            state = 'waiting'
        groups.append({'key': key, 'label': label, 'state': state, 'weight': weight,
            'job': {'id': job.id, 'status': job.status.value, 'attempts': job.attempts, 'max_attempts': job.max_attempts} if job else None})
    return {'progress_percent': total, 'complete': total == 100, 'groups': groups,
        'resumable': True, 'message': 'Импорт продолжится в фоне после закрытия страницы.'}


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
        'import': _import_progress(db, store.id, health),
        'evidence': metrics,
        'profile': ({'operating_model': profile.operating_model, 'label': MODEL_LABELS[profile.operating_model], 'answers': profile.answers, 'confirmed_at': profile.confirmed_at} if profile else None),
        'profile_decision': {'state': 'confirmation_required' if profile is None else 'confirmed', 'reason': 'Юридическую и операционную модель нельзя надёжно определить только по карточкам WB.'},
        'costing_questions': COSTING_QUESTIONS.get(profile.operating_model, []) if profile else [],
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


@router.post('/import', status_code=202)
def start_import(store_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id); require_store_admin(db, user, store)
    connection = db.query(MarketplaceConnection).filter(
        MarketplaceConnection.store_id == store.id,
        MarketplaceConnection.marketplace == 'wildberries',
        MarketplaceConnection.enabled.is_(True),
    ).first()
    if connection is None:
        raise HTTPException(409, 'Сначала подключите Wildberries к выбранному магазину.')
    now = datetime.now(timezone.utc)
    coverage = expected_coverage('finance', now=now, period_days=30)
    begin, today = coverage['date_from'], coverage['date_to']
    run_id = f'onboarding:{begin}:{today}:{int(now.timestamp() // 3600)}'
    recovery_slot = int(now.timestamp() // 3600)
    common = {'store_id': store.id, 'date_from': begin, 'date_to': today, 'run_id': run_id, 'origin': 'onboarding'}
    jobs = {
        'core': enqueue_sync_job(db, store=store, group='analytics', now=now, suffix=f'onboarding:{recovery_slot}', payload={'store_id': store.id, 'origin': 'onboarding'}, priority=50)[0],
        'finance': enqueue_sync_job(db, store=store, group='finance', now=now, suffix=f'{run_id}:start', payload=common | {'rrd_id': 0, 'page_number': 1}, priority=51)[0],
        'advertising': enqueue_sync_job(db, store=store, group='advertising', now=now, suffix=f'{run_id}:start', payload=common | {'campaign_ids': [], 'date_index': 0, 'batch_index': 0}, priority=52)[0],
    }
    db.add(OperationalAuditEvent(workspace_id=store.workspace_id, store_id=store.id, user_id=user.id,
        event_type='onboarding.import.requested', entity_type='store', entity_id=store.id,
        payload={'read_only': True, 'jobs': {key: job.id for key, job in jobs.items()}}))
    db.commit()
    return {'store_id': store.id, 'read_only': True,
        'jobs': {key: {'id': job.id, 'status': job.status.value} for key, job in jobs.items()},
        'message': 'Импорт поставлен в защищённую очередь и продолжится в фоне.'}
