from PySide6.QtCore import QTimer
from PySide6.QtWidgets import *
from .ui_v22 import Main as BaseMain
from .core import save_settings
from .workers import Worker
from .growth_engine import AutonomousCardOptimizer, growth_runs


class Main(BaseMain):
    def __init__(self):
        self.growth_worker=None
        self.growth_status='Ещё не запускался'
        super().__init__()
        self.setWindowTitle('Marketplace AI Studio PRO — Mega Edition 2.3 SELF-OPTIMIZING AI')
        self.growth_timer=QTimer(self)
        self.growth_timer.timeout.connect(self.run_card_growth_cycle)
        self._apply_growth_timer()
        QTimer.singleShot(120000,self._initial_growth_tick)

    def _apply_growth_timer(self):
        enabled=bool(self.cfg.get('autopilot_allow_ai_card_regeneration',False))
        minutes=max(60,min(int(self.cfg.get('autopilot_card_growth_minutes',180) or 180),1440))
        self.cfg['autopilot_card_growth_minutes']=minutes
        if enabled:self.growth_timer.start(minutes*60*1000)
        else:self.growth_timer.stop()

    def _initial_growth_tick(self):
        if self.cfg.get('autopilot_mode')=='autopilot' and self.cfg.get('autopilot_allow_ai_card_regeneration',False):
            self.run_card_growth_cycle()

    def dashboard(self):
        super().dashboard()
        w=self.stack.currentWidget(); layout=w.layout()
        group=QGroupBox('SELF-OPTIMIZING CARDS 2.3')
        form=QFormLayout(group)
        enabled=QCheckBox('Разрешить AI автоматически выбирать слабую карточку WB и полностью пересобирать тексты + SEO + визуал')
        enabled.setChecked(bool(self.cfg.get('autopilot_allow_ai_card_regeneration',False)))
        enabled.toggled.connect(self.set_growth_enabled); form.addRow(enabled)
        threshold=QSpinBox(); threshold.setRange(30,90); threshold.setValue(int(self.cfg.get('autopilot_card_score_threshold',70) or 70)); threshold.valueChanged.connect(self.set_growth_threshold); form.addRow('Пересобирать при SEO score ниже:',threshold)
        interval=QSpinBox(); interval.setRange(60,1440); interval.setSuffix(' мин'); interval.setValue(int(self.cfg.get('autopilot_card_growth_minutes',180) or 180)); interval.valueChanged.connect(self.set_growth_minutes); form.addRow('Не чаще одного товара каждые:',interval)
        run=QPushButton('Найти слабую карточку и пересобрать AI сейчас'); run.setObjectName('primary'); run.clicked.connect(self.run_card_growth_cycle); form.addRow(run)
        history=QPushButton('История AI-пересборок'); history.clicked.connect(self.growth_history_page); form.addRow(history)
        status=QLabel('Последний цикл: '+str(self.growth_status)); status.setWordWrap(True); form.addRow(status)
        note=QLabel('AI использует текущее фото WB как исходник, берёт только синхронизированные подтверждённые характеристики, создаёт новую версию текстов и полный визуальный комплект. За один цикл обрабатывается максимум одна карточка. Автоматическая публикация выполняется только когда одновременно включены режим AUTOPILOT и отдельное разрешение «Автопубликация WB».'); note.setWordWrap(True); form.addRow(note)
        layout.addWidget(group)

    def set_growth_enabled(self,value):
        self.cfg['autopilot_allow_ai_card_regeneration']=bool(value); save_settings(self.cfg); self._apply_growth_timer()

    def set_growth_threshold(self,value):
        self.cfg['autopilot_card_score_threshold']=int(value); save_settings(self.cfg)

    def set_growth_minutes(self,value):
        self.cfg['autopilot_card_growth_minutes']=int(value); save_settings(self.cfg); self._apply_growth_timer()

    def run_card_growth_cycle(self):
        if self.growth_worker or self.active_worker:
            self.growth_status='Пропущено: другая AI-задача уже выполняется'; return
        if not self.cfg.get('wb_token') or not self.cfg.get('openai_api_key'):
            self.growth_status='Нужны WB token и OpenAI API key'; return
        try:self.run_seo_scan(silent=True)
        except Exception as e:
            self.growth_status='SEO ошибка: '+str(e); return
        engine=AutonomousCardOptimizer(self.wb(),self.ai())
        candidate=engine.choose_candidate(self.seo_rows,int(self.cfg.get('autopilot_card_score_threshold',70) or 70))
        if not candidate:
            self.growth_status='Подходящих слабых карточек нет или они уже стоят в очереди'; return
        worker=Worker(lambda progress,is_cancelled:engine.regenerate(candidate,7,progress,is_cancelled))
        self.growth_worker=worker; self.active_worker=worker
        worker.signals.progress.connect(lambda p,t:self._growth_progress(p,t))
        worker.signals.result.connect(self._growth_ready)
        worker.signals.error.connect(lambda e:self._growth_error(e))
        worker.signals.finished.connect(self._growth_finished)
        self.growth_status=f'Запущена AI-пересборка nmID {candidate.get("nm")} (score {candidate.get("score")})'
        self.pool.start(worker)

    def _growth_progress(self,p,text):
        self.growth_status=f'{p}% — {text}'

    def _growth_error(self,error):
        self.growth_status='Ошибка AI-пересборки: '+str(error)

    def _growth_finished(self):
        self.growth_worker=None
        if self.active_worker is not None:self.active_worker=None

    def _growth_ready(self,result):
        if not result or result.get('cancelled'):
            self.growth_status='AI-пересборка остановлена'; return
        aid=result.get('publish_action_id'); nm=result.get('nm'); ver=result.get('version'); images=result.get('images') or []
        self.growth_status=f'Готово nmID {nm}: версия {ver}, изображений {len(images)}, публикация #{aid} поставлена в очередь'
        if self.cfg.get('autopilot_mode')=='autopilot' and self.cfg.get('autopilot_allow_card_publish') and aid:
            try:
                self.execute_publish_action(aid,confirm=False)
                self.growth_status+= '; отправлено в WB автоматически'
            except Exception as e:
                self.growth_status+='; автопубликация ошибка: '+str(e)

    def growth_history_page(self):
        w,v=self.page('История SELF-OPTIMIZING AI','Какие карточки AI выбирал для полной пересборки, какую версию создал и какое действие публикации сформировал')
        rows=growth_runs(200); t=QTableWidget(); t.setColumnCount(9); t.setHorizontalHeaderLabels(['ID','Дата','MP','nmID','Score','Статус','Версия','Publish ID','Примечание']); t.setRowCount(len(rows)); t.setSelectionBehavior(QAbstractItemView.SelectRows)
        for i,r in enumerate(rows):
            vals=[r.get('id'),r.get('created'),r.get('marketplace'),r.get('entity_id'),r.get('source_score'),r.get('status'),r.get('generated_version'),r.get('publish_action_id'),r.get('notes')]
            for j,x in enumerate(vals):t.setItem(i,j,QTableWidgetItem(str(x or '')))
        t.horizontalHeader().setSectionResizeMode(8,QHeaderView.Stretch); v.addWidget(t,1); self.showp(w)


def run():
    app=QApplication([]); win=Main(); win.show(); app.exec()
