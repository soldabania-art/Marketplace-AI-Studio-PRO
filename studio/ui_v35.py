import logging
from PySide6.QtCore import Qt
from PySide6.QtWidgets import *

from .ui_v34 import Main as BaseMain
from .review_autopilot import ReviewAutopilot
from .safety_control import can_execute, record_usage, audit
from . import __version__

logger=logging.getLogger('ui.reviews')


class Main(BaseMain):
    """3.5: complete manual WB reputation workflow with AI drafting and guarded send."""

    def __init__(self):
        self.current_reviews=[]; self.selected_review=None; self.selected_review_analysis=None
        super().__init__()
        self.setWindowTitle(f'Marketplace AI Studio PRO — Mega Edition {__version__} REPUTATION CENTER')

    def reviews_page(self):
        w,v=self.page('Отзывы WB 3.5','Загрузить → выбрать отзыв → AI-анализ и черновик → отредактировать → отправить. Негативные и рискованные отзывы всегда остаются на ручном подтверждении.')
        top=QHBoxLayout(); self.rev_filter=QComboBox(); self.rev_filter.addItems(['Без ответа','С ответом']); top.addWidget(QLabel('Показывать:')); top.addWidget(self.rev_filter); top.addWidget(self.primary('Загрузить отзывы',self.load_reviews)); top.addStretch(); v.addLayout(top)
        split=QSplitter(Qt.Horizontal)
        left=QWidget(); lv=QVBoxLayout(left); self.rev_table=QTableWidget(); self.rev_table.setColumnCount(6); self.rev_table.setHorizontalHeaderLabels(['ID','★','Товар','Покупатель','Отзыв','Дата']); self.rev_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.rev_table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.rev_table.horizontalHeader().setSectionResizeMode(4,QHeaderView.Stretch); self.rev_table.itemSelectionChanged.connect(self._review_selected); lv.addWidget(self.rev_table,1); split.addWidget(left)
        right=QWidget(); rv=QVBoxLayout(right); self.review_meta=QLabel('Выберите отзыв в таблице.'); self.review_meta.setWordWrap(True); rv.addWidget(self.review_meta)
        self.review_text=QTextEdit(); self.review_text.setReadOnly(True); self.review_text.setPlaceholderText('Текст выбранного отзыва'); self.review_text.setMinimumHeight(120); rv.addWidget(self.review_text)
        self.review_risk=QLabel('AI-анализ ещё не выполнен.'); self.review_risk.setWordWrap(True); rv.addWidget(self.review_risk)
        rv.addWidget(self.primary('Создать AI-черновик ответа',self.generate_selected_review_reply))
        self.review_reply_edit=QTextEdit(); self.review_reply_edit.setPlaceholderText('Здесь появится черновик. Перед отправкой его можно полностью отредактировать.'); self.review_reply_edit.setMinimumHeight(160); rv.addWidget(self.review_reply_edit,1)
        self.review_send_btn=self.primary('Отправить ответ в WB',self.send_selected_review_reply); rv.addWidget(self.review_send_btn); split.addWidget(right); split.setSizes([760,520]); v.addWidget(split,1)
        self.review_status=QLabel('Отзывы ещё не загружены.'); self.review_status.setWordWrap(True); v.addWidget(self.review_status); self.showp(w)
        if self.current_reviews: self._reviews_ready(self.current_reviews)

    def _review_selected(self):
        if not hasattr(self,'rev_table'): return
        row=self.rev_table.currentRow()
        if row<0 or row>=len(self.current_reviews): return
        raw=self.current_reviews[row]; self.selected_review=ReviewAutopilot.normalize(raw); self.selected_review_analysis=None
        product=(raw.get('productDetails') or {}) if isinstance(raw,dict) else {}
        name=product.get('productName') or product.get('nmId') or self.selected_review.get('nm_id') or '—'
        self.review_meta.setText(f"Оценка: {self.selected_review.get('rating',0)}/5 · товар: {name} · feedback ID: {self.selected_review.get('id') or '—'}")
        self.review_text.setPlainText(self.selected_review.get('text') or '(покупатель не оставил текст)'); self.review_reply_edit.clear(); self.review_risk.setText('AI-анализ ещё не выполнен.')

    def generate_selected_review_reply(self):
        if not self.selected_review: return QMessageBox.information(self,'Отзывы WB','Сначала выберите отзыв.')
        raw=dict(self.selected_review.get('raw') or self.selected_review)
        def job(progress,is_cancelled):
            progress(15,'Отзывы: AI классифицирует риск...'); engine=ReviewAutopilot(self.wb(),self.ai()); item=engine.classify(raw)
            if is_cancelled(): return {'cancelled':True}
            progress(55,'Отзывы: AI создаёт черновик...'); item['reply']=self.ai().review_reply(item.get('text',''),item.get('rating',0))
            item['safe_auto']=item.get('rating',0)>=4 and str(item.get('risk','medium')).lower()=='low' and not bool(item.get('needs_human')) and bool(item.get('id'))
            progress(100,'Черновик ответа готов'); return {'cancelled':False,'item':item}
        return self._start_worker('AI ответ на отзыв',job,self._review_draft_ready)

    def _review_draft_ready(self,result):
        if (result or {}).get('cancelled'): return
        item=(result or {}).get('item') or {}; self.selected_review_analysis=item
        risk=str(item.get('risk') or 'medium').lower(); human=bool(item.get('needs_human')); reason=str(item.get('reason') or '')
        mode='низкий риск' if item.get('safe_auto') else 'требуется ручное подтверждение'
        self.review_risk.setText(f"AI: sentiment={item.get('sentiment','—')} · risk={risk} · {mode}. {reason}")
        self.review_reply_edit.setPlainText(str(item.get('reply') or '')); self.review_status.setText('Черновик готов. Проверьте и отредактируйте текст перед отправкой.')

    def send_selected_review_reply(self):
        if not self.selected_review: return QMessageBox.information(self,'Отзывы WB','Сначала выберите отзыв.')
        fid=str(self.selected_review.get('id') or ''); text=self.review_reply_edit.toPlainText().strip() if hasattr(self,'review_reply_edit') else ''
        if not fid: return QMessageBox.warning(self,'Отзывы WB','У отзыва нет feedback ID — отправка невозможна.')
        if len(text)<2: return QMessageBox.warning(self,'Отзывы WB','Введите текст ответа.')
        allowed,reason=can_execute(self.cfg,'review_reply',1)
        if not allowed:
            audit('review_reply','WB',fid,'blocked',{'reason':reason,'source':'manual_review_center'}); return QMessageBox.warning(self,'Защита AUTOPILOT',reason)
        analysis=self.selected_review_analysis or {}; risk=str(analysis.get('risk') or 'unknown'); rating=int(self.selected_review.get('rating') or 0)
        warning=f'Отправить этот ответ покупателю в Wildberries?\n\nОценка: {rating}/5 · AI risk: {risk}\n\nПосле отправки это внешнее действие.'
        if QMessageBox.question(self,'Подтверждение отправки',warning,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes: return
        def job(progress,is_cancelled):
            if is_cancelled(): return {'cancelled':True}
            progress(40,'WB: отправляю ответ...'); ok=self.wb().answer_review(fid,text); progress(100,'Ответ отправлен'); return {'cancelled':False,'ok':ok,'id':fid,'text':text,'rating':rating,'risk':risk}
        return self._start_worker('Отправка ответа WB',job,self._review_sent)

    def _review_sent(self,result):
        if (result or {}).get('cancelled'): return
        fid=str((result or {}).get('id') or '')
        record_usage('review_reply','WB',fid,1,{'source':'manual_review_center','rating':(result or {}).get('rating'),'risk':(result or {}).get('risk')}); audit('review_reply','WB',fid,'done',{'source':'manual_review_center'})
        self.review_status.setText('Ответ успешно отправлен в Wildberries.'); QMessageBox.information(self,'Отзывы WB','Ответ отправлен. Список будет обновлён.'); self.selected_review=None; self.selected_review_analysis=None; self.load_reviews()


def run():
    app=QApplication([]); win=Main(); win.show(); app.exec()
