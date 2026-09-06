import os
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import *
from .ui_v25 import Main as BaseMain
from .core import replace_products
from .workers import Worker
from .ozon_center import OzonCatalogCenter
from .diagnostics import log_path
from .updater import check_latest, download_installer, launch_installer
from . import __version__


class Main(BaseMain):
    def __init__(self):
        self.update_info=None
        super().__init__()
        self.setWindowTitle(f'Marketplace AI Studio PRO — Mega Edition {__version__} PRODUCTION OPS')
        QTimer.singleShot(45000,lambda:self.check_updates(True))

    def dashboard(self):
        super().dashboard()
        w=self.stack.currentWidget(); layout=w.layout()
        group=QGroupBox('PRODUCTION OPS 2.6')
        form=QFormLayout(group)
        state=QLabel('AI-визуал: исходный товар сохраняется + точный русский текст наносится приложением')
        state.setWordWrap(True); form.addRow('Карточки:',state)
        oz=QLabel('Ozon: безопасный read-only контур каталога. Write API не включается без отдельной верификации.')
        oz.setWordWrap(True); form.addRow('Ozon:',oz)
        row=QHBoxLayout()
        row.addWidget(self.primary('Синхронизировать весь Ozon',self.sync_all_ozon))
        row.addWidget(self.primary('Проверить обновление',lambda:self.check_updates(False)))
        row.addWidget(self.primary('Открыть логи',self.open_logs))
        form.addRow(row)
        self.ops_status=QLabel('Версия приложения: '+__version__); self.ops_status.setWordWrap(True); form.addRow(self.ops_status)
        layout.addWidget(group)

    def open_logs(self):
        p=log_path().parent
        try:
            if os.name=='nt':os.startfile(str(p))
            else:QMessageBox.information(self,'Логи',str(p))
        except Exception as e:QMessageBox.critical(self,'Логи',str(e))

    def sync_all_ozon(self):
        if self.active_worker:return QMessageBox.information(self,'Ozon','Другая задача уже выполняется.')
        if not self.cfg.get('ozon_client_id') or not self.cfg.get('ozon_api_key'):
            return QMessageBox.information(self,'Ozon','Сначала подключите Ozon Client ID и API key.')
        center=OzonCatalogCenter(self.ozon())
        worker=Worker(lambda progress,is_cancelled:center.products_all(10000,progress))
        self.active_worker=worker
        if hasattr(self,'ops_status'):worker.signals.progress.connect(lambda p,t:self.ops_status.setText(t))
        worker.signals.result.connect(self._ozon_sync_ready)
        worker.signals.error.connect(lambda e:QMessageBox.critical(self,'Ozon',str(e)))
        worker.signals.finished.connect(self.worker_finished)
        self.pool.start(worker)

    def _ozon_sync_ready(self,items):
        replace_products('Ozon',items or [])
        if hasattr(self,'ops_status'):self.ops_status.setText(f'Ozon синхронизирован: {len(items or [])} товаров')
        QMessageBox.information(self,'Ozon',f'Каталог синхронизирован: {len(items or [])} товаров. Контур остаётся read-only до проверки write API.')

    def check_updates(self,silent=False):
        if self.active_worker:
            if not silent:QMessageBox.information(self,'Обновление','Сейчас выполняется другая задача.')
            return
        worker=Worker(lambda progress,is_cancelled:check_latest())
        self.active_worker=worker
        worker.signals.result.connect(lambda info:self._update_checked(info,silent))
        worker.signals.error.connect(lambda e:self._update_error(e,silent))
        worker.signals.finished.connect(self.worker_finished)
        self.pool.start(worker)

    def _update_error(self,error,silent):
        if hasattr(self,'ops_status'):self.ops_status.setText('Проверка обновлений: '+str(error))
        if not silent:QMessageBox.warning(self,'Обновление',str(error))

    def _update_checked(self,info,silent=False):
        self.update_info=info or {}
        if not self.update_info.get('newer'):
            if hasattr(self,'ops_status'):self.ops_status.setText(f"Установлена актуальная версия {__version__}")
            if not silent:QMessageBox.information(self,'Обновление','У вас актуальная версия приложения.')
            return
        tag=self.update_info.get('tag') or 'новая версия'
        if hasattr(self,'ops_status'):self.ops_status.setText('Доступно обновление: '+tag)
        answer=QMessageBox.question(self,'Доступно обновление',f'Найдена версия {tag}. Скачать установщик и запустить обновление?',QMessageBox.Yes|QMessageBox.No,QMessageBox.Yes)
        if answer==QMessageBox.Yes:self.download_update()

    def download_update(self):
        if not self.update_info:return
        if self.active_worker:return QMessageBox.information(self,'Обновление','Другая задача уже выполняется.')
        worker=Worker(lambda progress,is_cancelled:download_installer(self.update_info,lambda p:progress(p,f'Скачивание обновления: {p}%')))
        self.active_worker=worker
        if hasattr(self,'ops_status'):worker.signals.progress.connect(lambda p,t:self.ops_status.setText(t))
        worker.signals.result.connect(self._update_downloaded)
        worker.signals.error.connect(lambda e:QMessageBox.critical(self,'Обновление',str(e)))
        worker.signals.finished.connect(self.worker_finished)
        self.pool.start(worker)

    def _update_downloaded(self,path):
        try:
            if hasattr(self,'ops_status'):self.ops_status.setText('Обновление скачано: '+str(path))
            launch_installer(path)
            QMessageBox.information(self,'Обновление','Установщик обновления запущен. Закройте приложение перед продолжением установки.')
        except Exception as e:QMessageBox.critical(self,'Обновление',str(e))


def run():
    app=QApplication([]); win=Main(); win.show(); app.exec()
