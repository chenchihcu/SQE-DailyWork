"""Supplier-event operational queue pages (overdue, root cause, open actions)."""

from __future__ import annotations

from typing import Literal

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from database.repo_helpers import CASE_ACTION_TYPE_LABELS
from services import supplier_event_queue_service
from ui.layout_constants import (
    CASE_QUEUE_ANOMALY_NO_WIDTH,
    CASE_QUEUE_DUE_DATE_WIDTH,
    CASE_QUEUE_RCA_WIDTH,
    CASE_QUEUE_RESPONSIBLE_WIDTH,
    CASE_QUEUE_SUPPLIER_WIDTH,
    CONTROL_ROW_SPACING,
    MANAGER_ACTION_QUEUE_ANOMALY_NO_WIDTH,
    MANAGER_ACTION_QUEUE_DUE_DATE_WIDTH,
    MANAGER_ACTION_QUEUE_STATUS_WIDTH,
    MANAGER_ACTION_QUEUE_SUPPLIER_WIDTH,
    MANAGER_ACTION_QUEUE_TYPE_WIDTH,
    PAGE_OUTER_MARGINS,
    PANEL_MARGINS,
)
from ui.list_column_contract import (
    CASE_QUEUE_COLUMNS,
    CASE_QUEUE_RCA_COLUMNS,
    OPERATIONAL_ACTION_QUEUE_COLUMNS,
)
from ui.theme import TOKENS
from ui.widgets.common_widgets import (
    EmptyStateWidget,
    QueryWorkflowShell,
    SortableTableWidgetItem,
    apply_table_action_affordance,
    create_status_item,
    preserve_table_sorting,
    style_table,
    text_table_item,
)

QueueKind = Literal["overdue", "root_cause", "open_actions"]

_QUEUE_SCOPE_TEXT = {
    "overdue": "逾期未結（待處理異常，不限月份）",
    "root_cause": "待根本原因（待處理異常，尚未開始或調查中，不限月份）",
    "open_actions": "進行中處置（待處理異常的已規劃／執行中處置，不限月份）",
}

_QUEUE_EMPTY_TEXT = {
    "overdue": ("目前沒有逾期未結異常", "所有待處理異常皆在期限內，或尚無待處理項目。"),
    "root_cause": ("目前沒有待調查根本原因", "所有待處理異常皆已完成根本原因調查。"),
    "open_actions": ("目前沒有進行中處置", "尚無已規劃或執行中的處置項目。"),
}


