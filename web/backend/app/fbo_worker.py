import hashlib
import json
from datetime import datetime, timezone

from pywebpush import WebPushException, webpush
from sqlalchemy.orm import Session

from .config import get_settings
from .models import FboWatch, PushSubscription


def slot_fingerprint(slots: list[dict]) -> str:
    normalized = sorted(f"{s.get('warehouse_name','')}|{s.get('date','')}|{s.get('coefficient','')}|{s.get('box_type_id','')}" for s in slots)
    return hashlib.sha256('\n'.join(normalized).encode()).hexdigest()


def send_slot_push(db: Session, watch: FboWatch, slots: list[dict]) -> int:
    settings = get_settings()
    if not settings.vapid_private_key or not settings.vapid_subject:
        return 0
    sent = 0
    best = slots[0]
    payload = json.dumps({'title':'Свободный склад FBO найден!','body':f"{best.get('warehouse_name','Склад')} · {best.get('date','дата доступна')} · коэффициент {best.get('coefficient','—')}",'url':'/fbo-slots','tag':f'fbo-{watch.marketplace}-{watch.id}'}, ensure_ascii=False)
    subscriptions = db.query(PushSubscription).filter(PushSubscription.user_id == watch.user_id).all()
    for sub in subscriptions:
        try:
            webpush(subscription_info={'endpoint':sub.endpoint,'keys':{'p256dh':sub.p256dh,'auth':sub.auth}}, data=payload, vapid_private_key=settings.vapid_private_key, vapid_claims={'sub':settings.vapid_subject}, ttl=300)
            sent += 1
        except WebPushException as exc:
            if getattr(exc.response, 'status_code', None) in {404, 410}:
                db.delete(sub)
    return sent


def process_watch(db: Session, watch: FboWatch, slots: list[dict]) -> int:
    watch.last_checked_at = datetime.now(timezone.utc)
    if watch.free_only:
        slots = [s for s in slots if s.get('free_acceptance')]
    names = {x.strip().lower() for x in watch.warehouse_filter.split(',') if x.strip()}
    if names:
        slots = [s for s in slots if any(name in str(s.get('warehouse_name','')).lower() for name in names)]
    fingerprint = slot_fingerprint(slots) if slots else ''
    sent = 0
    if slots and fingerprint != watch.last_slot_fingerprint:
        sent = send_slot_push(db, watch, slots)
        if sent:
            watch.last_slot_fingerprint = fingerprint
    db.commit()
    return sent
