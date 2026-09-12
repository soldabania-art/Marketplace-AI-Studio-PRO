from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from typing import Literal
from sqlalchemy.orm import Session

from .data_health import expected_coverage
from .db import get_db
from .job_queue import enqueue
from .marketplace_sync import latest_snapshot
from .models import BusinessOperatingProfile, CostImportBatch, CostImportMapping, MarketplaceAdvertisingLine, MarketplaceConnection, MarketplaceFinancialLine, OperationalAuditEvent, ProductCostProfile, StoreTaxProfile, User
from .security import get_current_user
from .store_access import require_store_admin, resolve_store
from .sync_scheduler import enqueue_sync_job

router = APIRouter(prefix='/profit-center', tags=['profit-center'])


class ProfitSyncRequest(BaseModel):
    store_id: str = Field(min_length=1, max_length=36)
    period_days: int = Field(default=30, ge=7, le=90)


CostingModel = Literal['reseller', 'manufacturer', 'distributor']
COST_COMPONENTS = {
    'reseller': {
        'purchase_price': 'Закупочная цена',
        'inbound_logistics': 'Доставка до склада',
        'customs': 'Таможня и пошлины',
        'fulfillment_unit': 'Обработка единицы',
        'packaging': 'Упаковка и маркировка',
    },
    'manufacturer': {
        'materials': 'Сырьё и комплектующие',
        'direct_labor': 'Сдельная работа',
        'packaging': 'Упаковка и маркировка',
        'equipment': 'Оборудование и энергия',
        'overhead': 'Доля цеховых расходов',
    },
    'distributor': {
        'net_purchase': 'Закупка после скидок',
        'fulfillment_unit': 'Логистика и обработка',
        'packaging': 'Упаковка и маркировка',
        'brand_fee': 'Подтверждённые платежи бренду',
    },
}


class ProductCostRequest(BaseModel):
    store_id: str = Field(min_length=1, max_length=36)
    cogs_rub: Decimal | None = Field(default=None, ge=Decimal('0.01'), le=Decimal('100000000'))
    operating_model: CostingModel | None = None
    components_rub: dict[str, Decimal] = Field(default_factory=dict)
    source_references: dict[str, str] = Field(default_factory=dict)
    confirmed: bool

    @model_validator(mode='after')
    def valid_cost_input(self):
        breakdown = self.operating_model is not None or bool(self.components_rub) or bool(self.source_references)
        if breakdown and self.cogs_rub is not None:
            raise ValueError('Передайте либо общую себестоимость, либо детализацию, но не оба варианта.')
        if not breakdown and self.cogs_rub is None:
            raise ValueError('Укажите подтверждённую себестоимость.')
        if breakdown and self.operating_model is None:
            raise ValueError('Для детализации выберите модель себестоимости.')
        return self


class CostImportRow(BaseModel):
    nm_id: int = Field(gt=0)
    operating_model: CostingModel
    components_rub: dict[str, Decimal]
    source_references: dict[str, str]


class CostImportPreviewRequest(BaseModel):
    store_id: str = Field(min_length=1, max_length=36)
    source_system: Literal['csv', '1c', 'moysklad', 'saby', 'kontur', 'partner_api']
    source_document_reference: str = Field(min_length=2, max_length=300)
    rows: list[CostImportRow] = Field(min_length=1, max_length=500)


class CostImportCommitRequest(BaseModel):
    store_id: str = Field(min_length=1, max_length=36)
    preview_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    confirmed: bool


class CostImportMappingRequest(BaseModel):
    store_id: str = Field(min_length=1, max_length=36)
    name: str = Field(min_length=2, max_length=80)
    source_system: Literal['csv', '1c', 'moysklad', 'saby', 'kontur', 'partner_api']
    mapping: dict


def _validated_import_mapping(value: dict) -> dict:
    allowed = {'nm_id', 'operating_model', 'row_source', 'components'}
    if not isinstance(value, dict) or set(value) - allowed or not isinstance(value.get('nm_id'), str) or not value['nm_id'].strip():
        raise HTTPException(422, 'Схема сопоставления содержит недопустимые поля или не имеет nmId.')
    components = value.get('components', {})
    component_keys = {key for catalog in COST_COMPONENTS.values() for key in catalog}
    if not isinstance(components, dict) or set(components) - component_keys:
        raise HTTPException(422, 'Схема содержит неизвестные компоненты себестоимости.')
    normalized = {}
    for key in ('nm_id', 'operating_model', 'row_source'):
        column = value.get(key, '')
        if not isinstance(column, str) or len(column.strip()) > 160:
            raise HTTPException(422, 'Некорректное имя колонки в схеме.')
        normalized[key] = column.strip()
    normalized['components'] = {}
    for key, column in components.items():
        if not isinstance(column, str) or len(column.strip()) > 160:
            raise HTTPException(422, 'Некорректное имя колонки компонента.')
        if column.strip(): normalized['components'][key] = column.strip()
    return normalized


