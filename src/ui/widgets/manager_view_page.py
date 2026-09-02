"""Manager summary view (case overview only)."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from services import manager_view_service
from ui.layout_constants import (
    CONTROL_ROW_SPACING,
    MANAGER_SUMMARY_ANOMALY_NO_WIDTH,
    MANAGER_SUMMARY_DUE_DATE_WIDTH,
    MANAGER_SUMMARY_QUALITY_WIDTH,
    MANAGER_SUMMARY_STATUS_WIDTH,
    MANAGER_SUMMARY_SUPPLIER_WIDTH,
    MANAGER_SUMMARY_UPDATED_WIDTH,
    PAGE_OUTER_MARGINS,
    PANEL_MARGINS,
)
from ui.list_column_contract import MANAGER_SUMMARY_COLUMNS
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
    def __init__(self, main_window, parent=None, *, embedded: bool = False) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self._embedded = embedded
        self._summary_rows: list[dict] = []
        self._owner_filter_timer = QTimer(self)
        self._owner_filter_timer.setSingleShot(True)
        self._owner_filter_timer.setInterval(300)
        self._owner_filter_timer.timeout.connect(self.refresh_data)
        self._build_ui()
        self.refresh_data()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        if self._embedded:
            root.setContentsMargins(0, 0, 0, 0)
        else:
            root.setContentsMargins(*PAGE_OUTER_MARGINS)
        root.setSpacing(CONTROL_ROW_SPACING)

        controls = QueryWorkflowShell()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(*PANEL_MARGINS)
        if not self._embedded:
            title = QLabel("案件總覽")
            title.setProperty("role", "sectionTitle")
            controls_layout.addWidget(title)
        controls_layout.addStretch(1)
        controls_layout.addWidget(QLabel("案件狀態"))
        self._status_combo = QComboBox()
        self._status_combo.addItem("待處理", "待處理")
        self._status_combo.addItem("已結案", "已結案")
        self._status_combo.addItem("全部", "ALL")
        self._status_combo.currentIndexChanged.connect(self.refresh_data)
        controls_layout.addWidget(self._status_combo)
        self._owner_filter = QLineEdit()
        self._owner_filter.setPlaceholderText("異常責任人篩選")
        self._owner_filter.setToolTip("比對異常責任人與目前處置責任人。")
        self._owner_filter.textChanged.connect(self._schedule_owner_filter_refresh)
        controls_layout.addWidget(self._owner_filter)
        refresh = QPushButton("重新整理")
        refresh.setProperty("variant", "secondary")
        refresh.clicked.connect(self.refresh_data)
        controls_layout.addWidget(refresh)
        export_btn = QPushButton("匯出 Excel")
        export_btn.setProperty("variant", "primary")
        export_btn.clicked.connect(self._export_excel)
        controls_layout.addWidget(export_btn)
        root.addWidget(controls)

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
        root.addWidget(self._summary_table, 1)
        root.addWidget(self._summary_empty)

        self._summary_table.cellDoubleClicked.connect(
            lambda row, _column: self._open_row(self._summary_table, row)
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

    def refresh_data(self) -> None:
        status = str(self._status_combo.currentData() or "待處理")
        owner = self._owner_filter.text().strip()
        self._summary_rows = manager_view_service.list_manager_summary_rows(
            status=status,
            responsible_person=owner,
        )
        self._render_summary_rows()
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
            "匯出案件總覽 Excel",
            get_default_export_filepath(default_name),
            "Excel Files (*.xlsx)",
        )
        if not file_path:
            return
        ok, message = manager_export_service.export_manager_view_excel(
            file_path,
            self._summary_rows,
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
            from ui.sidebar_nav import PAGE_MANAGER_VIEW

            opener(anomaly_id, source_page_key=PAGE_MANAGER_VIEW)
