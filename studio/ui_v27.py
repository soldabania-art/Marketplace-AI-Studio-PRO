import json, logging
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import *
from .ui_v26 import Main as BaseMain
from .core import replace_products, products
from .workers import Worker
from .ui_v15 import load_cogs
from .sku_analytics import sales_by_nm, sku_profitability
from .automation_center import build_alerts
from . import __version__

logger = logging.getLogger('ui.functional')


class Main(BaseMain):
    """2.7: functional UI, background network work and interactive product rows."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'Marketplace AI Studio PRO — Mega Edition {__version__} FUNCTIONAL UI')
        for label in self.findChildren(QLabel):
            if label.text().startswith('MEGA EDITION'):
                label.setText(f'MEGA EDITION {__version__}')
        self.statusBar().showMessage('Готово к работе')

    def _invoke(self, fn, label='Действие'):
        try:
            self.statusBar().showMessage(label)
            result = fn()
            QTimer.singleShot(1500, lambda: self.statusBar().showMessage('Готово'))
            return result
        except Exception as e:
            logger.exception('UI action failed: %s', label)
            self.statusBar().showMessage('Ошибка: ' + str(e))
            QMessageBox.critical(self, label, str(e))

    def primary(self, text, fn):
        b = QPushButton(text); b.setObjectName('primary'); b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda _=False, f=fn, t=text: self._invoke(f, t))
        return b

    def danger(self, text, fn):
        b = QPushButton(text); b.setObjectName('danger'); b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda _=False, f=fn, t=text: self._invoke(f, t))
        return b

    def dashboard(self):
        super().dashboard()
        w = self.stack.currentWidget(); layout = w.layout()
        box = QGroupBox('FUNCTIONAL CONTROL 2.7')
        v = QVBoxLayout(box)
        info = QLabel('Основные кнопки подключены к обработчикам. Долгие запросы WB/Ozon выполняются в фоне, повторный запуск блокируется до завершения, ошибки пишутся в лог.')
        info.setWordWrap(True); v.addWidget(info)
        row = QHBoxLayout()
        row.addWidget(self.primary('Обновить весь WB', self.refresh_wb_business_data))
        row.addWidget(self.primary('Обновить рекламу WB', self.refresh_ads_only))
        row.addWidget(self.primary('Загрузить отзывы WB', self.reviews_page))
        row.addWidget(self.primary('Синхронизировать Ozon', self.sync_all_ozon))
        row.addWidget(self.primary('AI Фабрика', self.factory))
        v.addLayout(row)
        self.functional_status = QLabel('Нажмите действие — статус появится здесь и в нижней строке окна.')
        self.functional_status.setWordWrap(True); v.addWidget(self.functional_status)
        layout.addWidget(box)

    def _start_worker(self, title, job, done, progress_widget=None):
        if self.active_worker:
            QMessageBox.information(self, title, 'Другая задача уже выполняется. Дождитесь завершения или отмените её.')
            return False
        worker = Worker(job); self.active_worker = worker
        def on_progress(p, text):
            self.statusBar().showMessage(text)
            if hasattr(self, 'functional_status'): self.functional_status.setText(text)
            if progress_widget is not None: progress_widget.setValue(p)
        worker.signals.progress.connect(on_progress)
        worker.signals.result.connect(done)
        worker.signals.error.connect(lambda e: self._worker_error(title, e))
        worker.signals.finished.connect(self.worker_finished)
        self.pool.start(worker)
        return True

    def _worker_error(self, title, error):
        logger.error('%s: %s', title, error)
        self.statusBar().showMessage('Ошибка: ' + str(error))
        if hasattr(self, 'functional_status'): self.functional_status.setText('Ошибка: ' + str(error))
        QMessageBox.critical(self, title, str(error))

    def sync(self, mp):
        if mp == 'WB': return self.sync_wb_full()
        if mp == 'Ozon': return self.sync_all_ozon()

    def sync_wb_full(self):
        def job(progress, is_cancelled):
            progress(5, 'WB: загружаю весь каталог...')
            items = self.wb().products_all(10000)
            if is_cancelled(): return {'cancelled': True}
            progress(55, f'WB: карточек {len(items)}, загружаю цены и остатки...')
            items = self.wb().hydrate_products(items)
            progress(95, 'WB: сохраняю каталог локально...')
            return {'items': items}
        return self._start_worker('Синхронизация WB', job, self._wb_sync_ready)

    def _wb_sync_ready(self, result):
        if result.get('cancelled'): return
        items = result.get('items') or []
        replace_products('WB', items)
        self.statusBar().showMessage(f'WB: обновлено {len(items)} товаров')
        if hasattr(self, 'functional_status'): self.functional_status.setText(f'WB синхронизирован: {len(items)} товаров')
        QMessageBox.information(self, 'Wildberries', f'Каталог обновлён: {len(items)} товаров.')
        self.products_page()

    def products_page(self):
        w, v = self.page('Товары 2.7', 'Каталог WB/Ozon. Двойной клик по строке открывает карточку товара и доступные действия.')
        top = QHBoxLayout()
        top.addWidget(self.primary('Обновить WB', self.sync_wb_full))
        top.addWidget(self.primary('Обновить Ozon', self.sync_all_ozon))
        top.addStretch(); v.addLayout(top)
        data = [dict(r) for r in products()]
        table = QTableWidget(); table.setColumnCount(6)
        table.setHorizontalHeaderLabels(['MP','ID','SKU','Название','Цена','Остаток']); table.setRowCount(len(data))
        table.setSelectionBehavior(QAbstractItemView.SelectRows); table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers); table.setCursor(Qt.PointingHandCursor)
        for i, row in enumerate(data):
            vals=[row.get('marketplace',''),row.get('external_id',''),row.get('sku',''),row.get('name',''),self._money(row.get('price')),self._num(row.get('stock'))]
            for j,val in enumerate(vals): table.setItem(i,j,QTableWidgetItem(str(val or '')))
        table.horizontalHeader().setSectionResizeMode(3,QHeaderView.Stretch)
        table.cellDoubleClicked.connect(lambda row, _col: self._product_actions(data[row]) if 0 <= row < len(data) else None)
        v.addWidget(table,1)
        hint=QLabel('Двойной клик по товару → открыть действия. Для WB можно сразу перейти в AI Фабрику с выбранным nmID.')
        hint.setWordWrap(True); v.addWidget(hint); self.showp(w)

    def _product_actions(self, product):
        mp=str(product.get('marketplace') or '')
        nm=str(product.get('external_id') or '')
        name=str(product.get('name') or product.get('sku') or nm)
        box=QMessageBox(self); box.setWindowTitle('Товар'); box.setText(name); box.setInformativeText(f'{mp} · ID {nm}\nВыберите действие с товаром.')
        ai_btn=box.addButton('Открыть в AI Фабрике', QMessageBox.ActionRole)
        refresh_btn=box.addButton('Обновить каталог', QMessageBox.ActionRole)
        box.addButton('Закрыть', QMessageBox.RejectRole); box.exec()
        clicked=box.clickedButton()
        if clicked is ai_btn:
            self.factory()
            for attr in ('factory_nm','product_nm','nm_input','nm_id_input'):
                widget=getattr(self,attr,None)
                if widget is not None and hasattr(widget,'setText'):
                    widget.setText(nm); break
        elif clicked is refresh_btn:
            self.sync_wb_full() if mp == 'WB' else self.sync_all_ozon()

    def refresh_ads_only(self):
        def job(progress, is_cancelled):
            progress(15, 'WB реклама: загружаю список кампаний...')
            wb = self.wb(); groups = wb.campaign_groups()
            if is_cancelled(): return {'cancelled': True}
            progress(55, 'WB реклама: загружаю статистику с контролем лимита API...')
            ads = self.business().ad_stats(groups, 30)
            progress(100, 'Рекламная статистика обновлена')
            return {'ads': ads}
        return self._start_worker('Реклама WB', job, self._ads_ready)

    def _ads_ready(self, result):
        if result.get('cancelled'): return
        self.ads_live = result.get('ads') or {}
        if hasattr(self, 'functional_status'):
            self.functional_status.setText(f"Реклама WB: расход {self.ads_live.get('spend',0):,.2f} ₽, ДРР {float(self.ads_live.get('drr') or 0):.2f}%")
        self.ads_page()

    def load_reviews(self):
        answered = self.rev_filter.currentIndex() == 1 if hasattr(self, 'rev_filter') else False
        def job(progress, is_cancelled):
            progress(20, 'WB отзывы: загрузка...')
            rows = self.wb().reviews(is_answered=answered, take=100)
            progress(100, f'Отзывы загружены: {len(rows)}')
            return rows
        return self._start_worker('Отзывы WB', job, self._reviews_ready)

    def _reviews_ready(self, rows):
        self.current_reviews = rows or []
        if not hasattr(self, 'rev_table'):
            self.reviews_page(); return
        self.rev_table.setRowCount(len(self.current_reviews))
        for i, r in enumerate(self.current_reviews):
            product = r.get('productDetails') or {}; user = r.get('userName') or (r.get('wbUserDetails') or {}).get('name') or ''
            vals = [r.get('id',''), r.get('productValuation',''), product.get('productName') or product.get('nmId') or '', user, r.get('text',''), r.get('createdDate','')]
            for j, val in enumerate(vals): self.rev_table.setItem(i, j, QTableWidgetItem(str(val or '')))
        self.review_status.setText(f'Загружено отзывов: {len(self.current_reviews)}')

    def refresh_wb_business_data(self):
        def job(progress, is_cancelled):
            wb = self.wb(); biz = self.business()
            progress(5, 'WB 1/7: карточки...'); items = wb.products_all(10000)
            progress(15, 'WB 2/7: цены и остатки...'); items = wb.hydrate_products(items)
            progress(30, 'WB 3/7: продажи...'); sales = wb.sales(30); summary = wb.sales_summary(sales)
            progress(42, 'WB 4/7: заказы...'); orders = wb.orders(30)
            progress(55, 'WB 5/7: финансы...')
            try:
                frows = biz.finance_rows(30); fsum = biz.finance_summary(frows); fsum['possibly_truncated'] = len(frows) >= 100000
            except Exception as e: fsum = {'error': str(e), 'by_nm': {}}
            progress(70, 'WB 6/7: реклама...')
            try:
                groups = wb.campaign_groups(); ads = biz.ad_stats(groups, 30)
            except Exception as e: groups = {'error': str(e)}; ads = {'error': str(e)}
            progress(82, 'WB 7/7: рейтинг и прибыль по SKU...')
            try: rating = wb.seller_rating()
            except Exception as e: rating = {'error': str(e)}
            s_by_nm = sales_by_nm(sales)
            sku = sku_profitability(items, fsum.get('by_nm', {}) if isinstance(fsum, dict) else {}, s_by_nm, ads.get('spend',0) if isinstance(ads,dict) else 0, load_cogs())
            live = {**summary, 'orders': len(orders) if isinstance(orders,list) else 0, 'stock_total': sum(float(p.get('stock') or 0) for p in items), 'products': len(items), 'rating': rating, 'campaigns': groups}
            progress(100, 'WB: полный цикл данных готов')
            return {'items': items, 'live': live, 'finance': fsum, 'ads': ads, 'sku': sku}
        return self._start_worker('WB бизнес-данные', job, self._business_ready)

    def _business_ready(self, result):
        items = result.get('items') or []; replace_products('WB', items)
        self.live = result.get('live') or {}; self.finance_live = result.get('finance') or {}; self.ads_live = result.get('ads') or {}; self.sku_live = result.get('sku') or []
        self.alerts_live = build_alerts([dict(r) for r in products()], self.live, self.finance_live, self.ads_live, load_cogs())
        self.dashboard()

    def test(self, mp):
        def job(progress, is_cancelled):
            progress(30, f'Проверяю {mp}...')
            msg = self.wb().test() if mp == 'WB' else self.ozon().test()
            progress(100, msg); return msg
        return self._start_worker(f'Проверка {mp}', job, lambda msg: QMessageBox.information(self, mp, msg))


def run():
    app = QApplication([]); win = Main(); win.show(); app.exec()
