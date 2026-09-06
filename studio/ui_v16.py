from PySide6.QtWidgets import *
from PySide6.QtCore import Qt
from .ui_v15 import Main as BaseMain, load_cogs
from .core import products
from .sku_analytics import sales_by_nm, sku_profitability
from .automation_center import build_alerts, add_task, load_tasks, set_task_status, TelegramNotifier
import json


class Main(BaseMain):
    def __init__(self):
        self.sku_live = []
        self.alerts_live = []
        super().__init__()
        self.setWindowTitle('Marketplace AI Studio PRO — Mega Edition 1.6')

    def dashboard(self):
        w, v = self.page('Dashboard 1.6', 'Прибыль по SKU, риски, AI-задачи, Telegram, продажи, реклама и финансы WB')
        data = products()
        cards = QHBoxLayout()
        metrics = [
            ('Товаров', str(len(data))),
            ('Продажи 30 дн.', self._money(self.live.get('gross'))),
            ('WB к выплате', self._money(self.finance_live.get('payout'))),
            ('Реклама', self._money(self.ads_live.get('spend'))),
            ('Сигналов', str(len(self.alerts_live)) if self.alerts_live else '—'),
        ]
        for title, value in metrics:
            g = QGroupBox(title); q = QVBoxLayout(g); lab = QLabel(value); lab.setStyleSheet('font-size:21px;font-weight:800'); q.addWidget(lab); cards.addWidget(g)
        v.addLayout(cards)
        actions = QHBoxLayout()
        actions.addWidget(self.primary('Обновить WB + прибыль по SKU', self.refresh_wb_business_data))
        actions.addWidget(self.primary('Прибыль по SKU', self.finance_page))
        actions.addWidget(self.primary('Центр рисков и задач', self.tasks_page))
        actions.addWidget(self.primary('Отзывы WB', self.reviews_page))
        v.addLayout(actions)
        self.live_status = QTextEdit(); self.live_status.setReadOnly(True); self.live_status.setMaximumHeight(300)
        self.live_status.setPlaceholderText('Нажмите «Обновить WB + прибыль по SKU».')
        if self.live or self.finance_live or self.ads_live:
            self.live_status.setPlainText(self._live_text_v16())
        v.addWidget(self.live_status)
        if self.alerts_live:
            box = QGroupBox('Главные сигналы'); bv = QVBoxLayout(box)
            for a in self.alerts_live[:5]:
                lab = QLabel(f"[{a.get('priority','').upper()}] {a.get('title','')} — {a.get('details','')}"); lab.setWordWrap(True); bv.addWidget(lab)
            v.addWidget(box)
        v.addStretch(); self.showp(w)

    def refresh_wb_business_data(self):
        try:
            wb = self.wb(); biz = self.business()
            self.live_status.setPlainText('1/8 Карточки WB...'); QApplication.processEvents()
            items = wb.hydrate_products(wb.products(100)); from .core import replace_products; replace_products('WB', items)
            self.live_status.append('2/8 Продажи 30 дней...'); QApplication.processEvents()
            sales = wb.sales(30); summary = wb.sales_summary(sales)
            self.live_status.append('3/8 Заказы...'); QApplication.processEvents()
            orders = wb.orders(30)
            self.live_status.append('4/8 Финансы WB...'); QApplication.processEvents()
            try:
                frows = biz.finance_rows(30); fsum = biz.finance_summary(frows); fsum['possibly_truncated'] = len(frows) >= 100000
            except Exception as e: fsum = {'error': str(e), 'by_nm': {}}
            self.live_status.append('5/8 Реклама...'); QApplication.processEvents()
            try:
                groups = wb.campaign_groups(); ads = biz.ad_stats(groups, 30)
            except Exception as e: groups = {'error': str(e)}; ads = {'error': str(e)}
            self.live_status.append('6/8 Рейтинг...'); QApplication.processEvents()
            try: rating = wb.seller_rating()
            except Exception as e: rating = {'error': str(e)}
            self.live_status.append('7/8 Прибыль по SKU...'); QApplication.processEvents()
            s_by_nm = sales_by_nm(sales)
            sku = sku_profitability(items, fsum.get('by_nm', {}) if isinstance(fsum, dict) else {}, s_by_nm, ads.get('spend',0) if isinstance(ads,dict) else 0, load_cogs())
            self.live_status.append('8/8 Риски и задачи...'); QApplication.processEvents()
            self.live = {**summary, 'orders': len(orders) if isinstance(orders,list) else 0, 'stock_total': sum(float(p.get('stock') or 0) for p in items), 'products': len(items), 'rating': rating, 'campaigns': groups}
            self.finance_live = fsum; self.ads_live = ads; self.sku_live = sku
            self.alerts_live = build_alerts([dict(r) for r in products()], self.live, self.finance_live, self.ads_live, load_cogs())
            self.dashboard()
        except Exception as e:
            QMessageBox.critical(self, 'WB бизнес-данные', str(e))

    def finance_page(self):
        w, v = self.page('Финансы 1.6', 'Прибыль по SKU с количеством продаж, себестоимостью и распределением рекламных расходов')
        top = QHBoxLayout(); top.addWidget(self.primary('Обновить данные', self.refresh_wb_business_data)); top.addStretch(); v.addLayout(top)
        if not self.sku_live:
            hint = QLabel('Сначала обновите WB данные. Таблица прибыли будет рассчитана после загрузки продаж, Finance API и рекламы.'); hint.setWordWrap(True); v.addWidget(hint)
        table = QTableWidget(); table.setColumnCount(12)
        table.setHorizontalHeaderLabels(['nmID','Название','Продано','Возвраты','Выручка','К выплате','Себест./шт','Себест. всего','Реклама*','Прибыль','Маржа %','Остаток'])
        table.setRowCount(len(self.sku_live))
        for i, r in enumerate(self.sku_live):
            vals = [r['nm'],r['name'],r['units'],r['returns'],self._money(r['gross']),self._money(r['payout']),self._money(r['cogs_unit']),self._money(r['cogs_total']),self._money(r['ad_share']),self._money(r['profit']),f"{r['margin']:.2f}",self._num(r['stock'])]
            for j,val in enumerate(vals): table.setItem(i,j,QTableWidgetItem(str(val)))
        table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch); v.addWidget(table,1)
        note = QLabel('*Реклама распределяется по SKU пропорционально выручке, потому что текущая агрегированная статистика кампаний не даёт надёжного рекламного расхода по каждому nmID. Себестоимость считается как введённая стоимость единицы × количество продаж из Statistics API.')
        note.setWordWrap(True); v.addWidget(note)
        self.showp(w)

    def tasks_page(self):
        w, v = self.page('AI Директор — Центр рисков и задач', 'Автоматические сигналы по остаткам, ДРР, возвратам, выплатам и себестоимости')
        row = QHBoxLayout(); row.addWidget(self.primary('Пересчитать сигналы', self.rebuild_alerts)); row.addWidget(self.primary('Создать задачи из сигналов', self.create_tasks_from_alerts)); row.addWidget(self.primary('Отправить сводку в Telegram', self.send_alerts_telegram)); row.addStretch(); v.addLayout(row)
        alerts = QTableWidget(); alerts.setColumnCount(3); alerts.setHorizontalHeaderLabels(['Приоритет','Сигнал','Что делать']); alerts.setRowCount(len(self.alerts_live))
        for i,a in enumerate(self.alerts_live):
            alerts.setItem(i,0,QTableWidgetItem(a.get('priority',''))); alerts.setItem(i,1,QTableWidgetItem(a.get('title',''))); alerts.setItem(i,2,QTableWidgetItem(a.get('details','')))
        alerts.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch); v.addWidget(alerts,1)
        tasks = load_tasks(); tt = QTableWidget(); tt.setColumnCount(5); tt.setHorizontalHeaderLabels(['ID','Статус','Приоритет','Задача','Источник']); tt.setRowCount(len(tasks))
        for i,t in enumerate(tasks):
            vals=[t.get('id'),t.get('status'),t.get('priority'),t.get('title'),t.get('source')]
            for j,val in enumerate(vals): tt.setItem(i,j,QTableWidgetItem(str(val or '')))
        tt.horizontalHeader().setSectionResizeMode(3,QHeaderView.Stretch); v.addWidget(tt,1)
        btns=QHBoxLayout()
        def set_selected(status):
            rows=tt.selectionModel().selectedRows()
            if not rows:return QMessageBox.information(self,'Задачи','Выберите задачу')
            task_id=tt.item(rows[0].row(),0).text(); set_task_status(task_id,status); self.tasks_page()
        btns.addWidget(self.primary('В работу',lambda:set_selected('in_progress'))); btns.addWidget(self.primary('Выполнено',lambda:set_selected('done'))); v.addLayout(btns)
        self.showp(w)

    def rebuild_alerts(self):
        self.alerts_live = build_alerts([dict(r) for r in products()], self.live, self.finance_live, self.ads_live, load_cogs())
        self.tasks_page()

    def create_tasks_from_alerts(self):
        existing = {(t.get('title'), t.get('status')) for t in load_tasks()}
        count=0
        for a in self.alerts_live:
            if (a.get('title'), 'open') not in existing and (a.get('title'), 'in_progress') not in existing:
                add_task(a.get('title','Сигнал'), a.get('priority','medium'), a.get('details',''), 'Auto Monitor'); count += 1
        QMessageBox.information(self,'AI Директор',f'Создано задач: {count}'); self.tasks_page()

    def send_alerts_telegram(self):
        if not self.alerts_live:return QMessageBox.information(self,'Telegram','Нет сигналов для отправки')
        text='Marketplace AI Studio PRO — сигналы\n\n'+'\n'.join([f"• [{a.get('priority','').upper()}] {a.get('title')}: {a.get('details')}" for a in self.alerts_live[:15]])
        try:
            TelegramNotifier(self.cfg.get('telegram_token',''), self.cfg.get('telegram_chat_id','')).send(text)
            QMessageBox.information(self,'Telegram','Сводка отправлена')
        except Exception as e: QMessageBox.critical(self,'Telegram',str(e))

    def _live_text_v16(self):
        base = self._live_text_v15()
        total_profit = sum(float(x.get('profit') or 0) for x in self.sku_live)
        loss = sum(1 for x in self.sku_live if float(x.get('profit') or 0) < 0)
        return base + f"\nОценка прибыли по SKU: {self._money(total_profit)}\nУбыточных SKU: {loss}\nСигналов AI Директора: {len(self.alerts_live)}"


def run():
    app = QApplication([])
    win = Main(); win.show(); app.exec()
