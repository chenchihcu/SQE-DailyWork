"""主視窗內嵌的供應商異常案件管理頁。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
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
    PAGE_OUTER_MARGINS,
    PANEL_MARGINS,
)
from ui.widgets.common_widgets import (
    CaseStageStepper,
    EmptyStateWidget,
    apply_clickable_affordance,
    create_section_card,
)
from ui.widgets.new_anomaly_dialog import NewAnomalyDialog
from ui.widgets.anomaly_attachment_panel import EvidenceAttachmentPanel
from ui.widgets.close_anomaly_dialog import CloseAnomalyDialog
from ui.widgets.reopen_anomaly_dialog import ReopenAnomalyDialog
from ui.widgets.repeat_issues_panel import RepeatIssuesPanel
from ui.popup_i18n import localize_exception


class AnomalyManagementPage(QWidget):
    """案件詳情與既有工作台資料的單一主視窗入口。"""

    TAB_NAMES = (
        "案件概況",
        "處理歷程",
        "異常分析",
        "Supplier 8D",
        "改善措施",
        "附件",
        "變更紀錄",
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
        self.stage_stepper: CaseStageStepper | None = None
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
        self.header_text = QLabel()
        self.header_text.setProperty("role", "title")
        self.header_text.setWordWrap(True)
        header_layout.addWidget(self.header_text, 1)
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
        header_layout.addWidget(self.reopen_button)
        self.edit_button = QPushButton("編輯")
        self.edit_button.setAccessibleName("編輯異常")
        self.edit_button.setProperty("variant", "primary")
        self.edit_button.clicked.connect(self.begin_edit)
        header_layout.addWidget(self.edit_button)
        root.addWidget(self.header)

        self.stage_stepper = CaseStageStepper()
        root.addWidget(self.stage_stepper)

        self.repeat_issues_panel = RepeatIssuesPanel(self)
        self.repeat_issues_panel.open_anomaly_requested.connect(
            self._open_repeat_issue_anomaly
        )
        root.addWidget(self.repeat_issues_panel)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("AnomalyManagementTabs")
        for name in self.TAB_NAMES:
            self.tabs.addTab(QWidget(), name)
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

    def load_anomaly(self, anomaly_id: str, *, edit: bool = False) -> None:
        anomaly_key = str(anomaly_id or "").strip()
        if not anomaly_key:
            raise ValueError("Anomaly id is required")
        self._anomaly_id = anomaly_key
        self._detail = _anomaly_service.get_anomaly_detail(anomaly_key)
        self._overview = _anomaly_workbench_service.get_overview_card(anomaly_key)
        self._editing = False
        self._remove_edit_form()
        self._render_header()
        if self.stage_stepper is not None:
            self.stage_stepper.set_case_state(self._detail, self._overview)
        if hasattr(self, "repeat_issues_panel"):
            self.repeat_issues_panel.load_anomaly(anomaly_key)
        self._render_tabs()
        if edit:
            self.begin_edit()

    def _render_header(self) -> None:
        number = self._detail.get("anomaly_no") or self._anomaly_id
        status = self._detail.get("status") or "—"
        supplier = self._detail.get("supplier_name") or "—"
        problem = self._detail.get("problem_desc") or "—"
        current = self._overview.get("current_action") or {}
        overdue_suffix = "　[逾期]" if self._overview.get("overdue") else ""
        self.header_text.setText(
            f"{number}  [{status}]{overdue_suffix}\n"
            f"{problem}\n"
            f"供應商：{supplier}　負責人：{current.get('owner') or '—'}"
        )
        self._update_header_actions()

    def _update_header_actions(self) -> None:
        is_closed = self._is_case_closed()
        self.close_button.setEnabled(not is_closed and bool(self._anomaly_id))
        self.reopen_button.setEnabled(is_closed and bool(self._anomaly_id))
        self.edit_button.setEnabled(not is_closed and bool(self._anomaly_id))

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
        builders = (
            self._build_overview_tab,
            self._build_timeline_tab,
            self._build_analysis_tab,
            self._build_eight_d_tab,
            self._build_corrective_tab,
            self._build_attachments_tab,
            self._build_history_tab,
        )
        for index, builder in enumerate(builders):
            old = self.tabs.widget(index)
            self.tabs.removeTab(index)
            if old is not None:
                old.deleteLater()
            self.tabs.insertTab(index, builder(), self.TAB_NAMES[index])
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
        card = create_section_card(tab)
        card_layout = card.layout()
        card_layout.addWidget(self._section_title("案件資料"))
        fields = (
            ("異常單號", self._detail.get("anomaly_no")),
            ("日期", self._detail.get("anomaly_date")),
            ("供應商", self._detail.get("supplier_name")),
            ("品名", self._detail.get("product_name")),
            ("料號", self._detail.get("product_code")),
            ("異常類別", self._detail.get("category")),
            ("來源 NCR 單號", self._detail.get("source_defect_no") or "—"),
            (
                "SMT 製程關鍵詞",
                format_process_keywords_display(self._detail.get("process_keywords")),
            ),
            ("數量", self._detail.get("batch_qty")),
            (
                "到期日",
                str((self._overview.get("current_action") or {}).get("due_date") or "")
                .strip()
                or str(self._detail.get("due_date") or "").strip()
                or "—",
            ),
            ("結案日期", self._detail.get("closed_at")),
        )
        for label, value in fields:
            card_layout.addWidget(self._kv(label, value))
        card_layout.addWidget(self._kv("不良現象", self._detail.get("problem_desc")))
        layout.addWidget(card)

        overview = self._overview
        quality_card = create_section_card(tab)
        quality_layout = quality_card.layout()
        quality_layout.addWidget(self._section_title("品質結論"))
        quality_layout.addLayout(
            self._quality_badge_row(
                "根本原因",
                overview.get("root_cause_status"),
            )
        )
        quality_layout.addLayout(
            self._quality_badge_row(
                "改善措施",
                overview.get("corrective_action_status"),
            )
        )
        quality_layout.addLayout(
            self._quality_badge_row(
                "有效性驗證",
                overview.get("verification_result"),
            )
        )
        hypothesis_count = int(overview.get("hypothesis_count") or 0)
        if hypothesis_count > 0:
            quality_layout.addWidget(
                self._kv("原因假設", f"{hypothesis_count} 筆（最深 L{overview.get('hypothesis_deepest_level') or 0}）")
            )
        layout.addWidget(quality_card)

        action_card = create_section_card(tab)
        action_layout = action_card.layout()
        action_layout.addWidget(self._section_title("目前處置"))
        current = overview.get("current_action") or {}
        if not current:
            action_layout.addWidget(
                EmptyStateWidget("尚無待處置動作。", "可建立下一步處置。")
            )
        else:
            action_layout.addWidget(
                self._kv("處置內容", current.get("description"))
            )
            action_layout.addWidget(
                self._kv("Action 類型", current.get("action_type_label"))
            )
            action_layout.addWidget(self._kv("負責人", current.get("owner")))
            action_layout.addWidget(self._kv("到期日", current.get("due_date")))
            action_layout.addWidget(
                self._kv("執行狀態", current.get("execution_status"))
            )
            action_layout.addWidget(
                self._kv("驗證狀態", current.get("verification_status"))
            )
            action_layout.addWidget(
                self._kv("逾期", "是" if overview.get("overdue") else "否")
            )
            command_row = QHBoxLayout()
            command_row.setSpacing(CONTROL_ROW_SPACING)
            if self._allows_case_action_commands():
                status = str(current.get("execution_status") or "")
                if status == "已規劃":
                    start_button = QPushButton("開始執行")
                    start_button.setProperty("variant", "secondary")
                    start_button.clicked.connect(
                        lambda _checked=False, action_id=str(current.get("id") or ""): (
                            self._start_case_action(action_id)
                        )
                    )
                    command_row.addWidget(start_button)
                if status in ("已規劃", "執行中"):
                    update_button = QPushButton(
                        "取消" if status == "已規劃" else "完成／取消"
                    )
                    update_button.setProperty("variant", "secondary")
                    update_button.clicked.connect(
                        lambda _checked=False, row=dict(current): (
                            self._open_complete_action_dialog(row)
                        )
                    )
                    command_row.addWidget(update_button)
            command_row.addStretch(1)
            action_layout.addLayout(command_row)
        self._add_action_button(
            action_layout, "新增 Action", self._open_add_action_dialog, requires_open_case=True
        )
        layout.addWidget(action_card)

        footer_row = QHBoxLayout()
        footer_row.setSpacing(CONTROL_ROW_SPACING)
        create_action = QPushButton("建立處置")
        create_action.setProperty("variant", "primary")
        create_action.clicked.connect(self._open_add_action_dialog)
        create_action.setEnabled(self._allows_case_action_commands())
        footer_row.addWidget(create_action)
        close_footer = QPushButton("結案")
        close_footer.setProperty("variant", "secondary")
        close_footer.clicked.connect(self._open_close_dialog)
        close_footer.setEnabled(str(self._detail.get("status") or "") != "已結案")
        footer_row.addWidget(close_footer)
        reopen_footer = QPushButton("重新開啟")
        reopen_footer.setProperty("variant", "secondary")
        reopen_footer.clicked.connect(self._open_reopen_dialog)
        reopen_footer.setEnabled(str(self._detail.get("status") or "") == "已結案")
        footer_row.addWidget(reopen_footer)
        footer_row.addStretch(1)
        layout.addLayout(footer_row)
        layout.addStretch(1)
        return tab

    def _build_timeline_tab(self) -> QWidget:
        tab, layout = self._base_tab()
        self._add_rows(
            layout,
            "處理歷程",
            _anomaly_workbench_service.list_timeline(self._anomaly_id),
            lambda row: f"{row.get('ts') or '—'}　{row.get('kind') or ''}　{row.get('actor') or ''}\n{row.get('summary') or '—'}",
        )
        return tab

    def _build_analysis_tab(self) -> QWidget:
        tab, layout = self._base_tab()
        self._add_rows(
            layout,
            "分析紀錄",
            _anomaly_workbench_service.list_analysis_notes(self._anomaly_id),
            lambda row: (
                f"[{row.get('evidence_label') or row.get('evidence_type') or '—'}] "
                f"{row.get('author_name') or '未知'}"
                + (
                    f"　📎 {int(row.get('attachment_count') or 0)} 份附件"
                    if int(row.get("attachment_count") or 0) > 0
                    else ""
                )
                + f"\n{row.get('content') or '—'}"
            ),
        )
        root_cause = _anomaly_workbench_service.get_root_cause(self._anomaly_id)
        card = create_section_card(tab)
        card.layout().addWidget(self._section_title("根本原因"))
        if root_cause:
            card.layout().addWidget(self._kv("狀態", root_cause.get("status")))
            card.layout().addWidget(self._kv("說明", root_cause.get("statement")))
            card.layout().addWidget(self._kv("驗證方式", root_cause.get("validation_method")))
        else:
            card.layout().addWidget(EmptyStateWidget("尚未建立根本原因", "可於異常分析流程補充。"))
        layout.addWidget(card)

        hypothesis_card = create_section_card(tab)
        hypothesis_card.layout().addWidget(self._section_title("多層原因假設"))
        self._hypothesis_list = QListWidget()
        self._hypothesis_list.setObjectName("AnomalyHypothesisList")
        try:
            hypotheses = _anomaly_workbench_service.list_hypotheses(self._anomaly_id)
        except RuntimeError:
            hypotheses = []
        if not hypotheses:
            hypothesis_card.layout().addWidget(
                EmptyStateWidget("尚無原因假設", "可建立 L1–L5 多層 Why 樹。")
            )
        else:
            for row in hypotheses:
                level = int(row.get("level") or 1)
                indent = "　" * max(level - 1, 0)
                attachment_count = int(row.get("attachment_count") or 0)
                attachment_suffix = (
                    f"　📎 {attachment_count}" if attachment_count > 0 else ""
                )
                text = (
                    f"{indent}L{level} [{row.get('status') or '—'}] "
                    f"{row.get('evidence_label') or row.get('evidence_type') or '—'}"
                    f"{attachment_suffix}\n{row.get('statement') or '—'}"
                )
                item = QListWidgetItem(text)
                item.setData(256, str(row.get("id") or ""))
                item.setData(257, str(row.get("status") or ""))
                self._hypothesis_list.addItem(item)
            hypothesis_card.layout().addWidget(self._hypothesis_list)
        layout.addWidget(hypothesis_card)

        self._add_action_button(layout, "新增分析紀錄", self._open_add_note_dialog)
        self._add_action_button(layout, "新增假設", self._open_add_hypothesis_dialog)
        self._add_action_button(layout, "編輯假設", self._open_edit_hypothesis_dialog)
        self._add_action_button(layout, "晉升為根本原因", self._promote_selected_hypothesis)
        self._add_action_button(layout, "編輯根本原因", self._open_root_cause_dialog)
        return tab

    def _build_eight_d_tab(self) -> QWidget:
        tab, layout = self._base_tab()
        reviews = _anomaly_workbench_service.list_eight_d_reviews(self._anomaly_id)
        card = create_section_card(tab)
        card.layout().addWidget(self._section_title("Supplier 8D 審查"))
        if not reviews:
            card.layout().addWidget(
                EmptyStateWidget("尚未上傳 Supplier 8D。", "可追加審查紀錄。")
            )
        else:
            for row in reviews:
                status = str(row.get("review_status") or "—")
                row_layout = QHBoxLayout()
                row_layout.addWidget(self._status_badge(status, self._eight_d_tone(status)))
                row_layout.addWidget(
                    self._kv(
                        f"Rev {row.get('revision') or '—'}",
                        row.get("review_comment") or "—",
                    ),
                    1,
                )
                card.layout().addLayout(row_layout)
        layout.addWidget(card)
        self._add_action_button(layout, "追加 Supplier 8D 審查", self._open_add_8d_dialog)
        return tab

    def _build_corrective_tab(self) -> QWidget:
        tab, layout = self._base_tab()
        actions = _case_action_service.list_case_actions(self._anomaly_id)
        self._add_case_action_rows(layout, actions)
        self._add_action_button(layout, "新增 Action", self._open_add_action_dialog, requires_open_case=True)
        return tab

    def _build_attachments_tab(self) -> QWidget:
        tab, layout = self._base_tab()
        panel = EvidenceAttachmentPanel(tab)
        panel.set_anomaly(self._anomaly_id)
        panel.changed.connect(self.refresh_data)
        layout.addWidget(panel)
        layout.addStretch(1)
        return tab

    def _build_history_tab(self) -> QWidget:
        tab, layout = self._base_tab()
        rows = _anomaly_workbench_service.list_audit_logs(self._anomaly_id)
        card = create_section_card(tab)
        card.layout().addWidget(self._section_title("變更紀錄"))
        if not rows:
            card.layout().addWidget(
                EmptyStateWidget("尚無變更紀錄", "其他操作完成後會出現於此。")
            )
        else:
            for row in rows:
                label = QLabel(
                    f"{row.get('action') or '—'}　"
                    f"{row.get('actor_name') or '未知'}　"
                    f"{row.get('created_at') or '—'}\n"
                    f"變更前：{row.get('before_value') or '—'}\n"
                    f"變更後：{row.get('after_value') or '—'}"
                )
                label.setWordWrap(True)
                label.setProperty("role", "value")
                label.setToolTip(label.text())
                card.layout().addWidget(label)
        layout.addWidget(card)
        self._add_action_button(layout, "新增處理紀錄", self._open_add_audit_log_dialog)
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

    def _open_add_note_dialog(self) -> None:
        from ui.widgets.anomaly_note_dialog import AnomalyNoteDialog

        dialog = AnomalyNoteDialog(self._anomaly_id, self)
        dialog.note_created.connect(lambda _id: self.refresh_data())
        dialog.exec()

    def _open_add_hypothesis_dialog(self) -> None:
        from ui.widgets.anomaly_hypothesis_dialog import AnomalyHypothesisDialog

        dialog = AnomalyHypothesisDialog(self._anomaly_id, parent=self)
        dialog.hypothesis_saved.connect(lambda _id: self.refresh_data())
        dialog.exec()

    def _selected_hypothesis(self) -> dict | None:
        if not hasattr(self, "_hypothesis_list"):
            return None
        item = self._hypothesis_list.currentItem()
        if item is None:
            return None
        return {
            "id": str(item.data(256) or ""),
            "status": str(item.data(257) or ""),
        }

    def _open_edit_hypothesis_dialog(self) -> None:
        from ui.widgets.anomaly_hypothesis_dialog import AnomalyHypothesisDialog

        selected = self._selected_hypothesis()
        if not selected or not selected.get("id"):
            QMessageBox.information(self, "編輯假設", "請先選取一筆原因假設。")
            return
        rows = {
            str(row.get("id") or ""): row
            for row in _anomaly_workbench_service.list_hypotheses(self._anomaly_id)
        }
        initial = rows.get(str(selected["id"]))
        if initial is None:
            QMessageBox.warning(self, "編輯假設", "找不到所選假設，請重新整理後再試。")
            return
        dialog = AnomalyHypothesisDialog(
            self._anomaly_id,
            initial=initial,
            parent=self,
        )
        dialog.hypothesis_saved.connect(lambda _id: self.refresh_data())
        dialog.exec()

    def _promote_selected_hypothesis(self) -> None:
        selected = self._selected_hypothesis()
        if not selected or not selected.get("id"):
            QMessageBox.information(self, "晉升根本原因", "請先選取一筆原因假設。")
            return
        if selected.get("status") not in {"採納", "支持"}:
            QMessageBox.information(
                self,
                "晉升根本原因",
                "僅「採納」或「支持」狀態的假設可晉升為根本原因。",
            )
            return
        answer = QMessageBox.question(
            self,
            "晉升根本原因",
            "將所選假設晉升為根本原因？此動作不會自動設為「已驗證」。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            _anomaly_workbench_service.promote_hypothesis_to_root_cause(
                anomaly_id=self._anomaly_id,
                hypothesis_id=str(selected["id"]),
            )
        except Exception as exc:
            QMessageBox.warning(self, "晉升失敗", localize_exception(exc))
            return
        self.refresh_data()

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

    def _open_add_8d_dialog(self) -> None:
        from ui.widgets.add_eight_d_review_dialog import AddEightDReviewDialog

        dialog = AddEightDReviewDialog(self._anomaly_id, parent=self)
        dialog.review_created.connect(lambda _id: self.refresh_data())
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

    def _add_rows(self, layout: QVBoxLayout, title: str, rows: list[dict], formatter) -> None:
        card = create_section_card(layout.parentWidget())
        card.layout().addWidget(self._section_title(title))
        if not rows:
            card.layout().addWidget(EmptyStateWidget(f"尚無{title}", "目前沒有可顯示的資料。"))
        else:
            for row in rows:
                label = QLabel(formatter(row))
                label.setWordWrap(True)
                label.setProperty("role", "value")
                label.setToolTip(label.text())
                card.layout().addWidget(label)
        layout.addWidget(card)
        layout.addStretch(1)

    def _add_case_action_rows(
        self,
        layout: QVBoxLayout,
        actions: list[dict],
    ) -> None:
        card = create_section_card(layout.parentWidget())
        card.layout().addWidget(self._section_title("Action 清單"))
        if not actions:
            card.layout().addWidget(
                EmptyStateWidget("尚無 Action", "可建立下一步處置或改善措施。")
            )
        for action in actions:
            summary = QLabel(
                f"{action.get('action_type_label') or action.get('action_type') or '—'}　"
                f"[{action.get('execution_status') or '—'}]　"
                f"驗證：{action.get('verification_status') or '—'}\n"
                f"{action.get('description') or '—'}\n"
                f"負責人：{action.get('owner') or '—'}　"
                f"到期日：{action.get('due_date') or '—'}"
            )
            summary.setWordWrap(True)
            summary.setProperty("role", "value")
            summary.setToolTip(summary.text())
            card.layout().addWidget(summary)

            command_row = QHBoxLayout()
            command_row.setSpacing(CONTROL_ROW_SPACING)
            if self._allows_case_action_commands():
                status = str(action.get("execution_status") or "")
                if status == "已規劃":
                    start_button = QPushButton("開始執行")
                    start_button.setAccessibleName(
                        f"開始執行 {action.get('description') or 'Action'}"
                    )
                    start_button.setProperty("variant", "secondary")
                    apply_clickable_affordance(start_button, tooltip="將狀態更新為執行中")
                    start_button.clicked.connect(
                        lambda _checked=False, action_id=str(action.get("id") or ""): (
                            self._start_case_action(action_id)
                        )
                    )
                    command_row.addWidget(start_button)
                if status in ("已規劃", "執行中"):
                    update_button = QPushButton(
                        "取消" if status == "已規劃" else "完成／取消"
                    )
                    update_button.setAccessibleName(
                        f"完成或取消 {action.get('description') or 'Action'}"
                    )
                    update_button.setProperty("variant", "secondary")
                    apply_clickable_affordance(update_button, tooltip="更新 Action 執行狀態")
                    update_button.clicked.connect(
                        lambda _checked=False, row=dict(action): (
                            self._open_complete_action_dialog(row)
                        )
                    )
                    command_row.addWidget(update_button)
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
                    lambda _checked=False, row=dict(action): (
                        self._open_verification_dialog(row)
                    )
                )
                command_row.addWidget(verification_button)
            command_row.addStretch(1)
            card.layout().addLayout(command_row)
        layout.addWidget(card)
        layout.addStretch(1)

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
        overview_tab = self.tabs.widget(0)
        old = getattr(overview_tab, "_workbench_content_layout", None)
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
            if self.stage_stepper is not None:
                self.stage_stepper.set_case_state(self._detail, self._overview)
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

    def _open_repeat_issue_anomaly(self, anomaly_id: str) -> None:
        peer_id = str(anomaly_id or "").strip()
        if not peer_id or peer_id == self._anomaly_id:
            return
        if not self.can_leave():
            return
        if hasattr(self.main_window, "open_anomaly_management"):
            self.main_window.open_anomaly_management(peer_id)

    def return_to_list(self) -> None:
        if not self.can_leave():
            return
        self.main_window.open_event_query_with_filters(event_scope=None)

    def refresh_data(self) -> None:
        if self._anomaly_id and not self._editing:
            self.load_anomaly(self._anomaly_id)

    @staticmethod
    def _section_title(text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("role", "sectionTitle")
        return label

    @staticmethod
    def _kv(label: str, value) -> QLabel:
        result = QLabel(f"{label}：{value or '—'}")
        result.setWordWrap(True)
        result.setProperty("role", "value")
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

    @staticmethod
    def _eight_d_tone(status: str) -> str:
        if status == "接受":
            return "success"
        if status == "退回修正":
            return "danger"
        if status == "需補充證據":
            return "warning"
        return "pending"
