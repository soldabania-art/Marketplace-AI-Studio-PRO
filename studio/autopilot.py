import json, sqlite3
from datetime import datetime
from .core import DB

MODES = ('observe', 'approve', 'autopilot')


def init_autopilot_db():
    with sqlite3.connect(DB) as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS autopilot_actions(
          id INTEGER PRIMARY KEY, created TEXT DEFAULT CURRENT_TIMESTAMP,
          marketplace TEXT, entity_id TEXT, action_type TEXT, risk TEXT,
          status TEXT DEFAULT 'proposed', payload TEXT, reason TEXT, result TEXT
        );
        CREATE TABLE IF NOT EXISTS card_versions(
          id INTEGER PRIMARY KEY, created TEXT DEFAULT CURRENT_TIMESTAMP,
          marketplace TEXT, entity_id TEXT, version INTEGER, status TEXT,
          card_json TEXT, images_json TEXT, metrics_json TEXT
        );
        ''')


def queue_action(marketplace, entity_id, action_type, payload, reason='', risk='medium'):
    init_autopilot_db()
    with sqlite3.connect(DB) as c:
        cur=c.execute('INSERT INTO autopilot_actions(marketplace,entity_id,action_type,risk,payload,reason) VALUES(?,?,?,?,?,?)',
            (marketplace,str(entity_id or ''),action_type,risk,json.dumps(payload,ensure_ascii=False),reason))
        return cur.lastrowid


def actions(limit=200):
    init_autopilot_db()
    with sqlite3.connect(DB) as c:
        c.row_factory=sqlite3.Row
        return [dict(r) for r in c.execute('SELECT * FROM autopilot_actions ORDER BY id DESC LIMIT ?',(limit,)).fetchall()]


def set_action_status(action_id,status,result=None):
    init_autopilot_db()
    with sqlite3.connect(DB) as c:
        c.execute('UPDATE autopilot_actions SET status=?, result=? WHERE id=?',(status,json.dumps(result,ensure_ascii=False) if result is not None else None,int(action_id)))


def save_card_version(marketplace, entity_id, card, images=None, status='draft', metrics=None):
    init_autopilot_db()
    with sqlite3.connect(DB) as c:
        row=c.execute('SELECT COALESCE(MAX(version),0)+1 FROM card_versions WHERE marketplace=? AND entity_id=?',(marketplace,str(entity_id or ''))).fetchone()
        ver=int(row[0])
        c.execute('INSERT INTO card_versions(marketplace,entity_id,version,status,card_json,images_json,metrics_json) VALUES(?,?,?,?,?,?,?)',
          (marketplace,str(entity_id or ''),ver,status,json.dumps(card,ensure_ascii=False),json.dumps([str(x) for x in (images or [])],ensure_ascii=False),json.dumps(metrics or {},ensure_ascii=False)))
        return ver


def card_versions(marketplace=None,entity_id=None,limit=100):
    init_autopilot_db(); where=[]; args=[]
    if marketplace: where.append('marketplace=?'); args.append(marketplace)
    if entity_id is not None: where.append('entity_id=?'); args.append(str(entity_id))
    sql='SELECT * FROM card_versions'+((' WHERE '+' AND '.join(where)) if where else '')+' ORDER BY id DESC LIMIT ?'; args.append(limit)
    with sqlite3.connect(DB) as c:
        c.row_factory=sqlite3.Row
        return [dict(r) for r in c.execute(sql,args).fetchall()]


def allowed_without_confirmation(action_type, risk, mode):
    if mode != 'autopilot': return False
    # Read/analysis/generation can be autonomous. Marketplace writes remain gated
    # until their exact API contracts and rollback behavior are implemented/tested.
    return risk == 'low' and action_type in {'analyze','generate_card','generate_visuals','draft_reply','create_task'}


def propose_store_maintenance(products, seo_rows, alerts):
    proposals=[]
    for row in seo_rows:
        if row.get('score',100) < 70:
            proposals.append({'marketplace':row.get('marketplace','WB'),'entity_id':row.get('nm'),'action_type':'generate_card','risk':'low','reason':f"SEO score {row.get('score')}/100",'payload':row})
    for alert in alerts:
        proposals.append({'marketplace':'WB','entity_id':'','action_type':'create_task','risk':'low','reason':alert.get('title','Сигнал'),'payload':alert})
    return proposals
