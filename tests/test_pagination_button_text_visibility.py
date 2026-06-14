from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton

from ui.theme import apply_app_theme
from ui.widgets.pagination_bar import PaginationBar


class PaginationButtonTextVisibilityTests(unittest.TestCase):
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
        self._page_changes: list[int] = []
        self.bar = PaginationBar(
            on_page_changed=self._page_changes.append,
            on_page_size_changed=lambda _size: None,
        )
        self.bar.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.bar.close()
        self.app.processEvents()

    def _page_buttons(self) -> list[QPushButton]:
        buttons: list[QPushButton] = []
        for idx in range(self.bar.page_buttons_layout.count()):
            item = self.bar.page_buttons_layout.itemAt(idx)
            widget = item.widget() if item is not None else None
            if isinstance(widget, QPushButton):
                buttons.append(widget)
        return buttons

    def test_page_buttons_expand_to_fit_text(self) -> None:
        self.bar.set_state(total_items=100, current_page=1, page_size=20)
        self.app.processEvents()

        buttons = self._page_buttons()
        self.assertEqual(["1", "2", "3", "4", "5"], [btn.text() for btn in buttons])
        for btn in buttons:
            self.assertGreaterEqual(
                btn.width(),
                btn.sizeHint().width(),
                f"button {btn.text()} width should not clip text",
            )

    def test_page_buttons_checked_state_and_click_callback(self) -> None:
        self.bar.set_state(total_items=100, current_page=3, page_size=20)
        self.app.processEvents()

        buttons = self._page_buttons()
        checked = [btn.text() for btn in buttons if btn.isChecked()]
        self.assertEqual(["3"], checked)

        target = next(btn for btn in buttons if btn.text() == "4")
        self.assertTrue(target.isEnabled())
        target.click()

        self.assertEqual([4], self._page_changes)


if __name__ == "__main__":
    unittest.main()
