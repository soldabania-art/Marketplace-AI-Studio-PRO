import requests

class WB:
    CONTENT='https://content-api.wildberries.ru'
    def __init__(self,token): self.token=token.strip(); self.h={'Authorization':self.token,'Content-Type':'application/json'}
    def products(self,limit=100):
        r=requests.post(self.CONTENT+'/content/v2/get/cards/list',headers=self.h,json={'settings':{'cursor':{'limit':min(limit,100)},'filter':{'withPhoto':-1}}},timeout=45)
        if not r.ok: raise RuntimeError(f'WB {r.status_code}: {r.text[:500]}')
        return [{'external_id':str(c.get('nmID','')),'sku':c.get('vendorCode',''),'name':c.get('title') or c.get('subjectName') or c.get('vendorCode',''),'price':0,'stock':0} for c in r.json().get('cards',[])]
    def test(self): return f'Wildberries подключён. Карточек в тесте: {len(self.products(1))}'

class Ozon:
    BASE='https://api-seller.ozon.ru'
    def __init__(self,client_id,key): self.h={'Client-Id':client_id.strip(),'Api-Key':key.strip(),'Content-Type':'application/json'}
    def products(self,limit=100):
        r=requests.post(self.BASE+'/v3/product/info/list',headers=self.h,json={'filter':{},'limit':min(limit,1000),'last_id':''},timeout=45)
        if not r.ok: raise RuntimeError(f'Ozon {r.status_code}: {r.text[:500]}')
        result=r.json().get('result',{}); items=result.get('items',[]) if isinstance(result,dict) else []
        return [{'external_id':str(c.get('id') or c.get('product_id') or ''),'sku':str(c.get('offer_id') or ''),'name':c.get('name') or c.get('offer_id') or '','price':0,'stock':0} for c in items]
    def test(self): return f'Ozon подключён. Товаров в тесте: {len(self.products(1))}'
