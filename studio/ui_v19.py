from PySide6.QtWidgets import *
from .ui_v18 import Main as BaseMain
from .core import products, save_settings
from .autopilot import init_autopilot_db, queue_action, actions, set_action_status, save_card_version, card_versions, propose_store_maintenance
import json


class Main(BaseMain):
    def __init__(self):
        init_autopilot_db()
        super().__init__()
        self.setWindowTitle('Marketplace AI Studio PRO — Mega Edition 1.9 AUTOPILOT')

    def dashboard(self):
        w,v=self.page('AUTOPILOT 1.9','AI управляет циклом: анализ → генерация карточек и визуала → очередь действий → контроль → измерение результата')
        mode=self.cfg.get('autopilot_mode','approve')
        cards=QHBoxLayout()
        for title,value in [('Режим',mode.upper()),('Товаров',str(len(products()))),('AI действий',str(len(actions()))),('Сигналов',str(len(self.alerts_live))),('SEO слабых',str(sum(1 for x in self.seo_rows if x.get('score',100)<70)))]:
            g=QGroupBox(title); q=QVBoxLayout(g); lab=QLabel(value); lab.setStyleSheet('font-size:21px;font-weight:800'); q.addWidget(lab); cards.addWidget(g)
        v.addLayout(cards)
        row=QHBoxLayout(); row.addWidget(self.primary('Запустить полный цикл AI',self.run_autopilot_cycle)); row.addWidget(self.primary('AI Фабрика карточек',self.factory)); row.addWidget(self.primary('Очередь действий',self.autopilot_page)); row.addWidget(self.primary('Версии карточек',self.versions_page)); v.addLayout(row)
        safety=QGroupBox('Уровень автономности'); sv=QHBoxLayout(safety); self.mode_combo=QComboBox(); self.mode_combo.addItems(['observe','approve','autopilot']); self.mode_combo.setCurrentText(mode); self.mode_combo.currentTextChanged.connect(self.save_mode); sv.addWidget(self.mode_combo); info=QLabel('observe — только анализ; approve — изменения через подтверждение; autopilot — безопасные AI-действия автоматически. Запись в маркетплейс не выполняется, пока конкретный write API не реализован и не протестирован.'); info.setWordWrap(True); sv.addWidget(info,1); v.addWidget(safety)
        self.auto_status=QTextEdit(); self.auto_status.setReadOnly(True); self.auto_status.setPlaceholderText('Здесь будет журнал решений AI Директора.'); v.addWidget(self.auto_status,1); self.showp(w)

    def save_mode(self,mode):
        self.cfg['autopilot_mode']=mode; save_settings(self.cfg)

    def run_autopilot_cycle(self):
        self.run_seo_scan(silent=True)
        proposals=propose_store_maintenance([dict(r) for r in products()],self.seo_rows,self.alerts_live)
        created=0
        for p in proposals:
            queue_action(p['marketplace'],p['entity_id'],p['action_type'],p['payload'],p['reason'],p['risk']); created+=1
        self.auto_status.setPlainText(f'Цикл завершён. Найдено и поставлено в очередь действий: {created}.\nAI может автоматически анализировать и генерировать контент. Публикация/цены/ставки остаются заблокированы до подключения и проверки точных write API.')
        self.autopilot_page()

    def full_pack_ready(self,result):
        super().full_pack_ready(result)
        if result.get('cancelled'): return
        card=result.get('card') or {}; images=result.get('images') or []
        entity=str(card.get('nmID') or card.get('vendorCode') or card.get('product_type') or 'new')
        ver=save_card_version('DRAFT',entity,card,images,'generated')
        queue_action('DRAFT',entity,'review_card',{'version':ver,'card':card,'images':images},'AI создал полный комплект карточки','medium')
        self.factory_status.setText(f'Карточка готова и сохранена как версия {ver}. Тексты + визуал находятся в очереди контроля.')

    def autopilot_page(self):
        w,v=self.page('Очередь AUTOPILOT','Единый журнал решений и действий AI. Изменения магазина с риском требуют отдельного write-коннектора и контроля.')
        top=QHBoxLayout(); top.addWidget(self.primary('Новый AI цикл',self.run_autopilot_cycle)); top.addStretch(); v.addLayout(top)
        rows=actions(); t=QTableWidget(); t.setColumnCount(7); t.setHorizontalHeaderLabels(['ID','Статус','Риск','MP','Объект','Действие','Причина']); t.setRowCount(len(rows)); t.setSelectionBehavior(QAbstractItemView.SelectRows)
        for i,r in enumerate(rows):
            vals=[r['id'],r['status'],r['risk'],r['marketplace'],r['entity_id'],r['action_type'],r['reason']]
            for j,x in enumerate(vals): t.setItem(i,j,QTableWidgetItem(str(x or '')))
        t.horizontalHeader().setSectionResizeMode(6,QHeaderView.Stretch); v.addWidget(t,1)
        buttons=QHBoxLayout()
        def mark(status):
            sel=t.selectionModel().selectedRows()
            if not sel:return
            aid=t.item(sel[0].row(),0).text(); set_action_status(aid,status); self.autopilot_page()
        buttons.addWidget(self.primary('Одобрить',lambda:mark('approved'))); buttons.addWidget(self.primary('Отклонить',lambda:mark('rejected'))); buttons.addWidget(self.primary('Выполнено',lambda:mark('done'))); v.addLayout(buttons); self.showp(w)

    def versions_page(self):
        w,v=self.page('Версии AI-карточек','История сгенерированных карточек и визуальных комплектов — основа для сравнения до/после и rollback')
        rows=card_versions(limit=200); t=QTableWidget(); t.setColumnCount(7); t.setHorizontalHeaderLabels(['ID','Дата','MP','Объект','Версия','Статус','Изображения']); t.setRowCount(len(rows)); t.setSelectionBehavior(QAbstractItemView.SelectRows)
        for i,r in enumerate(rows):
            try:n=len(json.loads(r.get('images_json') or '[]'))
            except:n=0
            vals=[r['id'],r['created'],r['marketplace'],r['entity_id'],r['version'],r['status'],n]
            for j,x in enumerate(vals):t.setItem(i,j,QTableWidgetItem(str(x or '')))
        t.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch); v.addWidget(t,1)
        detail=QTextEdit(); detail.setReadOnly(True); v.addWidget(detail,1)
        def show():
            sel=t.selectionModel().selectedRows()
            if not sel:return
            rid=int(t.item(sel[0].row(),0).text()); r=next((x for x in rows if x['id']==rid),None)
            if r:detail.setPlainText(json.dumps({'card':json.loads(r['card_json'] or '{}'),'images':json.loads(r['images_json'] or '[]'),'metrics':json.loads(r['metrics_json'] or '{}')},ensure_ascii=False,indent=2))
        t.itemSelectionChanged.connect(show); self.showp(w)


def run():
    app=QApplication([]); win=Main(); win.show(); app.exec()
