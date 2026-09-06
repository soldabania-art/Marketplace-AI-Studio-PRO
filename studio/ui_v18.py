from PySide6.QtWidgets import *
from PySide6.QtCore import QThreadPool
from .ui_v17 import Main as BaseMain
from .core import products, save_project, generated_dir
from .seo_batch import optimization_payload
from .workers import Worker
from .ai_errors import friendly_ai_error, OpenAIQuotaError
import json, os


class Main(BaseMain):
    def __init__(self):
        self.pool = QThreadPool.globalInstance()
        self.active_worker = None
        super().__init__()
        self.setWindowTitle('Marketplace AI Studio PRO — Mega Edition 1.8')

    def dashboard(self):
        w, v = self.page('Dashboard 1.8', 'Максимальная автоматизация: AI создаёт тексты, SEO, визуальную концепцию, инфографику, анализирует магазин и формирует задачи')
        data = products()
        scored = self.seo_rows or []
        avg = sum(x['score'] for x in scored)/len(scored) if scored else 0
        cards = QHBoxLayout()
        for title,value in [
            ('Товаров',str(len(data))),('Продажи 30 дн.',self._money(self.live.get('gross'))),
            ('Прибыль',self._money(sum(float(x.get('profit') or 0) for x in self.sku_live))),
            ('SEO score',f'{avg:.0f}/100' if scored else '—'),('AI режим','AUTOPILOT')]:
            g=QGroupBox(title); q=QVBoxLayout(g); lab=QLabel(value); lab.setStyleSheet('font-size:21px;font-weight:800'); q.addWidget(lab); cards.addWidget(g)
        v.addLayout(cards)
        row=QHBoxLayout()
        row.addWidget(self.primary('AI Фабрика: создать карточку целиком',self.factory))
        row.addWidget(self.primary('Массовый SEO Автопилот',self.seo_page))
        row.addWidget(self.primary('Обновить WB + аналитику',self.refresh_wb_business_data))
        row.addWidget(self.primary('Риски и задачи',self.tasks_page)); v.addLayout(row)
        note=QLabel('Принцип 1.8: пользователь даёт фото и подтверждённые факты. AI сам делает тексты, SEO, структуру, визуальную концепцию и изображения. Публикация в маркетплейс будет автоматизирована только через подтверждённые официальные методы API и с защитным режимом перед записью.')
        note.setWordWrap(True); v.addWidget(note)
        self.live_status=QTextEdit(); self.live_status.setReadOnly(True); self.live_status.setMaximumHeight(270)
        if self.live or self.finance_live or self.ads_live:self.live_status.setPlainText(self._live_text_v16())
        else:self.live_status.setPlaceholderText('Обновите WB данные или откройте AI Фабрику.')
        v.addWidget(self.live_status); v.addStretch(); self.showp(w)

    def _show_ai_error(self,title,error):
        msg=friendly_ai_error(error)
        if hasattr(self,'seo_status'):
            self.seo_status.setText(msg)
        if hasattr(self,'factory_status'):
            self.factory_status.setText(msg)
        QMessageBox.warning(self,title,msg)

    def factory(self):
        w,v=self.page('AI Фабрика 1.8 — ONE CLICK','Фото + факты → AI сам создаёт тексты, SEO, характеристики, визуальную систему и готовые изображения инфографики')
        self.photo_label=QLabel(self.photo or 'Фото товара не выбрано'); v.addWidget(self.photo_label)
        v.addWidget(self.primary('Выбрать фото товара',self.pick_photo))
        self.fact=QTextEdit(); self.fact.setPlaceholderText('Укажите только подтверждённые факты о товаре. Всё остальное AI разработает сам: позиционирование, тексты, SEO, визуал, структуру и инфографику.'); self.fact.setFixedHeight(125); v.addWidget(self.fact)
        opts=QHBoxLayout(); opts.addWidget(QLabel('Слайдов:')); self.slide_count=QSpinBox(); self.slide_count.setRange(3,10); self.slide_count.setValue(6); opts.addWidget(self.slide_count); opts.addStretch(); v.addLayout(opts)
        buttons=QHBoxLayout(); buttons.addWidget(self.primary('СОЗДАТЬ ВСЮ КАРТОЧКУ AI',self.start_full_pack)); buttons.addWidget(self.primary('Отменить',self.cancel_active)); buttons.addWidget(self.primary('Открыть готовые изображения',self.open_generated)); v.addLayout(buttons)
        self.factory_progress=QProgressBar(); self.factory_progress.setRange(0,100); v.addWidget(self.factory_progress)
        self.factory_status=QLabel('Готово к запуску'); self.factory_status.setObjectName('muted'); v.addWidget(self.factory_status)
        self.cardout=QTextEdit(); self.cardout.setPlaceholderText('Здесь появится полное AI-наполнение карточки.'); v.addWidget(self.cardout,1); self.showp(w)

    def start_full_pack(self):
        if self.active_worker:return QMessageBox.information(self,'AI Фабрика','Уже выполняется задача. Дождитесь окончания или нажмите «Отменить».')
        photo=self.photo; facts=self.fact.toPlainText().strip(); count=self.slide_count.value()
        if not photo:return QMessageBox.information(self,'AI Фабрика','Выберите фото товара. Оно является основой для AI-визуала.')
        if not facts:return QMessageBox.information(self,'AI Фабрика','Добавьте подтверждённые факты о товаре, чтобы AI не выдумывал характеристики.')
        worker=Worker(lambda progress,is_cancelled:self.ai().full_product_pack(photo,facts,count,progress,is_cancelled))
        self.active_worker=worker; self.factory_progress.setValue(0); self.factory_status.setText('AI запущен...')
        worker.signals.progress.connect(lambda p,t:(self.factory_progress.setValue(p),self.factory_status.setText(t)))
        worker.signals.result.connect(self.full_pack_ready)
        worker.signals.error.connect(lambda e:self._show_ai_error('AI Фабрика',e))
        worker.signals.finished.connect(self.worker_finished)
        self.pool.start(worker)

    def full_pack_ready(self,result):
        if result.get('cancelled'):
            self.factory_status.setText('Остановлено пользователем'); return
        self.card=result.get('card') or {}; images=result.get('images') or []
        name=self.card.get('product_type','AI карточка') if isinstance(self.card,dict) else 'AI карточка'
        save_project(name,self.photo,self.card)
        self.cardout.setPlainText(json.dumps({'card':self.card,'generated_images':images},ensure_ascii=False,indent=2))
        self.factory_progress.setValue(100); self.factory_status.setText(f'Полная карточка готова. Создано изображений: {len(images)}')
        QMessageBox.information(self,'AI Фабрика',f'Готово: тексты + SEO + визуальная концепция + {len(images)} изображений.')

    def cancel_active(self):
        if self.active_worker:
            self.active_worker.cancel()
            if hasattr(self,'factory_status'):self.factory_status.setText('Остановка после текущего запроса...')
            if hasattr(self,'seo_status'):self.seo_status.setText('Остановка после текущего запроса...')

    def worker_finished(self):
        self.active_worker=None

    def seo_page(self):
        w,v=self.page('SEO Автопилот 1.8','AI находит слабые карточки и в фоне создаёт для них новое наполнение: заголовки, описания, SEO и план визуала')
        top=QHBoxLayout(); top.addWidget(self.primary('1. Просканировать каталог',self.run_seo_scan)); top.addWidget(self.primary('2. Автоматически переделать слабые AI',self.start_seo_autopilot)); top.addWidget(self.primary('Отменить',self.cancel_active)); top.addStretch(); v.addLayout(top)
        self.seo_table=QTableWidget(); self.seo_table.setColumnCount(7); self.seo_table.setHorizontalHeaderLabels(['MP','ID','SKU','Название','Score','Класс','Проблемы']); self.seo_table.horizontalHeader().setSectionResizeMode(3,QHeaderView.Stretch); self.seo_table.horizontalHeader().setSectionResizeMode(6,QHeaderView.Stretch); v.addWidget(self.seo_table,2)
        self.seo_progress=QProgressBar(); v.addWidget(self.seo_progress)
        self.seo_status=QLabel(''); self.seo_status.setWordWrap(True); v.addWidget(self.seo_status)
        self.seo_output=QTextEdit(); self.seo_output.setPlaceholderText('AI-переработанные варианты карточек появятся здесь.'); v.addWidget(self.seo_output,1)
        self.run_seo_scan(silent=True); self.showp(w)

    def start_seo_autopilot(self):
        all_weak=[x for x in self.seo_rows if x['score']<70]
        if not all_weak:return QMessageBox.information(self,'SEO','Нет слабых карточек для обработки.')
        if self.active_worker:return QMessageBox.information(self,'SEO','Другая AI-задача уже выполняется.')
        maximum=min(len(all_weak),20)
        count,ok=QInputDialog.getInt(self,'SEO Автопилот','Сколько слабых карточек обработать сейчас?\nКаждая карточка = отдельный платный OpenAI API запрос.',min(5,maximum),1,maximum,1)
        if not ok:return
        answer=QMessageBox.question(self,'SEO Автопилот',f'Запустить {count} платных AI-запросов?\n\nПри отсутствии API-баланса пакет остановится после первой ошибки и покажет понятное сообщение.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if answer!=QMessageBox.Yes:return
        weak=all_weak[:count]
        def job(progress,is_cancelled):
            out={}; total=len(weak)
            for i,row in enumerate(weak,1):
                if is_cancelled():break
                progress(int((i-1)/total*100),f'AI переделывает карточку {i}/{total}: {row["name"]}')
                payload=json.dumps(optimization_payload(row),ensure_ascii=False,default=str)
                try:
                    out[row['nm']]=self.ai().seo_rebuild(payload)
                except OpenAIQuotaError:
                    raise
            progress(100,'Пакетная AI-оптимизация завершена')
            return out
        worker=Worker(job); self.active_worker=worker; self.seo_progress.setValue(0); self.seo_status.setText(f'Запущено: {count} карточек')
        worker.signals.progress.connect(lambda p,t:(self.seo_progress.setValue(p),self.seo_status.setText(t)))
        worker.signals.result.connect(self.seo_autopilot_ready)
        worker.signals.error.connect(lambda e:self._show_ai_error('SEO Автопилот',e))
        worker.signals.finished.connect(self.worker_finished); self.pool.start(worker)

    def seo_autopilot_ready(self,result):
        self.seo_ai_results.update(result or {}); self.seo_output.clear()
        for nm,text in (result or {}).items():self.seo_output.append(f'===== {nm} =====\n{text}\n')
        self.seo_status.setText(f'AI полностью переработал карточек: {len(result or {})}. Готово к следующему этапу автоматической публикации через официальные API.')

    def open_generated(self):
        p=str(generated_dir())
        try:
            if os.name=='nt':os.startfile(p)
            else:QMessageBox.information(self,'Папка',p)
        except Exception:QMessageBox.information(self,'Папка',p)


def run():
    app=QApplication([]); win=Main(); win.show(); app.exec()
