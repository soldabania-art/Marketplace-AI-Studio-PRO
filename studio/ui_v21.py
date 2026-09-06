from PySide6.QtWidgets import *
from .ui_v20 import Main as BaseMain
from .core import products, save_settings
from .autopilot import actions, set_action_status, card_versions
from .wb_ad_manager import WBAdManager
from .review_autopilot import ReviewAutopilot
from .performance_loop import save_snapshot, snapshots, compare, propose_rollback
from .workers import Worker
import json, os


class Main(BaseMain):
    def __init__(self):
        self.review_worker = None
        self.review_results = []
        super().__init__()
        self.setWindowTitle('Marketplace AI Studio PRO — Mega Edition 2.1 AUTONOMOUS GROWTH')

    def dashboard(self):
        w,v=self.page('AUTONOMOUS GROWTH 2.1','Карточки + визуал + SEO + реклама + отзывы + измерение результата + rollback')
        mode=self.cfg.get('autopilot_mode','approve')
        cards=QHBoxLayout()
        vals=[
            ('Режим',mode.upper()),('Товаров',str(len(products()))),('Действий',str(len(actions()))),
            ('Авто WB-карточки','ВКЛ' if self.cfg.get('autopilot_allow_card_publish') else 'ВЫКЛ'),
            ('Авто отзывы','ВКЛ' if self.cfg.get('autopilot_allow_review_reply') else 'ВЫКЛ'),
            ('Авто ставки','ВКЛ' if self.cfg.get('autopilot_allow_ad_bids') else 'ВЫКЛ'),
        ]
        for title,value in vals:
            g=QGroupBox(title); q=QVBoxLayout(g); lab=QLabel(value); lab.setStyleSheet('font-size:18px;font-weight:800'); q.addWidget(lab); cards.addWidget(g)
        v.addLayout(cards)
        row=QHBoxLayout(); row.addWidget(self.primary('Полный AI цикл',self.run_full_growth_cycle)); row.addWidget(self.primary('AI Фабрика → WB',self.factory)); row.addWidget(self.primary('Реклама AI',self.ad_center)); row.addWidget(self.primary('Отзывы AI',self.review_center)); row.addWidget(self.primary('До/После + rollback',self.performance_center)); v.addLayout(row)
        guard=QGroupBox('Разрешения FULL AUTOPILOT'); f=QFormLayout(guard)
        self.auto_cards=QCheckBox('Автоматически публиковать AI-карточки WB'); self.auto_cards.setChecked(bool(self.cfg.get('autopilot_allow_card_publish'))); self.auto_cards.toggled.connect(lambda x:self._save_flag('autopilot_allow_card_publish',x)); f.addRow(self.auto_cards)
        self.auto_reviews=QCheckBox('Автоматически отвечать только на безопасные отзывы 4–5★'); self.auto_reviews.setChecked(bool(self.cfg.get('autopilot_allow_review_reply'))); self.auto_reviews.toggled.connect(lambda x:self._save_flag('autopilot_allow_review_reply',x)); f.addRow(self.auto_reviews)
        self.auto_ads=QCheckBox('Разрешить автоматическое изменение ставок в пределах лимита'); self.auto_ads.setChecked(bool(self.cfg.get('autopilot_allow_ad_bids'))); self.auto_ads.toggled.connect(lambda x:self._save_flag('autopilot_allow_ad_bids',x)); f.addRow(self.auto_ads)
        self.ad_delta=QSpinBox(); self.ad_delta.setRange(5,30); self.ad_delta.setValue(int(self.cfg.get('autopilot_ad_max_change_pct',15) or 15)); self.ad_delta.valueChanged.connect(lambda x:self._save_flag('autopilot_ad_max_change_pct',int(x))); f.addRow('Макс. изменение ставки за цикл, %:',self.ad_delta)
        warn=QLabel('Высокорисковые действия — публикация карточек, rollback и неоднозначные отзывы — остаются в журнале и требуют отдельного разрешения. Реклама меняется только если API-данные содержат надёжную текущую ставку и изменение укладывается в заданный лимит.'); warn.setWordWrap(True); f.addRow(warn); v.addWidget(guard)
        self.auto_status=QTextEdit(); self.auto_status.setReadOnly(True); self.auto_status.setPlaceholderText('Журнал полного AI-цикла'); v.addWidget(self.auto_status,1); self.showp(w)

    def _save_flag(self,key,value):
        self.cfg[key]=value; save_settings(self.cfg)

    def run_full_growth_cycle(self):
        self.auto_status.setPlainText('1/4 SEO и риски...')
        QApplication.processEvents()
        try:
            super().run_autopilot_cycle()
        except Exception as e:
            self.auto_status.append('SEO/риски: '+str(e))
        self.auto_status.append('2/4 Реклама...'); QApplication.processEvents()
        try:
            created=self.build_ad_actions(auto_execute=True)
            self.auto_status.append(f'Рекламных действий создано: {created}')
        except Exception as e:self.auto_status.append('Реклама: '+str(e))
        self.auto_status.append('3/4 Снимки эффективности...'); QApplication.processEvents()
        try:
            count=self.capture_performance_snapshots()
            self.auto_status.append(f'Снимков эффективности: {count}')
        except Exception as e:self.auto_status.append('Метрики: '+str(e))
        self.auto_status.append('4/4 Отзывы: запустите «Отзывы AI» для фоновой обработки новых отзывов — ответы используют OpenAI и могут занимать время.')

    def _ads(self):
        if isinstance(self.ads_live,dict) and self.ads_live.get('rows'):
            return self.ads_live
        groups=self.wb().campaign_groups(); self.ads_live=self.business().ad_stats(groups,30); return self.ads_live

    def build_ad_actions(self,auto_execute=False):
        ads=self._ads(); mgr=WBAdManager(self.wb())
        target=float(self.cfg.get('autopilot_target_drr',15) or 15)
        delta=float(self.cfg.get('autopilot_ad_max_change_pct',15) or 15)
        props=mgr.propose(ads.get('rows') or [],target,delta); ids=mgr.queue_proposals(props)
        if auto_execute and self.cfg.get('autopilot_mode')=='autopilot' and self.cfg.get('autopilot_allow_ad_bids'):
            for aid,p in zip(ids,props):
                if not p.get('proposed_bid'): continue
                try:
                    set_action_status(aid,'running'); result=mgr.execute_action(p,delta); set_action_status(aid,'done',result)
                except Exception as e:set_action_status(aid,'failed',{'error':str(e)})
        return len(ids)

    def ad_center(self):
        w,v=self.page('Рекламный AUTOPILOT 2.1','AI ищет перерасход и возможности масштабирования. Запись ставок — только через официальный WB Promotion API и защитный лимит.')
        top=QHBoxLayout(); top.addWidget(self.primary('Проанализировать и создать действия',lambda:(self.build_ad_actions(False),self.ad_center()))); top.addStretch(); v.addLayout(top)
        rows=[x for x in actions(500) if x.get('action_type') in ('ad_bid_change','ad_bid_review')]
        t=QTableWidget(); t.setColumnCount(9); t.setHorizontalHeaderLabels(['ID','Статус','nmID','Кампания','ДРР','Расход','Продажи','Ставка → новая','Причина']); t.setRowCount(len(rows)); t.setSelectionBehavior(QAbstractItemView.SelectRows)
        for i,r in enumerate(rows):
            try:p=json.loads(r.get('payload') or '{}')
            except:p={}
            bid=f"{p.get('current_bid') or '—'} → {p.get('proposed_bid') or '—'}"
            vals=[r['id'],r['status'],p.get('nm_id'),p.get('advert_id'),f"{float(p.get('drr') or 0):.1f}%",f"{float(p.get('spend') or 0):.0f}",f"{float(p.get('sales') or 0):.0f}",bid,r.get('reason')]
            for j,x in enumerate(vals):t.setItem(i,j,QTableWidgetItem(str(x or '')))
        t.horizontalHeader().setSectionResizeMode(8,QHeaderView.Stretch); v.addWidget(t,1)
        def exec_selected():
            sel=t.selectionModel().selectedRows()
            if not sel:return
            aid=int(t.item(sel[0].row(),0).text()); row=next((x for x in rows if int(x['id'])==aid),None)
            try:p=json.loads(row.get('payload') or '{}')
            except:p={}
            ans=QMessageBox.warning(self,'WB реклама',f"Изменить ставку {p.get('current_bid')} → {p.get('proposed_bid')} коп. для nmID {p.get('nm_id')}?",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
            if ans!=QMessageBox.Yes:return
            try:
                set_action_status(aid,'running'); res=WBAdManager(self.wb()).execute_action(p,float(self.cfg.get('autopilot_ad_max_change_pct',15))); set_action_status(aid,'done',res); self.ad_center()
            except Exception as e:set_action_status(aid,'failed',{'error':str(e)}); QMessageBox.critical(self,'Реклама',str(e))
        v.addWidget(self.primary('Выполнить выбранное изменение ставки',exec_selected)); self.showp(w)

    def review_center(self):
        w,v=self.page('Отзывы AUTOPILOT 2.1','Новые отзывы → AI-классификация → ответ → безопасные 4–5★ могут отправляться автоматически')
        row=QHBoxLayout(); row.addWidget(self.primary('Обработать новые отзывы AI',self.start_review_cycle)); row.addStretch(); v.addLayout(row)
        self.review_progress=QProgressBar(); v.addWidget(self.review_progress)
        self.review_status=QLabel('Готово'); v.addWidget(self.review_status)
        rows=[x for x in actions(500) if x.get('action_type')=='review_reply']
        self.review_table=QTableWidget(); self.review_table.setColumnCount(8); self.review_table.setHorizontalHeaderLabels(['ID действия','Статус','Отзыв ID','Оценка','Риск','Авто','Текст','AI ответ']); self.review_table.setRowCount(len(rows)); self.review_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        for i,r in enumerate(rows):
            try:p=json.loads(r.get('payload') or '{}')
            except:p={}
            vals=[r['id'],r['status'],p.get('id'),p.get('rating'),p.get('risk'),'да' if p.get('safe_auto') else 'нет',p.get('text'),p.get('reply')]
            for j,x in enumerate(vals):self.review_table.setItem(i,j,QTableWidgetItem(str(x or '')))
        self.review_table.horizontalHeader().setSectionResizeMode(6,QHeaderView.Stretch); self.review_table.horizontalHeader().setSectionResizeMode(7,QHeaderView.Stretch); v.addWidget(self.review_table,1)
        v.addWidget(self.primary('Отправить выбранный AI-ответ',self.send_selected_review)); self.showp(w)

    def start_review_cycle(self):
        if self.active_worker:return QMessageBox.information(self,'Отзывы','Другая AI-задача уже выполняется.')
        try:raw=self.wb().reviews(False,20,0)
        except Exception as e:return QMessageBox.critical(self,'Отзывы',str(e))
        if not raw:return QMessageBox.information(self,'Отзывы','Новых неотвеченных отзывов нет.')
        engine=ReviewAutopilot(self.wb(),self.ai())
        def job(progress,is_cancelled):
            out=[]; total=len(raw)
            for i,r in enumerate(raw,1):
                if is_cancelled():break
                progress(int((i-1)/total*100),f'AI анализирует отзыв {i}/{total}')
                out.extend(engine.prepare([r],4))
            progress(100,'Отзывы обработаны'); return out
        worker=Worker(job); self.active_worker=worker
        worker.signals.progress.connect(lambda p,t:(self.review_progress.setValue(p),self.review_status.setText(t)))
        worker.signals.result.connect(self.review_cycle_ready); worker.signals.error.connect(lambda e:QMessageBox.critical(self,'Отзывы',e)); worker.signals.finished.connect(self.worker_finished); self.pool.start(worker)

    def review_cycle_ready(self,prepared):
        engine=ReviewAutopilot(self.wb(),self.ai()); ids=engine.queue(prepared or [])
        auto=self.cfg.get('autopilot_mode')=='autopilot' and self.cfg.get('autopilot_allow_review_reply')
        sent=0
        if auto:
            for aid,p in zip(ids,prepared or []):
                if not p.get('safe_auto'):continue
                try:set_action_status(aid,'running'); res=engine.execute(p); set_action_status(aid,'done',res); sent+=1
                except Exception as e:set_action_status(aid,'failed',{'error':str(e)})
        self.review_status.setText(f'Подготовлено ответов: {len(prepared or [])}; автоматически отправлено: {sent}')
        self.review_center()

    def send_selected_review(self):
        rows=[x for x in actions(500) if x.get('action_type')=='review_reply']
        sel=self.review_table.selectionModel().selectedRows() if hasattr(self,'review_table') else []
        if not sel:return
        aid=int(self.review_table.item(sel[0].row(),0).text()); row=next((x for x in rows if int(x['id'])==aid),None)
        try:p=json.loads(row.get('payload') or '{}')
        except:p={}
        ans=QMessageBox.question(self,'Отзывы',f"Отправить AI-ответ на отзыв {p.get('rating')}/5?",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if ans!=QMessageBox.Yes:return
        try:set_action_status(aid,'running'); res=ReviewAutopilot(self.wb(),self.ai()).execute(p); set_action_status(aid,'done',res); self.review_center()
        except Exception as e:set_action_status(aid,'failed',{'error':str(e)}); QMessageBox.critical(self,'Отзывы',str(e))

    def capture_performance_snapshots(self):
        versions=card_versions('WB',limit=500); latest={}
        for v in versions:
            latest.setdefault(str(v.get('entity_id')),v)
        by_sku={str(x.get('nm')):x for x in self.sku_live}
        count=0
        for nm,ver in latest.items():
            s=by_sku.get(nm)
            if not s:continue
            metrics={'gross':s.get('gross',0),'payout':s.get('payout',0),'units':s.get('units',0),'returns':s.get('returns',0),'profit':s.get('profit',0),'stock':s.get('stock',0),'ad_spend':s.get('ad_share',0),'drr':(float(s.get('ad_share') or 0)/float(s.get('gross') or 1)*100.0) if float(s.get('gross') or 0)>0 else 0}
            save_snapshot('WB',nm,ver.get('version',0),metrics,7); count+=1
        return count

    def performance_center(self):
        w,v=self.page('Контроль ДО/ПОСЛЕ + ROLLBACK','Снимки эффективности версий карточек. AI предлагает откат только при заметном ухудшении нескольких бизнес-метрик.')
        top=QHBoxLayout(); top.addWidget(self.primary('Снять текущие метрики',lambda:(self.capture_performance_snapshots(),self.performance_center()))); top.addStretch(); v.addLayout(top)
        rows=snapshots('WB',limit=300); t=QTableWidget(); t.setColumnCount(7); t.setHorizontalHeaderLabels(['ID','Дата','nmID','Версия','Выручка','Прибыль','ДРР']); t.setRowCount(len(rows)); t.setSelectionBehavior(QAbstractItemView.SelectRows)
        for i,r in enumerate(rows):
            try:m=json.loads(r.get('metrics_json') or '{}')
            except:m={}
            vals=[r['id'],r['created'],r['entity_id'],r['version'],f"{float(m.get('gross') or 0):.0f}",f"{float(m.get('profit') or 0):.0f}",f"{float(m.get('drr') or 0):.1f}%"]
            for j,x in enumerate(vals):t.setItem(i,j,QTableWidgetItem(str(x or '')))
        t.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch); v.addWidget(t,1)
        detail=QTextEdit(); detail.setReadOnly(True); v.addWidget(detail,1)
        def analyze_selected():
            sel=t.selectionModel().selectedRows()
            if not sel:return
            nm=t.item(sel[0].row(),2).text(); same=[r for r in rows if str(r.get('entity_id'))==nm]
            if len(same)<2:return detail.setPlainText('Для сравнения нужно минимум два снимка этого nmID.')
            after=same[0]; before=same[1]
            bm=json.loads(before.get('metrics_json') or '{}'); am=json.loads(after.get('metrics_json') or '{}')
            cmp=compare(bm,am); proposal=propose_rollback('WB',nm,after.get('version'),bm,am)
            detail.setPlainText(json.dumps({'comparison':cmp,'rollback_proposal':proposal},ensure_ascii=False,indent=2))
        t.itemSelectionChanged.connect(analyze_selected)
        v.addWidget(self.primary('Выполнить выбранный rollback из очереди',self.rollback_center)); self.showp(w)

    def rollback_center(self):
        rows=[x for x in actions(500) if x.get('action_type')=='rollback_card' and x.get('status') not in ('done','rejected')]
        if not rows:return QMessageBox.information(self,'Rollback','Нет предложенных откатов.')
        row=rows[0]
        try:p=json.loads(row.get('payload') or '{}')
        except:p={}
        ans=QMessageBox.warning(self,'ROLLBACK',f"Откатить WB {row.get('entity_id')} с версии {p.get('from_version')} на {p.get('to_version')}?\nПричины: {', '.join(p.get('reasons') or [])}",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if ans!=QMessageBox.Yes:return
        images=[x for x in (p.get('previous_images') or []) if isinstance(x,str) and os.path.exists(x)]
        try:
            set_action_status(row['id'],'running'); res=self.publisher().publish(row.get('entity_id'),p.get('previous_card') or {},images); set_action_status(row['id'],'done',res); QMessageBox.information(self,'Rollback','Предыдущая версия отправлена в WB.')
        except Exception as e:set_action_status(row['id'],'failed',{'error':str(e)}); QMessageBox.critical(self,'Rollback',str(e))

    def publisher(self):
        from .wb_publisher import WBPublisher
        return WBPublisher(self.wb())


def run():
    app=QApplication([]); win=Main(); win.show(); app.exec()
