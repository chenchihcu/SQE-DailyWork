"""Home daily-cockpit tests: six KPI cards + one read-only backlog (待辦) list.

The backlog list replaces the former 70%-empty home. It is read-only: it reads
existing services and routes through existing navigation, with no new write
paths. (The retired generic recent-event table / quick-action write panel must
stay retired.)
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
        self.warehouse_tracker_calls = 0

    def refresh_all_views(self) -> None:
        return

    def open_new_visit_dialog(self) -> None:
        return

    def open_new_anomaly_dialog(self) -> None:
        return

    def open_warehouse_nonconforming_tracker(self) -> None:
        self.warehouse_tracker_calls += 1

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

    def test_home_renders_six_kpi_cards_plus_backlog_panel(self) -> None:
        labels = self._label_texts()
        self.assertTrue(any(label.startswith("本月品質工作台") for label in labels))
        self.assertNotIn("快速入口", labels)

        expected_kpi_titles = {
            "總異常件數",
            "已結案",
            "逾期未結",
            "單獨異常",
            "訪廠發現異常",
            "倉庫待處理不合格品",
        }
        self.assertTrue(expected_kpi_titles.issubset(set(labels)))

        kpi_cards = [
            frame
            for frame in self.widget.findChildren(QFrame)
            if frame.property("role") == "kpiCard"
        ]
        self.assertEqual(6, len(kpi_cards))
        self.assertIsNotNone(self.widget.findChild(QFrame, "HomeKpiPanel"))
        # Daily cockpit: exactly one read-only backlog panel below the KPI cards.
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
        # The only home button is the warehouse navigation shortcut (no write actions).
        self.assertNotIn("新增異常", button_texts)
        self.assertNotIn("新增訪廠", button_texts)
        self.assertNotIn("基礎資料", button_texts)
        self.assertTrue(
            any(text.startswith("倉庫待處理不合格品") for text in button_texts)
        )

    def test_warehouse_shortcut_routes_to_tracker(self) -> None:
        self.widget._warehouse_summary_btn.click()
        self.assertEqual(1, self.host.warehouse_tracker_calls)

    @patch("services.event_service.list_events")
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

    @patch("services.event_service.list_events", return_value=[])
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

    def test_all_kpi_cards_are_clickable_workbench_routes(self) -> None:
        for key, card in self.widget._kpi_cards.items():
            with self.subTest(key=key):
                self.assertEqual(
                    Qt.CursorShape.PointingHandCursor, card.cursor().shape()
                )
                self.assertTrue(card.toolTip())
                self.assertIn(key, self.widget._kpi_click_filters)

        self.widget._kpi_click_filters["visit_open_anomaly_count"]._callback()
        self.widget._kpi_click_filters["defect_open_count"]._callback()

        self.assertEqual(
            event_service.EVENT_SCOPE_VISIT_WITH_ANOMALY,
            self.host.quick_filter_calls[-1]["event_scope"],
        )
        self.assertEqual("待處理", self.host.quick_filter_calls[-1]["status"])
        self.assertEqual(1, self.host.warehouse_tracker_calls)

        # 逾期未結 KPI 下鑽要帶 overdue_only=True（清單與計數一致）。
        self.widget._kpi_click_filters["overdue_open_anomaly_count"]._callback()
        overdue_call = self.host.quick_filter_calls[-1]
        self.assertTrue(overdue_call["overdue_only"])
        self.assertEqual("待處理", overdue_call["status"])
        self.assertEqual(
            event_service.EVENT_SCOPE_ANOMALY_ONLY, overdue_call["event_scope"]
        )


if __name__ == "__main__":
    unittest.main()
