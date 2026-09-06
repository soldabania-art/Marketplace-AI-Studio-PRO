from PySide6.QtWidgets import *
from .core import init_db,load_settings,save_settings,replace_products,products,save_project,projects
from .services import AIService,calc_profit,export_xlsx
from .connectors import WB,Ozon
import json

STYLE='''QWidget{background:#0b1220;color:#eef2ff;font-family:Segoe UI;font-size:14px}QFrame#side{background:#111827}QPushButton{background:#1f2937;border:none;border-radius:8px;padding:10px;text-align:left}QPushButton:hover{background:#334155}QPushButton#primary{background:#2563eb;text-align:center;font-weight:700}QLineEdit,QTextEdit,QTableWidget,QComboBox,QDoubleSpinBox{background:#111827;border:1px solid #334155;border-radius:7px;padding:7px}QLabel#title{font-size:28px;font-weight:800}QLabel#muted{color:#94a3b8}QGroupBox{border:1px solid #273449;border-radius:10px;margin-top:12px;padding:12px;font-weight:700}'''

class Main(QMainWindow):
    def __init__(self):
        super().__init__(); init_db(); self.cfg=load_settings(); self.photo=''; self.card=None
        self.setWindowTitle('Marketplace AI Studio PRO — Mega Edition 1.1'); self.resize(1500,920)
        root=QWidget(); self.setCentralWidget(root); layout=QHBoxLayout(root); layout.setContentsMargins(0,0,0,0)
        side=QFrame(); side.setObjectName('side'); side.setFixedWidth(240); sl=QVBoxLayout(side)
        brand=QLabel('Marketplace\nAI Studio PRO'); brand.setStyleSheet('font-size:23px;font-weight:900;padding:18px'); sl.addWidget(brand)
        self.stack=QStackedWidget(); layout.addWidget(side); layout.addWidget(self.stack,1)
        pages=[('Dashboard',self.dashboard),('AI Фабрика',self.factory),('Товары',self.products_page),('SEO Аудит',self.seo_page),('Отзывы',self.reviews_page),('Реклама',self.ads_page),('Финансы',self.finance_page),('AI Директор',self.director_page),('Проекты',self.projects_page),('Подключения',self.settings_page)]
        for name,fn in pages:
            b=QPushButton(name); b.clicked.connect(fn); sl.addWidget(b)
        sl.addStretch(); self.setStyleSheet(STYLE); self.dashboard()
    def page(self,title,sub=''):
        w=QWidget(); v=QVBoxLayout(w); v.setContentsMargins(28,24,28,24)
        t=QLabel(title); t.setObjectName('title'); v.addWidget(t); m=QLabel(sub); m.setObjectName('muted'); v.addWidget(m); return w,v
    def showp(self,w): self.stack.addWidget(w); self.stack.setCurrentWidget(w)
    def primary(self,text,fn): b=QPushButton(text); b.setObjectName('primary'); b.clicked.connect(fn); return b
    def dashboard(self):
        w,v=self.page('Dashboard','Центр управления Wildberries + Ozon + AI')
        row=QHBoxLayout()
        for a,b in [('Товаров в базе',str(len(products()))),('Wildberries','готов к синхронизации'),('Ozon','готов к синхронизации'),('AI','Product Factory')]:
            g=QGroupBox(a); q=QVBoxLayout(g); q.addWidget(QLabel(b)); row.addWidget(g)
        v.addLayout(row); r=QHBoxLayout(); r.addWidget(self.primary('Синхронизировать WB',lambda:self.sync('WB'))); r.addWidget(self.primary('Синхронизировать Ozon',lambda:self.sync('Ozon'))); r.addWidget(self.primary('Создать карточку по фото',self.factory)); v.addLayout(r); v.addStretch(); self.showp(w)
    def factory(self):
        w,v=self.page('AI Фабрика','Фото + факты о товаре → SEO, тексты, характеристики и сценарий инфографики')
        self.photo_label=QLabel(self.photo or 'Фото не выбрано'); v.addWidget(self.photo_label); v.addWidget(self.primary('Выбрать фото',self.pick_photo))
        self.fact=QTextEdit(); self.fact.setPlaceholderText('Введите реальные характеристики, материал, размеры, комплектацию, целевую аудиторию...'); self.fact.setFixedHeight(150); v.addWidget(self.fact)
        r=QHBoxLayout(); r.addWidget(self.primary('Сгенерировать полную карточку',self.generate_card)); r.addWidget(self.primary('Экспорт XLSX',self.export_card)); v.addLayout(r)
        self.cardout=QTextEdit(); v.addWidget(self.cardout,1); self.showp(w)
    def pick_photo(self):
        p,_=QFileDialog.getOpenFileName(self,'Фото','','Images (*.jpg *.jpeg *.png *.webp)')
        if p:self.photo=p;self.photo_label.setText(p)
    def generate_card(self):
        try:
            self.card=AIService(self.cfg.get('openai_api_key',''),self.cfg.get('openai_model','gpt-5.6')).product_card(self.photo,self.fact.toPlainText())
            save_project(self.card.get('product_type','AI карточка') if isinstance(self.card,dict) else 'AI карточка',self.photo,self.card)
            self.cardout.setPlainText(json.dumps(self.card,ensure_ascii=False,indent=2))
        except Exception as e: QMessageBox.critical(self,'AI',str(e))
    def export_card(self):
        if not self.card:return QMessageBox.information(self,'Экспорт','Сначала создайте карточку')
        rows=[{'section':k,'value':json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else str(v)} for k,v in self.card.items()]
        p=export_xlsx(rows,'product_card.xlsx'); QMessageBox.information(self,'Экспорт',str(p))
    def products_page(self):
        w,v=self.page('Товары','Единый каталог WB и Ozon'); t=QTableWidget(); data=products(); t.setColumnCount(6); t.setHorizontalHeaderLabels(['Маркетплейс','ID','SKU','Название','Цена','Остаток']); t.setRowCount(len(data))
        for i,r in enumerate(data):
            for j,k in enumerate(['marketplace','external_id','sku','name','price','stock']): t.setItem(i,j,QTableWidgetItem(str(r[k] or '')))
        t.horizontalHeader().setSectionResizeMode(3,QHeaderView.Stretch); v.addWidget(t); self.showp(w)
    def seo_page(self):
        w,v=self.page('SEO Аудит','Контент-анализ карточки и поисковых запросов'); e=QTextEdit(); e.setPlaceholderText('Вставьте название и описание карточки'); out=QTextEdit(); v.addWidget(e)
        def go():
            try:out.setPlainText(AIService(self.cfg.get('openai_api_key',''),self.cfg.get('openai_model','gpt-5.6')).seo_audit(e.toPlainText()))
            except Exception as x:QMessageBox.critical(self,'SEO',str(x))
        v.addWidget(self.primary('Провести AI SEO-аудит',go)); v.addWidget(out); self.showp(w)
    def reviews_page(self):
        w,v=self.page('Отзывы','AI-ответы и подготовка жалобы на проблемный отзыв'); rating=QComboBox(); rating.addItems(['1','2','3','4','5']); txt=QTextEdit(); txt.setPlaceholderText('Текст отзыва'); out=QTextEdit(); v.addWidget(rating); v.addWidget(txt)
        def go():
            try:out.setPlainText(AIService(self.cfg.get('openai_api_key',''),self.cfg.get('openai_model','gpt-5.6')).review_reply(txt.toPlainText(),int(rating.currentText())))
            except Exception as e:QMessageBox.critical(self,'Отзывы',str(e))
        v.addWidget(self.primary('Сгенерировать ответ',go)); v.addWidget(out); v.addWidget(QLabel('Жалоба: готовим аргументированный текст; автоматическая отправка включается только для официально разрешённых API-действий.')); self.showp(w)
    def ads_page(self):
        w,v=self.page('Реклама','Контроль эффективности, ДРР и рекомендации'); g=QGroupBox('Рекламный анализ'); q=QFormLayout(g); spend=QDoubleSpinBox(); spend.setMaximum(1e9); revenue=QDoubleSpinBox(); revenue.setMaximum(1e9); q.addRow('Расход',spend); q.addRow('Продажи',revenue); lbl=QLabel('ДРР: —'); q.addRow(lbl); v.addWidget(g); v.addWidget(self.primary('Рассчитать ДРР',lambda:lbl.setText(f'ДРР: {(spend.value()/revenue.value()*100 if revenue.value() else 0):.2f}%'))); v.addStretch(); self.showp(w)
    def finance_page(self):
        w,v=self.page('Финансы','Юнит-экономика и чистая прибыль'); f=QFormLayout(); vals=[]
        for n in ['Выручка','Комиссия','Логистика','Реклама','Себестоимость']:
            x=QDoubleSpinBox(); x.setMaximum(1e9); x.setDecimals(2); f.addRow(n,x); vals.append(x)
        box=QWidget(); box.setLayout(f); v.addWidget(box); result=QLabel('Чистая прибыль: —'); v.addWidget(result); v.addWidget(self.primary('Рассчитать',lambda:result.setText(f'Чистая прибыль: {calc_profit(*[x.value() for x in vals]):,.2f}'))); v.addStretch(); self.showp(w)
    def director_page(self):
        w,v=self.page('AI Директор','Приоритетный план развития магазина'); inp=QTextEdit(); inp.setPlaceholderText('Добавьте цели, проблемы или сводку показателей'); out=QTextEdit(); v.addWidget(inp)
        def go():
            try:out.setPlainText(AIService(self.cfg.get('openai_api_key',''),self.cfg.get('openai_model','gpt-5.6')).director_plan(inp.toPlainText()))
            except Exception as e:QMessageBox.critical(self,'AI Директор',str(e))
        v.addWidget(self.primary('Сформировать план директора',go)); v.addWidget(out); self.showp(w)
    def projects_page(self):
        w,v=self.page('Проекты','История сгенерированных карточек'); t=QTableWidget(); data=projects(); t.setColumnCount(4); t.setHorizontalHeaderLabels(['ID','Название','Фото','Создан']); t.setRowCount(len(data))
        for i,r in enumerate(data):
            for j,k in enumerate(['id','name','photo','created']):t.setItem(i,j,QTableWidgetItem(str(r[k] or '')))
        t.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch); v.addWidget(t); self.showp(w)
    def settings_page(self):
        w,v=self.page('Подключения','Секретные ключи хранятся в Windows Credential Manager'); f=QFormLayout(); self.fields={}
        for label,key,secret in [('OpenAI API key','openai_api_key',1),('AI модель','openai_model',0),('WB token','wb_token',1),('Ozon Client ID','ozon_client_id',0),('Ozon API key','ozon_api_key',1),('Telegram bot token','telegram_token',1),('Telegram chat ID','telegram_chat_id',0)]:
            e=QLineEdit(self.cfg.get(key,''));
            if secret:e.setEchoMode(QLineEdit.Password)
            f.addRow(label,e); self.fields[key]=e
        box=QWidget(); box.setLayout(f); v.addWidget(box); r=QHBoxLayout(); r.addWidget(self.primary('Сохранить',self.save_cfg)); r.addWidget(self.primary('Проверить WB',lambda:self.test('WB'))); r.addWidget(self.primary('Проверить Ozon',lambda:self.test('Ozon'))); v.addLayout(r); v.addStretch(); self.showp(w)
    def save_cfg(self):
        self.cfg.update({k:e.text().strip() for k,e in self.fields.items()}); save_settings(self.cfg); QMessageBox.information(self,'Настройки','Сохранено безопасно')
    def test(self,mp):
        try:msg=WB(self.cfg.get('wb_token','')).test() if mp=='WB' else Ozon(self.cfg.get('ozon_client_id',''),self.cfg.get('ozon_api_key','')).test(); QMessageBox.information(self,mp,msg)
        except Exception as e:QMessageBox.critical(self,mp,str(e))
    def sync(self,mp):
        try:
            data=WB(self.cfg.get('wb_token','')).products(100) if mp=='WB' else Ozon(self.cfg.get('ozon_client_id',''),self.cfg.get('ozon_api_key','')).products(100); replace_products(mp,data); QMessageBox.information(self,'Синхронизация',f'{mp}: загружено {len(data)} товаров'); self.dashboard()
        except Exception as e:QMessageBox.critical(self,'Синхронизация',str(e))

def run():
    app=QApplication([]); win=Main(); win.show(); app.exec()
