from PySide6.QtCore import QTimer
from PySide6.QtWidgets import *
from .ui_v23 import Main as BaseMain
from .core import save_settings
from .autopilot import card_versions, actions
from .performance_loop import save_snapshot
from .performance_evaluator import evaluate_all, queue_needed_rollbacks
from .rollback_executor import WBRollbackExecutor


class Main(BaseMain):
    def __init__(self):
        self.evaluation_status='Ещё не запускался'
        super().__init__()
        self.setWindowTitle('Marketplace AI Studio PRO — Mega Edition 2.4 CLOSED-LOOP AUTOPILOT')
        self.evaluation_timer=QTimer(self)
        self.evaluation_timer.timeout.connect(self.evaluate_performance_cycle)
        self.evaluation_timer.start(6*60*60*1000)
        QTimer.singleShot(180000,self.evaluate_performance_cycle)

    def dashboard(self):
        super().dashboard()
        w=self.stack.currentWidget(); layout=w.layout()
        group=QGroupBox('CLOSED-LOOP CONTROL 2.4')
        form=QFormLayout(group)
        hours=QSpinBox(); hours.setRange(24,168); hours.setSuffix(' ч'); hours.setValue(int(self.cfg.get('autopilot_evaluation_hours',48) or 48)); hours.valueChanged.connect(self.set_eval_hours); form.addRow('Минимум данных после публикации:',hours)
        auto=QCheckBox('Разрешить автоматический rollback при сильном подтверждённом ухудшении метрик')
        auto.setChecked(bool(self.cfg.get('autopilot_allow_auto_rollback',False))); auto.toggled.connect(self.set_auto_rollback); form.addRow(auto)
        run=QPushButton('Снять метрики → сравнить версии → проверить rollback'); run.setObjectName('primary'); run.clicked.connect(self.evaluate_performance_cycle); form.addRow(run)
        center=QPushButton('Открыть центр контроля версий'); center.clicked.connect(self.closed_loop_center); form.addRow(center)
        status=QLabel('Последняя проверка: '+str(self.evaluation_status)); status.setWordWrap(True); form.addRow(status)
        note=QLabel('Rollback предлагается только после выдержки времени и заметного ухудшения нескольких показателей. Автоматический откат требует одновременно режима AUTOPILOT и отдельного разрешения выше. Для автоматического отката используется сохранённая предыдущая версия текста и визуала.'); note.setWordWrap(True); form.addRow(note)
        layout.addWidget(group)

    def set_eval_hours(self,value):
        self.cfg['autopilot_evaluation_hours']=int(value); save_settings(self.cfg)

    def set_auto_rollback(self,value):
        self.cfg['autopilot_allow_auto_rollback']=bool(value); save_settings(self.cfg)

    def capture_performance_snapshots(self):
        versions=card_versions('WB',limit=1000); latest={}
        for v in versions:
            status=str(v.get('status') or '').lower()
            if status not in ('published','rollback_published'):continue
            latest.setdefault(str(v.get('entity_id')),v)
        by_sku={str(x.get('nm')):x for x in self.sku_live}; count=0
        for nm,ver in latest.items():
            s=by_sku.get(nm)
            if not s:continue
            gross=float(s.get('gross') or 0); ad=float(s.get('ad_share') or 0)
            metrics={'gross':gross,'payout':float(s.get('payout') or 0),'units':float(s.get('units') or 0),'returns':float(s.get('returns') or 0),'profit':float(s.get('profit') or 0),'stock':float(s.get('stock') or 0),'ad_spend':ad,'drr':(ad/gross*100.0) if gross>0 else 0.0}
            save_snapshot('WB',nm,ver.get('version',0),metrics,7); count+=1
        return count

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
                    try:executor.execute_action(aid); executed+=1
                    except Exception:pass
            self.evaluation_status=f'снимков {captured}; сравнений {len(evaluations)}; rollback предложено {len(queued)}; выполнено автоматически {executed}'
        except Exception as e:
            self.evaluation_status='Ошибка контроля: '+str(e)

    def closed_loop_center(self):
        w,v=self.page('CLOSED-LOOP CONTROL 2.4','Версия карточки → бизнес-метрики → сравнение → решение оставить или откатить')
        top=QHBoxLayout(); top.addWidget(self.primary('Обновить оценку',lambda:(self.evaluate_performance_cycle(),self.closed_loop_center()))); top.addStretch(); v.addLayout(top)
        hours=int(self.cfg.get('autopilot_evaluation_hours',48) or 48); rows=evaluate_all('WB',hours)
        t=QTableWidget(); t.setColumnCount(8); t.setHorizontalHeaderLabels(['nmID','Текущая версия','Предыдущая','Score риска','Прибыль до','Прибыль после','ДРР до → после','Причины']); t.setRowCount(len(rows)); t.setSelectionBehavior(QAbstractItemView.SelectRows)
        for i,r in enumerate(rows):
            before=r.get('before') or {}; after=r.get('after') or {}
            vals=[r.get('entity_id'),r.get('current_version'),r.get('previous_version'),r.get('score'),round(float(before.get('profit') or 0),2),round(float(after.get('profit') or 0),2),f"{float(before.get('drr') or 0):.1f}% → {float(after.get('drr') or 0):.1f}%",'; '.join(r.get('reasons') or [])]
            for j,x in enumerate(vals):t.setItem(i,j,QTableWidgetItem(str(x or '')))
        t.horizontalHeader().setSectionResizeMode(7,QHeaderView.Stretch); v.addWidget(t,1)
        rb=[x for x in actions(1000) if x.get('marketplace')=='WB' and x.get('action_type')=='rollback_card']
        info=QLabel(f'Rollback-действий в журнале: {len(rb)}. Автоматический откат выполняется только для score ≥ 6 и при отдельном разрешении.'); info.setWordWrap(True); v.addWidget(info)
        self.showp(w)


def run():
    app=QApplication([]); win=Main(); win.show(); app.exec()
