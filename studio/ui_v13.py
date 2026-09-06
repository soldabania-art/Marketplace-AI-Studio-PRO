from PySide6.QtWidgets import *
from PySide6.QtCore import Qt
from .core import init_db, load_settings, save_settings, replace_products, products, save_project, projects, generated_dir
from .services import AIService, calc_profit, export_xlsx
from .connectors import WB, Ozon
import json, os

STYLE='''
QWidget{background:#0b1220;color:#eef2ff;font-family:Segoe UI;font-size:14px}
QFrame#side{background:#111827}
QPushButton{background:#1f2937;border:none;border-radius:8px;padding:10px;text-align:left}
QPushButton:hover{background:#334155}
QPushButton#primary{background:#2563eb;text-align:center;font-weight:700}
QPushButton#danger{background:#b91c1c;text-align:center;font-weight:700}
QLineEdit,QTextEdit,QPlainTextEdit,QTableWidget,QComboBox,QDoubleSpinBox,QSpinBox{background:#111827;border:1px solid #334155;border-radius:7px;padding:7px}
QLabel#title{font-size:28px;font-weight:800}
QLabel#muted{color:#94a3b8}
QLabel#good{color:#4ade80;font-weight:700}
QLabel#warn{color:#facc15;font-weight:700}
QGroupBox{border:1px solid #273449;border-radius:10px;margin-top:12px;padding:12px;font-weight:700}
QHeaderView::section{background:#1f2937;color:#e5e7eb;padding:7px;border:none}
'''

