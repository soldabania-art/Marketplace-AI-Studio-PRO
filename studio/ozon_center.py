class OzonCatalogCenter:
    """Read-only Ozon catalog helper built on the already configured Seller API connector.

    Write endpoints are intentionally not guessed here. The center paginates the existing
    product-info endpoint and stops safely when the API does not return a continuation id.
    """
    def __init__(self,ozon):
        self.ozon=ozon

    @staticmethod
    def _normalize(c):
        return {
            'external_id':str(c.get('id') or c.get('product_id') or ''),
            'sku':str(c.get('offer_id') or ''),
            'name':c.get('name') or c.get('offer_id') or '',
            'price':0,'stock':0,'raw':c,
        }

    def products_all(self,max_products=10000,progress=None):
        out=[]; last_id=''; page=0
        while len(out)<max(1,int(max_products)):
            page+=1
            data=self.ozon._post('/v3/product/info/list',{'filter':{},'limit':1000,'last_id':last_id})
            result=data.get('result') or {}
            items=result.get('items') or [] if isinstance(result,dict) else []
            out.extend(self._normalize(x) for x in items)
            if progress:progress(min(99,int(len(out)/max(1,max_products)*100)),f'Ozon: загружено {len(out)} товаров')
            if not items or len(items)<1000:break
            nxt=(result.get('last_id') if isinstance(result,dict) else None) or data.get('last_id')
            if not nxt or str(nxt)==str(last_id):break
            last_id=str(nxt)
        if progress:progress(100,f'Ozon: готово {len(out[:max_products])} товаров')
        return out[:max_products]

    def diagnose(self):
        rows=self.products_all(1)
        return {'ok':True,'products_tested':len(rows),'mode':'read_only'}
