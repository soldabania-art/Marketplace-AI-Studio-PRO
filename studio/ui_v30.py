from PySide6.QtWidgets import *
from .ui_v29 import Main as BaseMain
from .hardware_probe import probe_hardware, recommendation_text
from .ai_router import AIRouter
from .core import save_settings
from . import __version__


class Main(BaseMain):
    """3.0: free-first text + local images + automatic hardware recommendation."""

    def __init__(self):
        self.hardware_info=probe_hardware()
        super().__init__()
        self.setWindowTitle(f'Marketplace AI Studio PRO — Mega Edition {__version__} ZERO-COST AI')

    def _ai_mode_text(self):
        base=super()._ai_mode_text()
        local_img='ВКЛ' if bool(self.cfg.get('local_images_enabled',True)) else 'ВЫКЛ'
        return base+f' · Local Image: {local_img}'

    def dashboard(self):
        super().dashboard()
        w=self.stack.currentWidget(); layout=w.layout()
        box=QGroupBox('Локальный AI — возможности этого компьютера')
        v=QVBoxLayout(box)
        self.hw_label=QLabel(recommendation_text(self.hardware_info)); self.hw_label.setWordWrap(True); v.addWidget(self.hw_label)
        status=AIRouter(self.cfg).status(); text=status.get('local') or {}; img=status.get('local_images') or {}
        self.local_stack_status=QLabel(
            f"Local Text: {'готов' if text.get('ok') else 'не запущен'} · Local Image: {'готов' if img.get('ok') else 'не запущен'}\n"
            "Если оба локальных сервера работают, создание текстов, SEO, ответов и визуалов не использует платный OpenAI API."
        )
        self.local_stack_status.setWordWrap(True); v.addWidget(self.local_stack_status)
        row=QHBoxLayout(); row.addWidget(self.primary('Проверить весь Local AI',self.test_local_stack)); row.addWidget(self.primary('Настройки Local AI',self.settings_page)); row.addStretch(); v.addLayout(row)
        layout.addWidget(box)

    def settings_page(self):
        super().settings_page()
        w=self.stack.currentWidget(); layout=w.layout()
        group=QGroupBox('Local Image AI — бесплатные визуалы')
        form=QFormLayout(group)
        self.local_images_enabled=QCheckBox('Использовать локальную генерацию изображений первой'); self.local_images_enabled.setChecked(bool(self.cfg.get('local_images_enabled',True))); form.addRow(self.local_images_enabled)
        self.local_image_url=QLineEdit(str(self.cfg.get('local_image_url','http://127.0.0.1:7860'))); form.addRow('Stable Diffusion WebUI / Forge URL:',self.local_image_url)
        self.local_image_model=QLineEdit(str(self.cfg.get('local_image_model','') or '')); self.local_image_model.setPlaceholderText('Можно оставить пустым — используется текущая модель сервера'); form.addRow('Checkpoint / модель:',self.local_image_model)
        hw=QLabel(recommendation_text(self.hardware_info)); hw.setWordWrap(True); form.addRow('Этот компьютер:',hw)
        note=QLabel('Поддерживается локальный AUTOMATIC1111/Forge-совместимый API. Для существующего фото товара используется img2img с низкой силой изменения, затем точный русский текст накладывается локально. Если Local Image недоступен, платный OpenAI НЕ включается без отдельного разрешения.')
        note.setWordWrap(True); form.addRow(note)
        row=QHBoxLayout(); row.addWidget(self.primary('Проверить Local Image',self.test_local_image)); row.addWidget(self.primary('Сохранить',self.save_cfg)); row.addStretch(); form.addRow(row)
        layout.insertWidget(max(0,layout.count()-1),group)

    def save_cfg(self):
        if hasattr(self,'local_images_enabled'):
            self.cfg['local_images_enabled']=bool(self.local_images_enabled.isChecked())
            self.cfg['local_image_url']=self.local_image_url.text().strip() or 'http://127.0.0.1:7860'
            self.cfg['local_image_model']=self.local_image_model.text().strip()
        return super().save_cfg()

    def test_local_image(self):
        if hasattr(self,'local_image_url'):
            self.cfg['local_image_url']=self.local_image_url.text().strip() or 'http://127.0.0.1:7860'
            self.cfg['local_image_model']=self.local_image_model.text().strip()
            self.cfg['local_images_enabled']=bool(self.local_images_enabled.isChecked())
        def job(progress,is_cancelled):
            progress(20,'Проверяю Local Image AI...')
            st=AIRouter(self.cfg).status().get('local_images') or {}
            progress(100,'Local Image проверен')
            return st
        return self._start_worker('Local Image AI',job,self._local_image_ready)

    def _local_image_ready(self,status):
        if status.get('ok'):
            QMessageBox.information(self,'Local Image AI',f"Локальная генерация доступна.\nURL: {status.get('url')}\nМодель: {status.get('model') or 'текущая модель сервера'}\n\nПлатный OpenAI Image API для этих генераций не нужен.")
        else:
            QMessageBox.warning(self,'Local Image AI',f"Локальный image-сервер пока не запущен.\nURL: {status.get('url')}\n{status.get('error') or 'HTTP '+str(status.get('status'))}\n\nВ режиме 0 ₽ приложение не переключится на платные изображения автоматически.")

    def test_local_stack(self):
        def job(progress,is_cancelled):
            progress(10,'Проверяю Local Text AI...')
            st=AIRouter(self.cfg).status()
            progress(70,'Проверяю Local Image AI...')
            st['hardware']=self.hardware_info
            progress(100,'Local AI проверен')
            return st
        return self._start_worker('Local AI стек',job,self._local_stack_ready)

    def _local_stack_ready(self,status):
        text=status.get('local') or {}; img=status.get('local_images') or {}
        msg=(f"Text AI: {'ГОТОВ' if text.get('ok') else 'НЕ ЗАПУЩЕН'}\n"
             f"Image AI: {'ГОТОВ' if img.get('ok') else 'НЕ ЗАПУЩЕН'}\n\n"
             +recommendation_text(status.get('hardware') or self.hardware_info))
        if text.get('ok') and img.get('ok'):
            msg+='\n\nПолный AI-конвейер может работать локально без оплаты OpenAI API.'
            QMessageBox.information(self,'Local AI стек',msg)
        else:
            msg+='\n\nОтсутствующие локальные сервисы нужно запустить. Платный fallback остаётся заблокированным, пока вы сами его не разрешите.'
            QMessageBox.warning(self,'Local AI стек',msg)


def run():
    app=QApplication([]); win=Main(); win.show(); app.exec()
