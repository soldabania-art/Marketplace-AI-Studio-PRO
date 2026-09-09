import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .db import get_db
from .director_service import build_director
from .marketplace_sync import latest_snapshot
from .models import AutomationControl, DirectorAction, DirectorRun, OperationalAuditEvent, User
from .profit_center_router import profit_center
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
    return result


@router.get('')
def daily_director(store_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id); _connection(db, store.id)
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
    run, rows = _persist_run(db, store, result)
    control = db.query(AutomationControl).filter(AutomationControl.store_id == store.id, AutomationControl.marketplace == 'wildberries').first()
    audit = db.query(OperationalAuditEvent).filter(OperationalAuditEvent.store_id == store.id).order_by(OperationalAuditEvent.created_at.desc()).limit(20).all()
    return _attach_persisted(result, run, rows, control, audit)


@router.patch('/actions/{action_id}')
def decide_action(action_id: str, payload: DecisionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, payload.store_id); require_store_admin(db, user, store)
    row = db.query(DirectorAction).filter(DirectorAction.id == action_id, DirectorAction.store_id == store.id).with_for_update().first()
    if row is None: raise HTTPException(404, 'Рекомендация не найдена в выбранном магазине.')
    if not row.requires_approval: raise HTTPException(409, 'Это диагностическое действие не требует решения владельца.')
    row.status = _transition(row.status, payload.decision)
    row.decision_note = payload.note.strip(); row.decided_by_user_id = user.id; row.decided_at = datetime.now(timezone.utc)
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
