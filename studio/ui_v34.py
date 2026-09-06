import logging
from PySide6.QtWidgets import QApplication, QMessageBox

from .ui_v33 import Main as BaseMain
from .ai_errors import friendly_ai_error
from .core import replace_products, products
from .ui_v15 import load_cogs
from .sku_analytics import sales_by_nm, sku_profitability
from .automation_center import build_alerts
from . import __version__

logger=logging.getLogger('ui.stability')


class Main(BaseMain):
    """3.4 stability audit: friendly errors, cancellation-safe WB jobs and complete status refresh."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'Marketplace AI Studio PRO — Mega Edition {__version__} STABILITY AUDIT')

    def _worker_error(self,title,error):
        logger.error('%s: %s',title,error)
        text=friendly_ai_error(error) if ('AI' in title or 'OpenAI' in str(error) or 'quota' in str(error).lower()) else str(error)
        self.statusBar().showMessage('Ошибка: '+text)
        if hasattr(self,'functional_status'): self.functional_status.setText('Ошибка: '+text)
        QMessageBox.critical(self,title,text)

    def _openai_credit_ready(self,info):
        self.openai_credit_info=info or {}
        text=self._credit_text()
        if hasattr(self,'credit_label'): self.credit_label.setText(text)
        if hasattr(self,'functional_status'): self.functional_status.setText(text)
        self.statusBar().showMessage(text,8000)

    def sync_wb_full(self):
        def job(progress,is_cancelled):
            progress(5,'WB: загружаю весь каталог...')
            items=self.wb().products_all(10000)
            if is_cancelled(): return {'cancelled':True,'items':[]}
            progress(55,f'WB: карточек {len(items)}, цены и остатки...')
            items=self.wb().hydrate_products(items)
            if is_cancelled(): return {'cancelled':True,'items':[]}
            progress(95,'WB: сохраняю каталог...')
            return {'cancelled':False,'items':items}
        return self._start_worker('Синхронизация WB',job,self._wb_sync_ready)

    def _wb_sync_ready(self,result):
        if (result or {}).get('cancelled'):
            self.statusBar().showMessage('Синхронизация WB остановлена')
            return
        items=(result or {}).get('items') or []
        replace_products('WB',items)
        if hasattr(self,'functional_status'): self.functional_status.setText(f'WB каталог обновлён: {len(items)} товаров')
        QMessageBox.information(self,'Wildberries',f'Каталог обновлён: {len(items)} товаров.')
        self.products_page()

    def refresh_ads_only(self):
        def job(progress,is_cancelled):
            progress(15,'WB реклама: список кампаний...')
            groups=self.wb().campaign_groups()
            if is_cancelled(): return {'cancelled':True}
            progress(55,'WB реклама: статистика...')
            ads=self.business().ad_stats(groups,30)
            if is_cancelled(): return {'cancelled':True}
            progress(100,'Реклама обновлена')
            return {'cancelled':False,'ads':ads}
        return self._start_worker('Реклама WB',job,self._ads_ready_v34)

    def _ads_ready_v34(self,result):
        if (result or {}).get('cancelled'): return
        self.ads_live=(result or {}).get('ads') or {}
        self.ads_page()

    def load_reviews(self):
        answered=self.rev_filter.currentIndex()==1 if hasattr(self,'rev_filter') else False
        def job(progress,is_cancelled):
            progress(20,'WB отзывы: загрузка...')
            rows=self.wb().reviews(is_answered=answered,take=100)
            if is_cancelled(): return {'cancelled':True,'rows':[]}
            progress(100,f'Отзывы: {len(rows)}')
            return {'cancelled':False,'rows':rows}
        return self._start_worker('Отзывы WB',job,self._reviews_ready_v34)

    def _reviews_ready_v34(self,result):
        if (result or {}).get('cancelled'): return
        return super()._reviews_ready((result or {}).get('rows') or [])

    def refresh_wb_business_data(self):
        def job(progress,is_cancelled):
            wb=self.wb(); biz=self.business()
            progress(5,'WB: карточки...'); items=wb.products_all(10000)
            if is_cancelled(): return {'cancelled':True}
            items=wb.hydrate_products(items)
            if is_cancelled(): return {'cancelled':True}
            progress(30,'WB: продажи...'); sales=wb.sales(30)
            if is_cancelled(): return {'cancelled':True}
            summary=wb.sales_summary(sales); orders=wb.orders(30)
            if is_cancelled(): return {'cancelled':True}
            try:frows=biz.finance_rows(30); fsum=biz.finance_summary(frows)
            except Exception as e:fsum={'error':str(e),'by_nm':{}}
            if is_cancelled(): return {'cancelled':True}
            try:groups=wb.campaign_groups(); ads=biz.ad_stats(groups,30)
            except Exception as e:groups={'error':str(e)}; ads={'error':str(e)}
            if is_cancelled(): return {'cancelled':True}
            try:rating=wb.seller_rating()
            except Exception as e:rating={'error':str(e)}
            sku=sku_profitability(items,fsum.get('by_nm',{}),sales_by_nm(sales),ads.get('spend',0) if isinstance(ads,dict) else 0,load_cogs())
            live={**summary,'orders':len(orders) if isinstance(orders,list) else 0,'stock_total':sum(float(p.get('stock') or 0) for p in items),'products':len(items),'rating':rating,'campaigns':groups}
            progress(100,'WB: готово')
            return {'cancelled':False,'items':items,'live':live,'finance':fsum,'ads':ads,'sku':sku}
        return self._start_worker('WB бизнес-данные',job,self._business_ready_v34)

    def _business_ready_v34(self,result):
        if (result or {}).get('cancelled'):
            self.statusBar().showMessage('Обновление WB остановлено')
            return
        replace_products('WB',(result or {}).get('items') or [])
        self.live=(result or {}).get('live') or {}
        self.finance_live=(result or {}).get('finance') or {}
        self.ads_live=(result or {}).get('ads') or {}
        self.sku_live=(result or {}).get('sku') or []
        self.alerts_live=build_alerts([dict(r) for r in products()],self.live,self.finance_live,self.ads_live,load_cogs())
        self.dashboard()


def run():
    app=QApplication([]); win=Main(); win.show(); app.exec()
