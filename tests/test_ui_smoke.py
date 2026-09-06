import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

import unittest
from PySide6.QtWidgets import QApplication
from studio.ui_v34 import Main


class TestUISmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_main_window_constructs(self):
        win=Main()
        self.assertIsNotNone(win.centralWidget())
        self.assertIn('Marketplace AI Studio PRO',win.windowTitle())
        win.close()

    def test_core_pages_construct(self):
        win=Main()
        for method in ('dashboard','settings_page','products_page','factory'):
            getattr(win,method)()
            self.assertIsNotNone(win.stack.currentWidget())
        win.close()


if __name__=='__main__':
    unittest.main()
