from datetime import datetime, timezone
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import *
from .ui_v24 import Main as BaseMain
from .core import save_settings
from .autopilot import actions, set_action_status
from .automation_center import TelegramNotifier
from .wb_ad_manager import WBAdManager
from .review_autopilot import ReviewAutopilot
from .performance_evaluator import evaluate_all, queue_needed_rollbacks
from .rollback_executor import WBRollbackExecutor
from .safety_control import (
    init_safety_db, audit, audit_rows, usage_today, can_execute, record_usage,
    emergency_stop, resume_autopilot, daily_summary,
)


class Main(BaseMain):
    def __init__(self):
        init_safety_db()
        super().__init__()
        self.setWindowTitle('Marketplace AI Studio PRO — Mega Edition 2.5 COMMERCIAL GUARDRAILS')
        self.report_timer=QTimer(self)
        self.report_timer.timeout.connect(self.maybe_send_daily_report)
        self.report_timer.start(60*60*1000)
        QTimer.singleShot(30000,self.maybe_send_daily_report)

    def dashboard(self):
        super().dashboard()
        w=self.stack.currentWidget(); layout=w.layout()
        group=QGroupBox('COMMERCIAL GUARDRAILS 2.5')
        form=QFormLayout(group)
        stopped=bool(self.cfg.get('autopilot_emergency_stop',False))
        state=QLabel('⛔ AUTOPILOT STOP' if stopped else '✓ AUTOPILOT доступен')
        state.setStyleSheet('font-size:18px;font-weight:800'); form.addRow('Состояние:',state)
        row=QHBoxLayout()
        stop=QPushButton('АВАРИЙНЫЙ STOP AUTOPILOT'); stop.setObjectName('danger'); stop.clicked.connect(self.emergency_stop_ui); row.addWidget(stop)
        resume=QPushButton('Снять STOP'); resume.clicked.connect(self.resume_ui); row.addWidget(resume)
        form.addRow(row)
        card=QSpinBox(); card.setRange(0,50); card.setValue(int(self.cfg.get('autopilot_daily_card_publish_limit',3) or 0)); card.valueChanged.connect(lambda x:self._guard_setting('autopilot_daily_card_publish_limit',x)); form.addRow('Публикаций карточек / день:',card)
        ads=QSpinBox(); ads.setRange(0,200); ads.setValue(int(self.cfg.get('autopilot_daily_ad_change_limit',10) or 0)); ads.valueChanged.connect(lambda x:self._guard_setting('autopilot_daily_ad_change_limit',x)); form.addRow('Изменений ставок / день:',ads)
        delta=QSpinBox(); delta.setRange(0,1000); delta.setSuffix(' %'); delta.setValue(int(self.cfg.get('autopilot_daily_ad_delta_budget_pct',100) or 0)); delta.valueChanged.connect(lambda x:self._guard_setting('autopilot_daily_ad_delta_budget_pct',x)); form.addRow('Суммарный бюджет изменения ставок / день:',delta)
        rev=QSpinBox(); rev.setRange(0,500); rev.setValue(int(self.cfg.get('autopilot_daily_review_reply_limit',30) or 0)); rev.valueChanged.connect(lambda x:self._guard_setting('autopilot_daily_review_reply_limit',x)); form.addRow('Автоответов / день:',rev)
        rb=QSpinBox(); rb.setRange(0,10); rb.setValue(int(self.cfg.get('autopilot_daily_rollback_limit',1) or 0)); rb.valueChanged.connect(lambda x:self._guard_setting('autopilot_daily_rollback_limit',x)); form.addRow('Rollback / день:',rb)
        telegram=QCheckBox('Отправлять один ежедневный отчёт AUTOPILOT в Telegram'); telegram.setChecked(bool(self.cfg.get('autopilot_telegram_daily_report',False))); telegram.toggled.connect(lambda x:self._guard_setting('autopilot_telegram_daily_report',bool(x))); form.addRow(telegram)
        buttons=QHBoxLayout(); buttons.addWidget(self.primary('Отправить Telegram-отчёт сейчас',self.send_guard_report)); buttons.addWidget(self.primary('Журнал действий AI',self.audit_page)); form.addRow(buttons)
        u=usage_today(); summary=QLabel('Сегодня: карточки {}/{} · ставки {}/{} · отзывы {}/{} · rollback {}/{}'.format(
            int(u.get('publish_card',{}).get('count') or 0),int(self.cfg.get('autopilot_daily_card_publish_limit',3) or 0),
            int(u.get('ad_bid_change',{}).get('count') or 0),int(self.cfg.get('autopilot_daily_ad_change_limit',10) or 0),
            int(u.get('review_reply',{}).get('count') or 0),int(self.cfg.get('autopilot_daily_review_reply_limit',30) or 0),
            int(u.get('rollback_card',{}).get('count') or 0),int(self.cfg.get('autopilot_daily_rollback_limit',1) or 0)))
        summary.setWordWrap(True); form.addRow(summary)
        note=QLabel('STOP блокирует фоновые AI-циклы и все внешние write-действия. Дневные лимиты проверяются перед публикацией карточек, изменением рекламных ставок, автоответами и rollback. Каждая выполненная запись фиксируется в локальном audit-журнале.'); note.setWordWrap(True); form.addRow(note)
        layout.addWidget(group)

    def _guard_setting(self,key,value):
        self.cfg[key]=value; save_settings(self.cfg)

    def emergency_stop_ui(self):
        emergency_stop(self.cfg,save_settings)
        try:self.scheduler.stop()
        except Exception:pass
        try:self.growth_timer.stop()
        except Exception:pass
        audit('ui_stop','','','blocked',{'source':'dashboard'})
        QMessageBox.warning(self,'AUTOPILOT STOP','Фоновые циклы и внешние write-действия заблокированы. Режим переключён в observe.')
        self.dashboard()

    def resume_ui(self):
        resume_autopilot(self.cfg,save_settings)
        try:self._apply_scheduler()
        except Exception:pass
        try:self._apply_growth_timer()
        except Exception:pass
        QMessageBox.information(self,'AUTOPILOT','Аварийный STOP снят. Для полной автономности отдельно выберите режим autopilot и нужные разрешения.')
        self.dashboard()

    def scheduled_tick(self):
        if self.cfg.get('autopilot_emergency_stop'):
            self.scheduler_last='STOP: фоновый цикл заблокирован'; audit('scheduled_tick','','','blocked',{'reason':'emergency_stop'}); return
        return super().scheduled_tick()

    def run_card_growth_cycle(self):
        if self.cfg.get('autopilot_emergency_stop'):
            self.growth_status='STOP: AI-пересборка заблокирована'; audit('card_growth','WB','','blocked',{'reason':'emergency_stop'}); return
        return super().run_card_growth_cycle()

    def execute_publish_action(self,aid,confirm=True):
        row=next((x for x in actions(1000) if str(x.get('id'))==str(aid)),None)
        if not row:return
        if row.get('status')=='done':return super().execute_publish_action(aid,confirm)
        allowed,reason=can_execute(self.cfg,'publish_card',1)
        if not allowed:
            audit('publish_card','WB',row.get('entity_id'),'blocked',{'reason':reason,'action_id':aid})
            if confirm:QMessageBox.warning(self,'Защита AUTOPILOT',reason)
            return
        super().execute_publish_action(aid,confirm)
        latest=next((x for x in actions(1000) if str(x.get('id'))==str(aid)),None)
        if latest and latest.get('status')=='done':
            record_usage('publish_card','WB',row.get('entity_id'),1,{'action_id':aid})

    def build_ad_actions(self,auto_execute=False):
        ads=self._ads(); mgr=WBAdManager(self.wb())
        target=float(self.cfg.get('autopilot_target_drr',15) or 15)
        delta=float(self.cfg.get('autopilot_ad_max_change_pct',15) or 15)
        props=mgr.propose(ads.get('rows') or [],target,delta); ids=mgr.queue_proposals(props)
        if auto_execute and self.cfg.get('autopilot_mode')=='autopilot' and self.cfg.get('autopilot_allow_ad_bids'):
            for aid,p in zip(ids,props):
                current=float(p.get('current_bid') or 0); proposed=float(p.get('proposed_bid') or 0)
                if not proposed:continue
                change=abs((proposed-current)/current*100.0) if current else delta
                allowed,reason=can_execute(self.cfg,'ad_bid_change',change)
                if not allowed:
                    audit('ad_bid_change','WB',p.get('nm_id'),'blocked',{'reason':reason,'action_id':aid}); continue
                try:
                    set_action_status(aid,'running'); result=mgr.execute_action(p,delta); set_action_status(aid,'done',result)
                    record_usage('ad_bid_change','WB',p.get('nm_id'),change,{'action_id':aid,'advert_id':p.get('advert_id'),'from':current,'to':proposed})
                except Exception as e:
                    set_action_status(aid,'failed',{'error':str(e)}); audit('ad_bid_change','WB',p.get('nm_id'),'failed',{'error':str(e),'action_id':aid})
        return len(ids)

    def review_cycle_ready(self,prepared):
        engine=ReviewAutopilot(self.wb(),self.ai()); ids=engine.queue(prepared or [])
        auto=self.cfg.get('autopilot_mode')=='autopilot' and self.cfg.get('autopilot_allow_review_reply')
        sent=0
        if auto:
            for aid,p in zip(ids,prepared or []):
                if not p.get('safe_auto'):continue
                allowed,reason=can_execute(self.cfg,'review_reply',1)
                if not allowed:
                    audit('review_reply','WB',p.get('id'),'blocked',{'reason':reason,'action_id':aid}); continue
                try:
                    set_action_status(aid,'running'); res=engine.execute(p); set_action_status(aid,'done',res); sent+=1
                    record_usage('review_reply','WB',p.get('id'),1,{'action_id':aid,'rating':p.get('rating')})
                except Exception as e:
                    set_action_status(aid,'failed',{'error':str(e)}); audit('review_reply','WB',p.get('id'),'failed',{'error':str(e),'action_id':aid})
        if hasattr(self,'review_status'):self.review_status.setText(f'Подготовлено ответов: {len(prepared or [])}; автоматически отправлено: {sent}')
        self.review_center()

    def evaluate_performance_cycle(self):
        if not self.cfg.get('wb_token'):
            self.evaluation_status='Нет WB token'; return
        try:
            captured=self.capture_performance_snapshots()
            hours=int(self.cfg.get('autopilot_evaluation_hours',48) or 48)
            evaluations=evaluate_all('WB',hours)
            queued=queue_needed_rollbacks('WB',hours)
            executed=0
            if self.cfg.get('autopilot_mode')=='autopilot' and self.cfg.get('autopilot_allow_auto_rollback'):
                executor=WBRollbackExecutor(self.wb())
                for item in queued:
                    if int(item.get('score') or 0)<6:continue
                    aid=(item.get('rollback') or {}).get('action_id')
                    if not aid:continue
                    allowed,reason=can_execute(self.cfg,'rollback_card',1)
                    if not allowed:
                        audit('rollback_card','WB',item.get('entity_id'),'blocked',{'reason':reason,'action_id':aid}); continue
                    try:
                        executor.execute_action(aid); executed+=1
                        record_usage('rollback_card','WB',item.get('entity_id'),1,{'action_id':aid,'score':item.get('score')})
                    except Exception as e:audit('rollback_card','WB',item.get('entity_id'),'failed',{'error':str(e),'action_id':aid})
            self.evaluation_status=f'снимков {captured}; сравнений {len(evaluations)}; rollback предложено {len(queued)}; выполнено автоматически {executed}'
        except Exception as e:
            self.evaluation_status='Ошибка контроля: '+str(e); audit('performance_cycle','WB','','failed',{'error':str(e)})

    def send_guard_report(self,silent=False):
        try:
            text=daily_summary(self.cfg,actions(1000),getattr(self,'alerts_live',[]))
            TelegramNotifier(self.cfg.get('telegram_token',''),self.cfg.get('telegram_chat_id','')).send(text)
            self.cfg['autopilot_last_telegram_report_date']=datetime.now(timezone.utc).date().isoformat(); save_settings(self.cfg)
            audit('telegram_report','','','done',{})
            if not silent:QMessageBox.information(self,'Telegram','Отчёт AUTOPILOT отправлен.')
            return True
        except Exception as e:
            audit('telegram_report','','','failed',{'error':str(e)})
            if not silent:QMessageBox.critical(self,'Telegram',str(e))
            return False

    def maybe_send_daily_report(self):
        if not self.cfg.get('autopilot_telegram_daily_report'):return
        today=datetime.now(timezone.utc).date().isoformat()
        if self.cfg.get('autopilot_last_telegram_report_date')==today:return
        if not self.cfg.get('telegram_token') or not self.cfg.get('telegram_chat_id'):return
        self.send_guard_report(silent=True)

    def audit_page(self):
        w,v=self.page('AUDIT LOG 2.5','Полная локальная история решений, блокировок и внешних write-действий AUTOPILOT')
        rows=audit_rows(500); t=QTableWidget(); t.setColumnCount(7); t.setHorizontalHeaderLabels(['ID','Дата','Событие','MP','Объект','Статус','Детали']); t.setRowCount(len(rows)); t.setSelectionBehavior(QAbstractItemView.SelectRows)
        for i,r in enumerate(rows):
            vals=[r.get('id'),r.get('created'),r.get('event_type'),r.get('marketplace'),r.get('entity_id'),r.get('status'),r.get('details_json')]
            for j,x in enumerate(vals):t.setItem(i,j,QTableWidgetItem(str(x or '')))
        t.horizontalHeader().setSectionResizeMode(6,QHeaderView.Stretch); v.addWidget(t,1); self.showp(w)


def run():
    app=QApplication([]); win=Main(); win.show(); app.exec()
