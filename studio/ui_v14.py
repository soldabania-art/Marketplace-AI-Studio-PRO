from PySide6.QtWidgets import *
from .ui_v13 import Main as BaseMain
from .core import products, replace_products
import json


class Main(BaseMain):
    def __init__(self):
        self.live = {}
        super().__init__()
        self.setWindowTitle('Marketplace AI Studio PRO — Mega Edition 1.4')

    def dashboard(self):
        w, v = self.page('Dashboard 1.4', 'Живые данные WB: товары, цены, остатки, продажи, заказы, отзывы и реклама')
        data = products()
        cards = QHBoxLayout()
        metrics = [
            ('Товаров', str(len(data))),
            ('Продажи 30 дн.', self._money(self.live.get('gross'))),
            ('Остатки WB', self._num(self.live.get('stock_total'))),
            ('Возвраты', self._num(self.live.get('returns'))),
        ]
        for title, value in metrics:
            box = QGroupBox(title)
            q = QVBoxLayout(box)
            label = QLabel(value)
            label.setStyleSheet('font-size:24px;font-weight:800')
            q.addWidget(label)
            cards.addWidget(box)
        v.addLayout(cards)

        actions = QHBoxLayout()
        actions.addWidget(self.primary('Обновить все данные WB', self.refresh_wb_business_data))
        actions.addWidget(self.primary('Синхронизировать Ozon', lambda: self.sync('Ozon')))
        actions.addWidget(self.primary('Отзывы WB', self.reviews_page))
        actions.addWidget(self.primary('Реклама WB', self.ads_page))
        v.addLayout(actions)

        self.live_status = QTextEdit()
        self.live_status.setReadOnly(True)
        self.live_status.setMaximumHeight(240)
        self.live_status.setPlaceholderText('Нажмите «Обновить все данные WB».')
        if self.live:
            self.live_status.setPlainText(self._live_text())
        v.addWidget(self.live_status)

        note = QGroupBox('Важно')
        nv = QVBoxLayout(note)
        info = QLabel('Продажи из Statistics API — оперативные данные, а не бухгалтерский отчёт. Для точной чистой прибыли следующим этапом подключается детализация финансовых отчётов и комиссии.')
        info.setWordWrap(True)
        nv.addWidget(info)
        v.addWidget(note)
        v.addStretch()
        self.showp(w)

    def refresh_wb_business_data(self):
        try:
            wb = self.wb()
            self.live_status.setPlainText('1/5 Загружаю карточки товаров...')
            QApplication.processEvents()
            items = wb.products(100)

            self.live_status.append('2/5 Загружаю актуальные цены и остатки...')
            QApplication.processEvents()
            items = wb.hydrate_products(items)
            replace_products('WB', items)

            self.live_status.append('3/5 Загружаю продажи за 30 дней...')
            QApplication.processEvents()
            sales = wb.sales(30)
            summary = wb.sales_summary(sales)

            self.live_status.append('4/5 Загружаю заказы за 30 дней...')
            QApplication.processEvents()
            orders = wb.orders(30)

            self.live_status.append('5/5 Загружаю рейтинг и рекламные кампании...')
            QApplication.processEvents()
            try:
                rating = wb.seller_rating()
            except Exception as e:
                rating = {'error': str(e)}
            try:
                campaigns = wb.campaign_groups()
            except Exception as e:
                campaigns = {'error': str(e)}

            self.live = {
                **summary,
                'orders': len(orders) if isinstance(orders, list) else 0,
                'stock_total': sum(float(p.get('stock') or 0) for p in items),
                'products': len(items),
                'rating': rating,
                'campaigns': campaigns,
            }
            self.dashboard()
        except Exception as e:
            QMessageBox.critical(self, 'Обновление WB', str(e))

    def products_page(self):
        w, v = self.page('Товары 1.4', 'Каталог с актуальными WB ценами и остатками')
        top = QHBoxLayout()
        top.addWidget(self.primary('Обновить WB: карточки + цены + остатки', self.sync_wb_full))
        top.addWidget(self.primary('Обновить Ozon', lambda: self.sync('Ozon')))
        top.addStretch()
        v.addLayout(top)

        data = products()
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(['MP', 'ID', 'SKU', 'Название', 'Цена', 'Остаток'])
        table.setRowCount(len(data))
        for i, row in enumerate(data):
            keys = ['marketplace', 'external_id', 'sku', 'name', 'price', 'stock']
            for j, key in enumerate(keys):
                val = row[key]
                if key == 'price' and val not in (None, ''):
                    try:
                        val = f'{float(val):,.2f}'
                    except Exception:
                        pass
                table.setItem(i, j, QTableWidgetItem(str(val or '')))
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        v.addWidget(table)
        self.showp(w)

    def sync_wb_full(self):
        try:
            wb = self.wb()
            items = wb.hydrate_products(wb.products(100))
            replace_products('WB', items)
            QMessageBox.information(self, 'WB', f'Обновлено товаров: {len(items)}')
            self.products_page()
        except Exception as e:
            QMessageBox.critical(self, 'WB', str(e))

    def finance_page(self):
        w, v = self.page('Финансы 1.4', 'Оперативная экономика магазина + ручная себестоимость')
        live = QGroupBox('Данные WB за 30 дней')
        form = QFormLayout(live)
        form.addRow('Продажи:', QLabel(self._money(self.live.get('gross'))))
        form.addRow('Предварительно к выплате:', QLabel(self._money(self.live.get('payout'))))
        form.addRow('Проданных единиц:', QLabel(self._num(self.live.get('units'))))
        form.addRow('Возвратов:', QLabel(self._num(self.live.get('returns'))))
        form.addRow('Заказов:', QLabel(self._num(self.live.get('orders'))))
        form.addRow('Остатков на складах:', QLabel(self._num(self.live.get('stock_total'))))
        v.addWidget(live)
        v.addWidget(self.primary('Обновить финансовую сводку WB', self.refresh_wb_business_data))

        manual = QGroupBox('Расчёт чистой прибыли')
        mf = QFormLayout(manual)
        self.fin_inputs = {}
        defaults = {
            'revenue': float(self.live.get('gross') or 0),
            'commission': 0,
            'logistics': 0,
            'ads': 0,
            'cogs': 0,
        }
        labels = [('revenue','Выручка'),('commission','Комиссия'),('logistics','Логистика'),('ads','Реклама'),('cogs','Себестоимость')]
        for key, label in labels:
            x = QDoubleSpinBox()
            x.setMaximum(1e12)
            x.setDecimals(2)
            x.setValue(defaults[key])
            self.fin_inputs[key] = x
            mf.addRow(label, x)
        v.addWidget(manual)
        self.fin_result = QLabel('Чистая прибыль: —')
        self.fin_result.setStyleSheet('font-size:24px;font-weight:800')
        v.addWidget(self.fin_result)
        v.addWidget(self.primary('Рассчитать чистую прибыль', self.calc_live_profit))
        v.addStretch()
        self.showp(w)

    def calc_live_profit(self):
        f = self.fin_inputs
        profit = f['revenue'].value() - f['commission'].value() - f['logistics'].value() - f['ads'].value() - f['cogs'].value()
        margin = profit / f['revenue'].value() * 100 if f['revenue'].value() else 0
        self.fin_result.setText(f'Чистая прибыль: {profit:,.2f} ₽   |   Маржа: {margin:.2f}%')

    def director_page(self):
        w, v = self.page('AI Директор 1.4', 'AI анализирует реальные оперативные данные WB и формирует приоритетный план')
        out = QTextEdit()
        extra = QTextEdit()
        extra.setPlaceholderText('Дополнительная цель владельца бизнеса, например: увеличить прибыль на 20%, снизить ДРР, распродать остатки...')
        extra.setMaximumHeight(120)
        v.addWidget(extra)

        def go():
            try:
                if not self.live:
                    return QMessageBox.information(self, 'AI Директор', 'Сначала обновите данные WB на Dashboard.')
                payload = {
                    'live_wb_30d': self.live,
                    'products_sample': [dict(r) for r in products()[:50]],
                    'owner_goal': extra.toPlainText(),
                }
                out.setPlainText(self.ai().director_plan(json.dumps(payload, ensure_ascii=False, default=str)))
            except Exception as e:
                QMessageBox.critical(self, 'AI Директор', str(e))

        v.addWidget(self.primary('Проанализировать магазин и дать план', go))
        v.addWidget(out)
        self.showp(w)

    def _live_text(self):
        return '\n'.join([
            f"Товаров WB: {self._num(self.live.get('products'))}",
            f"Продажи 30 дней: {self._money(self.live.get('gross'))}",
            f"Предварительно к выплате: {self._money(self.live.get('payout'))}",
            f"Продано единиц: {self._num(self.live.get('units'))}",
            f"Возвратов: {self._num(self.live.get('returns'))}",
            f"Заказов: {self._num(self.live.get('orders'))}",
            f"Остаток на складах WB: {self._num(self.live.get('stock_total'))}",
            'Рейтинг: ' + json.dumps(self.live.get('rating', {}), ensure_ascii=False),
        ])

    @staticmethod
    def _money(value):
        if value is None:
            return '—'
        try:
            return f'{float(value):,.2f} ₽'
        except Exception:
            return str(value)

    @staticmethod
    def _num(value):
        if value is None:
            return '—'
        try:
            f = float(value)
            return f'{f:,.0f}' if f.is_integer() else f'{f:,.2f}'
        except Exception:
            return str(value)


def run():
    app = QApplication([])
    win = Main()
    win.show()
    app.exec()
