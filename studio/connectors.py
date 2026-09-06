from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests, time


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
        max_retries = int(kwargs.pop('max_retries', 3))
        for attempt in range(max_retries + 1):
            r = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
            if r.status_code != 429:
                break
            if attempt >= max_retries:
                raise APIError('WB временно ограничил частоту запросов. Подождите немного и повторите обновление.')
            retry = r.headers.get('X-RateLimit-Retry') or r.headers.get('Retry-After')
            try:
                delay = float(retry)
                # Some APIs expose an absolute Unix timestamp instead of seconds.
                if delay > 1000000:
                    delay = max(0.0, delay - time.time())
            except Exception:
                delay = min(2 ** attempt, 8)
            time.sleep(max(0.5, min(delay, 60.0)))
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
        return {'external_id': str(c.get('nmID', '')), 'sku': c.get('vendorCode', ''), 'name': c.get('title') or c.get('subjectName') or c.get('vendorCode', ''), 'price': 0, 'stock': 0, 'raw': c}

    def products(self, limit=100):
        data = self._request('POST', self.CONTENT + '/content/v2/get/cards/list', json={'settings': {'cursor': {'limit': min(int(limit), 100)}, 'filter': {'withPhoto': -1}}})
        return [self._card_to_product(c) for c in data.get('cards', [])]

    def products_all(self, max_cards=10000):
        out = []; cursor = {'limit': 100}
        while len(out) < max(1, int(max_cards)):
            data = self._request('POST', self.CONTENT + '/content/v2/get/cards/list', json={'settings': {'sort': {'ascending': True}, 'cursor': cursor, 'filter': {'withPhoto': -1}}})
            cards = data.get('cards') or []; out.extend(self._card_to_product(c) for c in cards)
            if len(cards) < 100 or len(out) >= max_cards: break
            nxt = data.get('cursor') or {}; updated = nxt.get('updatedAt'); nm_id = nxt.get('nmID')
            if not updated or not nm_id: break
            cursor = {'limit': 100, 'updatedAt': updated, 'nmID': nm_id}
        return out[:max_cards]

    def update_card(self, card_payload):
        if not isinstance(card_payload, dict) or not card_payload.get('nmID'): raise ValueError('Для обновления карточки нужен полный объект с nmID')
        return self._request('POST', self.CONTENT + '/content/v2/cards/update', json=[card_payload], timeout=90)

    def upload_media_file(self, nm_id, file_path, photo_number):
        path=Path(file_path)
        if not path.exists(): raise FileNotFoundError(str(path))
        headers={'Authorization':self.token,'X-Nm-Id':str(nm_id),'X-Photo-Number':str(photo_number)}
        with path.open('rb') as fh:
            return self._request('POST',self.CONTENT+'/content/v3/media/file',headers=headers,files={'uploadfile':(path.name,fh)},timeout=120)

    def set_media_urls(self,nm_id,urls):
        return self._request('POST',self.CONTENT+'/content/v3/media/save',json={'nmId':int(nm_id),'data':list(urls)},timeout=90)

    def prices(self,nm_ids):
        if not nm_ids:return []
        data=self._request('POST',self.PRICES+'/api/v2/list/goods/filter',json={'nmList':[int(x) for x in nm_ids[:1000]]})
        return data.get('data',{}).get('listGoods') or data.get('listGoods') or []

    def warehouse_stocks(self,nm_ids=None,limit=1000,offset=0):
        body={'limit':min(max(int(limit),1),1000),'offset':max(int(offset),0)}
        if nm_ids:body['nmIds']=[int(x) for x in nm_ids]
        data=self._request('POST',self.ANALYTICS+'/api/analytics/v1/stocks-report/wb-warehouses',json=body)
        if isinstance(data,list):return data
        if isinstance(data,dict):
            value=data.get('data') or data.get('stocks') or data.get('items') or []
            if isinstance(value,dict):value=value.get('items') or value.get('stocks') or []
            return value if isinstance(value,list) else []
        return []

    def sales(self,days=30):
        date_from=(datetime.now(timezone.utc)-timedelta(days=max(int(days),0))).isoformat()
        data=self._request('GET',self.STATISTICS+'/api/v1/supplier/sales',params={'dateFrom':date_from,'flag':0})
        return data if isinstance(data,list) else []

    def orders(self,days=30):
        date_from=(datetime.now(timezone.utc)-timedelta(days=max(int(days),0))).isoformat()
        data=self._request('GET',self.STATISTICS+'/api/v1/supplier/orders',params={'dateFrom':date_from,'flag':0})
        return data if isinstance(data,list) else []

    def sales_summary(self,days=30):
        rows=self.sales(days); gross=0.0; returns=0
        for r in rows:
            try:gross+=float(r.get('forPay') or r.get('finishedPrice') or r.get('priceWithDisc') or 0)
            except Exception:pass
            if r.get('saleID','').startswith('R') or r.get('isReturn') is True:returns+=1
        return {'rows':len(rows),'gross':gross,'returns':returns,'raw':rows}

    def hydrate_products(self,items):
        ids=[int(x['external_id']) for x in items if str(x.get('external_id','')).isdigit()]
        warnings=[]
        try:
            price_rows=self.prices(ids); by_price={str(x.get('nmID') or x.get('nmId')):x for x in price_rows}
            for p in items:
                r=by_price.get(str(p.get('external_id')),{})
                p['price']=r.get('discountedPrice') or r.get('price') or p.get('price',0)
        except APIError as e:warnings.append('Цены: '+str(e))
        try:
            stocks=self.warehouse_stocks(ids); by_stock={}
            for r in stocks:
                key=str(r.get('nmID') or r.get('nmId') or r.get('nm_id') or '')
                qty=r.get('quantity') or r.get('stock') or r.get('quantityFull') or 0
                try:by_stock[key]=by_stock.get(key,0)+int(qty)
                except Exception:pass
            for p in items:p['stock']=by_stock.get(str(p.get('external_id')),p.get('stock',0))
        except APIError as e:warnings.append('Остатки: '+str(e))
        return items,warnings

    def seller_rating(self):return self._request('GET',self.FEEDBACKS+'/api/common/v1/rating')
    def reviews(self,answered=False,nm_id=None,take=100,skip=0):
        params={'isAnswered':str(bool(answered)).lower(),'take':take,'skip':skip,'order':'dateDesc'}
        if nm_id:params['nmId']=nm_id
        return self._request('GET',self.FEEDBACKS+'/api/v1/feedbacks',params=params)
    def answer_review(self,feedback_id,text):return self._request('POST',self.FEEDBACKS+'/api/v1/feedbacks/answer',json={'id':feedback_id,'text':text})
    def campaign_groups(self):return self._request('GET',self.ADVERT+'/adv/v1/promotion/count')
    def test(self):
        info=self.seller_info(); name=info.get('name') or info.get('tradeMark') or info.get('sid') or 'seller'
        return f'Wildberries подключён: {name}'
