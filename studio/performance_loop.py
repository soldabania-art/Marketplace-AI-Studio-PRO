import json, sqlite3
from .core import DB
from .autopilot import card_versions, queue_action


def init_performance_db():
    with sqlite3.connect(DB) as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS performance_snapshots(
          id INTEGER PRIMARY KEY, created TEXT DEFAULT CURRENT_TIMESTAMP,
          marketplace TEXT, entity_id TEXT, version INTEGER,
          window_days INTEGER, metrics_json TEXT
        );
        ''')


def save_snapshot(marketplace, entity_id, version, metrics, window_days=7):
    init_performance_db()
    with sqlite3.connect(DB) as c:
        cur=c.execute('INSERT INTO performance_snapshots(marketplace,entity_id,version,window_days,metrics_json) VALUES(?,?,?,?,?)',
            (marketplace,str(entity_id),int(version or 0),int(window_days),json.dumps(metrics or {},ensure_ascii=False)))
        return cur.lastrowid


def snapshots(marketplace=None, entity_id=None, limit=200):
    init_performance_db(); where=[]; args=[]
    if marketplace: where.append('marketplace=?'); args.append(marketplace)
    if entity_id is not None: where.append('entity_id=?'); args.append(str(entity_id))
    sql='SELECT * FROM performance_snapshots'+((' WHERE '+' AND '.join(where)) if where else '')+' ORDER BY id DESC LIMIT ?'; args.append(int(limit))
    with sqlite3.connect(DB) as c:
        c.row_factory=sqlite3.Row
        return [dict(r) for r in c.execute(sql,args).fetchall()]


def _num(d,key):
    try:return float((d or {}).get(key) or 0)
    except Exception:return 0.0


def compare(before, after):
    b=before or {}; a=after or {}
    fields=('gross','payout','orders','units','returns','ad_spend','profit','stock')
    out={}
    for k in fields:
        bv=_num(b,k); av=_num(a,k)
        out[k]={'before':bv,'after':av,'delta':av-bv,'pct':((av-bv)/abs(bv)*100.0) if bv else None}
    bconv=_num(b,'conversion'); aconv=_num(a,'conversion')
    out['conversion']={'before':bconv,'after':aconv,'delta':aconv-bconv,'pct':((aconv-bconv)/abs(bconv)*100.0) if bconv else None}
    bdrr=_num(b,'drr'); adrr=_num(a,'drr')
    out['drr']={'before':bdrr,'after':adrr,'delta':adrr-bdrr,'pct':((adrr-bdrr)/abs(bdrr)*100.0) if bdrr else None}
    return out


def rollback_score(before, after):
    """Positive score means the new version looks worse. Conservative by design."""
    b=before or {}; a=after or {}; score=0; reasons=[]
    bp=_num(b,'profit'); ap=_num(a,'profit')
    if bp>0 and ap < bp*0.80:
        score+=3; reasons.append('прибыль снизилась более чем на 20%')
    bg=_num(b,'gross'); ag=_num(a,'gross')
    if bg>0 and ag < bg*0.75:
        score+=2; reasons.append('выручка снизилась более чем на 25%')
    bc=_num(b,'conversion'); ac=_num(a,'conversion')
    if bc>0 and ac < bc*0.80:
        score+=2; reasons.append('конверсия снизилась более чем на 20%')
    bd=_num(b,'drr'); ad=_num(a,'drr')
    if bd>0 and ad > bd*1.35:
        score+=2; reasons.append('ДРР вырос более чем на 35%')
    if _num(a,'returns') > max(_num(b,'returns')*1.5, _num(b,'returns')+3):
        score+=1; reasons.append('заметно выросли возвраты')
    return score,reasons


def propose_rollback(marketplace, entity_id, current_version, before_metrics, after_metrics):
    score,reasons=rollback_score(before_metrics,after_metrics)
    if score < 4:
        return None
    versions=card_versions(marketplace,entity_id,limit=100)
    previous=next((v for v in versions if int(v.get('version') or 0) < int(current_version or 0)),None)
    if not previous:
        return None
    payload={
        'from_version':int(current_version or 0),
        'to_version':int(previous['version']),
        'previous_card':json.loads(previous.get('card_json') or '{}'),
        'previous_images':json.loads(previous.get('images_json') or '[]'),
        'before_metrics':before_metrics or {},
        'after_metrics':after_metrics or {},
        'score':score,'reasons':reasons,
    }
    aid=queue_action(marketplace,entity_id,'rollback_card',payload,'; '.join(reasons),'high')
    return {'action_id':aid,'score':score,'reasons':reasons,'to_version':previous['version']}
