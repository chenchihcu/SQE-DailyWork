from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton

from ui.main_window import MainWindow
from ui.widgets.home_widget import HomeWidget


class _DialogProbe:
    calls: list[dict] = []

    def __init__(self, *_args, **kwargs) -> None:
        self.calls.append(dict(kwargs))

    def exec(self) -> int:
        return 0


class _HomeHost:
    def __init__(self) -> None:
        self.visit_calls = 0
        self.defect_calls = 0
        self.anomaly_calls = 0

    def refresh_all_views(self) -> None:
        return

    def open_new_visit_dialog(self) -> None:
        self.visit_calls += 1

    def open_new_visit_defect_dialog(self) -> None:
        self.defect_calls += 1

    def open_new_anomaly_dialog(self) -> None:
        self.anomaly_calls += 1

    def open_warehouse_nonconforming_tracker(self) -> None:
        return


class LightweightVisitEntryRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_home_no_longer_owns_lightweight_visit_defect_button(self) -> None:
        host = _HomeHost()
        widget = HomeWidget(host)
        self.addCleanup(widget.close)

        button_texts = [
            button.text().strip()
            for button in widget.findChildren(QPushButton)
            if button.text().strip()
        ]

        self.assertNotIn("登錄訪廠缺失", button_texts)
        self.assertEqual(0, host.defect_calls)
        self.assertEqual(0, host.anomaly_calls)

    def test_main_window_keeps_formal_anomaly_entry_separate(self) -> None:
        _DialogProbe.calls = []
        with patch("ui.main_window.event_service.has_active_suppliers", return_value=True), patch(
            "ui.main_window.NewAnomalyDialog",
            _DialogProbe,
        ):
            window = MainWindow()
            self.addCleanup(window.close)
            window.open_new_anomaly_dialog()

        self.assertEqual([{}], _DialogProbe.calls)

    def test_main_window_lightweight_defect_entry_focuses_defect_note(self) -> None:
        _DialogProbe.calls = []
        with patch("ui.main_window.event_service.has_active_suppliers", return_value=True), patch(
            "ui.main_window.NewVisitDialog",
            _DialogProbe,
        ):
            window = MainWindow()
            self.addCleanup(window.close)
            window.open_new_visit_defect_dialog()

        self.assertEqual([{"focus_defect_note": True}], _DialogProbe.calls)


if __name__ == "__main__":
    unittest.main()
