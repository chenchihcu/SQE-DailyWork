from __future__ import annotations

import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt

from ui.widgets.supplier_360_page import Supplier360Page
from ui.widgets.defect_list_widget import EVENT_QUERY_SCOPE_TABS
from ui.widgets.supplier_overview_page import SupplierOverviewPage


class SupplierOrientedUiContractTests(unittest.TestCase):
    def test_event_scope_contract_has_four_page_local_views(self) -> None:
        self.assertEqual(
            ["單獨異常", "訪廠發現異常", "訪廠紀錄", "已結案"],
            [label for label, _scope, _event_type in EVENT_QUERY_SCOPE_TABS],
        )

    def test_source_scopes_are_not_navigation_labels(self) -> None:
        from ui.sidebar_nav import _NAV_GROUPS

        labels = [
            label
            for _group, entries in _NAV_GROUPS
            for label, _action, _badge, _icon in entries
        ]
        self.assertNotIn("單獨異常", labels)
        self.assertNotIn("訪廠發現異常", labels)
        self.assertIn("事件管理", labels)
        self.assertIn("供應商總覽", labels)

    def test_supplier_overview_defaults_to_open_anomaly_scope(self) -> None:
        with patch(
            "ui.widgets.supplier_overview_page.supplier_360_service.list_supplier_rows",
            return_value=[],
        ) as list_rows, patch(
            "ui.widgets.supplier_overview_page.supplier_360_service.list_supplier_scorecards",
            return_value={},
        ):
            page = SupplierOverviewPage()
            self.assertEqual("open_anomaly", page.scope_combo.currentData())
            self.assertEqual(12, page.table.columnCount())
            self.assertEqual("最新異常單號", page.table.horizontalHeaderItem(3).text())
            self.assertEqual("問題摘要", page.table.horizontalHeaderItem(6).text())
            self.assertEqual("評級", page.table.horizontalHeaderItem(10).text())
            list_rows.assert_called_with(view_scope="open_anomaly")

    def test_supplier_360_refresh_without_supplier_is_safe(self) -> None:
        page = Supplier360Page(main_window=None)
        page.refresh_data()

    def test_supplier_overview_keeps_all_cells_when_sorting_is_enabled(self) -> None:
        rows = [
            {
                "id": "supplier-a",
                "supplier_name": "甲供應商",
                "open_anomaly_count": 2,
                "overdue_anomaly_count": 1,
                "latest_anomaly_no": "20260820001",
                "latest_anomaly_date": "2026-08-20",
                "latest_anomaly_category": "製程異常",
                "latest_anomaly_desc": "摘要甲",
                "latest_anomaly_due_date": "2026-08-21",
                "ncr_90d_count": 3,
                "latest_visit_date": "2026-08-19",
                "grade": "A",
                "is_active": 1,
            },
            {
                "id": "supplier-b",
                "supplier_name": "乙供應商",
                "open_anomaly_count": 1,
                "overdue_anomaly_count": 0,
                "latest_anomaly_no": "20260819001",
                "latest_anomaly_date": "2026-08-19",
                "latest_anomaly_category": "來料異常",
                "latest_anomaly_desc": "摘要乙",
                "latest_anomaly_due_date": "2026-08-25",
                "ncr_90d_count": 0,
                "latest_visit_date": "2026-08-18",
                "grade": "B",
                "is_active": 1,
            },
        ]
        with patch(
            "ui.widgets.supplier_overview_page.supplier_360_service.list_supplier_rows",
            return_value=rows,
        ), patch(
            "ui.widgets.supplier_overview_page.supplier_360_service.list_supplier_scorecards",
            return_value={"supplier-a": "A", "supplier-b": "B"},
        ):
            page = SupplierOverviewPage()
            page.table.sortItems(0, Qt.SortOrder.DescendingOrder)
            page._rows = list(reversed(rows))
            page._render()

            rows_by_supplier = {
                page.table.item(row_index, 0).text(): row_index
                for row_index in range(page.table.rowCount())
            }
            row_a = rows_by_supplier["甲供應商"]
            row_b = rows_by_supplier["乙供應商"]
            self.assertEqual("20260819001", page.table.item(row_b, 3).text())
            self.assertEqual("來料異常", page.table.item(row_b, 5).text())
            self.assertEqual("摘要乙", page.table.item(row_b, 6).text())
            self.assertEqual("2", page.table.item(row_a, 1).text())
            self.assertEqual("2026-08-21", page.table.item(row_a, 7).text())
            self.assertEqual("supplier-a", page.table.item(row_a, 0).data(32))
            self.assertEqual(
                Qt.SortOrder.DescendingOrder,
                page.table.horizontalHeader().sortIndicatorOrder(),
            )

if __name__ == "__main__":
    unittest.main()
