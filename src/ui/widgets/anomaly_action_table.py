"""Read-only Action list table for the anomaly management workbench."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTableWidget,
    QWidget,
)

from database.repo_helpers import (
    ACTION_VERIFICATION_PENDING,
    CASE_ACTION_TYPE_LABELS,
)
from services.event import _case_action_service
from ui.layout_constants import (
    WORKBENCH_ACTION_DUE_DATE_WIDTH,
    WORKBENCH_ACTION_EDIT_WIDTH,
    WORKBENCH_ACTION_FLOW_WIDTH,
    WORKBENCH_ACTION_OWNER_WIDTH,
    WORKBENCH_ACTION_ROW_HEIGHT,
    WORKBENCH_ACTION_STATUS_WIDTH,
    WORKBENCH_ACTION_TYPE_WIDTH,
)
from ui.popup_i18n import localize_exception
from ui.widgets.common_widgets import (
    make_table_cell_action_button,
    make_table_cell_widget_host,
    style_table,
    text_table_item,
)


class AnomalyActionTable(QTableWidget):
    """Read-only Action list with separated edit and workflow columns."""

    TABLE_HEADERS = (
        "狀態",
        "Action 類型",
        "處置內容",
        "責任人",
        "預定日期",
        "編輯",
        "流程",
    )

    COL_STATUS = 0
    COL_TYPE = 1
    COL_DESC = 2
    COL_OWNER = 3
    COL_DUE = 4
    COL_EDIT = 5
    COL_FLOW = 6

    data_changed = Signal()

    def __init__(
        self,
        actions: list[dict],
        *,
        commands_enabled: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(len(actions), len(self.TABLE_HEADERS), parent)
        self.setObjectName("AnomalyActionTable")
        self.setHorizontalHeaderLabels(list(self.TABLE_HEADERS))
        style_table(self, enable_sorting=False)
        self._commands_enabled = commands_enabled
        self._row_actions: list[dict] = []

        header = self.horizontalHeader()
        header.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self.COL_TYPE, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self.COL_DESC, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_OWNER, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self.COL_DUE, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self.COL_EDIT, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self.COL_FLOW, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(self.COL_STATUS, WORKBENCH_ACTION_STATUS_WIDTH)
        self.setColumnWidth(self.COL_TYPE, WORKBENCH_ACTION_TYPE_WIDTH)
        self.setColumnWidth(self.COL_OWNER, WORKBENCH_ACTION_OWNER_WIDTH)
        self.setColumnWidth(self.COL_DUE, WORKBENCH_ACTION_DUE_DATE_WIDTH)
        self.setColumnWidth(self.COL_EDIT, WORKBENCH_ACTION_EDIT_WIDTH)
        self.setColumnWidth(self.COL_FLOW, WORKBENCH_ACTION_FLOW_WIDTH)

        self.cellDoubleClicked.connect(self._on_cell_double_clicked)

        for row_index, action in enumerate(actions):
            self._populate_row(row_index, action)

    def _populate_row(self, row_index: int, action: dict) -> None:
        row_action = dict(action)
        self._row_actions.append(row_action)
        editable = self._is_row_editable(action)

        self.setCellWidget(
            row_index, self.COL_STATUS, self._build_status_widget(action)
        )
        self.setItem(
            row_index,
            self.COL_TYPE,
            text_table_item(self._action_type_label(action)),
        )
        self.setItem(
            row_index,
            self.COL_DESC,
            text_table_item(str(action.get("description") or "")),
        )
        self.setItem(
            row_index,
            self.COL_OWNER,
            text_table_item(str(action.get("owner") or "")),
        )
        self.setItem(
            row_index,
            self.COL_DUE,
            text_table_item(str(action.get("due_date") or "").strip()),
        )
        self.setCellWidget(
            row_index,
            self.COL_EDIT,
            self._build_edit_widget(action, editable=editable),
        )
        self.setCellWidget(
            row_index,
            self.COL_FLOW,
            self._build_flow_widget(action),
        )
        self.setRowHeight(row_index, WORKBENCH_ACTION_ROW_HEIGHT)

        if editable:
            for column in (
                self.COL_TYPE,
                self.COL_DESC,
                self.COL_OWNER,
                self.COL_DUE,
            ):
                item = self.item(row_index, column)
                if item is not None:
                    item.setToolTip("雙擊開啟編輯對話框")

    def _is_row_editable(self, action: dict) -> bool:
        if not self._commands_enabled:
            return False
        return str(action.get("execution_status") or "") in ("已規劃", "執行中")

    @staticmethod
    def _action_type_label(action: dict) -> str:
        label = str(action.get("action_type_label") or "").strip()
        if label:
            return label
        action_type = str(action.get("action_type") or "")
        return CASE_ACTION_TYPE_LABELS.get(action_type, action_type)

    def _build_status_widget(self, action: dict) -> QWidget:
        status_label, status_tone = self._action_display_status(action)
        host = QWidget()
        layout = QHBoxLayout(host)
        layout.setContentsMargins(4, 2, 4, 2)
        badge = QLabel(f"  {status_label}  ")
        badge.setProperty("role", "statusBadge")
        badge.setProperty("tone", status_tone)
        layout.addWidget(badge)
        layout.addStretch(1)
        return host

    def _build_edit_widget(self, action: dict, *, editable: bool) -> QWidget:
        host, row = make_table_cell_widget_host()
        action_id = str(action.get("id") or "")

        if editable:
            row.addWidget(
                make_table_cell_action_button(
                    "編輯",
                    accessible_name=f"編輯 Action {action_id}",
                    tooltip="開啟編輯對話框",
                    on_clicked=lambda row_data=dict(action): self._open_edit_dialog(
                        row_data
                    ),
                )
            )
        row.addStretch(1)
        return host

    def _build_flow_widget(self, action: dict) -> QWidget:
        host, row = make_table_cell_widget_host()
        action_id = str(action.get("id") or "")

        if self._commands_enabled:
            status = str(action.get("execution_status") or "")
            if status == "已規劃":
                row.addWidget(
                    make_table_cell_action_button(
                        "開始執行",
                        accessible_name=f"開始執行 {action.get('description') or 'Action'}",
                        tooltip="將狀態更新為執行中",
                        on_clicked=lambda aid=action_id: self._start_case_action(aid),
                    )
                )
                row.addWidget(
                    make_table_cell_action_button(
                        "取消",
                        accessible_name=f"取消 Action {action_id}",
                        tooltip="取消此 Action",
                        on_clicked=lambda row_data=dict(action): self._open_cancel_dialog(
                            row_data
                        ),
                    )
                )
            elif status == "執行中":
                row.addWidget(
                    make_table_cell_action_button(
                        "完成",
                        accessible_name=f"完成 {action.get('description') or 'Action'}",
                        tooltip="標記 Action 為已完成",
                        on_clicked=lambda row_data=dict(action): (
                            self._open_complete_action_dialog(row_data)
                        ),
                    )
                )
                row.addWidget(
                    make_table_cell_action_button(
                        "取消",
                        accessible_name=f"取消 Action {action_id}",
                        tooltip="取消此 Action",
                        on_clicked=lambda row_data=dict(action): self._open_cancel_dialog(
                            row_data
                        ),
                    )
                )

        if self._allows_action_verification(action):
            row.addWidget(
                make_table_cell_action_button(
                    "新增有效性驗證",
                    accessible_name=f"驗證 {action.get('description') or 'Action'}",
                    tooltip="追加一筆有效性驗證紀錄",
                    on_clicked=lambda row_data=dict(action): (
                        self._open_verification_dialog(row_data)
                    ),
                )
            )
        row.addStretch(1)
        return host

    def _allows_action_verification(self, action: dict) -> bool:
        if not self._commands_enabled:
            return False
        status = str(action.get("execution_status") or "")
        if status != "已完成" or not bool(action.get("verification_required")):
            return False
        verify_status = str(
            action.get("verification_status") or ACTION_VERIFICATION_PENDING
        )
        return verify_status == ACTION_VERIFICATION_PENDING

    @staticmethod
    def _action_display_status(action: dict) -> tuple[str, str]:
        execution_status = str(action.get("execution_status") or "")
        tone_map = {
            "已規劃": "warning",
            "執行中": "info",
            "已完成": "success",
            "已取消": "na",
        }
        if execution_status in tone_map:
            return execution_status, tone_map[execution_status]
        return execution_status or "—", "pending"

    def _on_cell_double_clicked(self, row: int, column: int) -> None:
        if column in (self.COL_EDIT, self.COL_FLOW):
            return
        if row < 0 or row >= len(self._row_actions):
            return
        action = self._row_actions[row]
        if not self._is_row_editable(action):
            return
        self._open_edit_dialog(action)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        index = self.indexAt(event.position().toPoint())
        if index.isValid() and index.column() in (self.COL_EDIT, self.COL_FLOW):
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _start_case_action(self, action_id: str) -> None:
        try:
            _case_action_service.start_case_action(action_id)
        except (ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "無法開始 Action", localize_exception(exc))
            return
        self.data_changed.emit()

    def _open_edit_dialog(self, action: dict) -> None:
        from ui.widgets.edit_anomaly_action_dialog import EditAnomalyActionDialog

        dialog = EditAnomalyActionDialog(action, parent=self.window())
        dialog.action_updated.connect(lambda _id: self.data_changed.emit())
        dialog.exec()

    def _open_cancel_dialog(self, action: dict) -> None:
        from ui.widgets.complete_action_dialog import (
            CompleteActionDialog,
            OUTCOME_CANCELLED,
        )

        dialog = CompleteActionDialog(
            str(action.get("id") or ""),
            action_summary=str(action.get("description") or ""),
            parent=self.window(),
        )
        cancel_index = dialog.outcome_combo.findData(OUTCOME_CANCELLED)
        if cancel_index >= 0:
            dialog.outcome_combo.setCurrentIndex(cancel_index)
        dialog.action_updated.connect(lambda _id: self.data_changed.emit())
        dialog.exec()

    def _open_complete_action_dialog(self, action: dict) -> None:
        from ui.widgets.complete_action_dialog import CompleteActionDialog

        dialog = CompleteActionDialog(
            str(action.get("id") or ""),
            action_summary=str(action.get("description") or ""),
            parent=self.window(),
        )
        dialog.action_updated.connect(lambda _id: self.data_changed.emit())
        dialog.exec()

    def _open_verification_dialog(self, action: dict) -> None:
        from ui.widgets.add_verification_dialog import AddVerificationDialog

        dialog = AddVerificationDialog(
            str(action.get("id") or ""),
            description=str(action.get("description") or ""),
            parent=self.window(),
        )
        dialog.verification_created.connect(lambda _id: self.data_changed.emit())
        dialog.exec()
