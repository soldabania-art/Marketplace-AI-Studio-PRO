from PySide6.QtWidgets import *
from .ui_v30 import Main as BaseMain
from .local_ai_setup import setup_status, install_ollama, pull_ollama_model, ensure_ollama_running, launch_image_server
from .hardware_probe import recommendation_text
from .core import save_settings
from . import __version__


class Main(BaseMain):
    """3.1: one-click Windows Local AI setup wizard."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'Marketplace AI Studio PRO — Mega Edition {__version__} LOCAL AI SETUP')

    def dashboard(self):
        super().dashboard()
        w=self.stack.currentWidget(); layout=w.layout()
        box=QGroupBox('Бесплатный AI — мастер установки')
        v=QVBoxLayout(box)
        s=setup_status()
        self.setup_status_label=QLabel(self._setup_text(s)); self.setup_status_label.setWordWrap(True); v.addWidget(self.setup_status_label)
        row=QHBoxLayout(); row.addWidget(self.primary('Установить/настроить Local Text AI',self.local_ai_wizard)); row.addWidget(self.primary('Запустить Local Image AI',self.launch_local_image_wizard)); row.addStretch(); v.addLayout(row)
        note=QLabel('Программа ничего платного не включает автоматически. Установка Ollama выполняется через Windows winget только после вашего подтверждения; модель загружается локально на компьютер.')
        note.setWordWrap(True); v.addWidget(note); layout.addWidget(box)

    def _setup_text(self,s=None):
        s=s or setup_status(); oll='найден' if s.get('ollama') else 'не установлен'; img=len(s.get('image_launchers') or [])
        return f"Ollama: {oll} · winget: {'готов' if s.get('winget') else 'не найден'} · найдено Local Image launcher: {img}\n"+recommendation_text(self.hardware_info)

    def local_ai_wizard(self):
        model,ok=QInputDialog.getText(self,'Local Text AI','Локальная модель Ollama:',QLineEdit.Normal,str(self.cfg.get('local_ai_model') or 'qwen2.5:3b'))
        if not ok:return
        model=(model or 'qwen2.5:3b').strip()
        s=setup_status()
        if not s.get('ollama'):
            ans=QMessageBox.question(self,'Установка Ollama','Ollama не найден. Установить его через официальный пакет Windows winget?\n\nЭто бесплатный локальный AI-движок. Продолжить?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
            if ans!=QMessageBox.Yes:return
        else:
            ans=QMessageBox.question(self,'Local AI',f'Загрузить/обновить локальную модель «{model}»? Размер зависит от модели и займёт место на диске.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
            if ans!=QMessageBox.Yes:return
        def job(progress,is_cancelled):
            if not setup_status().get('ollama'):
                progress(5,'Устанавливаю Ollama...'); install_ollama(progress)
            if is_cancelled():return {'cancelled':True}
            progress(55,'Запускаю локальный AI...'); ensure_ollama_running()
            result=pull_ollama_model(model,lambda p,t:progress(55+int(p*.45),t))
            return result
        return self._start_worker('Мастер Local AI',job,self._local_ai_installed)

    def _local_ai_installed(self,result):
        if result.get('cancelled'):return
        self.cfg['ai_mode']='free'; self.cfg['local_ai_url']=result.get('url') or 'http://127.0.0.1:11434/v1'; self.cfg['local_ai_model']=result.get('model') or 'qwen2.5:3b'; self.cfg['ai_allow_paid_fallback']=False
        save_settings(self.cfg)
        if hasattr(self,'setup_status_label'):self.setup_status_label.setText(self._setup_text())
        QMessageBox.information(self,'Local AI',f"Готово.\nМодель: {self.cfg['local_ai_model']}\nURL: {self.cfg['local_ai_url']}\n\nРежим установлен на 0 ₽, платный fallback выключен.")
        self.test_local_ai()

    def launch_local_image_wizard(self):
        s=setup_status(); launchers=s.get('image_launchers') or []
        if launchers:
            choice,ok=QInputDialog.getItem(self,'Local Image AI','Найденные launchers:',launchers,0,False)
            if not ok:return
            launcher=choice
        else:
            launcher,_=QFileDialog.getOpenFileName(self,'Выберите webui-user.bat / run.bat','','Batch/Executable (*.bat *.cmd *.exe);;All files (*)')
            if not launcher:return
        ans=QMessageBox.question(self,'Local Image AI','Запустить выбранный локальный image-сервер с параметром --api?\n\nОткроется отдельное окно сервера. Это не использует OpenAI API.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if ans!=QMessageBox.Yes:return
        try:
            launch_image_server(launcher,'--api')
            self.cfg['local_images_enabled']=True; self.cfg['local_image_url']='http://127.0.0.1:7860'; self.cfg['local_image_launcher']=launcher; save_settings(self.cfg)
            QMessageBox.information(self,'Local Image AI','Сервер запускается. Подождите загрузку модели, затем нажмите «Проверить весь Local AI».')
        except Exception as e:
            QMessageBox.critical(self,'Local Image AI',str(e))

    def settings_page(self):
        super().settings_page(); w=self.stack.currentWidget(); layout=w.layout()
        box=QGroupBox('Мастер бесплатного Local AI'); v=QVBoxLayout(box)
        v.addWidget(QLabel('Автоустановка Local Text AI: Ollama через winget → запуск → загрузка выбранной модели → автоматическое сохранение URL и режима 0 ₽.'))
        row=QHBoxLayout(); row.addWidget(self.primary('Запустить мастер Text AI',self.local_ai_wizard)); row.addWidget(self.primary('Запустить/подключить Image AI',self.launch_local_image_wizard)); row.addStretch(); v.addLayout(row)
        layout.insertWidget(max(0,layout.count()-1),box)


def run():
    app=QApplication([]); win=Main(); win.show(); app.exec()
