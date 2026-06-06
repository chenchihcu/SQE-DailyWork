from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from services import event_service
from ui.status_colors import get_status_color_hex, get_status_palette
from ui.theme import apply_app_theme
from ui.widgets.common_widgets import EMPTY_DISPLAY
from ui.widgets.defect_list_widget import EventListWidget


class _DummyMainWindow:
    def refresh_all_views(self) -> None:
        return

    def open_new_visit_dialog(self) -> None:
        return

    def open_new_anomaly_dialog(self) -> None:
        return


class EventListWidgetRenderStabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        apply_app_theme(cls.app)

    def setUp(self) -> None:
        self._list_events_patch = patch(
            "ui.widgets.defect_list_widget.event_service.list_events",
            return_value=self._build_rows(),
        )
        self._list_events = self._list_events_patch.start()
        self.widget = EventListWidget(_DummyMainWindow(), mode="query")
        self.widget.resize(1200, 760)
        self.widget.show()
        self._drain_events()

    def tearDown(self) -> None:
        self.widget.close()
        self._drain_events()
        self._list_events_patch.stop()

    def _drain_events(self) -> None:
        self.app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def _build_rows(self) -> list[dict]:
        return [
            {
                "event_id": "a0",
                "event_date": "2026-04-18",
                "event_type": "ANOMALY",
                "supplier_name": "供應商-A",
                "product_name": "產品-A",
                "product_code": "PN-A001",
                "product_stage": "試產",
                "work_order_no": "WO-001",
                "production_qty": 10,
                "content": "問題-0",
                "status": "待處理",
                "linked_visit_date": None,
                "linked_visit_id": None,
            },
            {
                "event_id": "v1",
                "event_date": "2026-04-17",
                "event_type": "VISIT",
                "supplier_name": "供應商-B",
                "product_name": "產品-B",
                "product_code": "PN-B002",
                "product_stage": "量產",
                "work_order_no": "WO-002",
                "production_qty": 0,
                "content": "摘要-1",
                "status": "已完成",
                "linked_visit_date": None,
                "linked_visit_id": None,
            },
            {
                "event_id": "a2",
                "event_date": "",
                "event_type": "ANOMALY",
                "supplier_name": "供應商-C",
                "product_name": "產品-C",
                "product_code": "PN-C003",
                "product_stage": "量產",
                "work_order_no": "WO-003",
                "production_qty": 8,
                "content": None,
                "status": "待處理",
                "linked_visit_date": None,
                "linked_visit_id": None,
            },
            {
                "event_id": "a3",
                "event_date": "2026-04-15",
                "event_type": None,
                "supplier_name": "",
                "product_name": "",
                "product_code": "",
                "product_stage": "",
                "work_order_no": None,
                "production_qty": -1,
                "content": "問題-3",
                "status": None,
                "linked_visit_date": None,
                "linked_visit_id": None,
            },
        ]

    def _headers(self) -> list[str]:
        return [
            self.widget.table.horizontalHeaderItem(idx).text()
            for idx in range(self.widget.table.columnCount())
        ]

    def test_table_headers_match_template_eleven_columns(self) -> None:
        self.assertEqual(11, self.widget.table.columnCount())
        self.assertEqual(
            ["日期", "類型", "供應商", "品名", "料號", "階段", "工單", "數量", "問題/摘要", "缺失紀錄", "狀態"],
            self._headers(),
        )

    def test_query_scope_tabs_replace_type_filter(self) -> None:
        self.assertIsNone(self.widget.event_type_combo)
        self.assertIsNotNone(self.widget.event_scope_tab_bar)
        assert self.widget.event_scope_tab_bar is not None
        labels = [
            self.widget.event_scope_tab_bar.tabText(index)
            for index in range(self.widget.event_scope_tab_bar.count())
        ]
        self.assertEqual(
            ["訪廠紀錄", "訪廠發現異常", "單獨異常"],
            labels,
        )
        self.assertEqual(
            event_service.EVENT_SCOPE_VISIT_ONLY,
            self.widget.event_scope_tab_bar.tabData(0),
        )
        self.assertIsNotNone(self.widget.export_pdf_button)
        assert self.widget.export_pdf_button is not None
        self.assertEqual("輸出PDF", self.widget.export_pdf_button.text())
        self.assertFalse(self.widget.export_pdf_button.isEnabled())
        self.assertIn("請先選取", self.widget.export_pdf_button.toolTip())
        self.assertIsNotNone(self.widget.source_tag_label)
        assert self.widget.source_tag_label is not None
        self.assertEqual("供應商事件 / 訪廠紀錄", self.widget.source_tag_label.text())

    def test_switching_query_scope_tab_refreshes_with_scope(self) -> None:
        self._list_events.reset_mock()
        assert self.widget.event_scope_tab_bar is not None
        self.widget.event_scope_tab_bar.setCurrentIndex(1)
        self._drain_events()

        self._list_events.assert_called_once()
        filters = self._list_events.call_args.args[0]
        self.assertEqual(event_service.EVENT_SCOPE_VISIT_WITH_ANOMALY, filters["event_scope"])
        self.assertEqual("ANOMALY", filters["event_type"])

    def test_export_pdf_button_stays_available_across_query_scope_tabs(self) -> None:
        assert self.widget.event_scope_tab_bar is not None
        for index in range(self.widget.event_scope_tab_bar.count()):
            self.widget.event_scope_tab_bar.setCurrentIndex(index)
            self._drain_events()
            self.assertEqual(11, self.widget.table.columnCount())
            self.assertIsNotNone(self.widget.export_pdf_button)
            assert self.widget.export_pdf_button is not None
            self.assertEqual("輸出PDF", self.widget.export_pdf_button.text())
            self.assertFalse(self.widget.export_pdf_button.isEnabled())

    def test_export_pdf_button_enables_only_after_row_selection(self) -> None:
        assert self.widget.export_pdf_button is not None
        self.assertFalse(self.widget.export_pdf_button.isEnabled())

        self.widget.table.setCurrentCell(0, 0)
        self.widget.table.selectRow(0)
        self._drain_events()
        self.assertTrue(self.widget.export_pdf_button.isEnabled())
        self.assertIn("目前選取", self.widget.export_pdf_button.toolTip())

        self.widget.table.clearSelection()
        self._drain_events()
        self.assertFalse(self.widget.export_pdf_button.isEnabled())
        self.assertIn("請先選取", self.widget.export_pdf_button.toolTip())

    def test_reset_filters_keeps_current_query_scope(self) -> None:
        assert self.widget.event_scope_tab_bar is not None
        assert self.widget.status_combo is not None
        assert self.widget.supplier_filter_input is not None
        self.widget.event_scope_tab_bar.setCurrentIndex(2)
        self._drain_events()
        self._list_events.reset_mock()

        self.widget._filter_supplier = "供應商-A"
        self.widget._filter_status = "待處理"
        self.widget._sync_filter_widgets_from_state()
        self._drain_events()
        self._list_events.reset_mock()
        self.widget._reset_filters_ui()
        self._drain_events()

        self._list_events.assert_called_once()
        filters = self._list_events.call_args.args[0]
        self.assertEqual(2, self.widget.event_scope_tab_bar.currentIndex())
        self.assertEqual(event_service.EVENT_SCOPE_ANOMALY_ONLY, filters["event_scope"])
        self.assertEqual("ALL", filters["status"])
        self.assertEqual("", filters["supplier"])

    def test_refresh_data_keeps_eleven_column_structure_without_cell_widgets(self) -> None:
        expected_rows = len(self._build_rows())
        for _ in range(5):
            self.widget.refresh_data()
            self._drain_events()
            self.assertEqual(11, self.widget.table.columnCount())
            self.assertEqual(expected_rows, self.widget.table.rowCount())

        has_cell_widget = any(
            self.widget.table.cellWidget(row_idx, col_idx) is not None
            for row_idx in range(self.widget.table.rowCount())
            for col_idx in range(self.widget.table.columnCount())
        )
        self.assertFalse(has_cell_widget)

    def test_rows_map_expected_fields_and_fill_dash(self) -> None:
        table = self.widget.table

        self.assertEqual("2026-04-18", table.item(0, 0).text())
        self.assertEqual("異常", table.item(0, 1).text())
        self.assertEqual("供應商-A", table.item(0, 2).text())
        self.assertEqual("產品-A", table.item(0, 3).text())
        self.assertEqual("PN-A001", table.item(0, 4).text())
        self.assertEqual("試產", table.item(0, 5).text())
        self.assertEqual("WO-001", table.item(0, 6).text())
        self.assertEqual("10", table.item(0, 7).text())
        self.assertEqual("問題-0", table.item(0, 8).text())
        self.assertEqual(EMPTY_DISPLAY, table.item(0, 9).text())
        self.assertEqual("待處理", table.item(0, 10).text())

        self.assertEqual("-", table.item(1, 7).text())
        self.assertEqual(EMPTY_DISPLAY, table.item(2, 0).text())
        self.assertEqual(EMPTY_DISPLAY, table.item(2, 8).text())
        self.assertEqual("-", table.item(3, 1).text())
        self.assertEqual(EMPTY_DISPLAY, table.item(3, 2).text())
        self.assertEqual(EMPTY_DISPLAY, table.item(3, 3).text())
        self.assertEqual(EMPTY_DISPLAY, table.item(3, 4).text())
        self.assertEqual(EMPTY_DISPLAY, table.item(3, 5).text())
        self.assertEqual(EMPTY_DISPLAY, table.item(3, 6).text())
        self.assertEqual("-", table.item(3, 7).text())
        self.assertEqual(EMPTY_DISPLAY, table.item(3, 9).text())
        self.assertEqual("-", table.item(3, 10).text())

    def test_status_cells_keep_color_mapping(self) -> None:
        table = self.widget.table
        row0_color = table.item(0, 10).foreground().color().name().lower()
        row1_color = table.item(1, 10).foreground().color().name().lower()
        row3_color = table.item(3, 10).foreground().color().name().lower()
        row0_bg = table.item(0, 10).background().color().name().lower()

        self.assertEqual(
            QColor(get_status_color_hex("待處理")).name().lower(),
            row0_color,
        )
        self.assertEqual(
            QColor(get_status_color_hex("已完成")).name().lower(),
            row1_color,
        )
        self.assertEqual(
            QColor(get_status_color_hex("")).name().lower(),
            row3_color,
        )
        self.assertEqual(
            QColor(get_status_palette("待處理").background).name().lower(),
            row0_bg,
        )

    def test_date_cell_preserves_original_row_payload(self) -> None:
        item = self.widget.table.item(0, 0)
        payload = item.data(Qt.ItemDataRole.UserRole)
        self.assertIsInstance(payload, dict)
        assert isinstance(payload, dict)
        self.assertEqual("a0", payload.get("event_id"))
        self.assertEqual("ANOMALY", payload.get("event_type"))

    def test_export_pdf_without_selection_shows_prompt(self) -> None:
        self.widget.table.clearSelection()
        self.widget._selected_event_row = None

        with patch("ui.widgets.defect_list_widget.QMessageBox.information") as info:
            self.widget._export_selected_pdf()

        info.assert_called_once()
        self.assertEqual("提示", info.call_args.args[1])
        self.assertIn("請先選取一筆資料", info.call_args.args[2])

    def test_export_pdf_uses_selected_row_and_save_dialog_target(self) -> None:
        self.widget.table.setCurrentCell(0, 0)
        self.widget.table.selectRow(0)
        self._drain_events()

        with (
            patch(
                "ui.widgets.defect_list_widget.event_service.default_event_pdf_filename",
                return_value="SQE_異常單_20260507001_供應商.pdf",
            ) as default_name,
            patch(
                "ui.widgets.defect_list_widget.QFileDialog.getSaveFileName",
                return_value=("scratch\\selected_event", "PDF Files (*.pdf)"),
            ) as save_dialog,
            patch(
                "ui.widgets.defect_list_widget.event_service.export_event_pdf",
                return_value=(True, "已匯出至：scratch\\selected_event.pdf"),
            ) as export_pdf,
            patch("ui.widgets.defect_list_widget.QMessageBox.information") as info,
        ):
            self.widget._export_selected_pdf()

        default_name.assert_called_once()
        save_dialog.assert_called_once()
        export_pdf.assert_called_once()
        target, row = export_pdf.call_args.args
        self.assertEqual("scratch\\selected_event.pdf", target)
        self.assertEqual("a0", row["event_id"])
        self.assertEqual("ANOMALY", row["event_type"])
        self.assertEqual("成功", info.call_args.args[1])

    def test_apply_quick_filters_sets_visible_month(self) -> None:
        self._list_events.reset_mock()
        self.widget.apply_quick_filters(
            event_type="ANOMALY",
            supplier_keyword="供應商-A",
            yyyymm="202604",
            status="ALL",
        )
        self._drain_events()

        self._list_events.assert_called_once()
        filters = self._list_events.call_args.args[0]
        self.assertEqual("ANOMALY", filters["event_type"])
        self.assertEqual(event_service.EVENT_SCOPE_ANOMALY_ONLY, filters["event_scope"])
        self.assertEqual("供應商-A", filters["supplier"])
        self.assertEqual("ALL", filters["status"])
        self.assertEqual("202604", filters["yyyymm"])
        # C4: the drill-down month is now an explicit, visible filter (not hidden).
        self.assertEqual("202604", self.widget._filter_yyyymm)
        self.assertFalse(self.widget.all_months_checkbox.isChecked())
        self.assertEqual("202604", self.widget.month_input.date().toString("yyyyMM"))

    def test_apply_quick_filters_applies_status_when_valid(self) -> None:
        self._list_events.reset_mock()
        self.widget.apply_quick_filters(
            event_type="ANOMALY",
            supplier_keyword="供應商-A",
            yyyymm="202604",
            status="待處理",
        )
        self._drain_events()

        self._list_events.assert_called_once()
        filters = self._list_events.call_args.args[0]
        self.assertEqual("ANOMALY", filters["event_type"])
        self.assertEqual(event_service.EVENT_SCOPE_ANOMALY_ONLY, filters["event_scope"])
        self.assertEqual("供應商-A", filters["supplier"])
        self.assertEqual("待處理", filters["status"])
        self.assertEqual("202604", filters["yyyymm"])
        self.assertEqual("待處理", self.widget._filter_status)

    def test_apply_quick_filters_invalid_status_falls_back_to_all(self) -> None:
        self._list_events.reset_mock()
        self.widget.apply_quick_filters(
            event_type="ANOMALY",
            supplier_keyword="供應商-A",
            yyyymm="202604",
            status="INVALID",
        )
        self._drain_events()

        self._list_events.assert_called_once()
        filters = self._list_events.call_args.args[0]
        self.assertEqual("ALL", filters["status"])
        self.assertEqual(event_service.EVENT_SCOPE_ANOMALY_ONLY, filters["event_scope"])
        self.assertEqual("ALL", self.widget._filter_status)

    def test_subsequent_quick_filter_without_month_clears_month(self) -> None:
        self.widget.apply_quick_filters(
            event_type="ANOMALY",
            supplier_keyword="供應商-A",
            yyyymm="202604",
        )
        self._drain_events()

        self._list_events.reset_mock()
        # 第二次 quick filter 不帶月份 → 明確月份被清掉
        self.widget.apply_quick_filters(
            event_type="ANOMALY",
            supplier_keyword="供應商-A",
            yyyymm=None,
            status="待處理",
        )
        self._drain_events()

        self._list_events.assert_called_once()
        filters = self._list_events.call_args.args[0]
        self.assertNotIn("yyyymm", filters)
        self.assertIsNone(self.widget._filter_yyyymm)
        self.assertEqual("待處理", filters["status"])
        self.assertEqual(event_service.EVENT_SCOPE_ANOMALY_ONLY, filters["event_scope"])

    def test_apply_quick_filters_overdue_only_sets_lens(self) -> None:
        self._list_events.reset_mock()
        self.widget.apply_quick_filters(
            event_type="ANOMALY",
            yyyymm="202604",
            status="待處理",
            event_scope=event_service.EVENT_SCOPE_ANOMALY_ONLY,
            overdue_only=True,
        )
        self._drain_events()

        self._list_events.assert_called_once()
        filters = self._list_events.call_args.args[0]
        self.assertIs(True, filters["overdue_only"])
        self.assertEqual("待處理", filters["status"])
        self.assertEqual("202604", filters["yyyymm"])
        self.assertTrue(self.widget._filter_overdue_only)
        self.assertIn("逾期未結", self.widget.source_tag_label.text())

    def test_manual_filter_change_clears_overdue_lens(self) -> None:
        self.widget.apply_quick_filters(
            event_type="ANOMALY",
            yyyymm="202604",
            status="待處理",
            event_scope=event_service.EVENT_SCOPE_ANOMALY_ONLY,
            overdue_only=True,
        )
        self._drain_events()
        self.assertTrue(self.widget._filter_overdue_only)

        # 手動操作控制列 → 逾期鏡頭解除
        self.widget._apply_filters_from_ui()
        self._drain_events()

        self.assertFalse(self.widget._filter_overdue_only)
        self.assertNotIn("逾期未結", self.widget.source_tag_label.text())
        filters = self._list_events.call_args.args[0]
        self.assertNotIn("overdue_only", filters)


if __name__ == "__main__":
    unittest.main()