class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        init_db(); self.cfg=load_settings(); self.photo=''; self.card=None
        self.current_reviews=[]
        self.setWindowTitle('Marketplace AI Studio PRO — Mega Edition 1.3')
        self.resize(1540,940)
        root=QWidget(); self.setCentralWidget(root)
        layout=QHBoxLayout(root); layout.setContentsMargins(0,0,0,0)
        side=QFrame(); side.setObjectName('side'); side.setFixedWidth(250); sl=QVBoxLayout(side)
        brand=QLabel('Marketplace\nAI Studio PRO'); brand.setStyleSheet('font-size:23px;font-weight:900;padding:18px'); sl.addWidget(brand)
        ver=QLabel('MEGA EDITION 1.3'); ver.setStyleSheet('color:#60a5fa;padding:0 18px 14px 18px;font-weight:700'); sl.addWidget(ver)
        self.stack=QStackedWidget(); layout.addWidget(side); layout.addWidget(self.stack,1)
        pages=[('Dashboard',self.dashboard),('AI Фабрика',self.factory),('Товары',self.products_page),('SEO Аудит',self.seo_page),('Отзывы WB',self.reviews_page),('Реклама WB',self.ads_page),('Финансы',self.finance_page),('AI Директор',self.director_page),('Проекты',self.projects_page),('Подключения',self.settings_page)]
        for name,fn in pages:
            b=QPushButton(name); b.clicked.connect(fn); sl.addWidget(b)
        sl.addStretch(); self.setStyleSheet(STYLE); self.dashboard()

    def page(self,title,sub=''):
        w=QWidget(); v=QVBoxLayout(w); v.setContentsMargins(28,24,28,24)
        t=QLabel(title); t.setObjectName('title'); v.addWidget(t)
        m=QLabel(sub); m.setObjectName('muted'); m.setWordWrap(True); v.addWidget(m)
        return w,v
    def showp(self,w): self.stack.addWidget(w); self.stack.setCurrentWidget(w)
    def primary(self,text,fn):
        b=QPushButton(text); b.setObjectName('primary'); b.clicked.connect(fn); return b
    def danger(self,text,fn):
        b=QPushButton(text); b.setObjectName('danger'); b.clicked.connect(fn); return b
    def ai(self): return AIService(self.cfg.get('openai_api_key',''),self.cfg.get('openai_model','gpt-5.6-sol'))
    def wb(self): return WB(self.cfg.get('wb_token',''))
    def ozon(self): return Ozon(self.cfg.get('ozon_client_id',''),self.cfg.get('ozon_api_key',''))

    def dashboard(self):
        w,v=self.page('Dashboard','Живой центр управления Wildberries + Ozon + AI')
        data=products(); row=QHBoxLayout()
        for a,b in [('Товаров в базе',str(len(data))),('AI','Card + Image Factory'),('Отзывы WB','Live API'),('Реклама WB','Live API')]:
            g=QGroupBox(a); q=QVBoxLayout(g); q.addWidget(QLabel(b)); row.addWidget(g)
        v.addLayout(row)
        actions=QHBoxLayout(); actions.addWidget(self.primary('Синхронизировать WB',lambda:self.sync('WB'))); actions.addWidget(self.primary('Синхронизировать Ozon',lambda:self.sync('Ozon'))); actions.addWidget(self.primary('Открыть отзывы WB',self.reviews_page)); actions.addWidget(self.primary('Открыть рекламу WB',self.ads_page)); v.addLayout(actions)
        self.health=QTextEdit(); self.health.setReadOnly(True); self.health.setMaximumHeight(180); self.health.setPlaceholderText('Нажмите «Проверить сервисы WB» для диагностики API.'); v.addWidget(self.health)
        v.addWidget(self.primary('Проверить сервисы WB',self.check_wb_services))
        v.addStretch(); self.showp(w)

    def check_wb_services(self):
        try:
            wb=self.wb(); lines=[]
            for key,label in [('content','Контент'),('feedbacks','Отзывы'),('promotion','Реклама'),('common','Общий API')]:
                try: wb.ping(key); lines.append(f'✓ {label}: доступен')
                except Exception as e: lines.append(f'✗ {label}: {e}')
            try:
                r=wb.seller_rating(); lines.append('Рейтинг продавца: '+json.dumps(r,ensure_ascii=False))
            except Exception as e: lines.append('Рейтинг: '+str(e))
            self.health.setPlainText('\n'.join(lines))
        except Exception as e: QMessageBox.critical(self,'WB диагностика',str(e))

    def factory(self):
        w,v=self.page('AI Фабрика','Фото + факты → SEO-карточка → реальные изображения инфографики')
        self.photo_label=QLabel(self.photo or 'Фото не выбрано'); v.addWidget(self.photo_label)
        v.addWidget(self.primary('Выбрать фото товара',self.pick_photo))
        self.fact=QTextEdit(); self.fact.setPlaceholderText('Реальные характеристики, материал, размеры, комплектация, особенности, ЦА, ограничения...'); self.fact.setFixedHeight(130); v.addWidget(self.fact)
        opts=QHBoxLayout(); opts.addWidget(QLabel('Слайдов инфографики:')); self.slide_count=QSpinBox(); self.slide_count.setRange(1,10); self.slide_count.setValue(6); opts.addWidget(self.slide_count); opts.addStretch(); v.addLayout(opts)
        r=QHBoxLayout(); r.addWidget(self.primary('1. Создать полную карточку',self.generate_card)); r.addWidget(self.primary('2. Создать изображения',self.generate_images)); r.addWidget(self.primary('Экспорт XLSX',self.export_card)); r.addWidget(self.primary('Папка изображений',self.open_generated)); v.addLayout(r)
        self.factory_status=QLabel('Готово к работе'); self.factory_status.setObjectName('muted'); v.addWidget(self.factory_status)
        self.cardout=QTextEdit(); v.addWidget(self.cardout,1); self.showp(w)
    def pick_photo(self):
        p,_=QFileDialog.getOpenFileName(self,'Фото','','Images (*.jpg *.jpeg *.png *.webp)')
        if p:self.photo=p;self.photo_label.setText(p)
    def generate_card(self):
        try:
            self.factory_status.setText('AI анализирует товар...')
            self.card=self.ai().product_card(self.photo,self.fact.toPlainText())
            save_project(self.card.get('product_type','AI карточка') if isinstance(self.card,dict) else 'AI карточка',self.photo,self.card)
            self.cardout.setPlainText(json.dumps(self.card,ensure_ascii=False,indent=2)); self.factory_status.setText('Карточка готова')
        except Exception as e:self.factory_status.setText('Ошибка'); QMessageBox.critical(self,'AI',str(e))
    def generate_images(self):
        if not self.card:return QMessageBox.information(self,'Инфографика','Сначала создайте карточку.')
        try:
            self.factory_status.setText('Генерация изображений...')
            name=self.card.get('product_type','product') if isinstance(self.card,dict) else 'product'
            paths=self.ai().generate_infographics(self.card,name,self.slide_count.value())
            self.factory_status.setText(f'Готово изображений: {len(paths)}')
            QMessageBox.information(self,'Инфографика','\n'.join(str(p) for p in paths))
        except Exception as e:QMessageBox.critical(self,'Инфографика',str(e))
    def open_generated(self):
        p=str(generated_dir())
        if os.name=='nt': os.startfile(p)
        else: QMessageBox.information(self,'Папка',p)
    def export_card(self):
        if not self.card:return QMessageBox.information(self,'Экспорт','Сначала создайте карточку')
        rows=[{'section':k,'value':json.dumps(val,ensure_ascii=False) if isinstance(val,(list,dict)) else str(val)} for k,val in self.card.items()]
        QMessageBox.information(self,'Экспорт',str(export_xlsx(rows,'product_card.xlsx')))

    def products_page(self):
        w,v=self.page('Товары','Единый каталог Wildberries и Ozon')
        controls=QHBoxLayout(); controls.addWidget(self.primary('Обновить WB',lambda:self.sync('WB'))); controls.addWidget(self.primary('Обновить Ozon',lambda:self.sync('Ozon'))); controls.addStretch(); v.addLayout(controls)
        data=products(); t=QTableWidget(); t.setColumnCount(6); t.setHorizontalHeaderLabels(['MP','ID','SKU','Название','Цена','Остаток']); t.setRowCount(len(data))
        for i,r in enumerate(data):
            for j,k in enumerate(['marketplace','external_id','sku','name','price','stock']):t.setItem(i,j,QTableWidgetItem(str(r[k] or '')))
        t.horizontalHeader().setSectionResizeMode(3,QHeaderView.Stretch); v.addWidget(t); self.showp(w)

    def seo_page(self):
        w,v=self.page('SEO Аудит','Проверка карточки на поисковую релевантность и качество контента')
        e=QTextEdit(); e.setPlaceholderText('Название + описание + ключи карточки'); out=QTextEdit(); v.addWidget(e)
        def go():
            try:out.setPlainText(self.ai().seo_audit(e.toPlainText()))
            except Exception as x:QMessageBox.critical(self,'SEO',str(x))
        v.addWidget(self.primary('Провести AI SEO-аудит',go)); v.addWidget(out); self.showp(w)

    def reviews_page(self):
        w,v=self.page('Отзывы Wildberries','Загрузка реальных отзывов → AI-ответ → отправка ответа через WB API')
        top=QHBoxLayout(); self.rev_filter=QComboBox(); self.rev_filter.addItems(['Без ответа','С ответом']); top.addWidget(self.rev_filter); top.addWidget(self.primary('Загрузить отзывы',self.load_reviews)); top.addStretch(); v.addLayout(top)
        self.rev_table=QTableWidget(); self.rev_table.setColumnCount(6); self.rev_table.setHorizontalHeaderLabels(['ID','Оценка','Товар','Покупатель','Текст','Дата']); self.rev_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.rev_table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.rev_table.horizontalHeader().setSectionResizeMode(4,QHeaderView.Stretch); self.rev_table.itemSelectionChanged.connect(self.review_selected); v.addWidget(self.rev_table,2)
        split=QHBoxLayout(); left=QVBoxLayout(); left.addWidget(QLabel('Выбранный отзыв')); self.review_text=QTextEdit(); self.review_text.setReadOnly(True); left.addWidget(self.review_text); right=QVBoxLayout(); right.addWidget(QLabel('Ответ продавца')); self.review_answer=QTextEdit(); right.addWidget(self.review_answer); split.addLayout(left,1); split.addLayout(right,1); v.addLayout(split,1)
        buttons=QHBoxLayout(); buttons.addWidget(self.primary('AI: написать ответ',self.ai_review_answer)); buttons.addWidget(self.primary('AI: подготовить жалобу',self.ai_review_complaint)); buttons.addWidget(self.danger('Отправить ответ в WB',self.send_review_answer)); v.addLayout(buttons)
        self.review_status=QLabel(''); self.review_status.setObjectName('muted'); v.addWidget(self.review_status); self.showp(w)

    def load_reviews(self):
        try:
            answered=self.rev_filter.currentIndex()==1; self.current_reviews=self.wb().reviews(is_answered=answered,take=100)
            self.rev_table.setRowCount(len(self.current_reviews))
            for i,r in enumerate(self.current_reviews):
                product=r.get('productDetails') or {}; user=r.get('userName') or r.get('wbUserDetails',{}).get('name') or ''
                vals=[r.get('id',''),r.get('productValuation',''),product.get('productName') or product.get('nmId') or '',user,r.get('text',''),r.get('createdDate','')]
                for j,val in enumerate(vals): self.rev_table.setItem(i,j,QTableWidgetItem(str(val or '')))
            self.review_status.setText(f'Загружено отзывов: {len(self.current_reviews)}')
        except Exception as e:QMessageBox.critical(self,'Отзывы WB',str(e))
    def selected_review(self):
        rows=self.rev_table.selectionModel().selectedRows() if hasattr(self,'rev_table') else []
        if not rows:return None
        i=rows[0].row(); return self.current_reviews[i] if i < len(self.current_reviews) else None
    def review_selected(self):
        r=self.selected_review()
        if r:self.review_text.setPlainText(r.get('text','') or '(текст отсутствует)')
    def ai_review_answer(self):
        r=self.selected_review()
        if not r:return QMessageBox.information(self,'Отзывы','Выберите отзыв в таблице')
        try:self.review_answer.setPlainText(self.ai().review_reply(r.get('text',''),int(r.get('productValuation') or 5)))
        except Exception as e:QMessageBox.critical(self,'AI',str(e))
    def ai_review_complaint(self):
        r=self.selected_review()
        if not r:return QMessageBox.information(self,'Отзывы','Выберите отзыв в таблице')
        try:self.review_answer.setPlainText(self.ai().review_complaint(r.get('text',''),int(r.get('productValuation') or 5)))
        except Exception as e:QMessageBox.critical(self,'AI',str(e))
    def send_review_answer(self):
        r=self.selected_review(); text=self.review_answer.toPlainText().strip()
        if not r:return QMessageBox.information(self,'Отзывы','Выберите отзыв')
        if not text:return QMessageBox.information(self,'Отзывы','Сначала подготовьте ответ')
        if QMessageBox.question(self,'Подтверждение','Отправить этот ответ покупателю через Wildberries API?') != QMessageBox.Yes:return
        try:self.wb().answer_review(r.get('id'),text); QMessageBox.information(self,'WB','Ответ отправлен'); self.load_reviews()
        except Exception as e:QMessageBox.critical(self,'WB',str(e))

    def ads_page(self):
        w,v=self.page('Реклама Wildberries','Реальные рекламные кампании из Promotion API')
        top=QHBoxLayout(); top.addWidget(self.primary('Загрузить кампании WB',self.load_campaigns)); top.addStretch(); v.addLayout(top)
        self.ads_table=QTableWidget(); self.ads_table.setColumnCount(4); self.ads_table.setHorizontalHeaderLabels(['Статус','Тип','Количество','ID кампаний']); self.ads_table.horizontalHeader().setSectionResizeMode(3,QHeaderView.Stretch); v.addWidget(self.ads_table,2)
        self.ads_raw=QTextEdit(); self.ads_raw.setReadOnly(True); self.ads_raw.setPlaceholderText('Сырой ответ API для диагностики и дальнейшего подключения статистики'); v.addWidget(self.ads_raw,1)
        calc=QGroupBox('Быстрый расчёт ДРР'); q=QFormLayout(calc); self.ad_spend=QDoubleSpinBox(); self.ad_spend.setMaximum(1e9); self.ad_revenue=QDoubleSpinBox(); self.ad_revenue.setMaximum(1e9); self.drr=QLabel('—'); q.addRow('Расход',self.ad_spend); q.addRow('Продажи',self.ad_revenue); q.addRow('ДРР',self.drr); v.addWidget(calc); v.addWidget(self.primary('Рассчитать ДРР',lambda:self.drr.setText(f'{(self.ad_spend.value()/self.ad_revenue.value()*100 if self.ad_revenue.value() else 0):.2f}%'))); self.showp(w)
    def load_campaigns(self):
        try:
            data=self.wb().campaign_groups(); self.ads_raw.setPlainText(json.dumps(data,ensure_ascii=False,indent=2))
            groups=data.get('adverts') or data.get('data') or data if isinstance(data,list) else data.get('adverts',[]) if isinstance(data,dict) else []
            if not isinstance(groups,list):groups=[]
            self.ads_table.setRowCount(len(groups))
            for i,g in enumerate(groups):
                ids=g.get('advert_list') or g.get('advertList') or g.get('ids') or []
                vals=[g.get('status',''),g.get('type',''),g.get('count',len(ids) if isinstance(ids,list) else ''),json.dumps(ids,ensure_ascii=False)]
                for j,val in enumerate(vals):self.ads_table.setItem(i,j,QTableWidgetItem(str(val)))
        except Exception as e:QMessageBox.critical(self,'Реклама WB',str(e))

    def finance_page(self):
        w,v=self.page('Финансы','Юнит-экономика и чистая прибыль')
        f=QFormLayout(); vals=[]
        for n in ['Выручка','Комиссия','Логистика','Реклама','Себестоимость']:
            x=QDoubleSpinBox(); x.setMaximum(1e9); x.setDecimals(2); f.addRow(n,x); vals.append(x)
        box=QWidget(); box.setLayout(f); v.addWidget(box); result=QLabel('Чистая прибыль: —'); v.addWidget(result); v.addWidget(self.primary('Рассчитать',lambda:result.setText(f'Чистая прибыль: {calc_profit(*[x.value() for x in vals]):,.2f}'))); v.addStretch(); self.showp(w)

    def director_page(self):
        w,v=self.page('AI Директор','AI-план по реальным данным магазина + вашим целям')
        inp=QTextEdit(); inp.setPlaceholderText('Цели бизнеса, проблемы, ограничения...'); out=QTextEdit(); v.addWidget(inp)
        def go():
            try:
                snapshot={'products':len(products())}
                try:snapshot['wb_rating']=self.wb().seller_rating()
                except Exception as e:snapshot['wb_rating_error']=str(e)
                try:snapshot['wb_campaigns']=self.wb().campaign_groups()
                except Exception as e:snapshot['wb_campaigns_error']=str(e)
                payload='Автоматическая сводка магазина: '+json.dumps(snapshot,ensure_ascii=False)+'\nЦели пользователя: '+inp.toPlainText()
                out.setPlainText(self.ai().director_plan(payload))
            except Exception as e:QMessageBox.critical(self,'AI Директор',str(e))
        v.addWidget(self.primary('Проанализировать магазин',go)); v.addWidget(out); self.showp(w)

    def projects_page(self):
        w,v=self.page('Проекты','История сгенерированных карточек')
        t=QTableWidget(); data=projects(); t.setColumnCount(4); t.setHorizontalHeaderLabels(['ID','Название','Фото','Создан']); t.setRowCount(len(data))
        for i,r in enumerate(data):
            for j,k in enumerate(['id','name','photo','created']):t.setItem(i,j,QTableWidgetItem(str(r[k] or '')))
        t.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch); v.addWidget(t); self.showp(w)

    def settings_page(self):
        w,v=self.page('Подключения','Секретные ключи хранятся через Windows Credential Manager')
        f=QFormLayout(); self.fields={}
        for label,key,secret in [('OpenAI API key','openai_api_key',1),('AI модель','openai_model',0),('WB token','wb_token',1),('Ozon Client ID','ozon_client_id',0),('Ozon API key','ozon_api_key',1),('Telegram bot token','telegram_token',1),('Telegram chat ID','telegram_chat_id',0)]:
            e=QLineEdit(self.cfg.get(key,''));
            if secret:e.setEchoMode(QLineEdit.Password)
            f.addRow(label,e); self.fields[key]=e
        box=QWidget(); box.setLayout(f); v.addWidget(box)
        r=QHBoxLayout(); r.addWidget(self.primary('Сохранить',self.save_cfg)); r.addWidget(self.primary('Проверить WB',lambda:self.test('WB'))); r.addWidget(self.primary('Проверить Ozon',lambda:self.test('Ozon'))); v.addLayout(r); v.addStretch(); self.showp(w)
    def save_cfg(self):
        self.cfg.update({k:e.text().strip() for k,e in self.fields.items()}); save_settings(self.cfg); QMessageBox.information(self,'Настройки','Сохранено безопасно')
    def test(self,mp):
        try:msg=self.wb().test() if mp=='WB' else self.ozon().test(); QMessageBox.information(self,mp,msg)
        except Exception as e:QMessageBox.critical(self,mp,str(e))
    def sync(self,mp):
        try:
            data=self.wb().products(100) if mp=='WB' else self.ozon().products(100); replace_products(mp,data); QMessageBox.information(self,'Синхронизация',f'{mp}: загружено {len(data)} товаров'); self.dashboard()
        except Exception as e:QMessageBox.critical(self,'Синхронизация',str(e))

def run():
    app=QApplication([]); win=Main(); win.show(); app.exec()
