from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from ui.window_sizing import fit_widget_to_available_screen


class WindowSizingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_fit_widget_preserves_supported_minimum_by_default(self) -> None:
        widget = QWidget()
        try:
            fit_widget_to_available_screen(
                widget,
                preferred_width=1360,
                preferred_height=860,
                minimum_width=1024,
                minimum_height=680,
                maximum_width=1920,
                maximum_height=1200,
            )
            self.assertEqual(1024, widget.minimumWidth())
            self.assertEqual(680, widget.minimumHeight())
            self.assertGreaterEqual(widget.width(), 1024)
            self.assertGreaterEqual(widget.height(), 680)
        finally:
            widget.close()

    def test_fit_widget_can_shrink_minimum_for_dialog_visibility(self) -> None:
        widget = QWidget()
        try:
            fit_widget_to_available_screen(
                widget,
                preferred_width=1200,
                preferred_height=900,
                minimum_width=1200,
                minimum_height=900,
                margin_x=40,
                margin_y=60,
                shrink_minimum_to_screen=True,
            )
            self.assertLessEqual(widget.width(), 1200)
            self.assertLessEqual(widget.height(), 900)
            self.assertLessEqual(widget.minimumWidth(), widget.width())
            self.assertLessEqual(widget.minimumHeight(), widget.height())
        finally:
            widget.close()


if __name__ == "__main__":
    unittest.main()
