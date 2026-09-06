from PySide6.QtCore import Qt
from PySide6.QtWidgets import *

from .ui_v35 import Main as BaseMain
from .ui_v15 import load_cogs, save_cogs
from . import __version__


class Main(BaseMain):
    """3.6: SKU Profit Center based on normalized sales, finance and exact ad attribution."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'Marketplace AI Studio PRO — Mega Edition {__version__} PROFIT CENTER')

    def dashboard(self):
        super().dashboard(); w=self.stack.currentWidget(); layout=w.layout()
        box=QGroupBox('PROFIT CENTER 3.6')
        v=QVBoxLayout(box)
        rows=list(getattr(self,'sku_live',[]) or [])
        loss=sum(1 for r in rows if float(r.get('profit') or 0)<0)
        profit=sum(float(r.get('profit') or 0) for r in rows)
        revenue=sum(float(r.get('gross') or 0) for r in rows)
        label=QLabel(f'Товаров рассчитано: {len(rows)} · убыточных: {loss} · оборот: {self._money(revenue)} · расчётная прибыль: {self._money(profit)}')
        label.setWordWrap(True); v.addWidget(label)
        row=QHBoxLayout(); row.addWidget(self.primary('Открыть Profit Center',self.profit_center)); row.addWidget(self.primary('Обновить WB данные',self.refresh_wb_business_data)); row.addStretch(); v.addLayout(row)
        note=QLabel('Profit Center использует продажи по nmID, выплаты Finance API, сохранённую себестоимость и точный рекламный расход SKU из Promotion fullstats. Если точной рекламной детализации SKU нет, аналитический слой явно использует резервное распределение.')
        note.setWordWrap(True); v.addWidget(note); layout.addWidget(box)

    def profit_center(self):
        w,v=self.page('Profit Center 3.6','Экономика каждого SKU. По умолчанию самые убыточные товары находятся сверху.')
        top=QHBoxLayout(); top.addWidget(self.primary('Обновить WB бизнес-данные',self.refresh_wb_business_data)); top.addWidget(self.primary('Сохранить себестоимость',self._save_profit_cogs)); top.addStretch(); v.addLayout(top)
        rows=[dict(x) for x in (getattr(self,'sku_live',[]) or [])]
        rows.sort(key=lambda x:float(x.get('profit') or 0))
        total_gross=sum(float(x.get('gross') or 0) for x in rows); total_payout=sum(float(x.get('payout') or 0) for x in rows); total_ads=sum(float(x.get('ad_share') or 0) for x in rows); total_cogs=sum(float(x.get('cogs_total') or 0) for x in rows); total_profit=sum(float(x.get('profit') or 0) for x in rows)
        summary=QGroupBox('Сводка по SKU'); form=QFormLayout(summary)
        form.addRow('Оборот:',QLabel(self._money(total_gross))); form.addRow('Выплата WB:',QLabel(self._money(total_payout))); form.addRow('Реклама:',QLabel(self._money(total_ads))); form.addRow('Себестоимость:',QLabel(self._money(total_cogs))); form.addRow('Прибыль:',QLabel(self._money(total_profit)))
        margin=(total_profit/total_gross*100.0) if total_gross else 0.0; form.addRow('Маржа:',QLabel(f'{margin:.2f}%')); v.addWidget(summary)
        self.profit_rows=rows; self.profit_table=QTableWidget(); t=self.profit_table
        headers=['nmID','Название','Продано','Возвраты','Оборот','Выплата WB','Реклама','ДРР','Себест./шт','Себестоимость','Прибыль','Маржа','Остаток','Статус']
        t.setColumnCount(len(headers)); t.setHorizontalHeaderLabels(headers); t.setRowCount(len(rows)); t.setSelectionBehavior(QAbstractItemView.SelectRows); t.setSortingEnabled(False)
        cogs=load_cogs()
        for i,r in enumerate(rows):
            gross=float(r.get('gross') or 0); ad=float(r.get('ad_share') or 0); profit=float(r.get('profit') or 0); drr=(ad/gross*100.0) if gross>0 else 0.0
            status='УБЫТОК' if profit<0 else 'низкая маржа' if gross>0 and float(r.get('margin') or 0)<10 else 'OK'
            vals=[r.get('nm',''),r.get('name',''),int(r.get('units') or 0),int(r.get('returns') or 0),self._money(gross),self._money(r.get('payout')),self._money(ad),f'{drr:.2f}%',None,self._money(r.get('cogs_total')),self._money(profit),f"{float(r.get('margin') or 0):.2f}%",self._num(r.get('stock')),status]
            for j,val in enumerate(vals):
                if j==8: continue
                item=QTableWidgetItem(str(val)); item.setFlags(item.flags() & ~Qt.ItemIsEditable); t.setItem(i,j,item)
            cost=QDoubleSpinBox(); cost.setRange(0,1e9); cost.setDecimals(2); cost.setValue(float(cogs.get(str(r.get('nm')),r.get('cogs_unit') or 0))); t.setCellWidget(i,8,cost)
        t.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch); t.setSortingEnabled(True); v.addWidget(t,1)
        foot=QLabel('Формула SKU: прибыль = выплата WB − себестоимость проданных единиц − рекламный расход SKU. Выплата WB уже является нормализованным финансовым показателем из текущего Finance слоя; отдельные удержания повторно не вычитаются, чтобы не задвоить расходы.')
        foot.setWordWrap(True); v.addWidget(foot); self.showp(w)

    def _save_profit_cogs(self):
        if not hasattr(self,'profit_table') or not hasattr(self,'profit_rows'): return
        data=load_cogs()
        for i,r in enumerate(self.profit_rows):
            widget=self.profit_table.cellWidget(i,8)
            if widget: data[str(r.get('nm'))]=float(widget.value())
        save_cogs(data)
        QMessageBox.information(self,'Profit Center','Себестоимость сохранена. Нажмите «Обновить WB бизнес-данные», чтобы пересчитать прибыль по всем SKU.')

    def finance_page(self):
        return self.profit_center()


def run():
    app=QApplication([]); win=Main(); win.show(); app.exec()
