"""Home daily-cockpit tests: one read-only backlog (待辦) list.

The backlog list replaces the former 70%-empty home. It is read-only: it reads
existing services and routes through existing navigation, with no new write
paths. KPI cards and the retired generic recent-event table / quick-action write
panel must stay retired.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QPushButton,
    QTableWidget,
)

from services import event_service
from ui.theme import apply_app_theme
from ui.widgets.home_widget import HomeWidget
from ui.widgets.pagination_bar import PaginationBar


def _backlog_row(idx: int, *, supplier: str, status: str = "待處理") -> dict:
    return {
        "event_id": f"evt-{idx}",
        "event_type": "ANOMALY",
        "event_date": f"2026-06-0{idx % 9 + 1}",
        "supplier_name": supplier,
        "content": f"待辦摘要 {idx}",
        "status": status,
    }


class _DummyMainWindow:
    def __init__(self) -> None:
        self.quick_filter_calls: list[dict[str, str | None]] = []
        self.warehouse_outsource_calls = 0
        self.warehouse_material_calls = 0
        self.warehouse_unclassified_calls = 0

    def refresh_all_views(self) -> None:
        return

    def open_new_visit_dialog(self) -> None:
        return

    def open_new_anomaly_dialog(self) -> None:
        return

    def open_warehouse_nonconforming_tracker(self) -> None:
        self.open_warehouse_pending_outsource()

    def open_warehouse_pending_outsource(self) -> None:
        self.warehouse_outsource_calls += 1

    def open_warehouse_pending_material(self) -> None:
        self.warehouse_material_calls += 1

    def open_warehouse_unclassified_pending(self) -> None:
        self.warehouse_unclassified_calls += 1

    def open_warehouse_nonconforming_create(self) -> None:
        return

    def open_event_query_with_filters(
        self,
        *,
        event_type: str = "ANOMALY",
        supplier_keyword: str = "",
        yyyymm: str | None = None,
        status: str = "ALL",
        event_scope: str | None = None,
        overdue_only: bool = False,
    ) -> None:
        self.quick_filter_calls.append(
            {
                "event_type": event_type,
                "supplier_keyword": supplier_keyword,
                "yyyymm": yyyymm,
                "status": status,
                "event_scope": event_scope,
                "overdue_only": overdue_only,
            }
        )


class HomeCockpitPanelTests(unittest.TestCase):
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
        self.host = _DummyMainWindow()
        self.widget = HomeWidget(self.host)
        self.widget.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.widget.close()
        self.app.processEvents()

    def _label_texts(self) -> list[str]:
        return [label.text() for label in self.widget.findChildren(QLabel)]

    def test_home_renders_backlog_panel_without_kpi_cards(self) -> None:
        labels = self._label_texts()
        self.assertNotIn("快速入口", labels)
        self.assertNotIn("逾期未結", labels)
        self.assertNotIn("單獨異常", labels)
        self.assertNotIn("訪廠發現異常", labels)
        self.assertNotIn("倉庫待處理不合格品", labels)
        self.assertNotIn("總異常件數", labels)

        kpi_cards = [
            frame
            for frame in self.widget.findChildren(QFrame)
            if frame.property("role") == "kpiCard"
        ]
        self.assertEqual(0, len(kpi_cards))
        self.assertIsNone(self.widget.findChild(QFrame, "HomeKpiPanel"))
        # Daily cockpit: exactly one read-only backlog panel.
        self.assertIsNotNone(self.widget.findChild(QFrame, "HomeBacklogPanel"))
        self.assertIsNotNone(self.widget.findChild(QTableWidget, "HomeBacklogTable"))
        # Retired surfaces stay retired.
        self.assertIsNone(self.widget.findChild(QFrame, "HomeQuickActionPanel"))
        self.assertIsNone(self.widget.findChild(QFrame, "OverdueBanner"))

    def test_home_backlog_is_read_only_navigation_only(self) -> None:
        # No legacy recent-event table attributes, no pagination, no write buttons.
        self.assertFalse(hasattr(self.widget, "recent_table"))
        self.assertFalse(hasattr(self.widget, "_recent_rows"))
        self.assertEqual([], self.widget.findChildren(PaginationBar))

        button_texts = [
            button.text().strip()
            for button in self.widget.findChildren(QPushButton)
            if button.text().strip()
        ]
        # The only home buttons are warehouse navigation shortcuts (no write actions).
        self.assertNotIn("新增異常", button_texts)
        self.assertNotIn("新增訪廠", button_texts)
        self.assertNotIn("基礎資料", button_texts)
        self.assertTrue(any(text.startswith("待處理委外加工") for text in button_texts))
        self.assertTrue(any(text.startswith("待處理原物料") for text in button_texts))
        self.assertTrue(any(text.startswith("未分流待整理") for text in button_texts))

    def test_warehouse_shortcuts_route_to_formal_lines_and_unclassified_cleanup(self) -> None:
        self.widget._warehouse_outsource_btn.click()
        self.widget._warehouse_material_btn.click()
        self.widget._warehouse_unclassified_btn.click()
        self.assertEqual(1, self.host.warehouse_outsource_calls)
        self.assertEqual(1, self.host.warehouse_material_calls)
        self.assertEqual(1, self.host.warehouse_unclassified_calls)

    @patch("services.event._query_service.list_events")
    def test_backlog_lists_pending_and_row_click_routes(self, mock_list) -> None:
        rows = [_backlog_row(i, supplier=f"供應商{i}") for i in range(3)]
        mock_list.return_value = rows
        widget = HomeWidget(self.host)
        widget.show()
        self.app.processEvents()
        try:
            table = widget._backlog_table
            self.assertTrue(table.isVisible())
            self.assertEqual(3, table.rowCount())

            widget._on_backlog_row_clicked(0, 0)
            call = self.host.quick_filter_calls[-1]
            self.assertEqual("待處理", call["status"])
            self.assertEqual(
                event_service.EVENT_SCOPE_ANOMALY_ONLY, call["event_scope"]
            )
            self.assertEqual("供應商0", call["supplier_keyword"])
        finally:
            widget.close()
            self.app.processEvents()

    @patch("services.event._query_service.list_events", return_value=[])
    def test_backlog_empty_state_when_no_pending(self, _mock) -> None:
        widget = HomeWidget(self.host)
        widget.show()
        self.app.processEvents()
        try:
            self.assertFalse(widget._backlog_table.isVisible())
            self.assertTrue(widget._backlog_empty.isVisible())
        finally:
            widget.close()
            self.app.processEvents()

    def test_refresh_data_remains_noop_compatibility_hook(self) -> None:
        self.assertIsNone(self.widget.refresh_data())
        self.assertFalse(hasattr(self.widget, "recent_table"))

    def test_warehouse_shortcut_buttons_are_clickable_navigation(self) -> None:
        for button in (
            self.widget._warehouse_outsource_btn,
            self.widget._warehouse_material_btn,
            self.widget._warehouse_unclassified_btn,
        ):
            with self.subTest(button=button.objectName()):
                self.assertEqual(
                    Qt.CursorShape.PointingHandCursor, button.cursor().shape()
                )
                self.assertTrue(button.toolTip())


if __name__ == "__main__":
    unittest.main()
