import hashlib
import json
from datetime import datetime, timezone

from pywebpush import WebPushException, webpush
from sqlalchemy.orm import Session

from .config import get_settings
from .models import DataHealthIncident, Membership, MembershipRole, PushSubscription


def _fingerprint(store_id: str, source_key: str, opened_at: datetime) -> str:
    return hashlib.sha256(f'{store_id}|{source_key}|{opened_at.isoformat()}'.encode()).hexdigest()


def _send_push(db: Session, workspace_id: str, incident: DataHealthIncident) -> int:
    settings = get_settings()
    if not settings.vapid_private_key or not settings.vapid_subject:
        return 0
    user_ids = [row[0] for row in db.query(Membership.user_id).filter(
        Membership.workspace_id == workspace_id,
        Membership.role.in_([MembershipRole.owner, MembershipRole.admin]),
    ).all()]
    if not user_ids:
        return 0
    subscriptions = db.query(PushSubscription).filter(PushSubscription.user_id.in_(user_ids)).all()
    payload = json.dumps({
        'title': 'TROVENDI: источник данных требует внимания',
        'body': incident.public_message,
        'url': '/data-health',
        'tag': f'data-health-{incident.store_id}-{incident.source_key}',
    }, ensure_ascii=False)
    sent = 0
    for subscription in subscriptions:
        try:
            webpush(
                subscription_info={'endpoint': subscription.endpoint, 'keys': {'p256dh': subscription.p256dh, 'auth': subscription.auth}},
                data=payload,
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={'sub': settings.vapid_subject},
                ttl=900,
            )
            sent += 1
        except WebPushException as exc:
            if getattr(exc.response, 'status_code', None) in {404, 410}:
                db.delete(subscription)
    return sent


def reconcile_health_incidents(db: Session, *, workspace_id: str, store_id: str, sources: list[dict], now: datetime | None = None) -> dict:
    """Open one incident per unhealthy source and resolve it only after recovery."""
    now = now or datetime.now(timezone.utc)
    rows = db.query(DataHealthIncident).filter(DataHealthIncident.store_id == store_id).all()
    by_source = {row.source_key: row for row in rows}
    opened = resolved = pushes = 0
    labels = {item['key']: item['label'] for item in sources}
    for item in sources:
        source_key, state = item['key'], item['status']
        row = by_source.get(source_key)
        if state in {'stale', 'error'}:
            state_message = 'синхронизация завершилась ошибкой' if state == 'error' else 'данные устарели'
            message = f"{labels[source_key]}: {state_message}. AI Director ограничил решения до восстановления источника."
            is_new_or_reopened = row is None or row.status != 'open'
            if row is None:
                row = DataHealthIncident(
                    workspace_id=workspace_id,
                    store_id=store_id,
                    source_key=source_key,
                    fingerprint=_fingerprint(store_id, source_key, now),
                    severity='critical' if state == 'error' else 'warning',
                    public_message=message,
                    opened_at=now,
                    last_seen_at=now,
                )
                db.add(row); db.flush()
            else:
                if is_new_or_reopened:
                    row.status = 'open'; row.opened_at = now; row.resolved_at = None
                row.last_seen_at = now
                row.severity = 'critical' if state == 'error' else 'warning'
                row.public_message = message
            if is_new_or_reopened:
                opened += 1; pushes += _send_push(db, workspace_id, row)
        elif state == 'healthy' and row is not None and row.status == 'open':
            row.status = 'resolved'; row.resolved_at = now; row.last_seen_at = now; resolved += 1
    db.commit()
    return {'opened': opened, 'resolved': resolved, 'pushes': pushes}
