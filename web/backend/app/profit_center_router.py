from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from typing import Literal
from sqlalchemy.orm import Session

from .db import get_db
from .job_queue import enqueue
from .marketplace_sync import latest_snapshot
from .models import BusinessOperatingProfile, MarketplaceAdvertisingLine, MarketplaceConnection, MarketplaceFinancialLine, OperationalAuditEvent, ProductCostProfile, StoreTaxProfile, User
from .security import get_current_user
from .store_access import require_store_admin, resolve_store

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
    end = date.today()
    start = end - timedelta(days=max(7, min(90, period_days)) - 1)
    return start.isoformat(), end.isoformat()


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


def _line_in_period(row: MarketplaceFinancialLine, date_from: str, date_to: str) -> bool:
    value = str(row.event_date or '')[:10]
    return bool(value and date_from <= value <= date_to)


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
    run_id = f'{date_from}:{date_to}:{datetime.now(timezone.utc).strftime("%Y%m%d%H")}'
    finance_job = enqueue(
        db,
        job_type='marketplace.wb.finance.sync',
        idempotency_key=f'wb-finance:{store.id}:{run_id}:start',
        payload={'store_id': store.id, 'date_from': date_from, 'date_to': date_to, 'rrd_id': 0, 'page_number': 1, 'run_id': run_id},
        workspace_id=store.workspace_id,
        store_id=store.id,
        priority=45,
        max_attempts=5,
    )
    advertising_job = enqueue(
        db,
        job_type='marketplace.wb.advertising.sync',
        idempotency_key=f'wb-ads:{store.id}:{run_id}:start',
        payload={'store_id':store.id,'date_from':date_from,'date_to':date_to,'run_id':run_id},
        workspace_id=store.workspace_id,
        store_id=store.id,
        priority=46,
        max_attempts=5,
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
    profile = db.query(BusinessOperatingProfile).filter(
        BusinessOperatingProfile.store_id == store.id,
        BusinessOperatingProfile.marketplace == 'wildberries',
    ).first()
    try:
        kopecks, operating_model, components, source_references, calculation_sha256 = _verified_cost(payload, profile)
    except InvalidOperation as exc:
        raise HTTPException(422, 'Некорректная себестоимость.') from exc
    row = db.query(ProductCostProfile).filter(
        ProductCostProfile.store_id == store.id,
        ProductCostProfile.marketplace == 'wildberries',
        ProductCostProfile.nm_id == nm_id,
    ).first()
    now = datetime.now(timezone.utc)
    if row is None:
        row = ProductCostProfile(store_id=store.id, marketplace='wildberries', nm_id=nm_id, cogs_kopecks=kopecks, confirmed_by_user_id=user.id, confirmed_at=now)
        db.add(row)
    row.cogs_kopecks = kopecks
    row.operating_model = operating_model
    row.components = components
    row.source_references = source_references
    row.calculation_sha256 = calculation_sha256
    row.confirmed_by_user_id = user.id
    row.source = 'manual_breakdown' if operating_model != 'legacy_total' else 'manual_legacy'
    row.confirmed_at = now
    db.flush()
    db.add(OperationalAuditEvent(
        workspace_id=store.workspace_id, store_id=store.id, user_id=user.id,
        event_type='profit.cost.confirmed', entity_type='product_cost', entity_id=row.id,
        payload={'marketplace': 'wildberries', 'nm_id': nm_id, 'operating_model': operating_model,
            'component_keys': sorted(components), 'cogs_kopecks': kopecks, 'calculation_sha256': calculation_sha256},
    ))
    db.commit()
    db.refresh(row)
    return {'nm_id': row.nm_id, 'cogs_rub': _rubles(row.cogs_kopecks), 'cost_profile': _public_cost(row)}


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
    finance_complete=bool(finance_matches and finance_payload.get('complete'))
    advertising_complete=bool(advertising_matches and advertising_payload.get('complete'))
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
    return {
        'store_id': store.id,
        'store_name': store.name,
        'marketplace': 'wildberries',
        'period': {'days': days, 'date_from': date_from, 'date_to': date_to},
        'sync': {
            'finance':{'started':bool(finance_sync),'coverage_matches':finance_matches,'complete':finance_complete,'page_number':finance_payload.get('page_number'),'last_snapshot_at':finance_sync.created_at if finance_sync else None,'next_rrd_id':finance_payload.get('rrd_id')},
            'advertising':{'started':bool(advertising_sync),'coverage_matches':advertising_matches,'complete':advertising_complete,'page_number':advertising_payload.get('page_number'),'last_snapshot_at':advertising_sync.created_at if advertising_sync else None,'campaign_count':advertising_payload.get('campaign_count')},
        },
        'source_line_count': len(lines),
        'advertising_line_count':len(advertising_lines),
        'amounts': _public_amounts(totals),
        'cogs_total': _rubles(total_cogs) if all_costs_known else None,
        'contribution_before_tax_ads': _rubles(contribution) if contribution is not None else None,
        'advertising':{'spend':_rubles(advertising_spend) if advertising_complete else None,'attributed_revenue':_rubles(advertising_revenue) if advertising_complete else None,'already_in_finance_deductions':_rubles(totals['advertising_deduction_kopecks']),'additional_adjustment':_rubles(advertising_adjustment) if advertising_complete else None},
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
