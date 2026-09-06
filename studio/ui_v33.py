import os
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import *
from .ui_v32 import Main as BaseMain
from .local_ai_manager import manager_status, auto_optimize
from .core import save_settings
from . import __version__


class Main(BaseMain):
    """3.3: Local AI Manager with RAM/VRAM monitoring and safe model downgrade."""
    def __init__(self):
        self.local_manager_state={}
        super().__init__()
        self.setWindowTitle(f'Marketplace AI Studio PRO — Mega Edition {__version__} LOCAL AI MANAGER')
        self.ai_manager_timer=QTimer(self)
        self.ai_manager_timer.timeout.connect(self._background_ai_memory_guard)
        if os.environ.get('MARKETPLACE_AI_TEST_MODE')!='1':
            self.ai_manager_timer.start(30000)
            QTimer.singleShot(1800,self.refresh_ai_manager_silent)

    def dashboard(self):
        super().dashboard(); w=self.stack.currentWidget(); layout=w.layout()
        box=QGroupBox('Local AI Manager — RAM / VRAM')
        v=QVBoxLayout(box)
        self.ai_manager_label=QLabel(self._manager_text(self.local_manager_state)); self.ai_manager_label.setWordWrap(True); v.addWidget(self.ai_manager_label)
        row=QHBoxLayout(); row.addWidget(self.primary('Обновить состояние AI',self.refresh_ai_manager)); row.addWidget(self.primary('Оптимизировать память',self.optimize_ai_memory)); row.addStretch(); v.addLayout(row)
        note=QLabel('Автозащита никогда не скачивает модели и не включает платный AI. При высокой загрузке памяти она может переключить Local Text AI только на уже установленную более лёгкую модель.')
        note.setWordWrap(True); v.addWidget(note); layout.addWidget(box)

    def _manager_text(self,state=None):
        s=state or {}; ram=s.get('ram') or {}; gpu=s.get('gpu') or {}; pressure=s.get('pressure') or '—'
        current=s.get('current_model') or str(self.cfg.get('local_ai_model') or '—')
        installed=s.get('installed') or []; loaded=s.get('loaded') or []
        ram_txt='?' if ram.get('used_percent') is None else f"{ram.get('used_percent'):.0f}% · свободно {ram.get('available_gb')} GB"
        gpu_txt='не обнаружена' if not gpu.get('name') else f"{gpu.get('name')} · {gpu.get('used_percent') if gpu.get('used_percent') is not None else '?'}% · свободно {gpu.get('free_gb')} GB"
        reason=', '.join(s.get('reasons') or []) or 'нагрузка в норме'
        lighter=s.get('lighter_installed') or 'нет'
        return (f"Текущая модель: {current}\nRAM: {ram_txt}\nGPU/VRAM: {gpu_txt}\n"
                f"Давление памяти: {pressure.upper()} ({reason}) · более лёгкая установленная модель: {lighter}\n"
                f"Установлено моделей: {len(installed)} · загружено сейчас: {len(loaded)}")

    def refresh_ai_manager_silent(self):
        if os.environ.get('MARKETPLACE_AI_TEST_MODE')=='1': return
        try:
            self.local_manager_state=manager_status(self.cfg)
            if hasattr(self,'ai_manager_label'):self.ai_manager_label.setText(self._manager_text(self.local_manager_state))
        except Exception:pass

    def refresh_ai_manager(self):
        def job(progress,is_cancelled):
            progress(20,'Проверяю RAM, VRAM и локальные модели...')
            st=manager_status(self.cfg)
            progress(100,'Состояние Local AI обновлено'); return st
        return self._start_worker('Local AI Manager',job,self._ai_manager_ready)

    def _ai_manager_ready(self,state):
        self.local_manager_state=state or {}
        if hasattr(self,'ai_manager_label'):self.ai_manager_label.setText(self._manager_text(self.local_manager_state))
        QMessageBox.information(self,'Local AI Manager',self._manager_text(self.local_manager_state))

    def optimize_ai_memory(self):
        st=manager_status(self.cfg); target=st.get('lighter_installed')
        if st.get('pressure') not in ('high','critical'):
            self.local_manager_state=st
            if hasattr(self,'ai_manager_label'):self.ai_manager_label.setText(self._manager_text(st))
            return QMessageBox.information(self,'Local AI Manager','Нагрузка памяти сейчас в норме. Переключение модели не требуется.')
        if not target:
            return QMessageBox.warning(self,'Local AI Manager','Память загружена сильно, но более лёгкая уже установленная модель не найдена. Автозащита ничего не будет скачивать без вашего решения. Можно установить облегчённую модель через мастер бесплатного AI.')
        current=st.get('current_model') or ''
        if QMessageBox.question(self,'Оптимизация памяти',f'Память загружена сильно ({", ".join(st.get("reasons") or [])}).\nПереключить Local Text AI с «{current}» на уже установленную «{target}»?',QMessageBox.Yes|QMessageBox.No,QMessageBox.Yes)!=QMessageBox.Yes:return
        result=auto_optimize(self.cfg,True)
        if result.get('changed'):
            save_settings(self.cfg); self.local_manager_state=manager_status(self.cfg)
            if hasattr(self,'ai_manager_label'):self.ai_manager_label.setText(self._manager_text(self.local_manager_state))
            QMessageBox.information(self,'Local AI Manager',f"Готово. Активная модель изменена: {result.get('from')} → {result.get('to')}. Платные API не использовались.")
        else:
            QMessageBox.information(self,'Local AI Manager','Переключение не потребовалось или подходящей установленной модели нет.')

    def _background_ai_memory_guard(self):
        if os.environ.get('MARKETPLACE_AI_TEST_MODE')=='1':return
        if not bool(self.cfg.get('local_ai_auto_memory',True)):return
        if getattr(self,'active_worker',None):return
        try:
            result=auto_optimize(self.cfg,True)
            self.local_manager_state=result.get('status') or {}
            if result.get('changed'):
                save_settings(self.cfg)
                if hasattr(self,'statusBar'):self.statusBar().showMessage(f"Local AI: память под защитой, модель {result.get('from')} → {result.get('to')}",8000)
            if hasattr(self,'ai_manager_label'):self.ai_manager_label.setText(self._manager_text(manager_status(self.cfg)))
        except Exception:pass

    def settings_page(self):
        super().settings_page(); w=self.stack.currentWidget(); layout=w.layout()
        box=QGroupBox('Local AI Manager — защита памяти'); form=QFormLayout(box)
        self.local_ai_auto_memory=QCheckBox('Автоматически переключаться на более лёгкую уже установленную модель при нехватке RAM/VRAM')
        self.local_ai_auto_memory.setChecked(bool(self.cfg.get('local_ai_auto_memory',True))); form.addRow(self.local_ai_auto_memory)
        self.local_ai_memory_interval=QSpinBox(); self.local_ai_memory_interval.setRange(15,300); self.local_ai_memory_interval.setSuffix(' сек'); self.local_ai_memory_interval.setValue(int(self.cfg.get('local_ai_memory_interval_sec',30) or 30)); form.addRow('Интервал проверки:',self.local_ai_memory_interval)
        info=QLabel('Порог защиты: высокая нагрузка RAM/VRAM. Менеджер использует только уже установленные локальные модели, не скачивает ничего автоматически и не включает OpenAI.')
        info.setWordWrap(True); form.addRow(info)
        row=QHBoxLayout(); row.addWidget(self.primary('Проверить сейчас',self.refresh_ai_manager)); row.addWidget(self.primary('Оптимизировать',self.optimize_ai_memory)); row.addWidget(self.primary('Сохранить',self.save_cfg)); row.addStretch(); form.addRow(row)
        layout.insertWidget(max(0,layout.count()-1),box)

    def save_cfg(self):
        if hasattr(self,'local_ai_auto_memory'):
            self.cfg['local_ai_auto_memory']=bool(self.local_ai_auto_memory.isChecked())
            self.cfg['local_ai_memory_interval_sec']=int(self.local_ai_memory_interval.value())
            if hasattr(self,'ai_manager_timer'):self.ai_manager_timer.setInterval(max(15,int(self.local_ai_memory_interval.value()))*1000)
        return super().save_cfg()


def run():
    app=QApplication([]); win=Main(); win.show(); app.exec()
