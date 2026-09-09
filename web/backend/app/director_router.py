import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .db import get_db
from .director_service import build_director, compare_measurement
from .job_queue import enqueue
from .marketplace_sync import latest_snapshot
from .models import AutomationControl, DirectorAction, DirectorRun, OperationalAuditEvent, User
from .profit_center_router import ProfitSyncRequest, profit_center, start_profit_sync
from .security import get_current_user
from .seller_data_router import _connection
from .store_access import require_store_admin, resolve_store
from .wb_analytics import build_network_supply_inputs

router = APIRouter(prefix='/director', tags=['director'])


class DecisionRequest(BaseModel):
    store_id: str = Field(min_length=1, max_length=36)
    decision: Literal['approve', 'reject']
    note: str = Field(default='', max_length=1000)


class ControlRequest(BaseModel):
    store_id: str = Field(min_length=1, max_length=36)
    stopped: bool
    reason: str = Field(min_length=3, max_length=1000)
    confirmation: str = Field(default='', max_length=80)


class ActionRequest(BaseModel):
    store_id: str = Field(min_length=1, max_length=36)


def _source(snapshot, name: str, *, complete: bool | None = None, coverage_matches: bool = True) -> dict:
    if snapshot is None: state, age = 'missing', None
    else:
        created = snapshot.created_at
        if created.tzinfo is None: created = created.replace(tzinfo=timezone.utc)
        age = max(0, int((datetime.now(timezone.utc) - created).total_seconds()))
        state = 'incomplete' if complete is False or not coverage_matches else ('stale' if age > 900 else 'live')
    return {'name': name, 'state': state, 'last_snapshot_at': snapshot.created_at.isoformat() if snapshot and snapshot.created_at else None, 'age_seconds': age}


def _control_payload(control: AutomationControl | None) -> dict:
    return {'stopped': bool(control and control.stopped), 'reason': control.reason if control else '',
            'changed_at': control.changed_at if control else None}


def _transition(current: str, decision: str) -> str:
    target = 'approved' if decision == 'approve' else 'rejected'
    if current == target: return target
    if current != 'proposed': raise HTTPException(409, 'Решение уже зафиксировано и не перезаписывается.')
    return target


def _validate_control(stopped: bool, confirmation: str) -> None:
    if not stopped and confirmation.strip().upper() != 'ВОЗОБНОВИТЬ TROVENDI':
        raise HTTPException(422, 'Для возобновления введите ВОЗОБНОВИТЬ TROVENDI.')


def _read_sync_group(action_key: str, recommendation: dict) -> str:
    if not recommendation.get('can_execute') or recommendation.get('execution_type') != 'read_sync':
        raise HTTPException(409, 'Для этого действия нет безопасного исполнителя. Откройте источник и выполните проверку вручную.')
    if action_key in {'source:catalog', 'source:stocks', 'source:sales_velocity_7d'}: return 'analytics'
    if action_key in {'source:finance_realization_sync', 'source:advertising_sync'}: return 'profit'
    raise HTTPException(409, 'Тип безопасного исполнителя не входит в allowlist.')


