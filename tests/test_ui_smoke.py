import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from studio.ui_v34 import Main


class TestUISmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def _new_window(self):
        # CI must not depend on localhost services, GitHub, WB, Ozon or OpenAI being reachable.
        with patch('requests.get',side_effect=RuntimeError('offline-ui-test')):
            return Main()

    def test_main_window_constructs(self):
        win=self._new_window()
        self.assertIsNotNone(win.centralWidget())
        self.assertIn('Marketplace AI Studio PRO',win.windowTitle())
        win.close()

    def test_core_pages_construct(self):
        win=self._new_window()
        with patch('requests.get',side_effect=RuntimeError('offline-ui-test')):
            for method in ('dashboard','settings_page','products_page','factory'):
                getattr(win,method)()
                self.assertIsNotNone(win.stack.currentWidget())
        win.close()


if __name__=='__main__':
    unittest.main()
