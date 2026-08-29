"""Manager summary view and operational action queue."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from services import manager_view_service
from ui.layout_constants import (
    CONTROL_ROW_SPACING,
    MANAGER_ACTION_QUEUE_ANOMALY_NO_WIDTH,
    MANAGER_ACTION_QUEUE_DUE_DATE_WIDTH,
    MANAGER_ACTION_QUEUE_STATUS_WIDTH,
    MANAGER_ACTION_QUEUE_SUPPLIER_WIDTH,
    MANAGER_ACTION_QUEUE_TYPE_WIDTH,
    MANAGER_SUMMARY_ANOMALY_NO_WIDTH,
    MANAGER_SUMMARY_DUE_DATE_WIDTH,
    MANAGER_SUMMARY_QUALITY_WIDTH,
    MANAGER_SUMMARY_STATUS_WIDTH,
    MANAGER_SUMMARY_SUPPLIER_WIDTH,
    MANAGER_SUMMARY_UPDATED_WIDTH,
    PAGE_OUTER_MARGINS,
    PANEL_MARGINS,
)
from ui.list_column_contract import (
    MANAGER_SUMMARY_COLUMNS,
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


class ManagerViewPage(QWidget):
    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self._summary_rows: list[dict] = []
        self._queue_rows: list[dict] = []
        self._owner_filter_timer = QTimer(self)
        self._owner_filter_timer.setSingleShot(True)
        self._owner_filter_timer.setInterval(300)
        self._owner_filter_timer.timeout.connect(self.refresh_data)
        self._build_ui()
        self.refresh_data()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(*PAGE_OUTER_MARGINS)
        root.setSpacing(CONTROL_ROW_SPACING)

        controls = QueryWorkflowShell()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(*PANEL_MARGINS)
        controls_layout.addWidget(QLabel("主管檢視"))
        self._metrics_label = QLabel()
        self._metrics_label.setProperty("role", "muted")
        controls_layout.addWidget(self._metrics_label, 1)
        controls_layout.addWidget(QLabel("案件狀態"))
        self._status_combo = QComboBox()
        self._status_combo.addItem("待處理", "待處理")
        self._status_combo.addItem("已結案", "已結案")
        self._status_combo.addItem("全部", "ALL")
        self._status_combo.currentIndexChanged.connect(self.refresh_data)
        controls_layout.addWidget(self._status_combo)
        self._owner_filter = QLineEdit()
        self._owner_filter.setPlaceholderText("異常責任人篩選")
        self._owner_filter.setToolTip(
            "案件總覽：比對異常責任人與目前處置責任人；作業清單：比對處置責任人。"
        )
        self._owner_filter.textChanged.connect(self._schedule_owner_filter_refresh)
        controls_layout.addWidget(self._owner_filter)
        self._overdue_only = QCheckBox("僅顯示逾期")
        self._overdue_only.stateChanged.connect(self.refresh_data)
        controls_layout.addWidget(self._overdue_only)
        refresh = QPushButton("重新整理")
        refresh.setProperty("variant", "secondary")
        refresh.clicked.connect(self.refresh_data)
        controls_layout.addWidget(refresh)
        export_btn = QPushButton("匯出 Excel")
        export_btn.setProperty("variant", "primary")
        export_btn.clicked.connect(self._export_excel)
        controls_layout.addWidget(export_btn)
        root.addWidget(controls)

        self._tabs = QTabWidget()
        self._summary_table = self._build_table(
            MANAGER_SUMMARY_COLUMNS,
            (
                MANAGER_SUMMARY_ANOMALY_NO_WIDTH,
                MANAGER_SUMMARY_SUPPLIER_WIDTH,
                None,
                MANAGER_SUMMARY_STATUS_WIDTH,
                None,
                MANAGER_SUMMARY_DUE_DATE_WIDTH,
                MANAGER_SUMMARY_STATUS_WIDTH,
                MANAGER_SUMMARY_QUALITY_WIDTH,
                MANAGER_SUMMARY_QUALITY_WIDTH,
                MANAGER_SUMMARY_QUALITY_WIDTH,
                MANAGER_SUMMARY_UPDATED_WIDTH,
            ),
            "ManagerSummaryTable",
            "雙擊案件列開啟案件工作台",
        )
        self._summary_empty = EmptyStateWidget("尚無符合條件的案件")
        self._summary_empty.setVisible(False)
        summary_tab = QWidget()
        summary_layout = QVBoxLayout(summary_tab)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.addWidget(self._summary_table, 1)
        summary_layout.addWidget(self._summary_empty)
        self._tabs.addTab(summary_tab, "案件總覽")

        self._queue_table = self._build_table(
            OPERATIONAL_ACTION_QUEUE_COLUMNS,
            (
                MANAGER_ACTION_QUEUE_ANOMALY_NO_WIDTH,
                MANAGER_ACTION_QUEUE_SUPPLIER_WIDTH,
                MANAGER_ACTION_QUEUE_TYPE_WIDTH,
                None,
                MANAGER_ACTION_QUEUE_SUPPLIER_WIDTH,
                MANAGER_ACTION_QUEUE_DUE_DATE_WIDTH,
                MANAGER_ACTION_QUEUE_STATUS_WIDTH,
                MANAGER_ACTION_QUEUE_STATUS_WIDTH,
            ),
            "OperationalActionQueueTable",
            "雙擊處置列開啟對應案件工作台",
        )
        self._queue_empty = EmptyStateWidget("目前沒有開啟中的處置")
        self._queue_empty.setVisible(False)
        queue_tab = QWidget()
        queue_layout = QVBoxLayout(queue_tab)
        queue_layout.setContentsMargins(0, 0, 0, 0)
        queue_layout.addWidget(self._queue_table, 1)
        queue_layout.addWidget(self._queue_empty)
        self._tabs.addTab(queue_tab, "作業清單")
        self._tabs.currentChanged.connect(self._sync_owner_filter_placeholder)
        root.addWidget(self._tabs, 1)

        self._summary_table.cellDoubleClicked.connect(
            lambda row, _column: self._open_row(self._summary_table, row)
        )
        self._queue_table.cellDoubleClicked.connect(
            lambda row, _column: self._open_row(self._queue_table, row)
        )

    def _build_table(
        self,
        columns: tuple,
        widths: tuple[int | None, ...],
        object_name: str,
        affordance: str,
    ) -> QTableWidget:
        table = QTableWidget(0, len(columns))
        table.setObjectName(object_name)
        table.setHorizontalHeaderLabels([column.label for column in columns])
        style_table(table)
        apply_table_action_affordance(table, affordance)
        header = table.horizontalHeader()
        for index, width in enumerate(widths):
            if width is None:
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Fixed)
                table.setColumnWidth(index, width)
        return table

    def _overdue_table_item(self, overdue: bool):
        item = text_table_item("逾期" if overdue else "—")
        if overdue:
            item.setForeground(QColor(TOKENS["status_danger_fg"]))
        return item

    def _schedule_owner_filter_refresh(self) -> None:
        self._owner_filter_timer.start()

    def _sync_owner_filter_placeholder(self) -> None:
        if self._tabs.currentIndex() == 0:
            self._owner_filter.setPlaceholderText("異常責任人篩選")
        else:
            self._owner_filter.setPlaceholderText("處置責任人篩選")

    def _filters_active(self) -> bool:
        status = str(self._status_combo.currentData() or "待處理")
        return bool(
            self._owner_filter.text().strip()
            or self._overdue_only.isChecked()
            or status != "待處理"
        )

    def refresh_data(self) -> None:
        status = str(self._status_combo.currentData() or "待處理")
        owner = self._owner_filter.text().strip()
        overdue_only = self._overdue_only.isChecked()
        metrics = manager_view_service.get_manager_operational_metrics()
        metrics_text = (
            f"待處理 {metrics.get('pending_anomaly_count', 0)}　"
            f"逾期 {metrics.get('overdue_anomaly_count', 0)}　"
            f"開啟處置 {metrics.get('open_action_count', 0)}　"
            f"根本原因待調查 {metrics.get('root_cause_pending_count', 0)}　"
            f"作業清單 {metrics.get('open_queue_action_count', 0)}"
        )
        if self._filters_active():
            metrics_text += "　（指標為全域；表格已套用篩選）"
        self._metrics_label.setText(metrics_text)
        self._summary_rows = manager_view_service.list_manager_summary_rows(
            status=status,
            overdue_only=overdue_only,
            responsible_person=owner,
        )
        self._queue_rows = manager_view_service.list_operational_action_queue(
            responsible_person=owner,
            overdue_only=overdue_only,
        )
        self._render_summary_rows()
        self._render_queue_rows()
        self.update()

    def _render_summary_rows(self) -> None:
        has_rows = bool(self._summary_rows)
        self._summary_table.setVisible(has_rows)
        self._summary_empty.setVisible(not has_rows)
        with preserve_table_sorting(self._summary_table):
            self._summary_table.setRowCount(0)
            for row in self._summary_rows:
                index = self._summary_table.rowCount()
                self._summary_table.insertRow(index)
                values = {
                    "ref_no": SortableTableWidgetItem(
                        str(row.get("ref_no") or "—"),
                        sort_key=str(row.get("ref_no") or ""),
                    ),
                    "supplier_name": text_table_item(row.get("supplier_name") or "—"),
                    "content": text_table_item(row.get("content") or "—"),
                    "status": create_status_item(
                        str(row.get("status") or "—"),
                        sort_key=str(row.get("status") or ""),
                    ),
                    "current_action_text": text_table_item(
                        row.get("current_action_text") or "—"
                    ),
                    "action_due_date": text_table_item(row.get("action_due_date") or "—"),
                    "overdue": self._overdue_table_item(bool(row.get("overdue"))),
                    "root_cause_status": text_table_item(
                        row.get("root_cause_status") or "—"
                    ),
                    "corrective_action_status": text_table_item(
                        row.get("corrective_action_status") or "—"
                    ),
                    "verification_result": text_table_item(
                        row.get("verification_result") or "—"
                    ),
                    "last_updated": text_table_item(row.get("last_updated") or "—"),
                }
                values["ref_no"].setData(
                    Qt.ItemDataRole.UserRole,
                    str(row.get("anomaly_id") or row.get("event_id") or ""),
                )
                for column, spec in enumerate(MANAGER_SUMMARY_COLUMNS):
                    self._summary_table.setItem(index, column, values[spec.field])

    def _render_queue_rows(self) -> None:
        has_rows = bool(self._queue_rows)
        self._queue_table.setVisible(has_rows)
        self._queue_empty.setVisible(not has_rows)
        with preserve_table_sorting(self._queue_table):
            self._queue_table.setRowCount(0)
            for row in self._queue_rows:
                index = self._queue_table.rowCount()
                self._queue_table.insertRow(index)
                ref_item = SortableTableWidgetItem(
                    str(row.get("ref_no") or "—"),
                    sort_key=str(row.get("ref_no") or ""),
                )
                ref_item.setData(
                    Qt.ItemDataRole.UserRole,
                    str(row.get("anomaly_id") or ""),
                )
                overdue_item = self._overdue_table_item(bool(row.get("overdue")))
                values = {
                    "ref_no": ref_item,
                    "supplier_name": text_table_item(row.get("supplier_name") or "—"),
                    "action_type": text_table_item(row.get("action_type") or "—"),
                    "description": text_table_item(row.get("description") or "—"),
                    "owner": text_table_item(row.get("owner") or "—"),
                    "due_date": text_table_item(row.get("due_date") or "—"),
                    "execution_status": create_status_item(
                        str(row.get("execution_status") or "—"),
                        sort_key=str(row.get("execution_status") or ""),
                    ),
                    "overdue": overdue_item,
                }
                for column, spec in enumerate(OPERATIONAL_ACTION_QUEUE_COLUMNS):
                    self._queue_table.setItem(index, column, values[spec.field])

    def _export_excel(self) -> None:
        from datetime import datetime

        from PySide6.QtWidgets import QFileDialog, QMessageBox

        from services import manager_export_service
        from ui.export_helpers import get_default_export_filepath, handle_export_completion

        default_name = (
            f"SQE_Manager_View_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "匯出主管檢視 Excel",
            get_default_export_filepath(default_name),
            "Excel Files (*.xlsx)",
        )
        if not file_path:
            return
        ok, message = manager_export_service.export_manager_view_excel(
            file_path,
            self._summary_rows,
            self._queue_rows,
        )
        if ok:
            handle_export_completion(file_path, message, self)
        else:
            QMessageBox.critical(self, "失敗", message)

    def _open_row(self, table: QTableWidget, row: int) -> None:
        item = table.item(row, 0)
        if item is None:
            return
        anomaly_id = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        self._open_anomaly(anomaly_id)

    def _open_anomaly(self, anomaly_id: str) -> None:
        if not anomaly_id:
            return
        opener = getattr(self.main_window, "open_anomaly_management", None)
        if callable(opener):
            opener(anomaly_id)