class SupplierEventQueuePage(QWidget):
    def __init__(
        self,
        main_window,
        *,
        queue: QueueKind,
        page_key: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self.queue = queue
        self.page_key = page_key
        self._rows: list[dict] = []
        self._build_ui()
        self.refresh_data()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(*PAGE_OUTER_MARGINS)
        root.setSpacing(CONTROL_ROW_SPACING)

        shell = QueryWorkflowShell()
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(*PANEL_MARGINS)
        shell_layout.setSpacing(CONTROL_ROW_SPACING)

        self._scope_label = QLabel(f"目前佇列：{_QUEUE_SCOPE_TEXT[self.queue]}")
        self._scope_label.setProperty("role", "helperText")
        self._scope_label.setWordWrap(True)
        shell_layout.addWidget(self._scope_label)
        root.addWidget(shell)

        if self.queue == "open_actions":
            columns = OPERATIONAL_ACTION_QUEUE_COLUMNS
            widths = (
                MANAGER_ACTION_QUEUE_ANOMALY_NO_WIDTH,
                MANAGER_ACTION_QUEUE_SUPPLIER_WIDTH,
                MANAGER_ACTION_QUEUE_TYPE_WIDTH,
                None,
                MANAGER_ACTION_QUEUE_SUPPLIER_WIDTH,
                MANAGER_ACTION_QUEUE_DUE_DATE_WIDTH,
                MANAGER_ACTION_QUEUE_STATUS_WIDTH,
                MANAGER_ACTION_QUEUE_STATUS_WIDTH,
            )
            object_name = "SupplierEventOpenActionsQueueTable"
            affordance = "點擊處置列開啟對應案件工作台"
        elif self.queue == "root_cause":
            columns = CASE_QUEUE_RCA_COLUMNS
            widths = (
                CASE_QUEUE_ANOMALY_NO_WIDTH,
                CASE_QUEUE_SUPPLIER_WIDTH,
                None,
                None,
                CASE_QUEUE_DUE_DATE_WIDTH,
                CASE_QUEUE_RESPONSIBLE_WIDTH,
                CASE_QUEUE_RCA_WIDTH,
            )
            object_name = "SupplierEventRootCauseQueueTable"
            affordance = "點擊案件列開啟案件工作台"
        else:
            columns = CASE_QUEUE_COLUMNS
            widths = (
                CASE_QUEUE_ANOMALY_NO_WIDTH,
                CASE_QUEUE_SUPPLIER_WIDTH,
                None,
                None,
                CASE_QUEUE_DUE_DATE_WIDTH,
                CASE_QUEUE_RESPONSIBLE_WIDTH,
            )
            object_name = "SupplierEventOverdueQueueTable"
            affordance = "點擊案件列開啟案件工作台"

        self._columns = columns
        self._table = QTableWidget(0, len(columns))
        self._table.setObjectName(object_name)
        self._table.setHorizontalHeaderLabels([column.label for column in columns])
        style_table(self._table)
        apply_table_action_affordance(self._table, affordance)
        header = self._table.horizontalHeader()
        for index, width in enumerate(widths):
            if width is None:
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Fixed)
                self._table.setColumnWidth(index, width)
        self._table.cellClicked.connect(self._on_row_clicked)

        empty_title, empty_hint = _QUEUE_EMPTY_TEXT[self.queue]
        self._empty = EmptyStateWidget(empty_title, empty_hint)
        self._empty.setVisible(False)

        root.addWidget(self._table, 1)
        root.addWidget(self._empty)

    def refresh_data(self) -> None:
        if self.queue == "overdue":
            self._rows = supplier_event_queue_service.list_overdue_case_queue_rows()
        elif self.queue == "root_cause":
            self._rows = supplier_event_queue_service.list_root_cause_pending_case_queue_rows()
        else:
            self._rows = supplier_event_queue_service.list_open_action_queue_rows()
        self._render_rows()
        self.update()

    def _overdue_due_item(self, due_date: str, *, overdue: bool):
        item = text_table_item(due_date or "—")
        if overdue:
            item.setForeground(QColor(TOKENS["status_danger_fg"]))
            item.setToolTip("已逾期，請優先處理")
        return item

    def _render_rows(self) -> None:
        has_rows = bool(self._rows)
        self._table.setVisible(has_rows)
        self._empty.setVisible(not has_rows)
        with preserve_table_sorting(self._table):
            self._table.setRowCount(0)
            for row in self._rows:
                index = self._table.rowCount()
                self._table.insertRow(index)
                if self.queue == "open_actions":
                    ref_item = SortableTableWidgetItem(
                        str(row.get("ref_no") or "—"),
                        sort_key=str(row.get("ref_no") or ""),
                    )
                    ref_item.setData(
                        Qt.ItemDataRole.UserRole,
                        str(row.get("anomaly_id") or ""),
                    )
                    action_type = str(row.get("action_type") or "")
                    action_label = CASE_ACTION_TYPE_LABELS.get(action_type, action_type or "—")
                    values = {
                        "ref_no": ref_item,
                        "supplier_name": text_table_item(row.get("supplier_name") or "—"),
                        "action_type": text_table_item(action_label),
                        "description": text_table_item(row.get("description") or "—"),
                        "owner": text_table_item(row.get("owner") or "—"),
                        "due_date": self._overdue_due_item(
                            str(row.get("due_date") or ""),
                            overdue=bool(row.get("overdue")),
                        ),
                        "execution_status": create_status_item(
                            str(row.get("execution_status") or "—"),
                            sort_key=str(row.get("execution_status") or ""),
                        ),
                        "overdue": text_table_item("逾期" if row.get("overdue") else "—"),
                    }
                else:
                    ref_item = SortableTableWidgetItem(
                        str(row.get("ref_no") or "—"),
                        sort_key=str(row.get("ref_no") or ""),
                    )
                    ref_item.setData(
                        Qt.ItemDataRole.UserRole,
                        str(row.get("anomaly_id") or row.get("event_id") or ""),
                    )
                    values = {
                        "ref_no": ref_item,
                        "supplier_name": text_table_item(row.get("supplier_name") or "—"),
                        "content": text_table_item(row.get("content") or "—"),
                        "current_action_text": text_table_item(
                            row.get("current_action_text") or "—"
                        ),
                        "action_due_date": self._overdue_due_item(
                            str(row.get("action_due_date") or ""),
                            overdue=bool(row.get("overdue")),
                        ),
                        "responsible_person": text_table_item(
                            row.get("responsible_person") or "—"
                        ),
                    }
                    if self.queue == "root_cause":
                        values["root_cause_status"] = text_table_item(
                            row.get("root_cause_status") or "—"
                        )
                for column, spec in enumerate(self._columns):
                    self._table.setItem(index, column, values[spec.field])

    def _on_row_clicked(self, row: int, _column: int) -> None:
        item = self._table.item(row, 0)
        if item is None:
            return
        anomaly_id = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not anomaly_id:
            return
        opener = getattr(self.main_window, "open_anomaly_management", None)
        if callable(opener):
            opener(anomaly_id, source_page_key=self.page_key)
