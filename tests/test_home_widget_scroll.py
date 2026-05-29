from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame, QScrollArea

from ui.theme import apply_app_theme
from ui.widgets.home_widget import HomeWidget


class MockMainWindow:
    def refresh_all_views(self) -> None:
        return

    def open_new_visit_dialog(self) -> None:
        return

    def open_new_anomaly_dialog(self) -> None:
        return


class HomeWidgetLayoutContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        apply_app_theme(cls.app)

    def test_home_widget_uses_direct_simplified_layout(self):
        main_window = MockMainWindow()
        widget = HomeWidget(main_window)

        self.assertIsNone(widget.findChild(QScrollArea, "HomeScrollArea"))
        self.assertIsNone(widget.findChild(QFrame, "InfoPanel"))
        self.assertIsNotNone(widget.findChild(QFrame, "HomeQuickActionPanel"))
        self.assertIsNotNone(widget.findChild(QFrame, "HomeFeaturesPanel"))
        widget.close()


if __name__ == "__main__":
    unittest.main()
