from PySide6.QtWidgets import *
from .ui_v19 import Main as BaseMain
from .core import products, save_settings, save_project, generated_dir
from .workers import Worker
from .autopilot import queue_action, actions, set_action_status, save_card_version
from .wb_publisher import WBPublisher
import json, os


class Main(BaseMain):
    def __init__(self):
        self.target_wb_nm = ''
        self.last_pack_images = []
        super().__init__()
        self.setWindowTitle('Marketplace AI Studio PRO — Mega Edition 2.0 FULL AUTOPILOT')

    def dashboard(self):
        w,v=self.page('FULL AUTOPILOT 2.0','AI создаёт карточки и визуал, готовит безопасную WB-публикацию, ведёт версии и журнал действий')
        mode=self.cfg.get('autopilot_mode','approve')
        auto_publish=bool(self.cfg.get('autopilot_allow_card_publish',False))
        cards=QHBoxLayout()
        for title,value in [('Режим',mode.upper()),('Автопубликация WB','ВКЛ' if auto_publish else 'ВЫКЛ'),('Товаров',str(len(products()))),('Действий',str(len(actions()))),('Сигналов',str(len(self.alerts_live)))]:
            g=QGroupBox(title); q=QVBoxLayout(g); lab=QLabel(value); lab.setStyleSheet('font-size:20px;font-weight:800'); q.addWidget(lab); cards.addWidget(g)
        v.addLayout(cards)
        row=QHBoxLayout(); row.addWidget(self.primary('AI Фабрика → WB',self.factory)); row.addWidget(self.primary('Центр публикации WB',self.publish_center)); row.addWidget(self.primary('Запустить AI цикл',self.run_autopilot_cycle)); row.addWidget(self.primary('Очередь действий',self.autopilot_page)); v.addLayout(row)
        safety=QGroupBox('Защита автопилота'); sf=QFormLayout(safety)
        self.mode_combo=QComboBox(); self.mode_combo.addItems(['observe','approve','autopilot']); self.mode_combo.setCurrentText(mode); self.mode_combo.currentTextChanged.connect(self.save_mode); sf.addRow('Режим:',self.mode_combo)
        self.auto_publish_box=QCheckBox('Разрешить FULL AUTOPILOT публиковать AI-тексты и AI-изображения в WB без отдельного подтверждения'); self.auto_publish_box.setChecked(auto_publish); self.auto_publish_box.toggled.connect(self.set_auto_publish); sf.addRow(self.auto_publish_box)
        warn=QLabel('Публикация перезаписывает текстовые поля карточки и заменяет изображения в занятых слотах. Перед каждой записью программа сохраняет локальный снимок текущей WB-карточки. По умолчанию автопубликация выключена.'); warn.setWordWrap(True); sf.addRow(warn); v.addWidget(safety)
        self.auto_status=QTextEdit(); self.auto_status.setReadOnly(True); self.auto_status.setPlaceholderText('Журнал AUTOPILOT'); v.addWidget(self.auto_status,1); self.showp(w)

    def set_auto_publish(self,value):
        self.cfg['autopilot_allow_card_publish']=bool(value); save_settings(self.cfg)

    def factory(self):
        w,v=self.page('AI Фабрика 2.0 → WB','Выберите существующий товар WB, дайте исходное фото и факты. AI создаст тексты + SEO + визуал и подготовит публикацию.')
        form=QFormLayout(); self.target_combo=QComboBox(); self.target_combo.addItem('Новая карточка / без публикации','')
        for r in products():
            if str(r['marketplace'])=='WB': self.target_combo.addItem(f"{r['external_id']} — {r['name']}",str(r['external_id']))
        form.addRow('Целевая карточка WB:',self.target_combo); v.addLayout(form)
        self.photo_label=QLabel(self.photo or 'Фото товара не выбрано'); v.addWidget(self.photo_label); v.addWidget(self.primary('Выбрать исходное фото',self.pick_photo))
        self.fact=QTextEdit(); self.fact.setPlaceholderText('Только подтверждённые факты о товаре. AI сам создаст позиционирование, заголовки, описание, SEO, преимущества, характеристики-кандидаты и весь визуальный комплект.'); self.fact.setFixedHeight(125); v.addWidget(self.fact)
        opts=QHBoxLayout(); opts.addWidget(QLabel('AI-слайдов:')); self.slide_count=QSpinBox(); self.slide_count.setRange(3,10); self.slide_count.setValue(7); opts.addWidget(self.slide_count); opts.addStretch(); v.addLayout(opts)
        buttons=QHBoxLayout(); buttons.addWidget(self.primary('СОЗДАТЬ ВСЁ AI',self.start_full_pack_v20)); buttons.addWidget(self.primary('Отменить',self.cancel_active)); buttons.addWidget(self.primary('Центр публикации',self.publish_center)); v.addLayout(buttons)
        self.factory_progress=QProgressBar(); v.addWidget(self.factory_progress); self.factory_status=QLabel('Готово к запуску'); v.addWidget(self.factory_status); self.cardout=QTextEdit(); v.addWidget(self.cardout,1); self.showp(w)

    def start_full_pack_v20(self):
        self.target_wb_nm=str(self.target_combo.currentData() or '')
        if self.active_worker:return QMessageBox.information(self,'AI Фабрика','Уже выполняется задача.')
        photo=self.photo; facts=self.fact.toPlainText().strip(); count=self.slide_count.value()
        if not photo:return QMessageBox.information(self,'AI Фабрика','Выберите фото товара.')
        if not facts:return QMessageBox.information(self,'AI Фабрика','Введите подтверждённые факты.')
        context=facts + (f'\nЦелевая карточка Wildberries nmID: {self.target_wb_nm}. Не меняй идентификаторы и не выдумывай характеристики.' if self.target_wb_nm else '')
        worker=Worker(lambda progress,is_cancelled:self.ai().full_product_pack(photo,context,count,progress,is_cancelled))
        self.active_worker=worker; self.factory_progress.setValue(0); self.factory_status.setText('AI создаёт полный комплект...')
        worker.signals.progress.connect(lambda p,t:(self.factory_progress.setValue(p),self.factory_status.setText(t)))
        worker.signals.result.connect(self.full_pack_ready_v20); worker.signals.error.connect(lambda e:QMessageBox.critical(self,'AI Фабрика',e)); worker.signals.finished.connect(self.worker_finished); self.pool.start(worker)

    def full_pack_ready_v20(self,result):
        if result.get('cancelled'):
            self.factory_status.setText('Остановлено'); return
        self.card=result.get('card') or {}; self.last_pack_images=[str(x) for x in (result.get('images') or [])]
        name=self.card.get('product_type','AI карточка') if isinstance(self.card,dict) else 'AI карточка'; save_project(name,self.photo,self.card)
        mp='WB' if self.target_wb_nm else 'DRAFT'; entity=self.target_wb_nm or str(self.card.get('product_type') or 'new')
        ver=save_card_version(mp,entity,self.card,self.last_pack_images,'generated')
        self.cardout.setPlainText(json.dumps({'target_wb_nm':self.target_wb_nm,'version':ver,'card':self.card,'images':self.last_pack_images},ensure_ascii=False,indent=2))
        self.factory_progress.setValue(100)
        if self.target_wb_nm:
            try:
                aid=WBPublisher(self.wb()).queue_publish(self.target_wb_nm,self.card,self.last_pack_images,'AI создал новый текст и визуал для карточки')
                self.factory_status.setText(f'Готово. Версия {ver}; действие публикации #{aid} поставлено в очередь.')
                if self.cfg.get('autopilot_mode')=='autopilot' and self.cfg.get('autopilot_allow_card_publish'):
                    self.execute_publish_action(aid,confirm=False)
            except Exception as e:
                self.factory_status.setText('AI-комплект готов, но публикация не подготовлена: '+str(e))
        else:self.factory_status.setText(f'Готово. Версия {ver}; публикация не назначена.')

    def publish_center(self):
        w,v=self.page('WB Publish Center 2.0','Контролируемая запись AI-текстов и AI-изображений через официальные WB Content API')
        rows=[x for x in actions(300) if x.get('marketplace')=='WB' and x.get('action_type')=='publish_card']
        t=QTableWidget(); t.setColumnCount(7); t.setHorizontalHeaderLabels(['ID','Статус','nmID','Риск','Причина','Тексты','Изображения']); t.setRowCount(len(rows)); t.setSelectionBehavior(QAbstractItemView.SelectRows)
        for i,r in enumerate(rows):
            try:p=json.loads(r.get('payload') or '{}')
            except:p={}
            card=p.get('card') or {}; imgs=p.get('images') or []
            vals=[r['id'],r['status'],r['entity_id'],r['risk'],r['reason'],'да' if card else 'нет',len(imgs)]
            for j,x in enumerate(vals):t.setItem(i,j,QTableWidgetItem(str(x or '')))
        t.horizontalHeader().setSectionResizeMode(4,QHeaderView.Stretch); v.addWidget(t,1)
        detail=QTextEdit(); detail.setReadOnly(True); v.addWidget(detail,1)
        def selected_id():
            sel=t.selectionModel().selectedRows(); return int(t.item(sel[0].row(),0).text()) if sel else None
        def show():
            aid=selected_id(); r=next((x for x in rows if x['id']==aid),None)
            if r:
                try:p=json.loads(r.get('payload') or '{}')
                except:p={}
                detail.setPlainText(json.dumps(p,ensure_ascii=False,indent=2))
        t.itemSelectionChanged.connect(show)
        btn=QHBoxLayout(); btn.addWidget(self.primary('Проверить и опубликовать в WB',lambda:self.execute_publish_action(selected_id(),confirm=True))); btn.addWidget(self.primary('Отклонить',lambda:self.reject_publish(selected_id()))); v.addLayout(btn); self.showp(w)

    def reject_publish(self,aid):
        if aid:set_action_status(aid,'rejected',{'reason':'Отклонено пользователем'}); self.publish_center()

    def execute_publish_action(self,aid,confirm=True):
        if not aid:return
        row=next((x for x in actions(500) if int(x['id'])==int(aid)),None)
        if not row:return
        if row.get('status')=='done':return QMessageBox.information(self,'WB','Это действие уже выполнено.')
        try:payload=json.loads(row.get('payload') or '{}')
        except Exception:return QMessageBox.critical(self,'WB','Повреждён payload действия.')
        nm=row.get('entity_id'); card=payload.get('card') or {}; images=payload.get('images') or []
        if confirm:
            answer=QMessageBox.warning(self,'Публикация WB',f'Опубликовать AI-версию в карточку WB {nm}?\n\nБудут обновлены заголовок/описание и загружено изображений: {len(images)}. Перед записью сохранится снимок текущей карточки.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
            if answer!=QMessageBox.Yes:return
        try:
            set_action_status(aid,'running'); result=WBPublisher(self.wb()).publish(nm,card,images); set_action_status(aid,'done',result)
            if confirm:QMessageBox.information(self,'WB','AI-карточка отправлена в Wildberries. Синхронизация WB может занять время.')
        except Exception as e:
            set_action_status(aid,'failed',{'error':str(e)})
            if confirm:QMessageBox.critical(self,'WB',str(e))


def run():
    app=QApplication([]); win=Main(); win.show(); app.exec()