class TaxProfileRequest(BaseModel):
    store_id: str = Field(min_length=1, max_length=36)
    basis: Literal['gross_sales','wb_payout']
    rate_percent: Decimal = Field(ge=Decimal('0'), le=Decimal('100'))
    note: str = Field(default='', max_length=500)
    confirmed: bool


def _connection(db: Session, store_id: str):
    row = db.query(MarketplaceConnection).filter(
        MarketplaceConnection.store_id == store_id,
        MarketplaceConnection.marketplace == 'wildberries',
        MarketplaceConnection.enabled.is_(True),
    ).first()
    if not row:
        raise HTTPException(409, 'Wildberries не подключён к выбранному магазину.')
    return row


def _period(period_days: int) -> tuple[str, str]:
    coverage = expected_coverage('finance', period_days=max(7, min(90, period_days)))
    return coverage['date_from'], coverage['date_to']


def _rubles(kopecks: int) -> str:
    return f'{Decimal(kopecks) / Decimal(100):.2f}'


def _verified_cost(payload: ProductCostRequest, profile: BusinessOperatingProfile | None) -> tuple[int, str, dict, dict, str]:
    if not payload.confirmed:
        raise HTTPException(422, 'Подтвердите, что себестоимость взята из ваших документов.')
    if payload.cogs_rub is not None:
        kopecks = int((payload.cogs_rub * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        canonical = {'operating_model': 'legacy_total', 'components': {'legacy_total': kopecks}, 'sources': {}}
        digest = hashlib.sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        return kopecks, 'legacy_total', canonical['components'], {}, digest
    if profile is None or profile.status != 'confirmed':
        raise HTTPException(409, 'Сначала подтвердите модель бизнеса в мастере настройки.')
    model = str(payload.operating_model)
    if profile.operating_model != 'mixed' and model != profile.operating_model:
        raise HTTPException(422, 'Модель SKU должна совпадать с подтверждённой моделью магазина.')
    allowed = COST_COMPONENTS[model]
    unknown = sorted(set(payload.components_rub) - set(allowed))
    if unknown:
        raise HTTPException(422, f'Недопустимые компоненты себестоимости: {", ".join(unknown)}.')
    if not payload.components_rub:
        raise HTTPException(422, 'Добавьте хотя бы один компонент себестоимости.')
    components: dict[str, int] = {}
    sources: dict[str, str] = {}
    for key, amount in payload.components_rub.items():
        try:
            kopecks = int((Decimal(amount) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        except (InvalidOperation, ValueError) as exc:
            raise HTTPException(422, f'Некорректная сумма компонента {key}.') from exc
        if kopecks < 0 or kopecks > 10_000_000_000:
            raise HTTPException(422, f'Сумма компонента {key} вне допустимого диапазона.')
        if kopecks == 0:
            continue
        reference = str(payload.source_references.get(key) or '').strip()
        if not reference or len(reference) > 300:
            raise HTTPException(422, f'Укажите источник для компонента «{allowed[key]}» (до 300 символов).')
        components[key] = kopecks
        sources[key] = reference
    total = sum(components.values())
    if total <= 0 or total > 10_000_000_000:
        raise HTTPException(422, 'Итоговая себестоимость должна быть больше нуля и не превышать 100 млн ₽.')
    canonical = {'operating_model': model, 'components': components, 'sources': sources}
    digest = hashlib.sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return total, model, components, sources, digest


def _public_cost(row: ProductCostProfile | None) -> dict | None:
    if row is None:
        return None
    return {
        'operating_model': row.operating_model,
        'components_rub': {key: _rubles(int(value)) for key, value in dict(row.components or {}).items()},
        'source_references': dict(row.source_references or {}),
        'calculation_sha256': row.calculation_sha256,
        'source': row.source,
        'confirmed_at': row.confirmed_at,
    }


def _catalog_nm_ids(db: Session, store_id: str) -> set[int]:
    catalog = latest_snapshot(db, store_id=store_id, marketplace='wildberries', snapshot_type='catalog')
    if catalog is None:
        raise HTTPException(409, 'Сначала загрузите каталог Wildberries для выбранного магазина.')
    return {int(item['nm_id']) for item in ((catalog.payload or {}).get('items') or []) if item.get('nm_id')}


def _upsert_cost(db: Session, *, store, user: User, nm_id: int, kopecks: int, operating_model: str,
    components: dict, source_references: dict, calculation_sha256: str, source: str, now: datetime) -> ProductCostProfile:
    row = db.query(ProductCostProfile).filter(
        ProductCostProfile.store_id == store.id,
        ProductCostProfile.marketplace == 'wildberries',
        ProductCostProfile.nm_id == nm_id,
    ).with_for_update().first()
    if row is None:
        row = ProductCostProfile(store_id=store.id, marketplace='wildberries', nm_id=nm_id,
            cogs_kopecks=kopecks, confirmed_by_user_id=user.id, confirmed_at=now)
        db.add(row)
    row.cogs_kopecks = kopecks
    row.operating_model = operating_model
    row.components = components
    row.source_references = source_references
    row.calculation_sha256 = calculation_sha256
    row.confirmed_by_user_id = user.id
    row.source = source
    row.confirmed_at = now
    db.flush()
    return row


def _line_in_period(row: MarketplaceFinancialLine, date_from: str, date_to: str) -> bool:
    value = str(row.event_date or '')[:10]
    return bool(value and date_from <= value <= date_to)


def _sync_is_complete(coverage_matches: bool, payload: dict) -> bool:
    return bool(
        coverage_matches
        and payload.get('complete')
        and payload.get('schema_state') in {'valid','documented_empty'}
        and not payload.get('rejected_count')
    )


def _is_advertising_deduction(row: MarketplaceFinancialLine) -> bool:
    text=f'{getattr(row,"operation","") or ""} {getattr(row,"document_type","") or ""}'.lower()
    return any(marker in text for marker in ('реклам','продвиж','advert'))


def _totals(rows: list[MarketplaceFinancialLine]) -> dict:
    keys = (
        'gross_kopecks', 'payout_kopecks', 'commission_kopecks', 'logistics_kopecks',
        'acquiring_kopecks', 'storage_kopecks', 'acceptance_kopecks',
        'penalty_kopecks', 'deduction_kopecks', 'additional_payment_kopecks',
    )
    result = {key: sum(int(getattr(row, key) or 0) for row in rows) for key in keys}
    result['advertising_deduction_kopecks']=sum(int(row.deduction_kopecks or 0) for row in rows if _is_advertising_deduction(row))
    result['net_units'] = sum(int(row.quantity or 0) for row in rows)
    result['wb_net_kopecks'] = (
        result['payout_kopecks']
        - result['logistics_kopecks']
        - result['acquiring_kopecks']
        - result['storage_kopecks']
        - result['acceptance_kopecks']
        - result['penalty_kopecks']
        - result['deduction_kopecks']
        + result['additional_payment_kopecks']
    )
    return result


def _financial_risks(rows: list[MarketplaceFinancialLine], limit: int = 50) -> dict:
    events = []
    category_totals: dict[tuple[str, str], dict] = {}
    penalty_total = deduction_total = 0
    for row in rows:
        penalty = max(0, int(row.penalty_kopecks or 0))
        deduction = 0 if _is_advertising_deduction(row) else max(0, int(row.deduction_kopecks or 0))
        penalty_total += penalty; deduction_total += deduction
        if not penalty and not deduction: continue
        kind = 'penalty' if penalty else 'deduction'
        label = (str(row.operation or '').strip() or str(row.document_type or '').strip() or 'Без названия')[:120]
        category = category_totals.setdefault((kind, label), {'kind': kind, 'label': label, 'amount_kopecks': 0, 'count': 0})
        category['amount_kopecks'] += penalty or deduction; category['count'] += 1
        events.append({'source_line_id': row.source_line_id, 'kind': kind,
            'amount_kopecks': penalty or deduction, 'event_date': str(row.event_date or '')[:10],
            'operation': str(row.operation or '')[:255], 'document_type': str(row.document_type or '')[:80],
            'nm_id': int(row.nm_id) if row.nm_id else None, 'vendor_code': str(row.vendor_code or '')[:255]})
    events.sort(key=lambda item: (-item['amount_kopecks'], item['event_date'], item['source_line_id']))
    shown = events[:max(1, min(50, limit))]
    categories = sorted(category_totals.values(), key=lambda item: (-item['amount_kopecks'], item['label']))[:8]
    public_items = [{**{key: value for key, value in item.items() if key != 'amount_kopecks'},
                     'amount': _rubles(item['amount_kopecks'])} for item in shown]
    public_categories = [{**{key: value for key, value in item.items() if key != 'amount_kopecks'},
                          'amount': _rubles(item['amount_kopecks'])} for item in categories]
    return {'penalty_total': _rubles(penalty_total), 'deduction_total': _rubles(deduction_total),
        'event_count': len(events), 'shown_count': len(shown), 'categories': public_categories, 'items': public_items}


def _public_amounts(totals: dict) -> dict:
    return {key.removesuffix('_kopecks'): _rubles(value) if key.endswith('_kopecks') else value for key, value in totals.items()}


def _tax_kopecks(totals: dict, profile: StoreTaxProfile | None) -> int | None:
    if profile is None: return None
    basis=totals['gross_kopecks'] if profile.basis=='gross_sales' else totals['payout_kopecks']
    return max(0,int(basis))*int(profile.rate_bps)//10000


@router.post('/sync', status_code=202)
def start_profit_sync(payload: ProfitSyncRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, payload.store_id)
    _connection(db, store.id)
    date_from, date_to = _period(payload.period_days)
    now = datetime.now(timezone.utc)
    run_id = f'manual:profit:{date_from}:{date_to}:{int(now.timestamp() // 3600)}'
    finance_job, _ = enqueue_sync_job(
        db, store=store, group='finance', now=now, suffix=f'{run_id}:start',
        payload={'store_id': store.id, 'date_from': date_from, 'date_to': date_to, 'rrd_id': 0, 'page_number': 1, 'run_id': run_id},
        priority=45,
    )
    advertising_job, _ = enqueue_sync_job(
        db, store=store, group='advertising', now=now, suffix=f'{run_id}:start',
        payload={'store_id':store.id,'date_from':date_from,'date_to':date_to,'run_id':run_id},
        priority=46,
    )
    return {
        'job_id':finance_job.id,
        'jobs':{'finance':finance_job.id,'advertising':advertising_job.id},
        'status':'queued','date_from':date_from,'date_to':date_to,
        'message':'Финансы и рекламная статистика WB поставлены в безопасную фоновую очередь.',
    }


@router.patch('/costs/{nm_id}')
def save_product_cost(nm_id: int, payload: ProductCostRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if nm_id <= 0:
        raise HTTPException(422, 'Некорректный nmId.')
    store = resolve_store(db, user, payload.store_id)
    require_store_admin(db, user, store)
    _connection(db, store.id)
    if nm_id not in _catalog_nm_ids(db, store.id):
        raise HTTPException(404, 'Товар не найден в каталоге выбранного магазина.')
    profile = db.query(BusinessOperatingProfile).filter(
        BusinessOperatingProfile.store_id == store.id,
        BusinessOperatingProfile.marketplace == 'wildberries',
    ).first()
    try:
        kopecks, operating_model, components, source_references, calculation_sha256 = _verified_cost(payload, profile)
    except InvalidOperation as exc:
        raise HTTPException(422, 'Некорректная себестоимость.') from exc
    now = datetime.now(timezone.utc)
    row = _upsert_cost(db, store=store, user=user, nm_id=nm_id, kopecks=kopecks,
        operating_model=operating_model, components=components, source_references=source_references,
        calculation_sha256=calculation_sha256,
        source='manual_breakdown' if operating_model != 'legacy_total' else 'manual_legacy', now=now)
    db.add(OperationalAuditEvent(
        workspace_id=store.workspace_id, store_id=store.id, user_id=user.id,
        event_type='profit.cost.confirmed', entity_type='product_cost', entity_id=row.id,
        payload={'marketplace': 'wildberries', 'nm_id': nm_id, 'operating_model': operating_model,
            'component_keys': sorted(components), 'cogs_kopecks': kopecks, 'calculation_sha256': calculation_sha256},
    ))
    db.commit()
    db.refresh(row)
    return {'nm_id': row.nm_id, 'cogs_rub': _rubles(row.cogs_kopecks), 'cost_profile': _public_cost(row)}


def _public_import_batch(batch: CostImportBatch) -> dict:
    return {
        'id': batch.id,
        'source_system': batch.source_system,
        'source_document_reference': batch.source_document_reference,
        'preview_sha256': batch.payload_sha256,
        'status': batch.status,
        'expires_at': batch.expires_at,
        'committed_at': batch.committed_at,
        'row_count': len(batch.rows or []),
        'rows': [
            {'nm_id': item['nm_id'], 'operating_model': item['operating_model'],
             'cogs_rub': _rubles(int(item['cogs_kopecks'])), 'calculation_sha256': item['calculation_sha256']}
            for item in (batch.rows or [])
        ],
    }


def _public_import_summary(batch: CostImportBatch, now: datetime | None = None) -> dict:
    current = now or datetime.now(timezone.utc)
    expires_at = batch.expires_at
    if expires_at.tzinfo is None: expires_at = expires_at.replace(tzinfo=timezone.utc)
    status = 'expired' if batch.status == 'preview' and expires_at <= current else batch.status
    return {'id': batch.id, 'source_system': batch.source_system,
            'source_document_reference': batch.source_document_reference, 'preview_sha256': batch.payload_sha256,
            'status': status, 'row_count': len(batch.rows or []), 'created_at': batch.created_at,
            'expires_at': batch.expires_at, 'committed_at': batch.committed_at}


def _public_import_mapping(row: CostImportMapping) -> dict:
    return {'id': row.id, 'name': row.name, 'source_system': row.source_system,
            'mapping': row.mapping or {}, 'created_at': row.created_at, 'updated_at': row.updated_at}


@router.get('/cost-import-mappings')
def list_cost_import_mappings(store_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id); require_store_admin(db, user, store)
    rows = db.query(CostImportMapping).filter(CostImportMapping.store_id == store.id).order_by(CostImportMapping.name.asc()).all()
    return {'items': [_public_import_mapping(row) for row in rows]}


@router.post('/cost-import-mappings', status_code=201)
def save_cost_import_mapping(payload: CostImportMappingRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, payload.store_id); require_store_admin(db, user, store)
    name = payload.name.strip(); mapping = _validated_import_mapping(payload.mapping)
    row = db.query(CostImportMapping).filter(CostImportMapping.store_id == store.id, CostImportMapping.name == name).first()
    if row is None:
        row = CostImportMapping(workspace_id=store.workspace_id, store_id=store.id, created_by_user_id=user.id,
            name=name, source_system=payload.source_system, mapping=mapping); db.add(row)
    else:
        row.source_system=payload.source_system; row.mapping=mapping; row.created_by_user_id=user.id
    db.flush()
    db.add(OperationalAuditEvent(workspace_id=store.workspace_id, store_id=store.id, user_id=user.id,
        event_type='profit.cost_mapping.saved', entity_type='cost_mapping', entity_id=row.id,
        payload={'source_system': row.source_system, 'name': row.name, 'component_keys': sorted(mapping['components'])}))
    db.commit(); db.refresh(row)
    return _public_import_mapping(row)


@router.delete('/cost-import-mappings/{mapping_id}', status_code=204)
def delete_cost_import_mapping(mapping_id: str, store_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id); require_store_admin(db, user, store)
    row = db.query(CostImportMapping).filter(CostImportMapping.id == mapping_id, CostImportMapping.store_id == store.id).first()
    if row is None: raise HTTPException(404, 'Схема сопоставления не найдена.')
    db.add(OperationalAuditEvent(workspace_id=store.workspace_id, store_id=store.id, user_id=user.id,
        event_type='profit.cost_mapping.deleted', entity_type='cost_mapping', entity_id=row.id,
        payload={'source_system': row.source_system, 'name': row.name}))
    db.delete(row); db.commit()


@router.get('/cost-imports')
def list_cost_imports(store_id: str, limit: int = Query(default=10, ge=1, le=50),
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id); require_store_admin(db, user, store)
    rows = db.query(CostImportBatch).filter(CostImportBatch.store_id == store.id).order_by(CostImportBatch.created_at.desc()).limit(limit).all()
    return {'items': [_public_import_summary(row) for row in rows]}


@router.post('/cost-imports/preview', status_code=201)
def preview_cost_import(payload: CostImportPreviewRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, payload.store_id); require_store_admin(db, user, store); _connection(db, store.id)
    profile = db.query(BusinessOperatingProfile).filter(
        BusinessOperatingProfile.store_id == store.id,
        BusinessOperatingProfile.marketplace == 'wildberries',
        BusinessOperatingProfile.status == 'confirmed',
    ).first()
    catalog_ids = _catalog_nm_ids(db, store.id)
    incoming_ids = [item.nm_id for item in payload.rows]
    if len(incoming_ids) != len(set(incoming_ids)):
        raise HTTPException(422, {'message': 'Исправьте строки импорта.', 'row_errors': [
            {'row': index + 1, 'nm_id': nm_id, 'error': 'nmId повторяется в этом импорте.'}
            for index, nm_id in enumerate(incoming_ids) if incoming_ids.count(nm_id) > 1
        ]})
    normalized = []
    row_errors = []
    for index, item in enumerate(payload.rows):
        if item.nm_id not in catalog_ids:
            row_errors.append({'row': index + 1, 'nm_id': item.nm_id, 'error': 'Товар не принадлежит каталогу выбранного магазина.'})
            continue
        try:
            request = ProductCostRequest(store_id=store.id, operating_model=item.operating_model,
                components_rub=item.components_rub, source_references=item.source_references, confirmed=True)
            total, model, components, sources, digest = _verified_cost(request, profile)
        except HTTPException as exc:
            row_errors.append({'row': index + 1, 'nm_id': item.nm_id, 'error': str(exc.detail)})
            continue
        normalized.append({'nm_id': item.nm_id, 'operating_model': model, 'cogs_kopecks': total,
            'components': components, 'source_references': sources, 'calculation_sha256': digest})
    if row_errors:
        raise HTTPException(422, {'message': 'Исправьте строки импорта.', 'row_errors': row_errors})
    normalized.sort(key=lambda item: item['nm_id'])
    canonical = {'store_id': store.id, 'marketplace': 'wildberries', 'source_system': payload.source_system,
        'source_document_reference': payload.source_document_reference.strip(), 'rows': normalized}
    preview_sha256 = hashlib.sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    batch = db.query(CostImportBatch).filter(
        CostImportBatch.store_id == store.id,
        CostImportBatch.payload_sha256 == preview_sha256,
    ).first()
    if batch is None:
        batch = CostImportBatch(workspace_id=store.workspace_id, store_id=store.id, created_by_user_id=user.id,
            source_system=payload.source_system, source_document_reference=payload.source_document_reference.strip(),
            rows=normalized, payload_sha256=preview_sha256, status='preview',
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24))
        db.add(batch); db.commit(); db.refresh(batch)
    return _public_import_batch(batch)


@router.post('/cost-imports/{batch_id}/commit')
def commit_cost_import(batch_id: str, payload: CostImportCommitRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not payload.confirmed:
        raise HTTPException(422, 'Подтвердите применение показанного превью.')
    store = resolve_store(db, user, payload.store_id); require_store_admin(db, user, store); _connection(db, store.id)
    batch = db.query(CostImportBatch).filter(
        CostImportBatch.id == batch_id,
        CostImportBatch.store_id == store.id,
    ).with_for_update().first()
    if batch is None:
        raise HTTPException(404, 'Пакет импорта не найден.')
    if batch.created_by_user_id != user.id:
        raise HTTPException(403, 'Применить импорт может только пользователь, создавший превью.')
    if batch.payload_sha256 != payload.preview_sha256:
        raise HTTPException(409, 'Превью изменилось. Создайте его заново и повторно проверьте.')
    if batch.status == 'committed':
        return _public_import_batch(batch)
    expires_at = batch.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        batch.status = 'expired'; db.commit()
        raise HTTPException(409, 'Срок действия превью истёк. Создайте новое превью.')
    if batch.status != 'preview':
        raise HTTPException(409, 'Этот пакет нельзя применить.')
    catalog_ids = _catalog_nm_ids(db, store.id)
    if any(int(item['nm_id']) not in catalog_ids for item in (batch.rows or [])):
        raise HTTPException(409, 'Каталог изменился: один или несколько товаров больше не доступны.')
    now = datetime.now(timezone.utc)
    for item in batch.rows or []:
        _upsert_cost(db, store=store, user=user, nm_id=int(item['nm_id']), kopecks=int(item['cogs_kopecks']),
            operating_model=item['operating_model'], components=dict(item['components']),
            source_references=dict(item['source_references']), calculation_sha256=item['calculation_sha256'],
            source=f'import_{batch.source_system}', now=now)
    batch.status = 'committed'; batch.committed_at = now
    db.add(OperationalAuditEvent(workspace_id=store.workspace_id, store_id=store.id, user_id=user.id,
        event_type='profit.cost_import.committed', entity_type='cost_import', entity_id=batch.id,
        payload={'marketplace': 'wildberries', 'source_system': batch.source_system,
            'row_count': len(batch.rows or []), 'payload_sha256': batch.payload_sha256}))
    db.commit(); db.refresh(batch)
    return _public_import_batch(batch)


@router.patch('/tax')
def save_tax_profile(payload: TaxProfileRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not payload.confirmed:
        raise HTTPException(422,'Подтвердите налоговую базу и ставку по данным бухгалтера или налогового учёта.')
    store=resolve_store(db,user,payload.store_id)
    require_store_admin(db,user,store)
    _connection(db,store.id)
    rate_bps=int((payload.rate_percent*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    row=db.query(StoreTaxProfile).filter(StoreTaxProfile.store_id==store.id,StoreTaxProfile.marketplace=='wildberries').first()
    now=datetime.now(timezone.utc)
    if row is None:
        row=StoreTaxProfile(store_id=store.id,marketplace='wildberries',basis=payload.basis,rate_bps=rate_bps,note=payload.note.strip(),confirmed_by_user_id=user.id,confirmed_at=now)
        db.add(row)
    else:
        row.basis=payload.basis; row.rate_bps=rate_bps; row.note=payload.note.strip(); row.confirmed_by_user_id=user.id; row.confirmed_at=now
    db.commit(); db.refresh(row)
    return {'basis':row.basis,'rate_percent':f'{Decimal(row.rate_bps)/100:.2f}','note':row.note,'confirmed_at':row.confirmed_at}


@router.get('')
def profit_center(store_id: str, period_days: int = 30, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id)
    _connection(db, store.id)
    days = max(7, min(90, int(period_days)))
    date_from, date_to = _period(days)
    finance_sync = latest_snapshot(db, store_id=store.id, marketplace='wildberries', snapshot_type='finance_realization_sync')
    finance_payload = dict(finance_sync.payload or {}) if finance_sync else {}
    finance_matches = finance_payload.get('date_from') == date_from and finance_payload.get('date_to') == date_to
    advertising_sync = latest_snapshot(db, store_id=store.id, marketplace='wildberries', snapshot_type='advertising_sync')
    advertising_payload = dict(advertising_sync.payload or {}) if advertising_sync else {}
    advertising_matches = advertising_payload.get('date_from') == date_from and advertising_payload.get('date_to') == date_to
    all_lines = db.query(MarketplaceFinancialLine).filter(
        MarketplaceFinancialLine.store_id == store.id,
        MarketplaceFinancialLine.marketplace == 'wildberries',
    ).all()
    lines = [row for row in all_lines if _line_in_period(row, date_from, date_to)]
    advertising_lines = db.query(MarketplaceAdvertisingLine).filter(
        MarketplaceAdvertisingLine.store_id == store.id,
        MarketplaceAdvertisingLine.marketplace == 'wildberries',
    ).all()
    advertising_lines = [row for row in advertising_lines if date_from <= str(row.event_date or '')[:10] <= date_to]
    costs = db.query(ProductCostProfile).filter(
        ProductCostProfile.store_id == store.id,
        ProductCostProfile.marketplace == 'wildberries',
    ).all()
    cost_by_nm = {row.nm_id: row for row in costs}
    tax_profile = db.query(StoreTaxProfile).filter(
        StoreTaxProfile.store_id == store.id,
        StoreTaxProfile.marketplace == 'wildberries',
    ).first()
    operating_profile = db.query(BusinessOperatingProfile).filter(
        BusinessOperatingProfile.store_id == store.id,
        BusinessOperatingProfile.marketplace == 'wildberries',
        BusinessOperatingProfile.status == 'confirmed',
    ).first()
    catalog = latest_snapshot(db, store_id=store.id, marketplace='wildberries', snapshot_type='catalog')
    cards = {(item.get('nm_id')): item for item in ((catalog.payload or {}).get('items') or [])} if catalog else {}
    by_nm: dict[int, list[MarketplaceFinancialLine]] = {}
    unallocated = []
    for row in lines:
        if row.nm_id:
            by_nm.setdefault(int(row.nm_id), []).append(row)
        else:
            unallocated.append(row)
    ads_by_nm: dict[int, list[MarketplaceAdvertisingLine]] = {}
    unallocated_ads=[]
    for row in advertising_lines:
        if row.nm_id: ads_by_nm.setdefault(int(row.nm_id),[]).append(row)
        else: unallocated_ads.append(row)
    finance_complete=_sync_is_complete(finance_matches,finance_payload)
    advertising_complete=_sync_is_complete(advertising_matches,advertising_payload)
    products = []
    confirmed_products = 0
    for nm_id, product_lines in by_nm.items():
        values = _totals(product_lines)
        cost = cost_by_nm.get(nm_id)
        net_units = max(0, int(values['net_units']))
        cogs_total = int(cost.cogs_kopecks) * net_units if cost else None
        contribution = values['wb_net_kopecks'] - cogs_total if cogs_total is not None else None
        product_ads=sum(int(row.spend_kopecks or 0) for row in ads_by_nm.get(nm_id,[]))
        ads_adjustment=max(0,product_ads-values['advertising_deduction_kopecks'])
        product_tax=_tax_kopecks(values,tax_profile)
        final_profit=(contribution-ads_adjustment-product_tax) if contribution is not None and finance_complete and advertising_complete and product_tax is not None else None
        if cost:
            confirmed_products += 1
        card = cards.get(nm_id) or {}
        products.append({
            'nm_id': nm_id,
            'vendor_code': card.get('vendor_code') or product_lines[0].vendor_code,
            'title': card.get('title') or product_lines[0].title or f'WB товар {nm_id}',
            'amounts': _public_amounts(values),
            'cogs_per_unit': _rubles(cost.cogs_kopecks) if cost else None,
            'cogs_total': _rubles(cogs_total) if cogs_total is not None else None,
            'contribution_before_tax_ads': _rubles(contribution) if contribution is not None else None,
            'advertising_spend':_rubles(product_ads) if advertising_complete else None,
            'advertising_already_in_finance':_rubles(values['advertising_deduction_kopecks']),
            'tax_reserve':_rubles(product_tax) if product_tax is not None else None,
            'final_profit':_rubles(final_profit) if final_profit is not None else None,
            'cost_confirmed_at': cost.confirmed_at if cost else None,
            'cost_profile': _public_cost(cost),
        })
    products.sort(key=lambda item: (item['final_profit'] is None, Decimal(item['final_profit'] or item['contribution_before_tax_ads'] or '0'), item['nm_id']))
    totals = _totals(lines)
    total_cogs = sum(int(cost_by_nm[nm_id].cogs_kopecks) * max(0, _totals(rows)['net_units']) for nm_id, rows in by_nm.items() if nm_id in cost_by_nm)
    all_costs_known = bool(by_nm) and confirmed_products == len(by_nm)
    contribution = totals['wb_net_kopecks'] - total_cogs if all_costs_known else None
    advertising_spend=sum(int(row.spend_kopecks or 0) for row in advertising_lines)
    advertising_revenue=sum(int(row.attributed_revenue_kopecks or 0) for row in advertising_lines)
    advertising_adjustment=max(0,advertising_spend-totals['advertising_deduction_kopecks'])
    tax_reserve=_tax_kopecks(totals,tax_profile)
    complete=finance_complete and all_costs_known and advertising_complete and tax_profile is not None
    final_profit=(contribution-advertising_adjustment-tax_reserve) if complete else None
    financial_risks=_financial_risks(lines)
    return {
        'store_id': store.id,
        'store_name': store.name,
        'marketplace': 'wildberries',
        'period': {'days': days, 'date_from': date_from, 'date_to': date_to},
        'sync': {
            'finance':{'started':bool(finance_sync),'coverage_matches':finance_matches,'complete':finance_complete,'schema_state':finance_payload.get('schema_state'),'rejected_count':finance_payload.get('rejected_count'),'evidence':finance_payload.get('evidence') or [],'page_number':finance_payload.get('page_number'),'last_snapshot_at':finance_sync.created_at if finance_sync else None,'next_rrd_id':finance_payload.get('rrd_id')},
            'advertising':{'started':bool(advertising_sync),'coverage_matches':advertising_matches,'complete':advertising_complete,'schema_state':advertising_payload.get('schema_state'),'rejected_count':advertising_payload.get('rejected_count'),'evidence':advertising_payload.get('evidence') or [],'page_number':advertising_payload.get('page_number'),'last_snapshot_at':advertising_sync.created_at if advertising_sync else None,'campaign_count':advertising_payload.get('campaign_count')},
        },
        'source_line_count': len(lines),
        'advertising_line_count':len(advertising_lines),
        'amounts': _public_amounts(totals),
        'cogs_total': _rubles(total_cogs) if all_costs_known else None,
        'contribution_before_tax_ads': _rubles(contribution) if contribution is not None else None,
        'advertising':{'spend':_rubles(advertising_spend) if advertising_complete else None,'attributed_revenue':_rubles(advertising_revenue) if advertising_complete else None,'already_in_finance_deductions':_rubles(totals['advertising_deduction_kopecks']),'additional_adjustment':_rubles(advertising_adjustment) if advertising_complete else None},
        'financial_risks': financial_risks,
        'tax':{'basis':tax_profile.basis if tax_profile else None,'rate_percent':f'{Decimal(tax_profile.rate_bps)/100:.2f}' if tax_profile else None,'reserve':_rubles(tax_reserve) if tax_reserve is not None else None,'note':tax_profile.note if tax_profile else '','confirmed_at':tax_profile.confirmed_at if tax_profile else None},
        'operating_profile': ({
            'operating_model': operating_profile.operating_model,
            'allowed_sku_models': list(COST_COMPONENTS) if operating_profile.operating_model == 'mixed' else [operating_profile.operating_model],
            'component_catalog': COST_COMPONENTS,
            'confirmed_at': operating_profile.confirmed_at,
        } if operating_profile else None),
        'profit_status': 'complete' if complete else 'partial',
        'final_profit': _rubles(final_profit) if final_profit is not None else None,
        'completeness': {
            'wb_finance': finance_complete,
            'cogs': all_costs_known,
            'advertising': advertising_complete,
            'tax': tax_profile is not None,
            'unallocated_financial_lines': len(unallocated),
            'unallocated_advertising_lines':len(unallocated_ads),
        },
        'formula': 'WB к перечислению − расходы WB − подтверждённая себестоимость − реклама (без двойного списания удержаний) − подтверждённый налоговый резерв',
        'warning': 'Управленческий расчёт по подключённым источникам. Он не заменяет бухгалтерский и налоговый учёт.' if complete else 'Расчёт неполный: отсутствующие источники не заменяются прогнозами AI.',
        'products': products,
    }
