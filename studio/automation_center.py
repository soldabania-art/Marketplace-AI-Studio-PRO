import json
from datetime import datetime, timezone
import requests
from .core import DATA

TASKS_FILE = DATA / 'director_tasks.json'


def load_tasks():
    try:
        data = json.loads(TASKS_FILE.read_text(encoding='utf-8')) if TASKS_FILE.exists() else []
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_tasks(tasks):
    TASKS_FILE.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding='utf-8')


def add_task(title, priority='medium', details='', source='AI Director'):
    tasks = load_tasks()
    item = {
        'id': max([int(x.get('id', 0)) for x in tasks] + [0]) + 1,
        'title': str(title),
        'priority': priority,
        'details': str(details),
        'source': source,
        'status': 'open',
        'created': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }
    tasks.insert(0, item)
    save_tasks(tasks)
    return item


def set_task_status(task_id, status):
    tasks = load_tasks()
    for item in tasks:
        if int(item.get('id', 0)) == int(task_id):
            item['status'] = status
            item['updated'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
            break
    save_tasks(tasks)
    return tasks


def build_alerts(products, live, finance, ads, cogs=None):
    cogs = cogs or {}
    alerts = []
    stock_total = float(live.get('stock_total') or 0)
    if stock_total <= 0 and products:
        alerts.append({'priority':'high','title':'Нет остатков WB','details':'По загруженным данным общий остаток равен нулю. Проверьте поставки и доступность товаров.'})
    low = [p for p in products if str(p.get('marketplace')) == 'WB' and float(p.get('stock') or 0) <= 3]
    if low:
        alerts.append({'priority':'high','title':f'Низкий остаток у {len(low)} товаров','details':'Проверьте товары с остатком 0–3 шт. и запланируйте поставку.'})
    drr = float(ads.get('drr') or 0) if isinstance(ads, dict) else 0
    if drr >= 25:
        alerts.append({'priority':'high','title':f'Высокий ДРР: {drr:.1f}%','details':'Рекламные расходы высоки относительно рекламных продаж. Нужен разбор кампаний и ставок.'})
    elif drr >= 15:
        alerts.append({'priority':'medium','title':f'ДРР требует контроля: {drr:.1f}%','details':'Проверьте кампании с низкой эффективностью и корректность ставок.'})
    returns = int(live.get('returns') or 0)
    units = int(live.get('units') or 0)
    if units and returns / max(units, 1) >= 0.10:
        alerts.append({'priority':'high','title':'Высокая доля возвратов','details':f'Возвратов {returns} при {units} продажах. Проверьте контент карточек, ожидания покупателей и качество.'})
    payout = float(finance.get('payout') or 0) if isinstance(finance, dict) else 0
    gross = float(finance.get('gross') or 0) if isinstance(finance, dict) else 0
    if gross > 0 and payout / gross < 0.55:
        alerts.append({'priority':'medium','title':'Низкая доля выплаты от начислений','details':f'К выплате около {payout/gross*100:.1f}% от начислений. Проверьте логистику, хранение, штрафы и прочие удержания.'})
    missing_cogs = [p for p in products if str(p.get('marketplace')) == 'WB' and str(p.get('external_id')) not in cogs]
    if missing_cogs:
        alerts.append({'priority':'medium','title':f'Не заполнена себестоимость у {len(missing_cogs)} товаров','details':'Без себестоимости невозможно точно считать чистую прибыль по SKU.'})
    if not alerts:
        alerts.append({'priority':'low','title':'Критических сигналов не найдено','details':'По доступным данным явных критических проблем нет. Продолжайте следить за ДРР, остатками и возвратами.'})
    return alerts


class TelegramNotifier:
    def __init__(self, token, chat_id):
        self.token = (token or '').strip()
        self.chat_id = str(chat_id or '').strip()

    def send(self, text):
        if not self.token or not self.chat_id:
            raise RuntimeError('Не указан Telegram bot token или chat ID')
        r = requests.post(
            f'https://api.telegram.org/bot{self.token}/sendMessage',
            json={'chat_id': self.chat_id, 'text': str(text)[:4096]},
            timeout=30,
        )
        if not r.ok:
            raise RuntimeError(f'Telegram {r.status_code}: {(r.text or "")[:500]}')
        data = r.json() if r.content else {}
        if not data.get('ok', False):
            raise RuntimeError('Telegram не подтвердил отправку сообщения')
        return True
