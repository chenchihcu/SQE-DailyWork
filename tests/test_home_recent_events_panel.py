from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton

from ui.theme import apply_app_theme
from ui.widgets.home_widget import HomeWidget
from ui.widgets.pagination_bar import PaginationBar


class _DummyMainWindow:
    def refresh_all_views(self) -> None:
        return

    def open_new_visit_dialog(self) -> None:
        return

    def open_new_anomaly_dialog(self) -> None:
        return


class HomeSimplifiedPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        apply_app_theme(cls.app)

    def setUp(self) -> None:
        self.widget = HomeWidget(_DummyMainWindow())
        self.widget.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.widget.close()
        self.app.processEvents()

    def _label_texts(self) -> list[str]:
        return [label.text() for label in self.widget.findChildren(QLabel)]

    def _button_by_text(self, text: str) -> QPushButton:
        for button in self.widget.findChildren(QPushButton):
            if button.text().strip() == text:
                return button
        self.fail(f"button not found: {text}")

    def test_home_renders_simplified_overview_and_reference_panels(self) -> None:
        labels = self._label_texts()
        self.assertTrue(any(label.startswith("本月品質概況") for label in labels))
        self.assertIn("功能導覽", labels)
        self.assertIn("快速操作", labels)

    def test_home_no_longer_exposes_recent_event_table(self) -> None:
        self.assertFalse(hasattr(self.widget, "recent_table"))
        self.assertFalse(hasattr(self.widget, "_recent_rows"))
        self.assertEqual([], self.widget.findChildren(PaginationBar))

        button_texts = [
            button.text().strip()
            for button in self.widget.findChildren(QPushButton)
            if button.text().strip()
        ]
        self.assertNotIn("新增異常", button_texts)
        self.assertNotIn("新增訪廠", button_texts)
        self.assertNotIn("基礎清單", button_texts)

    def test_home_quick_actions_use_enhanced_button_contract(self) -> None:
        expected = {
            "登錄訪廠紀錄": ("visit", "建立新的訪廠紀錄"),
            "登錄訪廠缺失": ("anomaly", "在訪廠紀錄中新增現場缺失"),
            "匯出週報簡報": ("report", "產生 SQE 週會簡報 PowerPoint"),
        }

        for text, (tone, tooltip) in expected.items():
            button = self._button_by_text(text)
            self.assertEqual("quickActionButton", button.property("role"))
            self.assertEqual(tone, button.property("tone"))
            self.assertGreaterEqual(button.minimumHeight(), 80)
            self.assertEqual(Qt.CursorShape.PointingHandCursor, button.cursor().shape())
            self.assertEqual(tooltip, button.toolTip())
            self.assertEqual(tooltip, button.statusTip())

        quick_panel = self.widget.findChild(QFrame, "HomeQuickActionPanel")
        self.assertIsNotNone(quick_panel)
        assert quick_panel is not None
        quick_layout = quick_panel.layout()
        self.assertIsNotNone(quick_layout)
        assert quick_layout is not None
        self.assertEqual(16, quick_layout.spacing())
        self.assertEqual(4, quick_layout.count())
        self.assertIn('QPushButton[role="quickActionButton"]', self.app.styleSheet())
        self.assertIn("text-align: left", self.app.styleSheet())

    def test_refresh_data_remains_noop_compatibility_hook(self) -> None:
        self.assertIsNone(self.widget.refresh_data())
        self.assertFalse(hasattr(self.widget, "recent_table"))


if __name__ == "__main__":
    unittest.main()
