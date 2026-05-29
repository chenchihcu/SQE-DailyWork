from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication, QPushButton

from ui.theme import apply_app_theme
from ui.widgets import defect_list_widget
from ui.widgets.defect_list_widget import EventListWidget
from ui.widgets.pagination_bar import PaginationBar


class _DummyMainWindow:
    def refresh_all_views(self) -> None:
        return

    def open_new_visit_dialog(self) -> None:
        return

    def open_new_anomaly_dialog(self) -> None:
        return


class MicroInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        apply_app_theme(cls.app)

    def _drain_events(self) -> None:
        self.app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def _sample_rows(self) -> list[dict]:
        return [
            {
                "event_id": "a1",
                "event_date": "2026-05-01",
                "event_type": "ANOMALY",
                "supplier_name": "供應商-A",
                "product_name": "產品-A",
                "product_stage": "量產",
                "work_order_no": "WO-001",
                "production_qty": 5,
                "content": "尺寸異常",
                "status": "待處理",
                "linked_visit_id": "",
            }
        ]

    def test_pagination_buttons_have_clickable_affordance(self) -> None:
        page_changes: list[int] = []
        bar = PaginationBar(
            on_page_changed=page_changes.append,
            on_page_size_changed=lambda _size: None,
        )
        bar.set_state(total_items=100, current_page=3, page_size=10)
        bar.show()
        self._drain_events()

        for button in (bar.first_btn, bar.prev_btn, bar.next_btn, bar.last_btn):
            self.assertEqual(
                Qt.CursorShape.PointingHandCursor,
                button.cursor().shape(),
                f"{button.toolTip()} should show clickable cursor",
            )
            self.assertTrue(button.statusTip())

        page_buttons = [
            item.widget()
            for index in range(bar.page_buttons_layout.count())
            if (item := bar.page_buttons_layout.itemAt(index)) is not None
        ]
        page_buttons = [button for button in page_buttons if isinstance(button, QPushButton)]
        self.assertGreaterEqual(len(page_buttons), 3)
        for button in page_buttons:
            self.assertEqual(Qt.CursorShape.PointingHandCursor, button.cursor().shape())
            self.assertEqual(f"第 {button.text()} 頁", button.toolTip())
            self.assertEqual(f"前往第 {button.text()} 頁", button.statusTip())

        bar.close()
        self._drain_events()

    def test_event_management_controls_and_table_have_affordances(self) -> None:
        original_list_events = defect_list_widget.event_service.list_events
        defect_list_widget.event_service.list_events = lambda _filters: self._sample_rows()
        try:
            widget = EventListWidget(_DummyMainWindow(), mode="query")
            widget.show()
            self._drain_events()

            assert widget.event_scope_tab_bar is not None
            self.assertEqual(
                Qt.CursorShape.PointingHandCursor,
                widget.event_scope_tab_bar.cursor().shape(),
            )
            self.assertEqual("切換事件管理分類", widget.event_scope_tab_bar.toolTip())

            self.assertEqual(
                Qt.CursorShape.PointingHandCursor,
                widget.table.viewport().cursor().shape(),
            )
            self.assertIn("動作選單", widget.table.toolTip())
            self.assertIn("動作選單", widget.table.viewport().toolTip())

            buttons = {button.text(): button for button in widget.findChildren(QPushButton)}
            for text, tooltip in {
                "查詢": "套用篩選條件",
                "清除條件": "清除目前篩選條件",
                "新增訪廠": "建立新的訪廠紀錄",
                "新增異常": "建立新的異常單",
            }.items():
                self.assertIn(text, buttons)
                button = buttons[text]
                self.assertEqual(Qt.CursorShape.PointingHandCursor, button.cursor().shape())
                self.assertEqual(tooltip, button.toolTip())
                self.assertEqual(tooltip, button.statusTip())

            widget.close()
            self._drain_events()
        finally:
            defect_list_widget.event_service.list_events = original_list_events


if __name__ == "__main__":
    unittest.main()
