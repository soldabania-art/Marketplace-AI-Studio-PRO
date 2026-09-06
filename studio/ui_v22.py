from PySide6.QtCore import QTimer
from PySide6.QtWidgets import *
from .ui_v21 import Main as BaseMain
from .core import save_settings, products
from .automation_center import build_alerts
from .review_autopilot import ReviewAutopilot
from .autopilot import set_action_status
from .workers import Worker


class Main(BaseMain):
    def __init__(self):
        self.scheduler_busy=False
        self.scheduler_last='Ещё не запускался'
        super().__init__()
        self.setWindowTitle('Marketplace AI Studio PRO — Mega Edition 2.2 CONTINUOUS AUTOPILOT')
        self.scheduler=QTimer(self)
        self.scheduler.timeout.connect(self.scheduled_tick)
        self._apply_scheduler()
        QTimer.singleShot(15000,self._initial_tick)

    def _initial_tick(self):
        if self.cfg.get('autopilot_scheduler_enabled',True) and self.cfg.get('autopilot_mode')=='autopilot':
            self.scheduled_tick()

    def _apply_scheduler(self):
        enabled=bool(self.cfg.get('autopilot_scheduler_enabled',True))
        minutes=max(30,min(int(self.cfg.get('autopilot_scheduler_minutes',60) or 60),360))
        self.cfg['autopilot_scheduler_minutes']=minutes
        if enabled:self.scheduler.start(minutes*60*1000)
        else:self.scheduler.stop()

    def dashboard(self):
        super().dashboard()
        w=self.stack.currentWidget(); layout=w.layout()
        group=QGroupBox('Непрерывный AUTOPILOT 2.2')
        form=QFormLayout(group)
        box=QCheckBox('Автоматически проверять магазин, рекламу, риски и метрики, пока приложение запущено')
        box.setChecked(bool(self.cfg.get('autopilot_scheduler_enabled',True)))
        box.toggled.connect(self.set_scheduler_enabled); form.addRow(box)
        interval=QSpinBox(); interval.setRange(30,360); interval.setSuffix(' мин'); interval.setValue(int(self.cfg.get('autopilot_scheduler_minutes',60) or 60)); interval.valueChanged.connect(self.set_scheduler_minutes); form.addRow('Интервал:',interval)
        label=QLabel('Последний цикл: '+str(self.scheduler_last)); label.setWordWrap(True); form.addRow(label)
        run=QPushButton('Запустить фоновый цикл сейчас'); run.setObjectName('primary'); run.clicked.connect(self.scheduled_tick); form.addRow(run)
        note=QLabel('Фоновый цикл не требует открывать отдельные страницы. Он пересчитывает SEO-сигналы, риски, рекламные действия и снимки эффективности. Безопасные ответы на отзывы 4–5★ отправляются автоматически только если отдельно разрешён автопилот отзывов.'); note.setWordWrap(True); form.addRow(note)
        layout.addWidget(group)

    def set_scheduler_enabled(self,value):
        self.cfg['autopilot_scheduler_enabled']=bool(value); save_settings(self.cfg); self._apply_scheduler()

    def set_scheduler_minutes(self,value):
        self.cfg['autopilot_scheduler_minutes']=int(value); save_settings(self.cfg); self._apply_scheduler()

    def scheduled_tick(self):
        if self.scheduler_busy:return
        if not self.cfg.get('wb_token'):return
        self.scheduler_busy=True
        notes=[]
        try:
            self.run_seo_scan(silent=True)
            notes.append(f'SEO: {len(self.seo_rows)} карточек')
        except Exception as e:notes.append('SEO ошибка: '+str(e))
        try:
            self.alerts_live=build_alerts([dict(r) for r in products()],self.live,self.finance_live,self.ads_live,self._cogs())
            notes.append(f'риски: {len(self.alerts_live)}')
        except Exception as e:notes.append('риски ошибка: '+str(e))
        try:
            n=self.build_ad_actions(auto_execute=True); notes.append(f'реклама: {n} действий')
        except Exception as e:notes.append('реклама ошибка: '+str(e))
        try:
            n=self.capture_performance_snapshots(); notes.append(f'метрики: {n} снимков')
        except Exception as e:notes.append('метрики ошибка: '+str(e))
        self.scheduler_last='; '.join(notes)
        if self.cfg.get('autopilot_mode')=='autopilot' and self.cfg.get('autopilot_allow_review_reply') and self.cfg.get('openai_api_key'):
            self._scheduled_reviews()
        else:self.scheduler_busy=False

    def _cogs(self):
        try:
            from .ui_v15 import load_cogs
            return load_cogs()
        except Exception:return {}

    def _scheduled_reviews(self):
        try:raw=self.wb().reviews(False,5,0)
        except Exception:
            self.scheduler_busy=False; return
        if not raw:
            self.scheduler_busy=False; return
        engine=ReviewAutopilot(self.wb(),self.ai())
        def job(progress,is_cancelled):
            prepared=[]
            for r in raw:
                if is_cancelled():break
                prepared.extend(engine.prepare([r],4))
            return prepared
        worker=Worker(job); self.active_worker=worker
        worker.signals.result.connect(self._scheduled_reviews_ready)
        worker.signals.error.connect(lambda e:self._scheduler_finish('отзывы ошибка: '+str(e)))
        worker.signals.finished.connect(self.worker_finished)
        self.pool.start(worker)

    def _scheduled_reviews_ready(self,prepared):
        engine=ReviewAutopilot(self.wb(),self.ai()); ids=engine.queue(prepared or []); sent=0
        for aid,p in zip(ids,prepared or []):
            if not p.get('safe_auto'):continue
            try:
                set_action_status(aid,'running'); res=engine.execute(p); set_action_status(aid,'done',res); sent+=1
            except Exception as e:set_action_status(aid,'failed',{'error':str(e)})
        self._scheduler_finish(f'отзывы: подготовлено {len(prepared or [])}, отправлено {sent}')

    def _scheduler_finish(self,note=''):
        if note:self.scheduler_last=(self.scheduler_last+'; '+note).strip('; ')
        self.scheduler_busy=False


def run():
    app=QApplication([]); win=Main(); win.show(); app.exec()
