from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests


class APIError(RuntimeError):
    pass


class WB:
    CONTENT = 'https://content-api.wildberries.ru'
    FEEDBACKS = 'https://feedbacks-api.wildberries.ru'
    ADVERT = 'https://advert-api.wildberries.ru'
    COMMON = 'https://common-api.wildberries.ru'
    PRICES = 'https://discounts-prices-api.wildberries.ru'
    ANALYTICS = 'https://seller-analytics-api.wildberries.ru'
    STATISTICS = 'https://statistics-api.wildberries.ru'

    def __init__(self, token):
        self.token = (token or '').strip()
        self.h = {'Authorization': self.token, 'Content-Type': 'application/json'}

    def _request(self, method, url, **kwargs):
        if not self.token:
            raise APIError('Не указан Wildberries API token')
        headers = kwargs.pop('headers', None) or self.h
        timeout = kwargs.pop('timeout', 60)
        r = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
        if not r.ok:
            text = (r.text or '')[:900]
            raise APIError(f'WB {r.status_code}: {text}')
        if r.status_code == 204 or not r.content:
            return {}
        try:
            return r.json()
        except Exception:
            raise APIError('WB вернул ответ не в JSON')

    def seller_info(self):
        return self._request('GET', self.COMMON + '/api/v1/seller-info')

    @staticmethod
    def _card_to_product(c):
        return {
            'external_id': str(c.get('nmID', '')),
            'sku': c.get('vendorCode', ''),
            'name': c.get('title') or c.get('subjectName') or c.get('vendorCode', ''),
            'price': 0,
            'stock': 0,
            'raw': c,
        }

    def products(self, limit=100):
        data = self._request(
            'POST', self.CONTENT + '/content/v2/get/cards/list',
            json={'settings': {'cursor': {'limit': min(int(limit), 100)}, 'filter': {'withPhoto': -1}}}
        )
        return [self._card_to_product(c) for c in data.get('cards', [])]

    def products_all(self, max_cards=10000):
        """Load the catalog using WB cursor pagination.

        WB returns cursor.updatedAt and cursor.nmID. Both values are passed to the next
        request exactly as documented. max_cards is a local safety ceiling.
        """
        out = []
        cursor = {'limit': 100}
        while len(out) < max(1, int(max_cards)):
            data = self._request(
                'POST', self.CONTENT + '/content/v2/get/cards/list',
                json={'settings': {'sort': {'ascending': True}, 'cursor': cursor, 'filter': {'withPhoto': -1}}}
            )
            cards = data.get('cards') or []
            out.extend(self._card_to_product(c) for c in cards)
            if len(cards) < 100 or len(out) >= max_cards:
                break
            nxt = data.get('cursor') or {}
            updated = nxt.get('updatedAt')
            nm_id = nxt.get('nmID')
            if not updated or not nm_id:
                break
            cursor = {'limit': 100, 'updatedAt': updated, 'nmID': nm_id}
        return out[:max_cards]

    def update_card(self, card_payload):
        """Overwrite one WB product card with a complete prepared card object.

        WB explicitly overwrites the card, therefore callers must preserve unchanged
        dimensions, characteristics and sizes. Media is managed by separate endpoints.
        """
        if not isinstance(card_payload, dict) or not card_payload.get('nmID'):
            raise ValueError('Для обновления карточки нужен полный объект с nmID')
        return self._request(
            'POST', self.CONTENT + '/content/v2/cards/update',
            json=[card_payload], timeout=90,
        )

    def upload_media_file(self, nm_id, file_path, photo_number):
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(str(path))
        headers = {'Authorization': self.token, 'X-Nm-Id': str(nm_id), 'X-Photo-Number': str(int(photo_number))}
        with path.open('rb') as fh:
            return self._request(
                'POST', self.CONTENT + '/content/v3/media/file',
                headers=headers,
                files={'uploadfile': (path.name, fh)},
                timeout=120,
            )

    def save_media_urls(self, nm_id, urls):
        return self._request(
            'POST', self.CONTENT + '/content/v3/media/save',
            json={'nmId': int(nm_id), 'data': list(urls)}, timeout=90,
        )

    def prices(self, nm_ids):
        ids = [int(x) for x in nm_ids if str(x).isdigit()]
        if not ids:
            return {}
        result = {}
        for start in range(0, len(ids), 1000):
            chunk = ids[start:start + 1000]
            data = self._request('POST', self.PRICES + '/api/v2/list/goods/filter', json={'nmList': chunk})
            for item in (data.get('data', {}) or {}).get('listGoods', []) or []:
                sizes = item.get('sizes') or []
                values = []
                for s in sizes:
                    val = s.get('discountedPrice')
                    if val is None:
                        val = s.get('price')
                    try:
                        values.append(float(val))
                    except Exception:
                        pass
                result[str(item.get('nmID', ''))] = min(values) if values else 0.0
        return result

    @staticmethod
    def _extract_stock_rows(data):
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        for key in ('data', 'stocks', 'items', 'rows'):
            value = data.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                for sub in ('stocks', 'items', 'rows'):
                    if isinstance(value.get(sub), list):
                        return value[sub]
        return []

    def warehouse_stocks(self, nm_ids=None, limit=100000):
        ids = [int(x) for x in (nm_ids or []) if str(x).isdigit()][:1000]
        payload = {'nmIds': ids, 'chrtIds': [], 'limit': min(max(int(limit), 1), 250000), 'offset': 0}
        data = self._request('POST', self.ANALYTICS + '/api/analytics/v1/stocks-report/wb-warehouses', json=payload)
        rows = self._extract_stock_rows(data)
        by_nm = {}
        total = 0.0
        for row in rows:
            nm = row.get('nmId') or row.get('nmID') or row.get('nm_id')
            qty = row.get('quantity')
            if qty is None: qty = row.get('stockCount')
            if qty is None: qty = row.get('stock')
            try: qty = float(qty or 0)
            except Exception: qty = 0.0
            total += qty
            if nm is not None: by_nm[str(nm)] = by_nm.get(str(nm), 0.0) + qty
        return {'rows': rows, 'by_nm': by_nm, 'total': total}

    def _date_from(self, days):
        dt = datetime.now(timezone.utc) - timedelta(days=max(int(days), 0))
        return dt.isoformat(timespec='seconds').replace('+00:00', 'Z')

    def sales(self, days=30):
        return self._request('GET', self.STATISTICS + '/api/v1/supplier/sales', params={'dateFrom': self._date_from(days), 'flag': 0})

    def orders(self, days=30):
        return self._request('GET', self.STATISTICS + '/api/v1/supplier/orders', params={'dateFrom': self._date_from(days), 'flag': 0})

    @staticmethod
    def sales_summary(rows):
        gross = payout = 0.0
        units = returns = 0
        for r in rows if isinstance(rows, list) else []:
            try: amount = float(r.get('finishedPrice') or r.get('priceWithDisc') or 0)
            except Exception: amount = 0.0
            try: pay = float(r.get('forPay') or 0)
            except Exception: pay = 0.0
            sale_id = str(r.get('saleID') or r.get('saleId') or '')
            is_return = sale_id.upper().startswith('R') or amount < 0 or pay < 0
            if is_return: returns += 1
            else: units += 1
            gross += amount; payout += pay
        return {'operations': len(rows) if isinstance(rows, list) else 0, 'units': units, 'returns': returns, 'gross': gross, 'payout': payout}

    def hydrate_products(self, items):
        if not items:
            return items
        ids = [p.get('external_id') for p in items]
        warnings = []
        try: prices = self.prices(ids)
        except Exception as e: prices = {}; warnings.append('Цены: ' + str(e))
        try: stocks = self.warehouse_stocks(ids).get('by_nm', {})
        except Exception as e: stocks = {}; warnings.append('Остатки: ' + str(e))
        out = []
        for p in items:
            q = dict(p); nm = str(q.get('external_id') or '')
            q['price'] = prices.get(nm, q.get('price', 0)); q['stock'] = stocks.get(nm, q.get('stock', 0))
            if warnings: q['sync_warnings'] = warnings
            out.append(q)
        return out

    def seller_rating(self):
        return self._request('GET', self.FEEDBACKS + '/api/common/v1/rating')

    def reviews(self, is_answered=False, take=100, skip=0, nm_id=None, order='dateDesc'):
        params = {'isAnswered': str(bool(is_answered)).lower(), 'take': min(max(int(take), 1), 5000), 'skip': max(int(skip), 0), 'order': order}
        if nm_id: params['nmId'] = int(nm_id)
        data = self._request('GET', self.FEEDBACKS + '/api/v1/feedbacks', params=params)
        return data.get('data', {}).get('feedbacks', [])

    def answer_review(self, feedback_id, text):
        text = (text or '').strip()
        if len(text) < 2 or len(text) > 5000:
            raise ValueError('Ответ должен содержать от 2 до 5000 символов')
        self._request('POST', self.FEEDBACKS + '/api/v1/feedbacks/answer', json={'id': feedback_id, 'text': text})
        return True

    def campaign_groups(self):
        return self._request('GET', self.ADVERT + '/adv/v1/promotion/count')

    def test(self):
        info = self.seller_info()
        name = info.get('name') or info.get('tradeMark') or info.get('supplierName') or 'продавец'
        return f'Wildberries подключён: {name}'


class Ozon:
    BASE = 'https://api-seller.ozon.ru'

    def __init__(self, client_id, key):
        self.client_id = (client_id or '').strip(); self.key = (key or '').strip()
        self.h = {'Client-Id': self.client_id, 'Api-Key': self.key, 'Content-Type': 'application/json'}

    def _post(self, path, payload=None):
        if not self.client_id or not self.key: raise APIError('Не указаны Ozon Client ID / API key')
        r = requests.post(self.BASE + path, headers=self.h, json=payload or {}, timeout=60)
        if not r.ok: raise APIError(f'Ozon {r.status_code}: {(r.text or "")[:900]}')
        return r.json() if r.content else {}

    def products(self, limit=100):
        data = self._post('/v3/product/info/list', {'filter': {}, 'limit': min(int(limit), 1000), 'last_id': ''})
        result = data.get('result', {}); items = result.get('items', []) if isinstance(result, dict) else []
        return [{'external_id': str(c.get('id') or c.get('product_id') or ''), 'sku': str(c.get('offer_id') or ''), 'name': c.get('name') or c.get('offer_id') or '', 'price': 0, 'stock': 0, 'raw': c} for c in items]

    def test(self):
        return f'Ozon подключён. Товаров в тесте: {len(self.products(1))}'