def _persist_run(db: Session, store, result: dict) -> tuple[DirectorRun, list[DirectorAction]]:
    fingerprint_payload = {'sources': [{key: item.get(key) for key in ('name', 'state', 'last_snapshot_at')} for item in result['sources']], 'actions': [
        {key: value for key, value in item.items() if key not in {'status'}} for item in result['actions']
    ]}
    fingerprint = hashlib.sha256(json.dumps(fingerprint_payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    run = db.query(DirectorRun).filter(DirectorRun.store_id == store.id, DirectorRun.fingerprint == fingerprint).first()
    if run is None:
        run = DirectorRun(workspace_id=store.workspace_id, store_id=store.id, fingerprint=fingerprint,
                          source_payload={'sources': result['sources']}, summary_payload=result['summary'])
        db.add(run); db.flush()
        for item in result['actions']:
            db.add(DirectorAction(run_id=run.id, workspace_id=store.workspace_id, store_id=store.id,
                                  action_key=item['id'], kind=item['kind'], requires_approval=item['requires_approval'],
                                  recommendation_payload=item))
        db.commit(); db.refresh(run)
    actions = db.query(DirectorAction).filter(DirectorAction.run_id == run.id).order_by(DirectorAction.created_at.asc()).all()
    return run, actions


def _attach_persisted(result: dict, run: DirectorRun, rows: list[DirectorAction], control: AutomationControl | None, audit: list[OperationalAuditEvent]) -> dict:
    by_key = {row.action_key: row for row in rows}
    enriched = []
    for recommendation in result['actions']:
        row = by_key[recommendation['id']]
        enriched.append(recommendation | {'id': row.id, 'action_key': row.action_key, 'status': row.status,
            'decision_note': row.decision_note, 'decided_at': row.decided_at,
            'result': row.result_payload or None, 'rollback': row.rollback_payload or None})
    result['run_id'] = run.id; result['actions'] = enriched; result['control'] = _control_payload(control)
    result['audit'] = [{'id': row.id, 'event_type': row.event_type, 'entity_type': row.entity_type,
                        'entity_id': row.entity_id, 'payload': row.payload, 'created_at': row.created_at} for row in audit]
    result['summary']['approval_required'] = sum(item['requires_approval'] and item['status'] == 'proposed' for item in enriched)
    measurements = [row.payload.get('measurement') for row in audit if row.event_type == 'director.action.measured' and (row.payload or {}).get('measurement')]
    if measurements:
        improved = sum(item.get('outcome') in {'improved', 'no_longer_detected'} for item in measurements)
        result['summary']['measured_changes'] = f'Измерено результатов: {len(measurements)} · улучшений или закрытых проблем: {improved}.'
    return result


def _stored_action_payload(row: DirectorAction) -> dict:
    recommendation = dict(row.recommendation_payload or {})
    return recommendation | {'id': row.id, 'action_key': row.action_key, 'status': row.status,
        'decision_note': row.decision_note, 'decided_at': row.decided_at,
        'result': row.result_payload or None, 'rollback': row.rollback_payload or None}


def _current_result(db: Session, store, user: User) -> dict:
    snapshot = lambda name: latest_snapshot(db, store_id=store.id, marketplace='wildberries', snapshot_type=name)
    catalog, stocks, sales = snapshot('catalog'), snapshot('stocks'), snapshot('sales_velocity_7d')
    finance, advertising = snapshot('finance_realization_sync'), snapshot('advertising_sync')
    end = date.today(); date_from, date_to = (end - timedelta(days=29)).isoformat(), end.isoformat()
    finance_payload = dict(finance.payload or {}) if finance else {}
    advertising_payload = dict(advertising.payload or {}) if advertising else {}
    sources = [
        _source(catalog, 'catalog'), _source(stocks, 'stocks'), _source(sales, 'sales_velocity_7d'),
        _source(finance, 'finance_realization_sync', complete=bool(finance_payload.get('complete')) if finance else None,
                coverage_matches=finance_payload.get('date_from') == date_from and finance_payload.get('date_to') == date_to),
        _source(advertising, 'advertising_sync', complete=bool(advertising_payload.get('complete')) if advertising else None,
                coverage_matches=advertising_payload.get('date_from') == date_from and advertising_payload.get('date_to') == date_to),
    ]
    catalog_items = list((catalog.payload or {}).get('items') or []) if catalog else []
    stock_rows = list((stocks.payload or {}).get('rows') or []) if stocks else []
    sales_rows = list((sales.payload or {}).get('items') or []) if sales else []
    sales_map = {int(row['nm_id']): row for row in sales_rows if row.get('nm_id') is not None}
    supply_facts = build_network_supply_inputs(stock_rows, sales_map) if stocks and sales else []
    profit = profit_center(store_id=store.id, period_days=30, user=user, db=db)
    result = build_director(store_id=store.id, store_name=store.name, sources=sources,
                            catalog_items=catalog_items, supply_facts=supply_facts, profit=profit)
    result['profit_status'] = profit.get('profit_status')
    return result


@router.get('')
def daily_director(store_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id); _connection(db, store.id)
    result = _current_result(db, store, user)
    run, rows = _persist_run(db, store, result)
    control = db.query(AutomationControl).filter(AutomationControl.store_id == store.id, AutomationControl.marketplace == 'wildberries').first()
    audit = db.query(OperationalAuditEvent).filter(OperationalAuditEvent.store_id == store.id).order_by(OperationalAuditEvent.created_at.desc()).limit(20).all()
    response = _attach_persisted(result, run, rows, control, audit)
    current_ids = {row.id for row in rows}
    tracked = db.query(DirectorAction).filter(
        DirectorAction.store_id == store.id,
        DirectorAction.status.in_(['approved', 'executing', 'measured']),
    ).order_by(DirectorAction.updated_at.desc()).limit(20).all()
    response['tracked_actions'] = [_stored_action_payload(row) for row in tracked if row.id not in current_ids][:10]
    return response


@router.post('/actions/{action_id}/execute', status_code=202)
def execute_action(action_id: str, payload: ActionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, payload.store_id); require_store_admin(db, user, store); _connection(db, store.id)
    row = db.query(DirectorAction).filter(DirectorAction.id == action_id, DirectorAction.store_id == store.id).with_for_update().first()
    if row is None: raise HTTPException(404, 'Рекомендация не найдена в выбранном магазине.')
    recommendation = dict(row.recommendation_payload or {})
    executor_group = _read_sync_group(row.action_key, recommendation)
    if row.status == 'executing':
        return {'id': row.id, 'status': row.status, 'execution': (row.result_payload or {}).get('execution'), 'message': 'Обновление уже поставлено в очередь.'}
    if row.status != 'proposed': raise HTTPException(409, 'Эту рекомендацию уже обработали.')
    if executor_group == 'analytics':
        bucket = int(datetime.now(timezone.utc).timestamp() // 300)
        job = enqueue(db, job_type='marketplace.wb.analytics.sync', idempotency_key=f'wb-sync:{store.id}:{bucket}',
                      payload={'store_id': store.id}, workspace_id=store.workspace_id, store_id=store.id,
                      priority=55, max_attempts=5)
        jobs = {'analytics': job.id}
    else:
        queued = start_profit_sync(ProfitSyncRequest(store_id=store.id, period_days=30), user=user, db=db)
        jobs = queued['jobs']
    now = datetime.now(timezone.utc)
    row.status = 'executing'
    row.result_payload = {'baseline': recommendation.get('measurement'), 'execution': {
        'type': 'read_sync', 'read_only': True, 'jobs': jobs, 'started_at': now.isoformat()}}
    row.rollback_payload = {'available': False, 'reason': 'Read-only синхронизация не изменяет данные маркетплейса.'}
    db.add(OperationalAuditEvent(workspace_id=store.workspace_id, store_id=store.id, user_id=user.id,
        event_type='director.action.read_sync_queued', entity_type='director_action', entity_id=row.id,
        payload={'action_key': row.action_key, 'jobs': jobs, 'read_only': True}))
    db.commit(); db.refresh(row)
    return {'id': row.id, 'status': row.status, 'execution': row.result_payload['execution'],
            'message': 'Безопасное чтение поставлено в очередь. Данные WB не изменялись.'}


@router.post('/actions/{action_id}/measure')
def measure_action(action_id: str, payload: ActionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, payload.store_id); require_store_admin(db, user, store); _connection(db, store.id)
    row = db.query(DirectorAction).filter(DirectorAction.id == action_id, DirectorAction.store_id == store.id).with_for_update().first()
    if row is None: raise HTTPException(404, 'Рекомендация не найдена в выбранном магазине.')
    if row.status not in {'approved', 'executing', 'measured'}:
        raise HTTPException(409, 'Сначала подтвердите действие или запустите безопасное обновление источника.')
    recommendation = dict(row.recommendation_payload or {}); baseline = recommendation.get('measurement')
    if not baseline: raise HTTPException(409, 'Для этой рекомендации нет измеримой метрики.')
    current_result = _current_result(db, store, user)
    source_states = {item['name']: item['state'] for item in current_result['sources']}
    required_snapshot_sources = [name for name in recommendation.get('source_refs') or [] if name in source_states]
    if any(source_states[name] != 'live' for name in required_snapshot_sources):
        raise HTTPException(409, 'Нельзя измерить результат: один из исходных источников не актуален.')
    current_recommendation = next((item for item in current_result['actions'] if item['id'] == row.action_key), None)
    current_measurement = current_recommendation.get('measurement') if current_recommendation else None
    if baseline.get('metric') == 'source_state' and current_measurement is None:
        source_name = row.action_key.removeprefix('source:')
        current_measurement = {'metric': 'source_state', 'baseline': source_states.get(source_name), 'better_when': 'live'}
    try: measured = compare_measurement(baseline, current_measurement)
    except ValueError as exc: raise HTTPException(409, str(exc)) from exc
    now = datetime.now(timezone.utc); previous = dict(row.result_payload or {})
    row.result_payload = previous | {'baseline': baseline, 'measurement': measured, 'measured_at': now.isoformat()}
    row.status = 'measured'
    db.add(OperationalAuditEvent(workspace_id=store.workspace_id, store_id=store.id, user_id=user.id,
        event_type='director.action.measured', entity_type='director_action', entity_id=row.id,
        payload={'action_key': row.action_key, 'measurement': measured}))
    db.commit(); db.refresh(row)
    return {'id': row.id, 'status': row.status, 'measurement': measured, 'measured_at': now,
            'message': 'Результат рассчитан по свежим источникам без AI-прогноза.'}


@router.patch('/actions/{action_id}')
def decide_action(action_id: str, payload: DecisionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, payload.store_id); require_store_admin(db, user, store)
    row = db.query(DirectorAction).filter(DirectorAction.id == action_id, DirectorAction.store_id == store.id).with_for_update().first()
    if row is None: raise HTTPException(404, 'Рекомендация не найдена в выбранном магазине.')
    if not row.requires_approval: raise HTTPException(409, 'Это диагностическое действие не требует решения владельца.')
    row.status = _transition(row.status, payload.decision)
    row.decision_note = payload.note.strip(); row.decided_by_user_id = user.id; row.decided_at = datetime.now(timezone.utc)
    if row.status == 'approved':
        recommendation = dict(row.recommendation_payload or {})
        row.result_payload = {'baseline': recommendation.get('measurement'), 'approved_at': row.decided_at.isoformat()}
        row.rollback_payload = {'available': False, 'reason': 'Внешнее исполнение ещё не запускалось.'}
    db.add(OperationalAuditEvent(workspace_id=store.workspace_id, store_id=store.id, user_id=user.id,
        event_type=f'director.action.{row.status}', entity_type='director_action', entity_id=row.id,
        payload={'action_key': row.action_key, 'note': row.decision_note, 'execution_started': False}))
    db.commit(); db.refresh(row)
    return {'id': row.id, 'action_key': row.action_key, 'status': row.status, 'decision_note': row.decision_note,
            'decided_at': row.decided_at, 'execution_started': False,
            'message': 'Решение записано. Изменения в WB не выполнялись.'}


@router.patch('/control')
def set_automation_control(payload: ControlRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, payload.store_id); require_store_admin(db, user, store)
    _validate_control(payload.stopped, payload.confirmation)
    row = db.query(AutomationControl).filter(AutomationControl.store_id == store.id, AutomationControl.marketplace == 'wildberries').with_for_update().first()
    if row is None:
        row = AutomationControl(workspace_id=store.workspace_id, store_id=store.id, marketplace='wildberries',
                                changed_by_user_id=user.id); db.add(row)
    row.stopped = payload.stopped; row.reason = payload.reason.strip(); row.changed_by_user_id = user.id; row.changed_at = datetime.now(timezone.utc)
    db.flush()
    db.add(OperationalAuditEvent(workspace_id=store.workspace_id, store_id=store.id, user_id=user.id,
        event_type='automation.stopped' if payload.stopped else 'automation.resumed', entity_type='automation_control',
        entity_id=row.id, payload={'reason': row.reason, 'stopped': row.stopped}))
    db.commit(); db.refresh(row)
    return _control_payload(row) | {'message': 'Автоматические исполнения остановлены.' if row.stopped else 'Автоматические исполнения разрешены политикой магазина.'}
