import requests

class APIError(RuntimeError): pass

class WB:
    CONTENT='https://content-api.wildberries.ru'
    FEEDBACKS='https://feedbacks-api.wildberries.ru'
    ADVERT='https://advert-api.wildberries.ru'
    COMMON='https://common-api.wildberries.ru'

    def __init__(self,token):
        self.token=token.strip()
        self.h={'Authorization':self.token,'Content-Type':'application/json'}

    def _request(self,method,url,**kwargs):
        if not self.token: raise APIError('Не указан Wildberries API token')
        r=requests.request(method,url,headers=self.h,timeout=45,**kwargs)
        if not r.ok: raise APIError(f'WB {r.status_code}: {r.text[:700]}')
        if r.status_code==204 or not r.content:return {}
        return r.json()

    def ping(self,service='content'):
        bases={'content':self.CONTENT,'feedbacks':self.FEEDBACKS,'promotion':self.ADVERT,'common':self.COMMON}
        return self._request('GET',bases.get(service,self.CONTENT)+'/ping')

    def products(self,limit=100):
        data=self._request('POST',self.CONTENT+'/content/v2/get/cards/list',json={'settings':{'cursor':{'limit':min(limit,100)},'filter':{'withPhoto':-1}}})
        return [{'external_id':str(c.get('nmID','')),'sku':c.get('vendorCode',''),'name':c.get('title') or c.get('subjectName') or c.get('vendorCode',''),'price':0,'stock':0,'raw':c} for c in data.get('cards',[])]

    def seller_rating(self):
        return self._request('GET',self.FEEDBACKS+'/api/common/v1/rating')

    def reviews(self,is_answered=False,take=100,skip=0,nm_id=None,order='dateDesc'):
        params={'isAnswered':str(bool(is_answered)).lower(),'take':min(max(int(take),1),5000),'skip':max(int(skip),0),'order':order}
        if nm_id:params['nmId']=int(nm_id)
        data=self._request('GET',self.FEEDBACKS+'/api/v1/feedbacks',params=params)
        return data.get('data',{}).get('feedbacks',[])

    def answer_review(self,feedback_id,text):
        text=(text or '').strip()
        if len(text)<2 or len(text)>5000: raise ValueError('Ответ должен содержать от 2 до 5000 символов')
        self._request('POST',self.FEEDBACKS+'/api/v1/feedbacks/answer',json={'id':feedback_id,'text':text})
        return True

    def campaign_groups(self):
        return self._request('GET',self.ADVERT+'/adv/v1/promotion/count')

    def test(self):
        self.ping('content')
        return f'Wildberries подключён. Карточек в тесте: {len(self.products(1))}'

class Ozon:
    BASE='https://api-seller.ozon.ru'
    def __init__(self,client_id,key):
        self.client_id=client_id.strip(); self.key=key.strip()
        self.h={'Client-Id':self.client_id,'Api-Key':self.key,'Content-Type':'application/json'}

    def _post(self,path,payload=None):
        if not self.client_id or not self.key: raise APIError('Не указаны Ozon Client ID / API key')
        r=requests.post(self.BASE+path,headers=self.h,json=payload or {},timeout=45)
        if not r.ok: raise APIError(f'Ozon {r.status_code}: {r.text[:700]}')
        return r.json() if r.content else {}

    def products(self,limit=100):
        data=self._post('/v3/product/info/list',{'filter':{},'limit':min(limit,1000),'last_id':''})
        result=data.get('result',{}); items=result.get('items',[]) if isinstance(result,dict) else []
        return [{'external_id':str(c.get('id') or c.get('product_id') or ''),'sku':str(c.get('offer_id') or ''),'name':c.get('name') or c.get('offer_id') or '','price':0,'stock':0,'raw':c} for c in items]

    def test(self): return f'Ozon подключён. Товаров в тесте: {len(self.products(1))}'
