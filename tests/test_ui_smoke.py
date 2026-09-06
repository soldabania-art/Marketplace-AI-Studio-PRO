import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ['MARKETPLACE_AI_TEST_MODE']='1'

import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QMessageBox
from studio.ui_v36 import Main


FAST_STATUS={'ollama':None,'ollama_running':False,'winget':None,'image_launchers':[],'image_running':False,'free_space_gb':100.0,'recommended_model':{'model':'qwen2.5:3b','estimated_gb':2.8,'tier':'balanced'}}
FAST_HW={'os':'Windows','machine':'AMD64','ram_gb':16.0,'gpu':None,'recommendation':'text_only'}
FAST_AI_STATUS={'mode':'free','local':{'ok':False,'error':'offline'},'local_images':{'ok':False,'error':'offline'},'paid_allowed':False,'paid_images_allowed':False}


class TestUISmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def _patches(self):
        return [
            patch('studio.ui_v30.probe_hardware',return_value=FAST_HW),
            patch('studio.ui_v30.AIRouter.status',return_value=FAST_AI_STATUS),
            patch('studio.ui_v31.setup_status',return_value=FAST_STATUS),
            patch('studio.ui_v32.setup_status',return_value=FAST_STATUS),
            patch('studio.ui_v33.manager_status',return_value={'ram':{},'gpu':{},'pressure':'normal','installed':[],'loaded':[]}),
            patch('studio.ui_v33.auto_optimize',return_value={'changed':False,'status':{'ram':{},'gpu':{},'pressure':'normal','installed':[],'loaded':[]}}),
            patch('requests.get',side_effect=RuntimeError('offline-ui-test')),
            patch.object(QMessageBox,'information',return_value=QMessageBox.Ok),
            patch.object(QMessageBox,'warning',return_value=QMessageBox.Ok),
            patch.object(QMessageBox,'critical',return_value=QMessageBox.Ok),
            patch.object(QMessageBox,'question',return_value=QMessageBox.No),
        ]

    def _new_window(self):
        patches=self._patches()
        for p in patches:p.start()
        try:return Main()
        finally:
            for p in reversed(patches):p.stop()

    def test_main_window_constructs(self):
        win=self._new_window(); self.assertIsNotNone(win.centralWidget()); self.assertIn('Marketplace AI Studio PRO',win.windowTitle()); win.close(); self.app.processEvents()

    def test_core_pages_construct(self):
        win=self._new_window(); patches=self._patches()
        for p in patches:p.start()
        try:
            for method in ('dashboard','settings_page','products_page','factory','reviews_page','profit_center'):
                getattr(win,method)(); self.assertIsNotNone(win.stack.currentWidget()); self.app.processEvents()
        finally:
            for p in reversed(patches):p.stop()
            win.close(); self.app.processEvents()


if __name__=='__main__': unittest.main()
