from PySide6.QtCore import QTimer
from PySide6.QtWidgets import *
from .ui_v31 import Main as BaseMain
from .local_ai_setup import (
    setup_status, install_ollama, pull_ollama_model, ensure_ollama_running,
    launch_image_server, recommended_text_model, autostart_local_services,
)
from .hardware_probe import recommendation_text
from .core import save_settings
from . import __version__


class Main(BaseMain):
    """3.2: hardware-aware one-click free AI setup + safe local service autostart."""
    def __init__(self):
        self.local_boot_result={}
        super().__init__()
        self.setWindowTitle(f'Marketplace AI Studio PRO — Mega Edition {__version__} ONE-CLICK FREE AI')
        QTimer.singleShot(900,self._autostart_local_ai)

    def dashboard(self):
        super().dashboard(); w=self.stack.currentWidget(); layout=w.layout()
        s=setup_status(self.hardware_info); rec=s.get('recommended_model') or recommended_text_model(self.hardware_info)
        box=QGroupBox('Бесплатный AI — установка в 1 клик')
        v=QVBoxLayout(box)
        self.free_setup_label=QLabel(self._free_setup_text(s,rec)); self.free_setup_label.setWordWrap(True); v.addWidget(self.free_setup_label)
        row=QHBoxLayout(); row.addWidget(self.primary('Установить всё бесплатное',self.install_all_free)); row.addWidget(self.primary('Перезапустить Local AI',self.restart_local_services)); row.addStretch(); v.addLayout(row)
        note=QLabel('Кнопка автоматически выбирает текстовую модель под RAM/VRAM, проверяет свободное место, устанавливает Ollama через winget при необходимости и включает автозапуск. Local Image запускается автоматически только если Forge/A1111 уже найден — сторонний image-пакет без подтверждения не скачивается.')
        note.setWordWrap(True); v.addWidget(note); layout.addWidget(box)

    def _free_setup_text(self,s=None,rec=None):
        s=s or setup_status(self.hardware_info); rec=rec or s.get('recommended_model') or recommended_text_model(self.hardware_info)
        free=s.get('free_space_gb'); free_txt='?' if free is None else f'{free:.1f} GB'
        return (
            f"Рекомендованная Text-модель: {rec.get('model')} ({rec.get('tier')}, ~{rec.get('estimated_gb')} GB) · свободно: {free_txt}\n"
            f"Ollama: {'запущен' if s.get('ollama_running') else 'установлен' if s.get('ollama') else 'не установлен'} · "
            f"Local Image: {'запущен' if s.get('image_running') else 'launcher найден' if s.get('image_launchers') else 'не найден'}\n"
            +recommendation_text(self.hardware_info)
        )

    def install_all_free(self):
        s=setup_status(self.hardware_info); rec=s.get('recommended_model') or recommended_text_model(self.hardware_info)
        model=str(rec.get('model') or 'qwen2.5:3b'); estimated=float(rec.get('estimated_gb') or 3)
        free=s.get('free_space_gb')
        if free is not None and float(free) < estimated+2.0:
            return QMessageBox.warning(self,'Бесплатный AI',f'Недостаточно свободного места. Для модели {model} нужно примерно {estimated:.1f} GB плюс минимум 2 GB запаса. Сейчас свободно {float(free):.1f} GB.')
        image_launchers=s.get('image_launchers') or []
        text=('Программа настроит бесплатный Local AI:\n\n'
              f'• Text AI: {model} (~{estimated:.1f} GB)\n'
              f"• Ollama: {'уже установлен' if s.get('ollama') else 'будет установлен через winget'}\n"
              f"• Local Image: {'будет запущен из найденного launcher' if image_launchers else 'launcher пока не найден — этот шаг будет пропущен'}\n"
              '• Режим 0 ₽ и запрет платного fallback останутся включены\n'
              '• Local Text AI будет автоматически запускаться вместе с программой\n\nПродолжить?')
        if QMessageBox.question(self,'Установить всё бесплатное',text,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        launcher=image_launchers[0] if image_launchers else ''
        def job(progress,is_cancelled):
            progress(3,'Проверяю локальные компоненты...')
            if not setup_status(self.hardware_info).get('ollama'):
                install_ollama(lambda p,t:progress(3+int(p*.30),t))
            if is_cancelled():return {'cancelled':True}
            progress(36,'Запускаю Local Text AI...'); ensure_ollama_running()
            result=pull_ollama_model(model,lambda p,t:progress(38+int(p*.52),t))
            image_result=None
            if launcher and not is_cancelled():
                progress(92,'Запускаю Local Image AI...')
                try:image_result=launch_image_server(launcher,'--api')
                except Exception as e:image_result={'ok':False,'error':str(e)}
            progress(100,'Бесплатный AI настроен')
            return {'text':result,'image':image_result,'launcher':launcher,'model':model,'cancelled':bool(is_cancelled())}
        return self._start_worker('Установка бесплатного AI',job,self._all_free_ready)

    def _all_free_ready(self,result):
        if not result or result.get('cancelled'):return
        text=result.get('text') or {}; launcher=str(result.get('launcher') or '')
        self.cfg.update({
            'ai_mode':'free',
            'ai_allow_paid_fallback':False,
            'ai_allow_paid_images':False,
            'local_ai_url':text.get('url') or 'http://127.0.0.1:11434/v1',
            'local_ai_model':text.get('model') or result.get('model') or 'qwen2.5:3b',
            'local_text_autostart':True,
            'local_images_enabled':True,
        })
        if launcher:
            self.cfg['local_image_launcher']=launcher; self.cfg['local_image_url']='http://127.0.0.1:7860'; self.cfg['local_image_autostart']=True
        save_settings(self.cfg)
        s=setup_status(self.hardware_info)
        if hasattr(self,'free_setup_label'):self.free_setup_label.setText(self._free_setup_text(s))
        image=result.get('image')
        image_msg='Local Image launcher не найден; Text AI уже полностью бесплатный.' if not launcher else ('Local Image запущен.' if image and image.get('ok') else 'Local Image launcher найден, но сервер нужно проверить отдельно.')
        QMessageBox.information(self,'Бесплатный AI',f"Готово.\nText AI: {self.cfg['local_ai_model']}\nРежим: 0 ₽\nПлатный fallback: выключен\nПлатные изображения: выключены\n{image_msg}")
        self.test_local_stack()

    def _autostart_local_ai(self):
        try:
            self.local_boot_result=autostart_local_services(self.cfg)
            text=self.local_boot_result.get('text') or {}; image=self.local_boot_result.get('image') or {}
            if hasattr(self,'statusBar'):
                parts=[]
                if text:parts.append('Local Text '+('готов' if text.get('ok') else 'не запущен'))
                if image:parts.append('Local Image '+('готов' if image.get('ok') else 'не запущен'))
                if parts:self.statusBar().showMessage(' · '.join(parts),5000)
        except Exception:
            pass

    def restart_local_services(self):
        def job(progress,is_cancelled):
            progress(20,'Запускаю сохранённые Local AI сервисы...')
            result=autostart_local_services(self.cfg)
            progress(100,'Local AI запуск завершён'); return result
        return self._start_worker('Local AI автозапуск',job,self._local_restart_ready)

    def _local_restart_ready(self,result):
        self.local_boot_result=result or {}; text=(result or {}).get('text') or {}; image=(result or {}).get('image') or {}
        msg=f"Local Text: {'ГОТОВ' if text.get('ok') else 'НЕ ЗАПУЩЕН'}\n"
        if self.cfg.get('local_image_autostart',False):msg+=f"Local Image: {'ГОТОВ' if image.get('ok') else 'НЕ ЗАПУЩЕН'}\n"
        msg+='\nАвтозапуск ничего не устанавливает и не включает платные API.'
        QMessageBox.information(self,'Local AI',msg)

    def settings_page(self):
        super().settings_page(); w=self.stack.currentWidget(); layout=w.layout()
        box=QGroupBox('Автозапуск бесплатного AI'); form=QFormLayout(box)
        self.local_text_autostart=QCheckBox('Автоматически запускать Local Text AI вместе с программой'); self.local_text_autostart.setChecked(bool(self.cfg.get('local_text_autostart',True))); form.addRow(self.local_text_autostart)
        self.local_image_autostart=QCheckBox('Автоматически запускать Local Image AI, если launcher сохранён'); self.local_image_autostart.setChecked(bool(self.cfg.get('local_image_autostart',False))); form.addRow(self.local_image_autostart)
        s=setup_status(self.hardware_info); rec=s.get('recommended_model') or recommended_text_model(self.hardware_info)
        info=QLabel(self._free_setup_text(s,rec)); info.setWordWrap(True); form.addRow(info)
        row=QHBoxLayout(); row.addWidget(self.primary('Установить всё бесплатное',self.install_all_free)); row.addWidget(self.primary('Сохранить автозапуск',self.save_cfg)); row.addStretch(); form.addRow(row)
        layout.insertWidget(max(0,layout.count()-1),box)

    def save_cfg(self):
        if hasattr(self,'local_text_autostart'):self.cfg['local_text_autostart']=bool(self.local_text_autostart.isChecked())
        if hasattr(self,'local_image_autostart'):self.cfg['local_image_autostart']=bool(self.local_image_autostart.isChecked())
        return super().save_cfg()


def run():
    app=QApplication([]); win=Main(); win.show(); app.exec()
