from pathlib import Path
import os, sqlite3, json, keyring

APP='Marketplace AI Studio PRO'
SERVICE='MarketplaceAIStudioPRO'
DATA=Path(os.environ.get('LOCALAPPDATA',Path.home()))/'MarketplaceAIStudioPRO'
DATA.mkdir(parents=True,exist_ok=True)
DB=DATA/'studio.db'
CFG=DATA/'settings.json'
PUBLIC_DEFAULTS={
    'openai_model':'gpt-5.6-sol',
    'openai_monthly_budget_usd':0.0,
    'ai_mode':'free',
    'ai_allow_paid_fallback':False,
    'ai_allow_paid_images':False,
    'local_ai_url':'http://127.0.0.1:8080/v1',
    'local_ai_model':'local-model',
    'local_text_autostart':True,
    'local_images_enabled':True,
    'local_image_url':'http://127.0.0.1:7860',
    'local_image_model':'',
    'local_image_launcher':'',
    'local_image_autostart':False,
    'ozon_client_id':'',
    'company_name':'',
    'telegram_chat_id':'',
    'setup_completed':False,
}
SECRET_KEYS=('openai_api_key','openai_admin_key','wb_token','ozon_api_key','telegram_token')

def generated_dir():
    p=DATA/'generated'; p.mkdir(exist_ok=True); return p

def init_db():
    with sqlite3.connect(DB) as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, marketplace TEXT, external_id TEXT, sku TEXT, name TEXT, price REAL DEFAULT 0, stock REAL DEFAULT 0, raw_json TEXT, updated TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY, name TEXT, photo TEXT, result_json TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, title TEXT, priority TEXT, status TEXT DEFAULT 'open', details TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS unit_economics(id INTEGER PRIMARY KEY, sku TEXT, revenue REAL, commission REAL, logistics REAL, ads REAL, cogs REAL, profit REAL, created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS generated_assets(id INTEGER PRIMARY KEY, project_name TEXT, kind TEXT, path TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
        ''')

def load_settings():
    d=PUBLIC_DEFAULTS.copy()
    if CFG.exists():
        try:d.update(json.loads(CFG.read_text(encoding='utf-8')))
        except:pass
    for k in SECRET_KEYS:d[k]=keyring.get_password(SERVICE,k) or ''
    return d

def save_settings(values):
    pub={k:v for k,v in values.items() if k not in SECRET_KEYS}
    CFG.write_text(json.dumps(pub,ensure_ascii=False,indent=2),encoding='utf-8')
    for k in SECRET_KEYS:
        if k in values:keyring.set_password(SERVICE,k,values[k])

def replace_products(mp,items):
    with sqlite3.connect(DB) as c:
        c.execute('DELETE FROM products WHERE marketplace=?',(mp,))
        for p in items:
            c.execute('INSERT INTO products(marketplace,external_id,sku,name,price,stock,raw_json) VALUES(?,?,?,?,?,?,?)',(mp,p.get('external_id'),p.get('sku'),p.get('name'),p.get('price',0),p.get('stock',0),json.dumps(p,ensure_ascii=False)))

def products():
    with sqlite3.connect(DB) as c:
        c.row_factory=sqlite3.Row
        return c.execute('SELECT * FROM products ORDER BY marketplace,name').fetchall()

def save_project(name,photo,result):
    with sqlite3.connect(DB) as c:
        c.execute('INSERT INTO projects(name,photo,result_json) VALUES(?,?,?)',(name,photo,json.dumps(result,ensure_ascii=False)))

def projects():
    with sqlite3.connect(DB) as c:
        c.row_factory=sqlite3.Row
        return c.execute('SELECT * FROM projects ORDER BY id DESC').fetchall()

def add_task(title,priority='medium',details=''):
    with sqlite3.connect(DB) as c:
        c.execute('INSERT INTO tasks(title,priority,details) VALUES(?,?,?)',(title,priority,details))

def tasks():
    with sqlite3.connect(DB) as c:
        c.row_factory=sqlite3.Row
        return c.execute('SELECT * FROM tasks ORDER BY CASE priority WHEN "high" THEN 1 WHEN "medium" THEN 2 ELSE 3 END,id DESC').fetchall()

def save_asset(project_name,kind,path):
    with sqlite3.connect(DB) as c:
        c.execute('INSERT INTO generated_assets(project_name,kind,path) VALUES(?,?,?)',(project_name,kind,str(path)))
