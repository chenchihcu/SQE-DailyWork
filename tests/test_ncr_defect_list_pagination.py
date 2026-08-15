from __future__ import annotations

import os
import sqlite3
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ncr.db import crud, database
from ncr.models.defect import (
    LIST_FIELD_ORDER,
    PROCESSING_LINE_MATERIAL,
)
from ncr.services import defect_service
from ncr.ui.defect_list import DefectListWidget
from ncr.ui.ui_style import NCR_ITEMS_PER_PAGE


class _DialogProbe:
    opened_ids: list[int] = []

    def __init__(self, _conn, defect_id: int, _parent) -> None:
        self.opened_ids.append(defect_id)

    def exec(self) -> int:
        return 0


class NcrDefectListPaginationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            cls.app.quit()

    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        database.apply_schema(self.conn, with_version=True)
        for index in range(21):
            defect_service.create_defect(
                self.conn,
                {
                    "event_date": "2026-04-14",
                    "processing_line": PROCESSING_LINE_MATERIAL,
                    "return_slip_type": "廠內退料",
                    "work_order_no": f"WO-{index:03d}",
                    "item_no": f"ITEM-{index:03d}",
                    "product_name": f"產品 {index:03d}",
                    "qty": 1,
                    "category": "成品",
                    "supplier_name": "供應商 A",
                    "outsource_supplier_name": "",
                    "defect_desc": f"缺失 {index:03d}",
                    "status": "處理中",
                    "disposition": "重工",
                },
            )
        self.widget = DefectListWidget(
            self.conn,
            workflow="tracking",
            processing_line=PROCESSING_LINE_MATERIAL,
        )

    def tearDown(self) -> None:
        self.widget.close()
        self.conn.close()

    def test_crud_count_and_pages_cover_each_matching_record_once(self) -> None:
        filters = {"processing_line": PROCESSING_LINE_MATERIAL}
        self.assertEqual(21, crud.count_defects(self.conn, filters, "已結案"))

        pages = [
            crud.get_defects_page(
                self.conn,
                filters,
                "已結案",
                page=page,
                page_size=10,
            )
            for page in (1, 2, 3)
        ]
        self.assertEqual([10, 10, 1], [len(rows) for rows in pages])
        page_ids = [int(row["id"]) for rows in pages for row in rows]
        full_ids = [int(row["id"]) for row in crud.get_defects(self.conn, filters, "已結案")]
        self.assertEqual(full_ids, page_ids)

    def test_page_size_changes_rendered_rows_and_edit_targets_current_page(self) -> None:
        self.assertEqual(NCR_ITEMS_PER_PAGE, self.widget.open_table.rowCount())
        self.assertEqual("1 / 2", self.widget.pagination.page_info_label.text())

        self.widget._on_page_size_changed(10)
        self.app.processEvents()
        self.assertEqual(10, self.widget.open_table.rowCount())
        self.assertEqual("1 / 3", self.widget.pagination.page_info_label.text())

        self.widget._on_page_changed(3)
        self.app.processEvents()
        self.assertEqual(1, self.widget.open_table.rowCount())
        expected_id = int(self.widget.open_results[0]["id"])

        _DialogProbe.opened_ids = []
        with patch("ncr.ui.defect_list.DefectEditDialog", _DialogProbe):
            self.widget.open_edit_dialog(0, 0)
        self.assertEqual([expected_id], _DialogProbe.opened_ids)

    def test_compact_profile_fits_core_columns_and_full_mode_preserves_header_order(self) -> None:
        self.widget.resize(760, 680)
        self.widget.show()
        self.app.processEvents()

        core_fields = {
            "defect_no",
            "event_date",
            "item_no",
            "product_name",
            "defect_desc",
            "status",
        }
        for column_index, field_name in enumerate(LIST_FIELD_ORDER):
            self.assertEqual(field_name not in core_fields, self.widget.open_table.isColumnHidden(column_index))
        self.assertEqual("顯示完整欄位", self.widget.column_profile_button.text())
        self.assertEqual(0, self.widget.open_table.horizontalScrollBar().maximum())

        before_order = [
            self.widget.open_table.horizontalHeader().logicalIndex(index)
            for index in range(self.widget.open_table.columnCount())
        ]
        self.widget.column_profile_button.click()
        self.app.processEvents()

        self.assertEqual("使用重點欄位", self.widget.column_profile_button.text())
        self.assertFalse(any(
            self.widget.open_table.isColumnHidden(column_index)
            for column_index in range(self.widget.open_table.columnCount())
        ))
        after_order = [
            self.widget.open_table.horizontalHeader().logicalIndex(index)
            for index in range(self.widget.open_table.columnCount())
        ]
        self.assertEqual(before_order, after_order)

    def test_history_compact_profile_keeps_processing_line_visible(self) -> None:
        history = DefectListWidget(self.conn, workflow="trace")
        self.addCleanup(history.close)
        history.resize(760, 680)
        history.show()
        self.app.processEvents()

        processing_line_column = LIST_FIELD_ORDER.index("processing_line")
        self.assertFalse(history.closed_table.isColumnHidden(processing_line_column))

    def test_column_profile_does_not_change_export_records(self) -> None:
        exported_rows: list[list[dict]] = []

        def capture_export(rows, *_args, **_kwargs):
            exported_rows.append([dict(row) for row in rows])
            return "C:/temp/defect_report.xlsx"

        with (
            patch("ncr.ui.defect_list.QFileDialog.getSaveFileName", return_value=("C:/temp/defect_report.xlsx", "")),
            patch("ncr.ui.defect_list.export_service.export_to_excel", side_effect=capture_export),
            patch("ncr.ui.defect_list.QMessageBox.information"),
        ):
            self.widget.export_current_results()
            self.widget.column_profile_button.click()
            self.app.processEvents()
            self.widget.export_current_results()

        self.assertEqual(2, len(exported_rows))
        self.assertEqual(exported_rows[0], exported_rows[1])
        self.assertTrue(all("work_order_no" in row for row in exported_rows[0]))


if __name__ == "__main__":
    unittest.main()
