from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
import copy, json, requests, time, threading


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

    _rate_lock = threading.Lock()
    _last_request = {}
    _cache_lock = threading.Lock()
    _response_cache = {}

    def __init__(self, token):
        self.token = (token or '').strip()
        self.h = {'Authorization': self.token, 'Content-Type': 'application/json'}

    @classmethod
    def _endpoint_policy(cls, method, url):
        """Return (rate-key, minimum gap, cache ttl).

        Slow WB endpoints are protected by cache so repeated UI refreshes do not turn
        official quotas into long blocking sleeps. 429 handling remains the final guard.
        """
        parsed = urlparse(url); host = parsed.netloc; path = parsed.path
        key = host + path
        method = str(method).upper()
        if host == 'advert-api.wildberries.ru' and path.endswith('/adv/v3/fullstats'):
            return key, 20.5, 60.0 if method == 'GET' else 0.0
        if host == 'finance-api.wildberries.ru' and path.endswith('/api/finance/v1/sales-reports/detailed'):
            return key, 60.5, 300.0
        if method == 'GET':
            return key, 0.15, 15.0
        return key, 0.15, 0.0

    @classmethod
    def _pace(cls, method, url):
        key, min_gap, _ = cls._endpoint_policy(method, url)
        with cls._rate_lock:
            now = time.monotonic(); wait = min_gap - (now - cls._last_request.get(key, 0.0))
            if wait > 0: time.sleep(wait)
            cls._last_request[key] = time.monotonic()

    @staticmethod
    def _cache_key(method, url, kwargs):
        safe = {'params': kwargs.get('params'), 'json': kwargs.get('json')}
        try: encoded = json.dumps(safe, sort_keys=True, ensure_ascii=False, default=str)
        except Exception: encoded = repr(safe)
        return str(method).upper() + '|' + url + '|' + encoded

    @classmethod
    def clear_cache(cls):
        with cls._cache_lock: cls._response_cache.clear()

    def _request(self, method, url, **kwargs):
        if not self.token: raise APIError('Не указан Wildberries API token')
        headers = kwargs.pop('headers', None) or self.h
        timeout = kwargs.pop('timeout', 60)
        max_retries = max(0, int(kwargs.pop('max_retries', 3)))
        cache_ttl_override = kwargs.pop('cache_ttl', None)
        _, _, policy_ttl = self._endpoint_policy(method, url)
        cache_ttl = policy_ttl if cache_ttl_override is None else max(0.0, float(cache_ttl_override))
        cache_key = self._cache_key(method, url, kwargs)
        if cache_ttl > 0:
            with self._cache_lock:
                hit = self._response_cache.get(cache_key)
                if hit and time.monotonic() - hit[0] < cache_ttl: return copy.deepcopy(hit[1])
        for attempt in range(max_retries + 1):
            self._pace(method, url)
            r = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
            if r.status_code != 429: break
            if attempt >= max_retries:
                raise APIError('WB временно ограничил частоту запросов. Приложение уже повторило запрос несколько раз. Подождите 1–2 минуты и обновите данные снова.')
            retry = r.headers.get('X-RateLimit-Retry') or r.headers.get('Retry-After')
            try:
                delay = float(retry)
                if delay > 1000000: delay = max(0.0, delay - time.time())
            except Exception: delay = min(2 ** attempt, 8)
            time.sleep(max(0.8, min(delay, 60.0)))
        if not r.ok: raise APIError(f'WB {r.status_code}: {(r.text or "")[:900]}')
        if r.status_code == 204 or not r.content: result = {}
        else:
            try: result = r.json()
            except Exception: raise APIError('WB вернул ответ не в JSON')
        if cache_ttl > 0:
            with self._cache_lock:
                self._response_cache[cache_key] = (time.monotonic(), copy.deepcopy(result))
                if len(self._response_cache) > 256:
                    oldest = sorted(self._response_cache.items(), key=lambda x: x[1][0])[:64]
                    for k, _ in oldest: self._response_cache.pop(k, None)
        return result

    def seller_info(self): return self._request('GET', self.COMMON + '/api/v1/seller-info')

    @staticmethod
    def _card_to_product(c):
        return {'external_id': str(c.get('nmID', '')), 'sku': c.get('vendorCode', ''), 'name': c.get('title') or c.get('subjectName') or c.get('vendorCode', ''), 'price': 0, 'stock': 0, 'raw': c}

    def products(self, limit=100):
        data = self._request('POST', self.CONTENT + '/content/v2/get/cards/list', json={'settings': {'cursor': {'limit': min(int(limit), 100)}, 'filter': {'withPhoto': -1}}})
        return [self._card_to_product(c) for c in data.get('cards', [])]

    def products_all(self, max_cards=10000):
        out=[]; cursor={'limit':100}; seen=set()
        while len(out) < max(1,int(max_cards)):
            data=self._request('POST',self.CONTENT+'/content/v2/get/cards/list',json={'settings':{'sort':{'ascending':True},'cursor':cursor,'filter':{'withPhoto':-1}}})
            cards=data.get('cards') or []; out.extend(self._card_to_product(c) for c in cards)
            if len(cards)<100 or len(out)>=max_cards: break
            nxt=data.get('cursor') or {}; updated=nxt.get('updatedAt'); nm_id=nxt.get('nmID'); marker=(updated,nm_id)
            if not updated or not nm_id or marker in seen: break
            seen.add(marker); cursor={'limit':100,'updatedAt':updated,'nmID':nm_id}
        return out[:max_cards]

    def update_card(self, card_payload):
        if not isinstance(card_payload,dict) or not card_payload.get('nmID'): raise ValueError('Для обновления карточки нужен полный объект с nmID')
        result=self._request('POST',self.CONTENT+'/content/v2/cards/update',json=[card_payload],timeout=90); self.clear_cache(); return result

    def upload_media_file(self,nm_id,file_path,photo_number):
        path=Path(file_path)
        if not path.exists(): raise FileNotFoundError(str(path))
        headers={'Authorization':self.token,'X-Nm-Id':str(nm_id),'X-Photo-Number':str(int(photo_number))}
        with path.open('rb') as fh: result=self._request('POST',self.CONTENT+'/content/v3/media/file',headers=headers,files={'uploadfile':(path.name,fh)},timeout=120)
        self.clear_cache(); return result

    def save_media_urls(self,nm_id,urls):
        result=self._request('POST',self.CONTENT+'/content/v3/media/save',json={'nmId':int(nm_id),'data':list(urls)},timeout=90); self.clear_cache(); return result

    def prices(self,nm_ids):
        ids=[int(x) for x in nm_ids if str(x).isdigit()]
        if not ids:return {}
        result={}
        for start in range(0,len(ids),1000):
            data=self._request('POST',self.PRICES+'/api/v2/list/goods/filter',json={'nmList':ids[start:start+1000]},cache_ttl=60)
            for item in (data.get('data',{}) or {}).get('listGoods',[]) or []:
                vals=[]
                for s in item.get('sizes') or []:
                    val=s.get('discountedPrice'); val=s.get('price') if val is None else val
                    try: vals.append(float(val))
                    except Exception: pass
                result[str(item.get('nmID',''))]=min(vals) if vals else 0.0
        return result

    @staticmethod
    def _extract_stock_rows(data):
        if isinstance(data,list):return data
        if not isinstance(data,dict):return []
        for key in ('data','stocks','items','rows'):
            value=data.get(key)
            if isinstance(value,list):return value
            if isinstance(value,dict):
                for sub in ('stocks','items','rows'):
                    if isinstance(value.get(sub),list):return value[sub]
        return []

    def warehouse_stocks(self,nm_ids=None,limit=100000):
        ids=[int(x) for x in (nm_ids or []) if str(x).isdigit()][:1000]
        data=self._request('POST',self.ANALYTICS+'/api/analytics/v1/stocks-report/wb-warehouses',json={'nmIds':ids,'chrtIds':[],'limit':min(max(int(limit),1),250000),'offset':0},cache_ttl=60)
        rows=self._extract_stock_rows(data); by_nm={}; total=0.0
        for row in rows:
            nm=row.get('nmId') or row.get('nmID') or row.get('nm_id'); qty=row.get('quantity')
            if qty is None:qty=row.get('stockCount')
            if qty is None:qty=row.get('stock')
            try:qty=float(qty or 0)
            except Exception:qty=0.0
            total+=qty
            if nm is not None:by_nm[str(nm)]=by_nm.get(str(nm),0.0)+qty
        return {'rows':rows,'by_nm':by_nm,'total':total}

    def _date_from(self,days): return (datetime.now(timezone.utc)-timedelta(days=max(int(days),0))).isoformat(timespec='seconds').replace('+00:00','Z')
    def sales(self,days=30): return self._request('GET',self.STATISTICS+'/api/v1/supplier/sales',params={'dateFrom':self._date_from(days),'flag':0},cache_ttl=60)
    def orders(self,days=30): return self._request('GET',self.STATISTICS+'/api/v1/supplier/orders',params={'dateFrom':self._date_from(days),'flag':0},cache_ttl=60)

    @staticmethod
    def sales_summary(rows):
        gross=payout=0.0;units=returns=0
        for r in rows if isinstance(rows,list) else []:
            try:amount=float(r.get('finishedPrice') or r.get('priceWithDisc') or 0)
            except Exception:amount=0.0
            try:pay=float(r.get('forPay') or 0)
            except Exception:pay=0.0
            sale_id=str(r.get('saleID') or r.get('saleId') or ''); is_return=sale_id.upper().startswith('R') or amount<0 or pay<0
            if is_return:returns+=1
            else:units+=1
            gross+=amount;payout+=pay
        return {'operations':len(rows) if isinstance(rows,list) else 0,'units':units,'returns':returns,'gross':gross,'payout':payout}

    def hydrate_products(self,items):
        if not items:return items
        ids=[p.get('external_id') for p in items];warnings=[]
        try:prices=self.prices(ids)
        except Exception as e:prices={};warnings.append('Цены: '+str(e))
        try:stocks=self.warehouse_stocks(ids).get('by_nm',{})
        except Exception as e:stocks={};warnings.append('Остатки: '+str(e))
        out=[]
        for p in items:
            q=dict(p);nm=str(q.get('external_id') or '');q['price']=prices.get(nm,q.get('price',0));q['stock']=stocks.get(nm,q.get('stock',0))
            if warnings:q['sync_warnings']=list(warnings)
            out.append(q)
        return out

    def seller_rating(self): return self._request('GET',self.FEEDBACKS+'/api/common/v1/rating')
    def reviews(self,is_answered=False,take=100,skip=0,nm_id=None,order='dateDesc'):
        params={'isAnswered':str(bool(is_answered)).lower(),'take':min(max(int(take),1),5000),'skip':max(int(skip),0),'order':order}
        if nm_id:params['nmId']=int(nm_id)
        data=self._request('GET',self.FEEDBACKS+'/api/v1/feedbacks',params=params,cache_ttl=30)
        return data.get('data',{}).get('feedbacks',[])
    def answer_review(self,feedback_id,text):
        text=(text or '').strip()
        if len(text)<2 or len(text)>5000:raise ValueError('Ответ должен содержать от 2 до 5000 символов')
        self._request('POST',self.FEEDBACKS+'/api/v1/feedbacks/answer',json={'id':feedback_id,'text':text});self.clear_cache();return True
    def campaign_groups(self): return self._request('GET',self.ADVERT+'/adv/v1/promotion/count',cache_ttl=60)
    def test(self):
        info=self.seller_info();name=info.get('name') or info.get('tradeMark') or info.get('supplierName') or 'продавец';return f'Wildberries подключён: {name}'


class Ozon:
    BASE='https://api-seller.ozon.ru'
    def __init__(self,client_id,key):self.client_id=(client_id or '').strip();self.key=(key or '').strip();self.h={'Client-Id':self.client_id,'Api-Key':self.key,'Content-Type':'application/json'}
    def _post(self,path,payload=None):
        if not self.client_id or not self.key:raise APIError('Не указаны Ozon Client ID / API key')
        r=requests.post(self.BASE+path,headers=self.h,json=payload or {},timeout=60)
        if not r.ok:raise APIError(f'Ozon {r.status_code}: {(r.text or "")[:900]}')
        return r.json() if r.content else {}
    def products(self,limit=100):
        data=self._post('/v3/product/info/list',{'filter':{},'limit':min(int(limit),1000),'last_id':''});result=data.get('result',{});items=result.get('items',[]) if isinstance(result,dict) else []
        return [{'external_id':str(c.get('id') or c.get('product_id') or ''),'sku':str(c.get('offer_id') or ''),'name':c.get('name') or c.get('offer_id') or '','price':0,'stock':0,'raw':c} for c in items]
    def test(self):return f'Ozon подключён. Товаров в тесте: {len(self.products(1))}'
