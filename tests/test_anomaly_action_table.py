from __future__ import annotations

import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from ui.widgets.anomaly_action_table import AnomalyActionTable


def _sample_action(**overrides) -> dict:
    action = {
        "id": "action-1",
        "action_type": "CORRECTIVE_ACTION",
        "action_type_label": "改善措施",
        "description": "測試處置內容",
        "execution_status": "已規劃",
        "verification_required": False,
        "verification_status": "不需要",
        "owner": "SQE",
        "due_date": "2026-09-01",
    }
    action.update(overrides)
    return action


class AnomalyActionTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls._host = QWidget()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._host.close()
        cls._host.deleteLater()
        app = QApplication.instance()
        if app is not None:
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents()

    def tearDown(self) -> None:
        app = QApplication.instance()
        if app is not None:
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents()

    def test_status_labels_use_traditional_chinese(self) -> None:
        table = AnomalyActionTable(
            [
                _sample_action(execution_status="已規劃"),
                _sample_action(id="action-2", execution_status="執行中"),
                _sample_action(id="action-3", execution_status="已完成"),
            ],
            parent=self._host,
        )
        badges = [
            child.text().strip()
            for child in table.findChildren(QLabel)
            if child.property("role") == "statusBadge"
        ]
        self.assertEqual(["已規劃", "執行中", "已完成"], badges)
        self.assertNotIn("Open", badges)
        self.assertNotIn("Done", badges)

    def test_in_progress_row_exposes_complete_and_cancel_buttons(self) -> None:
        table = AnomalyActionTable(
            [_sample_action(execution_status="執行中")],
            parent=self._host,
        )
        buttons = [btn.text() for btn in table.findChildren(QPushButton)]
        self.assertIn("完成", buttons)
        self.assertIn("取消", buttons)
        self.assertNotIn("完成／取消", buttons)

    def test_planned_row_exposes_start_and_cancel_buttons(self) -> None:
        table = AnomalyActionTable(
            [_sample_action(execution_status="已規劃")],
            parent=self._host,
        )
        buttons = [btn.text() for btn in table.findChildren(QPushButton)]
        self.assertIn("開始執行", buttons)
        self.assertIn("取消", buttons)
        self.assertIn("編輯", buttons)

    def test_closed_case_hides_workflow_buttons(self) -> None:
        table = AnomalyActionTable(
            [_sample_action(execution_status="已規劃")],
            commands_enabled=False,
            parent=self._host,
        )
        buttons = [btn.text() for btn in table.findChildren(QPushButton)]
        self.assertNotIn("開始執行", buttons)
        self.assertNotIn("取消", buttons)
        self.assertNotIn("編輯", buttons)

    def test_double_click_opens_edit_dialog(self) -> None:
        table = AnomalyActionTable(
            [_sample_action(execution_status="已規劃")],
            parent=self._host,
        )
        with mock.patch(
            "ui.widgets.edit_anomaly_action_dialog.EditAnomalyActionDialog"
        ) as dialog_cls:
            dialog = mock.MagicMock()
            dialog_cls.return_value = dialog
            table.cellDoubleClicked.emit(0, AnomalyActionTable.COL_DESC)
            dialog_cls.assert_called_once()
            dialog.exec.assert_called_once()

    def test_read_only_cells_use_table_items_not_line_edits(self) -> None:
        table = AnomalyActionTable([_sample_action()], parent=self._host)
        self.assertIsNotNone(table.item(0, AnomalyActionTable.COL_DESC))
        self.assertEqual(
            "測試處置內容",
            table.item(0, AnomalyActionTable.COL_DESC).text(),
        )

    def test_table_headers_match_contract(self) -> None:
        self.assertEqual(
            (
                "狀態",
                "Action 類型",
                "處置內容",
                "責任人",
                "預定日期",
                "編輯",
                "流程",
            ),
            AnomalyActionTable.TABLE_HEADERS,
        )

    def test_workflow_buttons_use_table_cell_action_role(self) -> None:
        table = AnomalyActionTable(
            [_sample_action(execution_status="執行中")],
            parent=self._host,
        )
        for button in table.findChildren(QPushButton):
            self.assertEqual("tableCellAction", button.property("role"))

    def test_row_height_fits_cell_widget_size_hint(self) -> None:
        table = AnomalyActionTable(
            [_sample_action(execution_status="執行中")],
            parent=self._host,
        )
        flow_widget = table.cellWidget(0, AnomalyActionTable.COL_FLOW)
        self.assertIsNotNone(flow_widget)
        self.assertGreaterEqual(
            table.rowHeight(0),
            flow_widget.sizeHint().height(),
        )
