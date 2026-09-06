import json
from datetime import datetime, timezone
from .autopilot import card_versions
from .performance_loop import snapshots, rollback_score, propose_rollback


def _dt(value):
    if not value:return None
    text=str(value).replace('Z','+00:00')
    try:
        d=datetime.fromisoformat(text)
        if d.tzinfo is None:d=d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:return None


def _metrics(row):
    try:return json.loads(row.get('metrics_json') or '{}')
    except Exception:return {}


def _latest_snapshot_for_version(rows, version):
    found=[r for r in rows if int(r.get('version') or 0)==int(version or 0)]
    return found[0] if found else None


def evaluate_entity(marketplace, entity_id, min_hours=24):
    versions=card_versions(marketplace,entity_id,limit=100)
    published=[v for v in versions if str(v.get('status') or '').lower()=='published']
    if len(published)<1:return {'ready':False,'reason':'Нет опубликованной AI-версии'}
    current=published[0]
    current_version=int(current.get('version') or 0)
    rows=snapshots(marketplace,entity_id,limit=300)
    current_snap=_latest_snapshot_for_version(rows,current_version)
    if not current_snap:return {'ready':False,'reason':'Нет снимка метрик после публикации','version':current_version}
    created=_dt(current.get('created')); snap_time=_dt(current_snap.get('created'))
    if created and snap_time:
        hours=(snap_time-created).total_seconds()/3600.0
        if hours<float(min_hours):
            return {'ready':False,'reason':f'Нужно ещё данных: прошло {hours:.1f} ч из {min_hours}','version':current_version}
    previous_versions=[v for v in versions if int(v.get('version') or 0)<current_version and str(v.get('status') or '').lower() in ('published','before_publish')]
    if not previous_versions:return {'ready':False,'reason':'Нет предыдущей версии для сравнения','version':current_version}
    previous=previous_versions[0]
    prev_snap=_latest_snapshot_for_version(rows,int(previous.get('version') or 0))
    if not prev_snap:return {'ready':False,'reason':'Нет базового снимка предыдущей версии','version':current_version}
    before=_metrics(prev_snap); after=_metrics(current_snap)
    score,reasons=rollback_score(before,after)
    return {'ready':True,'marketplace':marketplace,'entity_id':str(entity_id),'current_version':current_version,'previous_version':int(previous.get('version') or 0),'score':score,'reasons':reasons,'before':before,'after':after}


def evaluate_all(marketplace='WB', min_hours=24, limit=200):
    versions=card_versions(marketplace,limit=1000); entities=[]
    for v in versions:
        nm=str(v.get('entity_id') or '')
        if nm and nm not in entities:entities.append(nm)
    out=[]
    for nm in entities[:int(limit)]:
        item=evaluate_entity(marketplace,nm,min_hours)
        if item.get('ready'):out.append(item)
    return out


def queue_needed_rollbacks(marketplace='WB',min_hours=24):
    queued=[]
    for item in evaluate_all(marketplace,min_hours):
        if int(item.get('score') or 0)<4:continue
        result=propose_rollback(marketplace,item['entity_id'],item['current_version'],item['before'],item['after'])
        if result:queued.append({**item,'rollback':result})
    return queued
