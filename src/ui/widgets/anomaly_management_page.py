"""主視窗內嵌的供應商異常案件管理頁。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.event import (
    _anomaly_service,
    _anomaly_workbench_service,
    _case_action_service,
)
from services.process_keyword_codec import format_process_keywords_display
from database.repo_helpers import ACTION_VERIFICATION_PENDING
from ui.layout_constants import (
    CONTROL_ROW_SPACING,
    FORM_VERTICAL_SPACING,
    GRID_GUTTER,
    PAGE_OUTER_MARGINS,
    PANEL_MARGINS,
    ROW_GAP,
    WORKBENCH_ACTION_DUE_DATE_WIDTH,
    WORKBENCH_ACTION_OPS_WIDTH,
    WORKBENCH_ACTION_OWNER_WIDTH,
    WORKBENCH_ACTION_STATUS_WIDTH,
)
from ui.widgets.common_widgets import (
    EmptyStateWidget,
    apply_clickable_affordance,
    create_section_card,
    make_multiline_label,
    style_table,
    sync_multiline_label_geometry,
)
from ui.widgets.new_anomaly_dialog import NewAnomalyDialog
from ui.widgets.anomaly_attachment_panel import EvidenceAttachmentPanel
from ui.widgets.close_anomaly_dialog import CloseAnomalyDialog
from ui.widgets.reopen_anomaly_dialog import ReopenAnomalyDialog
from ui.popup_i18n import localize_exception


class AnomalyManagementPage(QWidget):
    """案件詳情與既有工作台資料的單一主視窗入口。"""

    TAB_NAMES = (
        "案件概覽",
        "Action 清單",
        "根本原因",
        "附件與佐證",
        "處理歷程",
    )

    _ACTION_TABLE_HEADERS = (
        "預定日期",
        "責任人",
        "狀態",
        "處置內容",
        "操作",
    )

    _FULL_WIDTH_OVERVIEW_LABELS = frozenset(
        {"供應商", "品名", "料號", "異常類別", "SMT 製程關鍵詞", "來源 NCR 單號"}
    )

    def __init__(self, main_window, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self._anomaly_id = ""
        self._detail: dict = {}
        self._overview: dict = {}
        self._edit_form: NewAnomalyDialog | None = None
        self._editing = False
        self._source_scope: str | None = None
        self.setObjectName("AnomalyManagementPage")
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(*PAGE_OUTER_MARGINS)
        root.setSpacing(CONTROL_ROW_SPACING)

        self.header = QFrame()
        self.header.setObjectName("AnomalyManagementHeader")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(*PANEL_MARGINS)
        header_layout.setSpacing(CONTROL_ROW_SPACING)

        identity_column = QVBoxLayout()
        identity_column.setSpacing(ROW_GAP)

        id_row = QHBoxLayout()
        id_row.setSpacing(CONTROL_ROW_SPACING)
        self.header_number_label = QLabel()
        self.header_number_label.setProperty("role", "mono")
        id_row.addWidget(self.header_number_label)
        self.header_status_badge = self._status_badge("—", "na")
        id_row.addWidget(self.header_status_badge)
        self.header_overdue_badge = self._status_badge("逾期", "danger")
        self.header_overdue_badge.hide()
        id_row.addWidget(self.header_overdue_badge)
        id_row.addStretch(1)
        identity_column.addLayout(id_row)

        self.header_meta_label = make_multiline_label("", role="value")
        identity_column.addWidget(self.header_meta_label)

        identity_host = QWidget()
        identity_host.setLayout(identity_column)
        header_layout.addWidget(identity_host, 1)

        self.back_button = QPushButton("返回異常清單")
        self.back_button.setAccessibleName("返回異常清單")
        self.back_button.setProperty("variant", "secondary")
        self.back_button.clicked.connect(self.return_to_list)
        header_layout.addWidget(self.back_button)
        self.close_button = QPushButton("結案")
        self.close_button.setAccessibleName("結案")
        self.close_button.setProperty("variant", "secondary")
        self.close_button.clicked.connect(self._open_close_dialog)
        header_layout.addWidget(self.close_button)
        self.reopen_button = QPushButton("重新開啟")
        self.reopen_button.setAccessibleName("重新開啟")
        self.reopen_button.setProperty("variant", "secondary")
        self.reopen_button.clicked.connect(self._open_reopen_dialog)
        self.reopen_button.hide()
        header_layout.addWidget(self.reopen_button)
        self.repeat_button = QPushButton("潛在重複 (0)")
        self.repeat_button.setAccessibleName("潛在重複異常")
        self.repeat_button.setProperty("variant", "secondary")
        self.repeat_button.clicked.connect(self._open_repeat_issues_page)
        header_layout.addWidget(self.repeat_button)
        self.edit_button = QPushButton("編輯")
        self.edit_button.setAccessibleName("編輯異常")
        self.edit_button.setProperty("variant", "primary")
        self.edit_button.clicked.connect(self.begin_edit)
        header_layout.addWidget(self.edit_button)
        root.addWidget(self.header)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("AnomalyManagementTabs")
        root.addWidget(self.tabs, 1)

        self.save_button = QPushButton("儲存")
        self.save_button.setAccessibleName("儲存異常")
        self.save_button.setProperty("variant", "primary")
        self.save_button.clicked.connect(self.save_edit)
        self.cancel_button = QPushButton("取消編輯")
        self.cancel_button.setAccessibleName("取消編輯")
        self.cancel_button.setProperty("variant", "secondary")
        self.cancel_button.clicked.connect(self.cancel_edit)
        self.save_button.hide()
        self.cancel_button.hide()

        command_row = QHBoxLayout()
        command_row.addStretch(1)
        command_row.addWidget(self.save_button)
        command_row.addWidget(self.cancel_button)
        root.addLayout(command_row)

    @classmethod
    def resolve_tab_index(cls, initial_tab: str | int | None) -> int | None:
        if initial_tab is None:
            return None
        if isinstance(initial_tab, int):
            if 0 <= initial_tab < len(cls.TAB_NAMES):
                return initial_tab
            return None
        tab_name = str(initial_tab).strip()
        if not tab_name:
            return None
        try:
            return cls.TAB_NAMES.index(tab_name)
        except ValueError:
            return None

    def load_anomaly(
        self,
        anomaly_id: str,
        *,
        edit: bool = False,
        initial_tab: str | int | None = None,
    ) -> None:
        anomaly_key = str(anomaly_id or "").strip()
        if not anomaly_key:
            raise ValueError("Anomaly id is required")
        self._anomaly_id = anomaly_key
        self._detail = _anomaly_service.get_anomaly_detail(anomaly_key)
        self._overview = _anomaly_workbench_service.get_overview_card(anomaly_key)
        self._editing = False
        self._remove_edit_form()
        self._render_header()
        self._sync_back_button_label()
        self._update_repeat_button(anomaly_key)
        self._render_tabs()
        tab_index = self.resolve_tab_index(initial_tab)
        if tab_index is not None:
            self.tabs.setCurrentIndex(tab_index)
        if edit:
            self.begin_edit()

    def _update_repeat_button(self, anomaly_key: str) -> None:
        count = 0
        try:
            from services import repeat_issue_service

            rows = repeat_issue_service.list_repeat_issues(anomaly_key)
            count = len(rows)
        except Exception:
            count = 0
        self.repeat_button.setText(f"潛在重複 ({count})")
        if count > 0:
            self.repeat_button.setProperty("variant", "primary")
            self.repeat_button.setToolTip(
                f"發現 {count} 筆潛在重複歷史異常，點擊前往獨立檢閱與判定管理"
            )
        else:
            self.repeat_button.setProperty("variant", "secondary")
            self.repeat_button.setToolTip("查看此案件的潛在重複異常比對")

    def _open_repeat_issues_page(self) -> None:
        if hasattr(self.main_window, "open_repeat_issues_management"):
            self.main_window.open_repeat_issues_management(self._anomaly_id)

    def _render_header(self) -> None:
        number = self._detail.get("anomaly_no") or self._anomaly_id
        self.header_number_label.setText(str(number))

        status = str(self._detail.get("status") or "—")
        self._set_status_badge(self.header_status_badge, status, self._case_status_tone(status))

        if self._overview.get("overdue"):
            self.header_overdue_badge.show()
        else:
            self.header_overdue_badge.hide()

        supplier = self._detail.get("supplier_name") or "—"
        current = self._overview.get("current_action") or {}
        owner = (
            current.get("owner")
            or self._detail.get("responsible_person")
            or "—"
        )
        opened_on = self._detail.get("anomaly_date") or "—"
        self.header_meta_label.setText(
            f"供應商：{supplier}\n"
            f"負責人：{owner}　開立：{opened_on}"
        )
        sync_multiline_label_geometry(self.header_meta_label)
        self._update_header_actions()

    def _update_header_actions(self) -> None:
        has_case = bool(self._anomaly_id)
        is_closed = self._is_case_closed()
        if is_closed:
            self.close_button.hide()
            self.reopen_button.show()
            self.reopen_button.setEnabled(has_case)
        else:
            self.close_button.show()
            self.reopen_button.hide()
            self.close_button.setEnabled(has_case)
        self.edit_button.setEnabled(not is_closed and has_case)

    def _is_case_closed(self) -> bool:
        return str(self._detail.get("status") or "") == "已結案"

    def _allows_case_action_commands(self) -> bool:
        return bool(self._anomaly_id) and not self._is_case_closed()

    def _allows_action_verification(self, action: dict) -> bool:
        if not self._allows_case_action_commands():
            return False
        status = str(action.get("execution_status") or "")
        if status != "已完成" or not bool(action.get("verification_required")):
            return False
        verify_status = str(
            action.get("verification_status") or ACTION_VERIFICATION_PENDING
        )
        return verify_status == ACTION_VERIFICATION_PENDING

    def _render_tabs(self) -> None:
        while self.tabs.count():
            old = self.tabs.widget(0)
            self.tabs.removeTab(0)
            if old is not None:
                old.deleteLater()
        builders = (
            self._build_overview_tab,
            self._build_actions_tab,
            self._build_root_cause_tab,
            self._build_attachments_tab,
            self._build_timeline_tab,
        )
        for index, builder in enumerate(builders):
            self.tabs.addTab(builder(), self.TAB_NAMES[index])
        tab_bar = self.tabs.tabBar()
        tab_bar.setExpanding(False)
        tab_bar.setDocumentMode(True)
        self.tabs.setCurrentIndex(0)

    def _base_tab(self) -> tuple[QWidget, QVBoxLayout]:
        tab = QWidget()
        tab.setProperty("workbenchTab", True)
        tab_root = QVBoxLayout(tab)
        tab_root.setContentsMargins(0, 0, 0, 0)
        tab_root.setSpacing(0)

        scroll = QScrollArea(tab)
        scroll.setObjectName("AnomalyManagementTabScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(*PANEL_MARGINS)
        layout.setSpacing(FORM_VERTICAL_SPACING)
        scroll.setWidget(body)
        tab_root.addWidget(scroll)
        tab._workbench_content_layout = layout
        tab._workbench_content_body = body
        return tab, layout

    def _build_overview_tab(self) -> QWidget:
        tab, layout = self._base_tab()
        self._add_case_overview_grid(layout, tab)
        layout.addStretch(1)
        return tab

    def _build_actions_tab(self) -> QWidget:
        tab, layout = self._base_tab()
        actions = _case_action_service.list_case_actions(self._anomaly_id)
        card = create_section_card(tab)
        card.layout().addWidget(self._section_title("Action 清單"))
        if not actions:
            card.layout().addWidget(
                EmptyStateWidget("尚無 Action", "可建立下一步處置或改善措施。")
            )
        else:
            card.layout().addWidget(self._build_action_table(actions))
        layout.addWidget(card)
        self._add_action_button(
            layout,
            "新增 Action",
            self._open_add_action_dialog,
            requires_open_case=True,
        )
        layout.addStretch(1)
        return tab

    def _build_root_cause_tab(self) -> QWidget:
        tab, layout = self._base_tab()
        overview = self._overview
        progress_card = create_section_card(tab)
        progress_layout = progress_card.layout()
        progress_layout.addWidget(self._section_title("調查進度"))
        progress_layout.addLayout(
            self._quality_badge_row("根本原因", overview.get("root_cause_status"))
        )
        progress_layout.addLayout(
            self._quality_badge_row(
                "改善措施",
                overview.get("corrective_action_status"),
            )
        )
        progress_layout.addLayout(
            self._quality_badge_row(
                "有效性驗證",
                overview.get("verification_result"),
            )
        )
        layout.addWidget(progress_card)

        root_cause = _anomaly_workbench_service.get_root_cause(self._anomaly_id)
        root_card = create_section_card(tab)
        root_card.layout().addWidget(self._section_title("根本原因"))
        if root_cause:
            root_card.layout().addWidget(self._kv("狀態", root_cause.get("status")))
            root_card.layout().addWidget(self._kv("說明", root_cause.get("statement")))
            root_card.layout().addWidget(
                self._kv("驗證方式", root_cause.get("validation_method"))
            )
        else:
            root_card.layout().addWidget(
                EmptyStateWidget("尚未建立根本原因", "可於異常分析流程補充。")
            )
        layout.addWidget(root_card)
        self._add_action_button(layout, "編輯根本原因", self._open_root_cause_dialog)
        layout.addStretch(1)
        return tab

    def _add_case_overview_grid(self, layout: QVBoxLayout, tab: QWidget) -> None:
        card = create_section_card(tab)
        card_layout = card.layout()
        card_layout.addWidget(self._section_title("案件概覽"))

        always_fields = (
            ("異常單號", self._detail.get("anomaly_no")),
            ("日期", self._detail.get("anomaly_date")),
            ("供應商", self._detail.get("supplier_name")),
            ("品名", self._detail.get("product_name")),
            ("料號", self._detail.get("product_code")),
            ("異常類別", self._detail.get("category")),
            ("數量", self._detail.get("batch_qty")),
        )
        conditional_fields = (
            ("來源 NCR 單號", self._detail.get("source_defect_no")),
            (
                "SMT 製程關鍵詞",
                format_process_keywords_display(self._detail.get("process_keywords")),
            ),
            ("結案日期", self._detail.get("closed_at")),
        )
        fields = list(always_fields)
        fields.extend(
            (label, value)
            for label, value in conditional_fields
            if self._has_display_value(value)
        )

        grid = QGridLayout()
        grid.setHorizontalSpacing(GRID_GUTTER)
        grid.setVerticalSpacing(ROW_GAP)
        row = 0
        column = 0
        for label, value in fields:
            widget = self._kv(label, value)
            if label in self._FULL_WIDTH_OVERVIEW_LABELS:
                if column != 0:
                    row += 1
                    column = 0
                grid.addWidget(widget, row, 0, 1, 2)
                row += 1
                column = 0
                continue
            grid.addWidget(widget, row, column)
            column += 1
            if column >= 2:
                column = 0
                row += 1
        grid.addWidget(
            self._kv("不良現象", self._detail.get("problem_desc")),
            row if column == 0 else row + 1,
            0,
            1,
            2,
        )
        card_layout.addLayout(grid)
        layout.addWidget(card)

    def _build_timeline_tab(self) -> QWidget:
        tab, layout = self._base_tab()
        self._add_list_section(
            layout,
            tab,
            "處理歷程",
            _anomaly_workbench_service.list_timeline(self._anomaly_id),
            lambda row: (
                f"{row.get('ts') or '—'}　{row.get('kind') or ''}　"
                f"{row.get('actor') or ''}\n{row.get('summary') or '—'}"
            ),
        )
        rows = _anomaly_workbench_service.list_audit_logs(self._anomaly_id)
        audit_card = create_section_card(tab)
        audit_card.layout().addWidget(self._section_title("變更紀錄"))
        if not rows:
            audit_card.layout().addWidget(
                EmptyStateWidget("尚無變更紀錄", "其他操作完成後會出現於此。")
            )
        else:
            for row in rows:
                label = make_multiline_label(
                    f"{row.get('action') or '—'}　"
                    f"{row.get('actor_name') or '未知'}　"
                    f"{row.get('created_at') or '—'}\n"
                    f"變更前：{row.get('before_value') or '—'}\n"
                    f"變更後：{row.get('after_value') or '—'}",
                    role="value",
                )
                label.setToolTip(label.text())
                audit_card.layout().addWidget(label)
        layout.addWidget(audit_card)
        self._add_action_button(layout, "新增處理紀錄", self._open_add_audit_log_dialog)
        layout.addStretch(1)
        return tab

    def _build_attachments_tab(self) -> QWidget:
        tab, layout = self._base_tab()
        panel = EvidenceAttachmentPanel(tab)
        panel.set_anomaly(self._anomaly_id)
        panel.changed.connect(self.refresh_data)
        layout.addWidget(panel)
        layout.addStretch(1)
        return tab

    def _add_action_button(
        self,
        layout: QVBoxLayout,
        text: str,
        callback,
        *,
        requires_open_case: bool = False,
    ) -> None:
        row = QHBoxLayout()
        row.setSpacing(CONTROL_ROW_SPACING)
        button = QPushButton(text)
        button.setAccessibleName(text)
        button.setProperty("variant", "secondary")
        apply_clickable_affordance(button, tooltip=text)
        button.clicked.connect(callback)
        if requires_open_case:
            button.setEnabled(self._allows_case_action_commands())
        row.addWidget(button)
        row.addStretch(1)
        layout.addLayout(row)

    def _open_root_cause_dialog(self) -> None:
        from ui.widgets.anomaly_root_cause_dialog import AnomalyRootCauseDialog

        initial = _anomaly_workbench_service.get_root_cause(self._anomaly_id) or {}
        dialog = AnomalyRootCauseDialog(
            self._anomaly_id,
            initial=initial,
            parent=self,
        )
        dialog.root_cause_saved.connect(lambda _id: self.refresh_data())
        dialog.exec()

    def _open_add_action_dialog(self) -> None:
        from ui.widgets.anomaly_action_dialog import AddAnomalyActionDialog

        dialog = AddAnomalyActionDialog(self._anomaly_id, self)
        dialog.action_created.connect(lambda _id: self.refresh_data())
        dialog.exec()

    def _start_case_action(self, action_id: str) -> None:
        try:
            _case_action_service.start_case_action(action_id)
        except (ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "無法開始 Action", localize_exception(exc))
            return
        self.refresh_data()

    def _open_complete_action_dialog(self, action: dict) -> None:
        from ui.widgets.complete_action_dialog import CompleteActionDialog

        dialog = CompleteActionDialog(
            str(action.get("id") or ""),
            action_summary=str(action.get("description") or ""),
            parent=self,
        )
        if str(action.get("execution_status") or "") == "已規劃":
            dialog.outcome_combo.setCurrentIndex(1)
            dialog.outcome_combo.setEnabled(False)
        dialog.action_updated.connect(lambda _id: self.refresh_data())
        dialog.exec()

    def _open_verification_dialog(self, action: dict) -> None:
        from ui.widgets.add_verification_dialog import AddVerificationDialog

        dialog = AddVerificationDialog(
            str(action.get("id") or ""),
            description=str(action.get("description") or ""),
            parent=self,
        )
        dialog.verification_created.connect(lambda _id: self.refresh_data())
        dialog.exec()

    def _open_add_audit_log_dialog(self) -> None:
        from ui.widgets.add_audit_log_dialog import AddAuditLogDialog

        dialog = AddAuditLogDialog(self._anomaly_id, parent=self)
        dialog.audit_created.connect(lambda _id: self.refresh_data())
        dialog.exec()

    def _open_close_dialog(self) -> None:
        if str(self._detail.get("status") or "") == "已結案":
            return
        dialog = CloseAnomalyDialog(
            self._anomaly_id,
            str(self._detail.get("problem_desc") or ""),
            self,
        )
        if dialog.exec():
            self._after_workflow_mutation()

    def _open_reopen_dialog(self) -> None:
        if str(self._detail.get("status") or "") != "已結案":
            return
        dialog = ReopenAnomalyDialog(
            self._anomaly_id,
            str(self._detail.get("anomaly_no") or ""),
            self,
        )
        if dialog.exec():
            self._after_workflow_mutation()

    def _after_workflow_mutation(self) -> None:
        self.refresh_data()
        refresh = getattr(self.main_window, "refresh_all_views", None)
        if callable(refresh):
            refresh()

    def _add_list_section(
        self,
        layout: QVBoxLayout,
        tab: QWidget,
        title: str,
        rows: list[dict],
        formatter,
    ) -> None:
        card = create_section_card(tab)
        card.layout().addWidget(self._section_title(title))
        if not rows:
            card.layout().addWidget(
                EmptyStateWidget(f"尚無{title}", "目前沒有可顯示的資料。")
            )
        else:
            for row in rows:
                label = make_multiline_label(formatter(row), role="value")
                label.setToolTip(label.text())
                card.layout().addWidget(label)
        layout.addWidget(card)

    def _build_action_table(self, actions: list[dict]) -> QTableWidget:
        table = QTableWidget(len(actions), len(self._ACTION_TABLE_HEADERS))
        table.setObjectName("AnomalyActionTable")
        table.setHorizontalHeaderLabels(list(self._ACTION_TABLE_HEADERS))
        style_table(table, enable_sorting=False)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, WORKBENCH_ACTION_DUE_DATE_WIDTH)
        table.setColumnWidth(1, WORKBENCH_ACTION_OWNER_WIDTH)
        table.setColumnWidth(2, WORKBENCH_ACTION_STATUS_WIDTH)
        table.setColumnWidth(4, WORKBENCH_ACTION_OPS_WIDTH)

        for row_index, action in enumerate(actions):
            due_item = QTableWidgetItem(str(action.get("due_date") or "—"))
            due_item.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            table.setItem(row_index, 0, due_item)

            owner_item = QTableWidgetItem(str(action.get("owner") or "—"))
            owner_item.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            table.setItem(row_index, 1, owner_item)

            status_label, status_tone = self._action_display_status(action)
            status_host = QWidget()
            status_layout = QHBoxLayout(status_host)
            status_layout.setContentsMargins(4, 2, 4, 2)
            status_layout.addWidget(self._status_badge(status_label, status_tone))
            status_layout.addStretch(1)
            table.setCellWidget(row_index, 2, status_host)

            type_label = (
                action.get("action_type_label")
                or action.get("action_type")
                or "—"
            )
            description = str(action.get("description") or "—")
            content_item = QTableWidgetItem(f"{type_label}\n{description}")
            content_item.setToolTip(content_item.text())
            table.setItem(row_index, 3, content_item)

            table.setCellWidget(
                row_index,
                4,
                self._build_action_ops_widget(action),
            )
            table.setRowHeight(row_index, max(table.rowHeight(row_index), 56))

        return table

    def _build_action_ops_widget(self, action: dict) -> QWidget:
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(CONTROL_ROW_SPACING)
        if self._allows_case_action_commands():
            status = str(action.get("execution_status") or "")
            if status == "已規劃":
                start_button = QPushButton("開始執行")
                start_button.setAccessibleName(
                    f"開始執行 {action.get('description') or 'Action'}"
                )
                start_button.setProperty("variant", "secondary")
                apply_clickable_affordance(
                    start_button, tooltip="將狀態更新為執行中"
                )
                start_button.clicked.connect(
                    lambda _checked=False, action_id=str(action.get("id") or ""): (
                        self._start_case_action(action_id)
                    )
                )
                row.addWidget(start_button)
            if status in ("已規劃", "執行中"):
                update_button = QPushButton(
                    "取消" if status == "已規劃" else "完成／取消"
                )
                update_button.setAccessibleName(
                    f"完成或取消 {action.get('description') or 'Action'}"
                )
                update_button.setProperty("variant", "secondary")
                apply_clickable_affordance(
                    update_button, tooltip="更新 Action 執行狀態"
                )
                update_button.clicked.connect(
                    lambda _checked=False, row_data=dict(action): (
                        self._open_complete_action_dialog(row_data)
                    )
                )
                row.addWidget(update_button)
        if self._allows_action_verification(action):
            verification_button = QPushButton("新增有效性驗證")
            verification_button.setAccessibleName(
                f"驗證 {action.get('description') or 'Action'}"
            )
            verification_button.setProperty("variant", "secondary")
            apply_clickable_affordance(
                verification_button,
                tooltip="追加一筆有效性驗證紀錄",
            )
            verification_button.clicked.connect(
                lambda _checked=False, row_data=dict(action): (
                    self._open_verification_dialog(row_data)
                )
            )
            row.addWidget(verification_button)
        row.addStretch(1)
        return host

    @staticmethod
    def _action_display_status(action: dict) -> tuple[str, str]:
        execution_status = str(action.get("execution_status") or "")
        if execution_status == "已完成":
            return "Done", "success"
        if execution_status == "已取消":
            return "已取消", "na"
        if execution_status in {"已規劃", "執行中"}:
            return "Open", "warning"
        return execution_status or "—", "pending"

    def begin_edit(self) -> None:
        if not self._anomaly_id or self._editing:
            return
        self._editing = True
        self._edit_form = NewAnomalyDialog(
            self,
            anomaly_id=self._anomaly_id,
            initial_data=self._detail,
            embedded=True,
            page_mode=True,
        )
        processing_tab = self.tabs.widget(0)
        old = getattr(processing_tab, "_workbench_content_layout", None)
        if old is None:
            return
        while old.count():
            item = old.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        old.addWidget(self._edit_form)
        self.edit_button.hide()
        self.save_button.show()
        self.cancel_button.show()
        self.tabs.setCurrentIndex(0)

    def save_edit(self) -> None:
        if self._edit_form is None:
            return
        self._edit_form._on_submit()
        if not getattr(self._edit_form, "_dirty", False):
            self._detail = _anomaly_service.get_anomaly_detail(self._anomaly_id)
            self._overview = _anomaly_workbench_service.get_overview_card(
                self._anomaly_id
            )
            self._editing = False
            self._remove_edit_form()
            self._render_header()
            self._render_tabs()
            self.main_window.refresh_all_views()

    def cancel_edit(self) -> None:
        if self._edit_form is None:
            return
        if getattr(self._edit_form, "_dirty", False) and not self._edit_form._confirm_discard():
            return
        self._editing = False
        self._remove_edit_form()
        self._render_tabs()

    def _remove_edit_form(self) -> None:
        if self._edit_form is not None:
            self._edit_form.setParent(None)
            self._edit_form.deleteLater()
            self._edit_form = None
        self.edit_button.setVisible(bool(self._anomaly_id))
        self.save_button.hide()
        self.cancel_button.hide()

    def can_leave(self) -> bool:
        if self._edit_form is None or not getattr(self._edit_form, "_dirty", False):
            return True
        return self._edit_form._confirm_discard()

    def _sync_back_button_label(self) -> None:
        from ui.sidebar_nav import (
            PAGE_EVENT_OPEN_ACTIONS,
            PAGE_EVENT_OPS,
            PAGE_EVENT_OVERDUE,
            PAGE_EVENT_ROOT_CAUSE,
            PAGE_MANAGER_VIEW,
        )

        ops_keys = {
            PAGE_EVENT_OPS,
            PAGE_EVENT_OVERDUE,
            PAGE_EVENT_ROOT_CAUSE,
            PAGE_EVENT_OPEN_ACTIONS,
            PAGE_MANAGER_VIEW,
        }
        source_key = getattr(self.main_window, "_workbench_source_page_key", None)
        if source_key in ops_keys:
            self.back_button.setText("返回作業佇列")
            self.back_button.setAccessibleName("返回作業佇列")
        else:
            self.back_button.setText("返回異常清單")
            self.back_button.setAccessibleName("返回異常清單")

    def return_to_list(self) -> None:
        if not self.can_leave():
            return
        from ui.sidebar_nav import (
            PAGE_EVENT_OPEN_ACTIONS,
            PAGE_EVENT_OPS,
            PAGE_EVENT_OVERDUE,
            PAGE_EVENT_ROOT_CAUSE,
            PAGE_MANAGER_VIEW,
        )

        ops_keys = {
            PAGE_EVENT_OPS,
            PAGE_EVENT_OVERDUE,
            PAGE_EVENT_ROOT_CAUSE,
            PAGE_EVENT_OPEN_ACTIONS,
            PAGE_MANAGER_VIEW,
        }
        source_key = getattr(self.main_window, "_workbench_source_page_key", None)
        opener = getattr(self.main_window, "open_supplier_event_ops", None)
        if source_key in ops_keys and callable(opener):
            opener(source_key or PAGE_EVENT_OPS)
            return
        self.main_window.open_event_query_with_filters(event_scope=None)

    def refresh_data(self) -> None:
        if self._anomaly_id and not self._editing:
            self.load_anomaly(self._anomaly_id)

    @staticmethod
    def _has_display_value(value) -> bool:
        text = str(value or "").strip()
        return bool(text) and text != "—"

    @staticmethod
    def _section_title(text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("role", "sectionTitle")
        return label

    @staticmethod
    def _kv(label: str, value) -> QLabel:
        result = make_multiline_label(f"{label}：{value or '—'}", role="value")
        result.setToolTip(result.text())
        return result

    def _quality_badge_row(self, label: str, value) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(CONTROL_ROW_SPACING)
        row.addWidget(self._section_title(label))
        row.addWidget(self._status_badge(str(value or "—"), self._quality_tone(value)))
        row.addStretch(1)
        return row

    @staticmethod
    def _status_badge(text: str, tone: str) -> QLabel:
        badge = QLabel(f"  {text}  ")
        badge.setProperty("role", "statusBadge")
        badge.setProperty("tone", tone)
        return badge

    @staticmethod
    def _set_status_badge(badge: QLabel, text: str, tone: str) -> None:
        badge.setText(f"  {text}  ")
        badge.setProperty("tone", tone)
        style = badge.style()
        style.unpolish(badge)
        style.polish(badge)
        badge.update()

    @staticmethod
    def _case_status_tone(status: str) -> str:
        if status == "已結案":
            return "success"
        if status == "待處理":
            return "pending"
        return "na"

    @staticmethod
    def _quality_tone(value) -> str:
        text = str(value or "").strip()
        if text in ("", "—", "尚未開始", "未建立"):
            return "na"
        if text in ("已驗證", "有效", "已完成"):
            return "success"
        if text in ("無效", "反證", "淘汰"):
            return "danger"
        if text in ("待驗證", "調查中", "提案", "執行中", "支持"):
            return "warning"
        return "pending"
