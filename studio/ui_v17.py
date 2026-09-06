from PySide6.QtWidgets import *
from PySide6.QtCore import Qt
from .ui_v16 import Main as BaseMain
from .core import products, save_settings
from .seo_batch import batch_score, optimization_payload
import json


class SetupWizard(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle('Первичная настройка Marketplace AI Studio PRO')
        self.resize(720, 560)
        v = QVBoxLayout(self)
        title = QLabel('Добро пожаловать в Marketplace AI Studio PRO')
        title.setStyleSheet('font-size:24px;font-weight:800')
        v.addWidget(title)
        info = QLabel('Подключите сервисы, которыми будете пользоваться. Секретные ключи сохраняются через системное хранилище учётных данных Windows.')
        info.setWordWrap(True); v.addWidget(info)
        form = QFormLayout(); self.fields = {}
        for label, key, secret in [
            ('OpenAI API key','openai_api_key',True),
            ('AI модель','openai_model',False),
            ('Wildberries token','wb_token',True),
            ('Ozon Client ID','ozon_client_id',False),
            ('Ozon API key','ozon_api_key',True),
            ('Telegram bot token','telegram_token',True),
            ('Telegram chat ID','telegram_chat_id',False),
        ]:
            e = QLineEdit(str(parent.cfg.get(key,'') or ''))
            if secret: e.setEchoMode(QLineEdit.Password)
            form.addRow(label, e); self.fields[key] = e
        v.addLayout(form)
        self.status = QLabel('Можно заполнить только нужные подключения и вернуться к остальным позже.')
        self.status.setWordWrap(True); v.addWidget(self.status)
        row = QHBoxLayout()
        test = QPushButton('Проверить WB'); test.clicked.connect(self.test_wb); row.addWidget(test)
        save = QPushButton('Сохранить и начать работу'); save.setObjectName('primary'); save.clicked.connect(self.finish); row.addWidget(save)
        v.addLayout(row)

    def values(self):
        d = dict(self.parent.cfg)
        d.update({k:e.text().strip() for k,e in self.fields.items()})
        return d

    def test_wb(self):
        try:
            from .connectors import WB
            WB(self.fields['wb_token'].text().strip()).test()
            self.status.setText('✓ Wildberries подключён')
        except Exception as e:
            self.status.setText('WB: ' + str(e))

    def finish(self):
        d = self.values(); d['setup_completed'] = True
        save_settings(d); self.parent.cfg = d; self.accept()


class Main(BaseMain):
    def __init__(self):
        self.seo_rows = []
        self.seo_ai_results = {}
        super().__init__()
        self.setWindowTitle('Marketplace AI Studio PRO — Mega Edition 1.7')
        if not self.cfg.get('setup_completed'):
            SetupWizard(self).exec()

    def dashboard(self):
        w, v = self.page('Dashboard 1.7', 'WB + Ozon + прибыль + риски + массовый SEO-анализ карточек')
        data = products()
        scored = batch_score([dict(r) for r in data]) if data else []
        avg = sum(x['score'] for x in scored) / len(scored) if scored else 0
        bad = sum(1 for x in scored if x['score'] < 70)
        cards = QHBoxLayout()
        metrics = [
            ('Товаров', str(len(data))),
            ('Продажи 30 дн.', self._money(self.live.get('gross'))),
            ('Оценка прибыли', self._money(sum(float(x.get('profit') or 0) for x in self.sku_live))),
            ('SEO score', f'{avg:.0f}/100' if scored else '—'),
            ('Карточек на улучшение', str(bad) if scored else '—'),
        ]
        for title, value in metrics:
            g=QGroupBox(title); q=QVBoxLayout(g); lab=QLabel(value); lab.setStyleSheet('font-size:21px;font-weight:800'); q.addWidget(lab); cards.addWidget(g)
        v.addLayout(cards)
        actions=QHBoxLayout()
        actions.addWidget(self.primary('Обновить WB бизнес-данные',self.refresh_wb_business_data))
        actions.addWidget(self.primary('Массовый SEO-анализ',self.seo_page))
        actions.addWidget(self.primary('Центр рисков и задач',self.tasks_page))
        actions.addWidget(self.primary('AI Фабрика',self.factory))
        v.addLayout(actions)
        self.live_status=QTextEdit(); self.live_status.setReadOnly(True); self.live_status.setMaximumHeight(300)
        if self.live or self.finance_live or self.ads_live: self.live_status.setPlainText(self._live_text_v16())
        else: self.live_status.setPlaceholderText('Обновите WB данные, затем запускайте SEO-анализ всего каталога.')
        v.addWidget(self.live_status)
        v.addStretch(); self.showp(w)

    def seo_page(self):
        w, v = self.page('SEO Центр 1.7', 'Автоматическая оценка всех карточек → выбор слабых → пакетная AI-оптимизация')
        top=QHBoxLayout(); top.addWidget(self.primary('1. Оценить все карточки',self.run_seo_scan)); top.addWidget(self.primary('2. AI-оптимизировать слабые',self.optimize_weak)); top.addStretch(); v.addLayout(top)
        self.seo_table=QTableWidget(); self.seo_table.setColumnCount(7)
        self.seo_table.setHorizontalHeaderLabels(['MP','ID','SKU','Название','Score','Класс','Проблемы'])
        self.seo_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.seo_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.seo_table.horizontalHeader().setSectionResizeMode(3,QHeaderView.Stretch); self.seo_table.horizontalHeader().setSectionResizeMode(6,QHeaderView.Stretch)
        v.addWidget(self.seo_table,2)
        self.seo_output=QTextEdit(); self.seo_output.setPlaceholderText('Здесь появятся AI-рекомендации по выбранным карточкам. Ничего не публикуется автоматически в маркетплейс.')
        v.addWidget(self.seo_output,1)
        self.seo_status=QLabel(''); self.seo_status.setObjectName('muted'); v.addWidget(self.seo_status)
        self.run_seo_scan(silent=True)
        self.showp(w)

    def run_seo_scan(self, silent=False):
        self.seo_rows = batch_score([dict(r) for r in products()])
        if hasattr(self,'seo_table'):
            self.seo_table.setRowCount(len(self.seo_rows))
            for i,r in enumerate(self.seo_rows):
                vals=[r['marketplace'],r['nm'],r['sku'],r['name'],r['score'],r['grade'],', '.join(r['issues']) or 'нет критичных']
                for j,val in enumerate(vals): self.seo_table.setItem(i,j,QTableWidgetItem(str(val)))
            avg=sum(x['score'] for x in self.seo_rows)/len(self.seo_rows) if self.seo_rows else 0
            self.seo_status.setText(f'Проверено карточек: {len(self.seo_rows)} | Средний SEO score: {avg:.1f}/100 | Ниже 70: {sum(1 for x in self.seo_rows if x["score"]<70)}')
        if not silent and not self.seo_rows: QMessageBox.information(self,'SEO','Сначала синхронизируйте товары.')

    def optimize_weak(self):
        weak=[x for x in self.seo_rows if x['score']<70][:20]
        if not weak:return QMessageBox.information(self,'SEO','Нет карточек с score ниже 70 или каталог ещё не просканирован.')
        self.seo_output.clear(); self.seo_status.setText(f'AI анализирует {len(weak)} слабых карточек...')
        QApplication.processEvents()
        completed=0
        for row in weak:
            try:
                prompt = json.dumps(optimization_payload(row), ensure_ascii=False, default=str)
                result = self.ai().seo_audit(prompt)
                self.seo_ai_results[row['nm']] = result
                self.seo_output.append(f"===== {row['nm']} | {row['name']} | score {row['score']} =====\n{result}\n")
                completed += 1
            except Exception as e:
                self.seo_output.append(f"===== {row['nm']} | ERROR =====\n{e}\n")
            self.seo_status.setText(f'AI-оптимизация: {completed}/{len(weak)}'); QApplication.processEvents()
        self.seo_status.setText(f'Готово. Проанализировано AI: {completed}. Изменения не отправлялись в WB/Ozon автоматически.')

    def settings_page(self):
        super().settings_page()


def run():
    app=QApplication([])
    win=Main(); win.show(); app.exec()
