from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui.theme import apply_app_theme
from ui.widgets.home_widget import HomeWidget


class _DummyMainWindow:
    def refresh_all_views(self) -> None:
        return

    def open_new_visit_dialog(self) -> None:
        return

    def open_new_anomaly_dialog(self) -> None:
        return

    def open_warehouse_nonconforming_tracker(self) -> None:
        return


class HomeSimplifiedActionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        apply_app_theme(cls.app)


    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            cls.app.quit()

    def setUp(self) -> None:
        self.widget = HomeWidget(_DummyMainWindow())
        self.widget.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.widget.close()
        self.app.processEvents()

    def test_home_does_not_own_event_row_actions(self) -> None:
        self.assertFalse(hasattr(self.widget, "_event_actions"))
        self.assertFalse(hasattr(self.widget, "_on_recent_row_clicked"))
        self.assertFalse(hasattr(self.widget, "open_edit_anomaly_dialog"))
        self.assertFalse(hasattr(self.widget, "delete_anomaly"))
        self.assertFalse(hasattr(self.widget, "open_visit_detail"))


if __name__ == "__main__":
    unittest.main()
