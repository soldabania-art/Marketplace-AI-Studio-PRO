from PySide6.QtWidgets import *
from .ui_v14 import Main as BaseMain
from .core import products, replace_products, DATA
from .wb_business import WBBusiness
import json


COGS_FILE = DATA / 'cogs_by_nm.json'


def load_cogs():
    try:
        data = json.loads(COGS_FILE.read_text(encoding='utf-8')) if COGS_FILE.exists() else {}
        return {str(k): float(v or 0) for k, v in data.items()}
    except Exception:
        return {}


def save_cogs(data):
    COGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


class Main(BaseMain):
    def __init__(self):
        self.finance_live = {}
        self.ads_live = {}
        super().__init__()
        self.setWindowTitle('Marketplace AI Studio PRO — Mega Edition 1.5')

    def business(self):
        return WBBusiness(self.wb())

    def dashboard(self):
        w, v = self.page('Dashboard 1.5', 'WB бизнес-панель: продажи, выплаты, расходы, реклама, ДРР, остатки и прибыль')
        data = products()
        cards = QHBoxLayout()
        metrics = [
            ('Товаров', str(len(data))),
            ('Продажи 30 дн.', self._money(self.live.get('gross'))),
            ('WB к выплате', self._money(self.finance_live.get('payout'))),
            ('Реклама 30 дн.', self._money(self.ads_live.get('spend'))),
            ('ДРР рекламы', f"{float(self.ads_live.get('drr') or 0):.2f}%" if self.ads_live else '—'),
        ]
        for title, value in metrics:
            box = QGroupBox(title); q = QVBoxLayout(box)
            label = QLabel(value); label.setStyleSheet('font-size:22px;font-weight:800'); q.addWidget(label)
            cards.addWidget(box)
        v.addLayout(cards)

        actions = QHBoxLayout()
        actions.addWidget(self.primary('Обновить WB бизнес-данные', self.refresh_wb_business_data))
        actions.addWidget(self.primary('Финансы по SKU', self.finance_page))
        actions.addWidget(self.primary('Реклама WB', self.ads_page))
        actions.addWidget(self.primary('Отзывы WB', self.reviews_page))
        v.addLayout(actions)

        self.live_status = QTextEdit(); self.live_status.setReadOnly(True); self.live_status.setMaximumHeight(290)
        self.live_status.setPlaceholderText('Нажмите «Обновить WB бизнес-данные».')
        if self.live or self.finance_live or self.ads_live:
            self.live_status.setPlainText(self._live_text_v15())
        v.addWidget(self.live_status)

        note = QGroupBox('Точность данных')
        nv = QVBoxLayout(note)
        text = QLabel('Оперативные продажи берутся из Statistics API. Финансовый блок использует новый Finance API v1. Рекламные расходы и продажи — Promotion API v3. Себестоимость хранится локально по nmID и не отправляется в маркетплейс.')
        text.setWordWrap(True); nv.addWidget(text); v.addWidget(note)
        v.addStretch(); self.showp(w)

    def refresh_wb_business_data(self):
        try:
            wb = self.wb(); biz = self.business()
            self.live_status.setPlainText('1/7 Карточки WB...'); QApplication.processEvents()
            items = wb.products(100)
            self.live_status.append('2/7 Цены и остатки...'); QApplication.processEvents()
            items = wb.hydrate_products(items); replace_products('WB', items)
            self.live_status.append('3/7 Продажи 30 дней...'); QApplication.processEvents()
            sales = wb.sales(30); summary = wb.sales_summary(sales)
            self.live_status.append('4/7 Заказы 30 дней...'); QApplication.processEvents()
            orders = wb.orders(30)
            self.live_status.append('5/7 Финансовый отчёт WB Finance API v1...'); QApplication.processEvents()
            try:
                frows = biz.finance_rows(30)
                fsum = biz.finance_summary(frows)
                fsum['possibly_truncated'] = len(frows) >= 100000
            except Exception as e:
                fsum = {'error': str(e)}
            self.live_status.append('6/7 Рекламная статистика WB...'); QApplication.processEvents()
            try:
                groups = wb.campaign_groups(); ads = biz.ad_stats(groups, 30)
            except Exception as e:
                groups = {'error': str(e)}; ads = {'error': str(e)}
            self.live_status.append('7/7 Рейтинг продавца...'); QApplication.processEvents()
            try: rating = wb.seller_rating()
            except Exception as e: rating = {'error': str(e)}

            self.live = {
                **summary,
                'orders': len(orders) if isinstance(orders, list) else 0,
                'stock_total': sum(float(p.get('stock') or 0) for p in items),
                'products': len(items), 'rating': rating, 'campaigns': groups,
            }
            self.finance_live = fsum
            self.ads_live = ads
            self.dashboard()
        except Exception as e:
            QMessageBox.critical(self, 'WB бизнес-данные', str(e))

    def finance_page(self):
        w, v = self.page('Финансы 1.5', 'Finance API v1 + расходы + себестоимость по nmID + прибыль по товарам')
        top = QHBoxLayout(); top.addWidget(self.primary('Обновить все WB данные', self.refresh_wb_business_data)); top.addStretch(); v.addLayout(top)

        f = self.finance_live if isinstance(self.finance_live, dict) else {}
        a = self.ads_live if isinstance(self.ads_live, dict) else {}
        cogs = load_cogs()
        total_cogs = 0.0
        by_nm = f.get('by_nm', {}) if isinstance(f.get('by_nm'), dict) else {}
        for nm, b in by_nm.items():
            # Себестоимость задаётся на единицу; если нет точного количества в finance rows,
            # считаем её только в таблице как введённое значение и не умножаем автоматически.
            total_cogs += 0.0

        totals = QGroupBox('Финансовая сводка WB')
        tf = QFormLayout(totals)
        tf.addRow('Начисления / продажи:', QLabel(self._money(f.get('gross'))))
        tf.addRow('К выплате продавцу:', QLabel(self._money(f.get('payout'))))
        tf.addRow('Логистика:', QLabel(self._money(f.get('logistics'))))
        tf.addRow('Хранение:', QLabel(self._money(f.get('storage'))))
        tf.addRow('Приёмка:', QLabel(self._money(f.get('acceptance'))))
        tf.addRow('Штрафы:', QLabel(self._money(f.get('penalties'))))
        tf.addRow('Оценка прочих удержаний/комиссии:', QLabel(self._money(f.get('commission_estimate'))))
        tf.addRow('Рекламные расходы:', QLabel(self._money(a.get('spend'))))
        tf.addRow('Рекламные продажи:', QLabel(self._money(a.get('sales'))))
        tf.addRow('ДРР:', QLabel(f"{float(a.get('drr') or 0):.2f}%"))
        if f.get('possibly_truncated'):
            warn = QLabel('В отчёте получено 100 000 строк: возможно, есть следующая страница. Из-за лимита Finance API она не запрашивается автоматически.'); warn.setWordWrap(True); tf.addRow('Внимание:', warn)
        if f.get('error'):
            err = QLabel(str(f.get('error'))); err.setWordWrap(True); tf.addRow('Finance API:', err)
        v.addWidget(totals)

        hint = QLabel('Себестоимость: укажите закупочную стоимость единицы для нужных nmID и нажмите «Сохранить себестоимость».')
        hint.setWordWrap(True); v.addWidget(hint)
        table = QTableWidget(); table.setColumnCount(10)
        table.setHorizontalHeaderLabels(['nmID','Название','Продажи','К выплате','Логистика','Хранение','Приёмка','Штрафы','Себестоимость/шт','Опер. прибыль*'])
        prod_map = {str(r['external_id']): dict(r) for r in products() if str(r['marketplace']) == 'WB'}
        nms = list(by_nm.keys())
        table.setRowCount(len(nms))
        for i, nm in enumerate(nms):
            b = by_nm.get(nm, {}); name = (prod_map.get(nm) or {}).get('name', '')
            values = [nm, name, self._money(b.get('gross')), self._money(b.get('payout')), self._money(b.get('logistics')), self._money(b.get('storage')), self._money(b.get('acceptance')), self._money(b.get('penalties'))]
            for j, val in enumerate(values):
                item = QTableWidgetItem(str(val));
                if j != 8: item.setFlags(item.flags() & ~Qt.ItemIsEditable) if False else None
                table.setItem(i, j, item)
            cost = QDoubleSpinBox(); cost.setMaximum(1e9); cost.setDecimals(2); cost.setValue(float(cogs.get(nm, 0))); table.setCellWidget(i, 8, cost)
            # Without exact item quantity in the normalized finance data, operational profit
            # here excludes COGS. This is labeled clearly and avoids inventing quantities.
            op_profit = float(b.get('payout') or 0) - float(a.get('spend') or 0) / max(len(nms), 1)
            table.setItem(i, 9, QTableWidgetItem(self._money(op_profit)))
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch); v.addWidget(table, 1)

        def save_costs():
            data = load_cogs()
            for i, nm in enumerate(nms):
                widget = table.cellWidget(i, 8)
                if widget: data[str(nm)] = widget.value()
            save_cogs(data); QMessageBox.information(self, 'Себестоимость', 'Себестоимость сохранена локально.')
        v.addWidget(self.primary('Сохранить себестоимость', save_costs))
        foot = QLabel('*Операционная прибыль в таблице: выплата WB минус равномерно распределённые рекламные расходы. Себестоимость пока не вычитается автоматически без подтверждённого количества проданных единиц по nmID.')
        foot.setWordWrap(True); v.addWidget(foot)
        self.showp(w)

    def ads_page(self):
        w, v = self.page('Реклама WB 1.5', 'Promotion API v3: расход, продажи, заказы, показы, клики, CTR и ДРР')
        top = QHBoxLayout(); top.addWidget(self.primary('Обновить рекламную статистику', self.refresh_ads_only)); top.addStretch(); v.addLayout(top)
        a = self.ads_live if isinstance(self.ads_live, dict) else {}
        cards = QHBoxLayout()
        for title, value in [
            ('Расход', self._money(a.get('spend'))), ('Продажи', self._money(a.get('sales'))),
            ('Заказы', self._num(a.get('orders'))), ('ДРР', f"{float(a.get('drr') or 0):.2f}%" if a else '—')
        ]:
            g = QGroupBox(title); q = QVBoxLayout(g); lab = QLabel(value); lab.setStyleSheet('font-size:22px;font-weight:800'); q.addWidget(lab); cards.addWidget(g)
        v.addLayout(cards)
        rows = a.get('rows', []) if isinstance(a.get('rows'), list) else []
        table = QTableWidget(); table.setColumnCount(8); table.setHorizontalHeaderLabels(['Campaign ID','Расход','Продажи','Заказы','Показы','Клики','CTR','CPC']); table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            vals = [r.get('advertId',''), self._money(r.get('sum')), self._money(r.get('sum_price')), r.get('orders',0), r.get('views',0), r.get('clicks',0), r.get('ctr',0), r.get('cpc',0)]
            for j, val in enumerate(vals): table.setItem(i,j,QTableWidgetItem(str(val)))
        v.addWidget(table, 1)
        if a.get('error'):
            err = QLabel(str(a.get('error'))); err.setWordWrap(True); v.addWidget(err)
        self.showp(w)

    def refresh_ads_only(self):
        try:
            wb = self.wb(); biz = self.business(); groups = wb.campaign_groups(); self.ads_live = biz.ad_stats(groups, 30); self.ads_page()
        except Exception as e:
            QMessageBox.critical(self, 'Реклама WB', str(e))

    def director_page(self):
        w, v = self.page('AI Директор 1.5', 'AI анализирует продажи, выплаты, расходы, рекламу, ДРР, остатки и товары')
        goal = QTextEdit(); goal.setMaximumHeight(110); goal.setPlaceholderText('Цель владельца: увеличить прибыль, снизить ДРР, распродать остатки и т.п.'); out = QTextEdit(); v.addWidget(goal)
        def go():
            try:
                if not self.live:
                    return QMessageBox.information(self, 'AI Директор', 'Сначала обновите WB бизнес-данные на Dashboard.')
                payload = {
                    'operations_30d': self.live,
                    'finance_report_30d': self.finance_live,
                    'ads_30d': {k:v for k,v in self.ads_live.items() if k != 'rows'} if isinstance(self.ads_live, dict) else {},
                    'products': [dict(r) for r in products()[:100]],
                    'owner_goal': goal.toPlainText(),
                }
                out.setPlainText(self.ai().director_plan(json.dumps(payload, ensure_ascii=False, default=str)))
            except Exception as e:
                QMessageBox.critical(self, 'AI Директор', str(e))
        v.addWidget(self.primary('Провести полный AI-анализ магазина', go)); v.addWidget(out); self.showp(w)

    def _live_text_v15(self):
        f = self.finance_live if isinstance(self.finance_live, dict) else {}; a = self.ads_live if isinstance(self.ads_live, dict) else {}
        lines = [
            f"Товаров WB: {self._num(self.live.get('products'))}",
            f"Оперативные продажи 30 дней: {self._money(self.live.get('gross'))}",
            f"Finance API — к выплате: {self._money(f.get('payout'))}",
            f"Логистика: {self._money(f.get('logistics'))}",
            f"Хранение: {self._money(f.get('storage'))}",
            f"Приёмка: {self._money(f.get('acceptance'))}",
            f"Штрафы: {self._money(f.get('penalties'))}",
            f"Реклама — расход: {self._money(a.get('spend'))}",
            f"Реклама — продажи: {self._money(a.get('sales'))}",
            f"ДРР: {float(a.get('drr') or 0):.2f}%",
            f"Остаток на складах: {self._num(self.live.get('stock_total'))}",
        ]
        if f.get('error'): lines.append('Finance API: ' + str(f.get('error')))
        if a.get('error'): lines.append('Promotion API: ' + str(a.get('error')))
        return '\n'.join(lines)


def run():
    app = QApplication([])
    win = Main(); win.show(); app.exec()
