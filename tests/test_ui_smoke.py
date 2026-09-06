import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from studio.ui_v35 import Main


FAST_STATUS={'ollama':None,'ollama_running':False,'winget':None,'image_launchers':[],'image_running':False,'free_space_gb':100.0,'recommended_model':{'model':'qwen2.5:3b','estimated_gb':2.8,'tier':'balanced'}}


class TestUISmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def _new_window(self):
        with patch('studio.ui_v32.setup_status',return_value=FAST_STATUS), patch('requests.get',side_effect=RuntimeError('offline-ui-test')):
            return Main()

    def test_main_window_constructs(self):
        win=self._new_window(); self.assertIsNotNone(win.centralWidget()); self.assertIn('Marketplace AI Studio PRO',win.windowTitle()); win.close()

    def test_core_pages_construct(self):
        win=self._new_window()
        with patch('studio.ui_v32.setup_status',return_value=FAST_STATUS), patch('requests.get',side_effect=RuntimeError('offline-ui-test')):
            for method in ('dashboard','settings_page','products_page','factory','reviews_page'):
                getattr(win,method)(); self.assertIsNotNone(win.stack.currentWidget())
        win.close()


if __name__=='__main__': unittest.main()
