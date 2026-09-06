import json, sqlite3, time
import requests
from .core import DB, generated_dir, products
from .autopilot import actions, save_card_version, queue_action, card_versions
from .performance_loop import save_snapshot
from .wb_publisher import WBPublisher


def init_growth_db():
    with sqlite3.connect(DB) as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS growth_runs(
          id INTEGER PRIMARY KEY, created TEXT DEFAULT CURRENT_TIMESTAMP,
          marketplace TEXT, entity_id TEXT, source_score REAL,
          status TEXT, source_photo TEXT, generated_version INTEGER,
          publish_action_id INTEGER, notes TEXT
        );
        ''')


def growth_runs(limit=100):
    init_growth_db()
    with sqlite3.connect(DB) as c:
        c.row_factory=sqlite3.Row
        return [dict(r) for r in c.execute('SELECT * FROM growth_runs ORDER BY id DESC LIMIT ?',(int(limit),)).fetchall()]


def _record(marketplace, entity_id, score, status, source_photo='', version=None, action_id=None, notes=''):
    init_growth_db()
    with sqlite3.connect(DB) as c:
        cur=c.execute('''INSERT INTO growth_runs(marketplace,entity_id,source_score,status,source_photo,generated_version,publish_action_id,notes)
                         VALUES(?,?,?,?,?,?,?,?)''',
            (marketplace,str(entity_id),float(score or 0),status,str(source_photo or ''),version,action_id,str(notes or '')))
        return cur.lastrowid


def _raw_product(nm_id):
    for row in products():
        if str(row['marketplace'])=='WB' and str(row['external_id'])==str(nm_id):
            try:data=json.loads(row['raw_json'] or '{}')
            except Exception:data={}
            return data.get('raw') if isinstance(data,dict) and isinstance(data.get('raw'),dict) else data
    return {}


def _photo_url(raw):
    photos=(raw or {}).get('photos') or (raw or {}).get('mediaFiles') or []
    for item in photos if isinstance(photos,list) else []:
        if isinstance(item,str) and item.startswith('http'):return item
        if isinstance(item,dict):
            for key in ('big','c900x1200','c516x688','square','tm','url'):
                value=item.get(key)
                if isinstance(value,str) and value.startswith('http'):return value
    return ''


def _download_source_photo(url, nm_id):
    if not url:raise RuntimeError('У синхронизированной карточки WB не найдено исходное фото. Обновите каталог или создайте карточку через AI Фабрику вручную.')
    folder=generated_dir()/'autopilot_sources'; folder.mkdir(parents=True,exist_ok=True)
    path=folder/f'wb_{nm_id}_{int(time.time())}.jpg'
    r=requests.get(url,timeout=90)
    if not r.ok:raise RuntimeError(f'Не удалось загрузить исходное фото WB: HTTP {r.status_code}')
    path.write_bytes(r.content); return path


def _facts_from_raw(raw, nm_id):
    raw=raw or {}
    allowed={'nmID':raw.get('nmID') or nm_id,'vendorCode':raw.get('vendorCode'),'brand':raw.get('brand'),'title':raw.get('title'),'description':raw.get('description'),'subjectName':raw.get('subjectName'),'dimensions':raw.get('dimensions'),'characteristics':raw.get('characteristics'),'sizes':raw.get('sizes')}
    return {k:v for k,v in allowed.items() if v not in (None,'',[],{})}


def _recently_processed(nm_id):
    nm=str(nm_id)
    for run in growth_runs(100):
        if str(run.get('entity_id'))==nm and run.get('status') in ('generated','queued','published'):return True
    for a in actions(300):
        if str(a.get('entity_id'))==nm and a.get('action_type') in ('publish_card','regenerate_card') and a.get('status') in ('proposed','approved','running'):return True
    return False


def _capture_baseline(nm, metrics):
    if not isinstance(metrics,dict) or not metrics:return None
    versions=card_versions('WB',nm,limit=100)
    previous=next((v for v in versions if str(v.get('status') or '').lower() in ('published','before_publish','rollback_published')),None)
    if not previous:return None
    return save_snapshot('WB',nm,previous.get('version',0),metrics,7)


class AutonomousCardOptimizer:
    def __init__(self, wb, ai):self.wb=wb; self.ai=ai

    def choose_candidate(self, seo_rows, threshold=70):
        candidates=[]
        for row in seo_rows or []:
            if str(row.get('marketplace') or 'WB')!='WB':continue
            nm=str(row.get('nm') or row.get('external_id') or '')
            if not nm or float(row.get('score') or 100)>=float(threshold):continue
            if _recently_processed(nm):continue
            candidates.append(row)
        candidates.sort(key=lambda x: float(x.get('score') or 100)); return candidates[0] if candidates else None

    def regenerate(self, row, slide_count=7, progress=None, is_cancelled=None):
        nm=str(row.get('nm') or row.get('external_id') or '')
        if not nm:raise RuntimeError('У карточки отсутствует nmID')
        raw=_raw_product(nm)
        if not raw:raise RuntimeError('Нет синхронизированного исходника WB для карточки '+nm)
        _capture_baseline(nm,row.get('baseline_metrics') or {})
        source=_download_source_photo(_photo_url(raw),nm); facts=_facts_from_raw(raw,nm)
        context=('Автоматическая оптимизация существующей карточки Wildberries. Используй только подтверждённые данные ниже. Не меняй идентификатор товара, не выдумывай состав, размеры, сертификаты и свойства. Создай сильнее текущей версии тексты, SEO, визуальную концепцию и инфографику.\n'+json.dumps(facts,ensure_ascii=False,default=str))
        if progress:progress(5,f'Карточка {nm}: исходное фото загружено')
        pack=self.ai.full_product_pack(str(source),context,int(slide_count),progress,is_cancelled)
        if pack.get('cancelled'):
            _record('WB',nm,row.get('score'),'cancelled',source,notes='Остановлено пользователем'); return {'cancelled':True,'nm':nm}
        card=pack.get('card') or {}; images=pack.get('images') or []
        version=save_card_version('WB',nm,card,images,'autopilot_generated')
        action_id=WBPublisher(self.wb).queue_publish(nm,card,images,f'CONTINUOUS AUTOPILOT: SEO score {row.get("score")}/100, AI полностью пересобрал карточку и визуал')
        run_id=_record('WB',nm,row.get('score'),'queued',source,version,action_id,f'AI создал {len(images)} изображений; публикация #{action_id}')
        return {'cancelled':False,'run_id':run_id,'nm':nm,'score':row.get('score'),'card':card,'images':images,'version':version,'publish_action_id':action_id}
