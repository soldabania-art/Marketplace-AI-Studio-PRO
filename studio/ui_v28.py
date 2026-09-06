import json, os, logging
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import *
from .ui_v27 import Main as BaseMain
from .workers import Worker
from . import __version__

logger=logging.getLogger('ui.preview')


class Main(BaseMain):
    """2.8: interactive AI preview with per-slide regeneration before WB publication."""

    def __init__(self):
        self.preview_slide_index=0
        super().__init__()
        self.setWindowTitle(f'Marketplace AI Studio PRO — Mega Edition {__version__} AI PREVIEW')

    def ai_preview_page(self):
        pack=self.preview_pack or {}; card=pack.get('card') or {}; images=list(pack.get('images') or []); nm=pack.get('target_wb_nm') or ''
        w,v=self.page('Предпросмотр AI-карточки 2.8','Проверьте текст и каждый слайд. Можно перегенерировать только выбранный слайд, не оплачивая повторную генерацию всей карточки.')
        head=QGroupBox('Целевая карточка'); hf=QFormLayout(head); hf.addRow('WB nmID:',QLabel(nm or 'Черновик / без публикации')); hf.addRow('AI-изображений:',QLabel(str(len(images)))); v.addWidget(head)
        split=QSplitter(Qt.Horizontal)
        left=QWidget(); lv=QVBoxLayout(left); lv.addWidget(QLabel('Тексты / SEO / характеристики'))
        self.preview_text=QTextEdit(); self.preview_text.setPlainText(json.dumps(card,ensure_ascii=False,indent=2)); lv.addWidget(self.preview_text,1); split.addWidget(left)
        right=QWidget(); rv=QVBoxLayout(right)
        controls=QHBoxLayout(); controls.addWidget(QLabel('Слайд:')); self.preview_slide_combo=QComboBox()
        for i,path in enumerate(images,1):self.preview_slide_combo.addItem(f'Слайд {i}',i-1)
        self.preview_slide_combo.currentIndexChanged.connect(self._show_preview_slide); controls.addWidget(self.preview_slide_combo)
        controls.addWidget(self.primary('Перегенерировать этот слайд',self.regenerate_selected_slide)); controls.addStretch(); rv.addLayout(controls)
        self.preview_image=QLabel('Нет изображения'); self.preview_image.setAlignment(Qt.AlignCenter); self.preview_image.setMinimumSize(420,500); rv.addWidget(self.preview_image,1)
        self.preview_path=QLabel(''); self.preview_path.setWordWrap(True); self.preview_path.setTextInteractionFlags(Qt.TextSelectableByMouse); rv.addWidget(self.preview_path)
        self.preview_regen_status=QLabel(''); self.preview_regen_status.setWordWrap(True); rv.addWidget(self.preview_regen_status)
        split.addWidget(right); split.setSizes([560,560]); v.addWidget(split,1)
        row=QHBoxLayout(); row.addWidget(self.primary('Принять комплект → очередь WB',self.accept_ai_preview)); row.addWidget(self.primary('Вернуться в AI Фабрику',self.factory)); row.addWidget(self.danger('Отклонить комплект',self.reject_ai_preview)); v.addLayout(row)
        self.showp(w); self._show_preview_slide(0)

    def _show_preview_slide(self,index=None):
        pack=self.preview_pack or {}; images=list(pack.get('images') or [])
        if index is None and hasattr(self,'preview_slide_combo'):index=self.preview_slide_combo.currentIndex()
        try:index=int(index)
        except Exception:index=0
        self.preview_slide_index=max(0,min(index,max(0,len(images)-1)))
        if not images:
            if hasattr(self,'preview_image'):self.preview_image.setText('Изображения отсутствуют')
            return
        path=str(images[self.preview_slide_index])
        if hasattr(self,'preview_path'):self.preview_path.setText(path)
        if hasattr(self,'preview_image'):
            if os.path.exists(path):
                pix=QPixmap(path); self.preview_image.setPixmap(pix.scaled(500,650,Qt.KeepAspectRatio,Qt.SmoothTransformation))
            else:self.preview_image.setPixmap(QPixmap()); self.preview_image.setText('Файл не найден:\n'+path)

    def regenerate_selected_slide(self):
        pack=self.preview_pack or {}; card=pack.get('card') or {}; images=list(pack.get('images') or [])
        if not images:return QMessageBox.information(self,'AI визуал','Нет слайдов для перегенерации.')
        try:edited=json.loads(self.preview_text.toPlainText())
        except Exception as e:return QMessageBox.warning(self,'AI визуал','Сначала исправьте JSON карточки: '+str(e))
        plan=edited.get('infographic_plan') or []
        idx=self.preview_slide_combo.currentData() if hasattr(self,'preview_slide_combo') else self.preview_slide_index
        try:idx=int(idx)
        except Exception:idx=0
        if idx<0 or idx>=len(plan):return QMessageBox.warning(self,'AI визуал','Для выбранного слайда нет плана инфографики.')
        answer=QMessageBox.question(self,'Перегенерация слайда',f'Перегенерировать только слайд {idx+1}? Это один отдельный платный запрос Image API.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if answer!=QMessageBox.Yes:return
        one_card=dict(edited); one_card['infographic_plan']=[plan[idx]]; photo=pack.get('photo') or getattr(self,'photo',''); project=f"regen_{pack.get('target_wb_nm') or 'draft'}_{idx+1}"
        def job(progress,is_cancelled):
            progress(10,f'AI перегенерирует слайд {idx+1}...')
            paths=self.ai().generate_infographics(one_card,project,1,progress,is_cancelled,source_photo=photo)
            if not paths:raise RuntimeError('Image API не вернул новый слайд.')
            return {'index':idx,'path':str(paths[0]),'card':edited}
        if hasattr(self,'preview_regen_status'):self.preview_regen_status.setText(f'Слайд {idx+1}: генерация...')
        return self._start_worker('Перегенерация AI-слайда',job,self._slide_regenerated)

    def _slide_regenerated(self,result):
        pack=self.preview_pack or {}; images=list(pack.get('images') or []); idx=int(result.get('index',0)); path=str(result.get('path') or '')
        if not path:return
        if 0<=idx<len(images):images[idx]=path
        pack['images']=images; pack['card']=result.get('card') or pack.get('card') or {}; self.preview_pack=pack; self.card=pack['card']; self.last_pack_images=images
        if hasattr(self,'preview_text'):self.preview_text.setPlainText(json.dumps(pack['card'],ensure_ascii=False,indent=2))
        if hasattr(self,'preview_regen_status'):self.preview_regen_status.setText(f'Слайд {idx+1} заменён новым вариантом. Остальные слайды не тронуты.')
        if hasattr(self,'preview_slide_combo'):self.preview_slide_combo.setCurrentIndex(idx)
        self._show_preview_slide(idx)


def run():
    app=QApplication([]); win=Main(); win.show(); app.exec()
