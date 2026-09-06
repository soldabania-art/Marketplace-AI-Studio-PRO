import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import *
from .ui_v28 import Main as BaseMain
from .ai_router import AIRouter
from .core import save_settings
from . import __version__


class Main(BaseMain):
    """2.9: free-first AI provider routing and explicit paid-AI safety controls."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'Marketplace AI Studio PRO — Mega Edition {__version__} FREE-FIRST AI')

    def ai(self):
        return AIRouter(self.cfg)

    def _ai_mode_text(self):
        mode=str(self.cfg.get('ai_mode','free'))
        names={'free':'0 ₽ / Local AI','economy':'Экономный','premium':'Premium OpenAI'}
        paid_fallback=bool(self.cfg.get('ai_allow_paid_fallback',False))
        paid_images=bool(self.cfg.get('ai_allow_paid_images',False))
        return f"Режим: {names.get(mode,mode)} · платный fallback: {'ВКЛ' if paid_fallback else 'ВЫКЛ'} · платные изображения: {'ВКЛ' if paid_images else 'ВЫКЛ'}"

    def dashboard(self):
        super().dashboard()
        w=self.stack.currentWidget(); layout=w.layout()
        box=QGroupBox('AI COST CONTROL — FREE FIRST')
        v=QVBoxLayout(box)
        self.ai_mode_status=QLabel(self._ai_mode_text()); self.ai_mode_status.setWordWrap(True); v.addWidget(self.ai_mode_status)
        note=QLabel('В режиме 0 ₽ текстовые AI-задачи идут только в локальный OpenAI-совместимый сервер. Платные запросы OpenAI и платные изображения заблокированы. Если локальный AI недоступен, программа покажет ошибку и не потратит деньги.')
        note.setWordWrap(True); v.addWidget(note)
        row=QHBoxLayout(); row.addWidget(self.primary('Проверить Local AI',self.test_local_ai)); row.addWidget(self.primary('Настроить AI режим',self.settings_page)); row.addStretch(); v.addLayout(row)
        layout.addWidget(box)

    def settings_page(self):
        super().settings_page()
        w=self.stack.currentWidget(); layout=w.layout()
        group=QGroupBox('AI режим — максимум бесплатной работы')
        form=QFormLayout(group)
        self.ai_mode_combo=QComboBox(); self.ai_mode_combo.addItem('0 ₽ — только Local AI','free'); self.ai_mode_combo.addItem('Экономный — Local AI + платный fallback по разрешению','economy'); self.ai_mode_combo.addItem('Premium — OpenAI','premium')
        idx=self.ai_mode_combo.findData(str(self.cfg.get('ai_mode','free'))); self.ai_mode_combo.setCurrentIndex(max(0,idx)); form.addRow('Режим AI:',self.ai_mode_combo)
        self.local_ai_url=QLineEdit(str(self.cfg.get('local_ai_url','http://127.0.0.1:8080/v1'))); form.addRow('Local AI URL:',self.local_ai_url)
        self.local_ai_model=QLineEdit(str(self.cfg.get('local_ai_model','local-model'))); form.addRow('Local AI model:',self.local_ai_model)
        self.paid_fallback=QCheckBox('Разрешить платный OpenAI fallback, если Local AI не справился'); self.paid_fallback.setChecked(bool(self.cfg.get('ai_allow_paid_fallback',False))); form.addRow(self.paid_fallback)
        self.paid_images=QCheckBox('Разрешить платные изображения OpenAI Image API'); self.paid_images.setChecked(bool(self.cfg.get('ai_allow_paid_images',False))); form.addRow(self.paid_images)
        warn=QLabel('Без этих двух галочек программа не делает платные fallback-запросы и не запускает платную генерацию изображений. Это основной режим защиты от случайных расходов.')
        warn.setWordWrap(True); form.addRow(warn)
        row=QHBoxLayout(); row.addWidget(self.primary('Проверить Local AI',self.test_local_ai)); row.addWidget(self.primary('Сохранить AI настройки',self.save_cfg)); row.addStretch(); form.addRow(row)
        layout.insertWidget(max(0,layout.count()-1),group)

    def save_cfg(self):
        if hasattr(self,'fields'):
            for k,e in self.fields.items():
                if hasattr(e,'text'):
                    value=e.text().strip()
                    if k=='openai_monthly_budget_usd':
                        try:value=max(0.0,float(value.replace(',','.') or 0))
                        except Exception:return QMessageBox.warning(self,'Настройки','Месячный бюджет OpenAI должен быть числом.')
                    self.cfg[k]=value
        if hasattr(self,'ai_mode_combo'):
            self.cfg['ai_mode']=str(self.ai_mode_combo.currentData() or 'free')
            self.cfg['local_ai_url']=self.local_ai_url.text().strip() or 'http://127.0.0.1:8080/v1'
            self.cfg['local_ai_model']=self.local_ai_model.text().strip() or 'local-model'
            self.cfg['ai_allow_paid_fallback']=bool(self.paid_fallback.isChecked())
            self.cfg['ai_allow_paid_images']=bool(self.paid_images.isChecked())
        save_settings(self.cfg)
        if hasattr(self,'ai_mode_status'):self.ai_mode_status.setText(self._ai_mode_text())
        QMessageBox.information(self,'Настройки','Сохранено. Режим 0 ₽ блокирует платные AI-запросы.')

    def test_local_ai(self):
        def job(progress,is_cancelled):
            progress(20,'Проверяю локальный AI сервер...')
            status=AIRouter(self.cfg).status()
            progress(100,'Проверка Local AI завершена')
            return status
        return self._start_worker('Local AI',job,self._local_ai_ready)

    def _local_ai_ready(self,status):
        local=(status or {}).get('local') or {}
        if local.get('ok'):
            msg=f"Local AI доступен: {local.get('url')}\nРежим: {(status or {}).get('mode')}\nПлатный fallback: {'разрешён' if (status or {}).get('paid_allowed') else 'запрещён'}"
            QMessageBox.information(self,'Local AI',msg)
        else:
            msg=f"Local AI пока недоступен: {local.get('url')}\n{local.get('error') or 'HTTP '+str(local.get('status'))}\n\nВ режиме 0 ₽ платный OpenAI автоматически НЕ включится."
            QMessageBox.warning(self,'Local AI',msg)


def run():
    app=QApplication([]); win=Main(); win.show(); app.exec()
