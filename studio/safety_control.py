import json, sqlite3
from datetime import datetime, timezone
from .core import DB

DEFAULT_LIMITS={
    'publish_card':3,
    'ad_bid_change':10,
    'review_reply':30,
    'rollback_card':1,
}


def init_safety_db():
    with sqlite3.connect(DB) as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS autopilot_audit(
          id INTEGER PRIMARY KEY, created TEXT DEFAULT CURRENT_TIMESTAMP,
          event_type TEXT, marketplace TEXT, entity_id TEXT,
          status TEXT, details_json TEXT
        );
        CREATE TABLE IF NOT EXISTS autopilot_usage(
          id INTEGER PRIMARY KEY, created TEXT DEFAULT CURRENT_TIMESTAMP,
          action_type TEXT, marketplace TEXT, entity_id TEXT,
          amount REAL DEFAULT 1, details_json TEXT
        );
        ''')


def audit(event_type, marketplace='', entity_id='', status='info', details=None):
    init_safety_db()
    with sqlite3.connect(DB) as c:
        cur=c.execute('INSERT INTO autopilot_audit(event_type,marketplace,entity_id,status,details_json) VALUES(?,?,?,?,?)',
            (str(event_type),str(marketplace or ''),str(entity_id or ''),str(status),json.dumps(details or {},ensure_ascii=False,default=str)))
        return cur.lastrowid


def audit_rows(limit=300):
    init_safety_db()
    with sqlite3.connect(DB) as c:
        c.row_factory=sqlite3.Row
        return [dict(r) for r in c.execute('SELECT * FROM autopilot_audit ORDER BY id DESC LIMIT ?',(int(limit),)).fetchall()]


def _today_prefix():
    return datetime.now(timezone.utc).date().isoformat()


def usage_today(action_type=None):
    init_safety_db(); where=['created LIKE ?']; args=[_today_prefix()+'%']
    if action_type:
        where.append('action_type=?'); args.append(str(action_type))
    sql='SELECT action_type,COUNT(*) AS count,COALESCE(SUM(amount),0) AS amount FROM autopilot_usage WHERE '+' AND '.join(where)+' GROUP BY action_type'
    with sqlite3.connect(DB) as c:
        c.row_factory=sqlite3.Row
        rows=[dict(r) for r in c.execute(sql,args).fetchall()]
    if action_type:
        return rows[0] if rows else {'action_type':action_type,'count':0,'amount':0.0}
    return {r['action_type']:r for r in rows}


def record_usage(action_type, marketplace='', entity_id='', amount=1, details=None):
    init_safety_db()
    with sqlite3.connect(DB) as c:
        c.execute('INSERT INTO autopilot_usage(action_type,marketplace,entity_id,amount,details_json) VALUES(?,?,?,?,?)',
            (str(action_type),str(marketplace or ''),str(entity_id or ''),float(amount or 0),json.dumps(details or {},ensure_ascii=False,default=str)))
    audit('external_write',marketplace,entity_id,'done',{'action_type':action_type,'amount':amount,**(details or {})})


def limit_for(cfg, action_type):
    key={
        'publish_card':'autopilot_daily_card_publish_limit',
        'ad_bid_change':'autopilot_daily_ad_change_limit',
        'review_reply':'autopilot_daily_review_reply_limit',
        'rollback_card':'autopilot_daily_rollback_limit',
    }.get(action_type)
    default=DEFAULT_LIMITS.get(action_type,0)
    try:return max(0,int(cfg.get(key,default) if key else default))
    except Exception:return default


def can_execute(cfg, action_type, amount=1):
    if bool(cfg.get('autopilot_emergency_stop',False)):
        return False,'AUTOPILOT остановлен аварийным STOP'
    limit=limit_for(cfg,action_type)
    if limit<=0:
        return False,f'{action_type}: дневной лимит отключает автоматическое выполнение'
    used=usage_today(action_type)
    if int(used.get('count') or 0)>=limit:
        return False,f'{action_type}: достигнут дневной лимит {limit}'
    if action_type=='ad_bid_change':
        delta_limit=float(cfg.get('autopilot_daily_ad_delta_budget_pct',100) or 100)
        if float(used.get('amount') or 0)+abs(float(amount or 0))>delta_limit:
            return False,f'Реклама: достигнут дневной бюджет суммарного изменения ставок {delta_limit:.0f}%'
    return True,'ok'


def emergency_stop(cfg, save_settings, reason='Пользователь нажал аварийный STOP'):
    cfg['autopilot_emergency_stop']=True
    cfg['autopilot_mode']='observe'
    save_settings(cfg)
    audit('emergency_stop','','','blocked',{'reason':reason})


def resume_autopilot(cfg, save_settings):
    cfg['autopilot_emergency_stop']=False
    save_settings(cfg)
    audit('emergency_stop','','','resumed',{})


def daily_summary(cfg, actions_rows=None, alerts=None):
    usage=usage_today()
    lines=['Marketplace AI Studio PRO — отчёт AUTOPILOT',f"Режим: {cfg.get('autopilot_mode','approve')}"]
    if cfg.get('autopilot_emergency_stop'): lines.append('⛔ Аварийный STOP: ВКЛ')
    names={'publish_card':'публикации карточек','ad_bid_change':'изменения ставок','review_reply':'ответы на отзывы','rollback_card':'rollback'}
    for key in ('publish_card','ad_bid_change','review_reply','rollback_card'):
        row=usage.get(key,{}); lines.append(f"{names[key]}: {int(row.get('count') or 0)}/{limit_for(cfg,key)}")
    if alerts:
        high=[x for x in alerts if str(x.get('priority'))=='high']
        lines.append(f'Сигналы: {len(alerts)}, критичных: {len(high)}')
    if actions_rows:
        failed=sum(1 for x in actions_rows if x.get('status')=='failed')
        pending=sum(1 for x in actions_rows if x.get('status') in ('proposed','approved','running'))
        lines.append(f'Очередь: ожидают {pending}, ошибок {failed}')
    return '\n'.join(lines)
