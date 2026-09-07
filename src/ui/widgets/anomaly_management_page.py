"""主視窗內嵌的供應商異常案件管理頁。"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
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
from database.repo_helpers import (
    ACTION_VERIFICATION_PENDING,
    ANOMALY_EVIDENCE_LABELS,
    ANOMALY_EVIDENCE_TYPES,
    ANOMALY_ROOT_CAUSE_NOT_ESTABLISHED,
    ANOMALY_ROOT_CAUSE_NOT_STARTED,
    ANOMALY_ROOT_CAUSE_PROPOSED,
    ANOMALY_ROOT_CAUSE_STATUSES,
    ANOMALY_ROOT_CAUSE_UNDER_INVESTIGATION,
    ANOMALY_ROOT_CAUSE_VERIFIED,
)
from ui.layout_constants import (
    CONTROL_ROW_SPACING,
    FORM_HORIZONTAL_SPACING,
    FORM_VERTICAL_SPACING,
    PAGE_OUTER_MARGINS,
    PANEL_MARGINS,
)
from ui.widgets.bullet_list_widget import BulletListWidget
from ui.widgets.common_widgets import (
    CaseStageStepper,
    EmptyStateWidget,
    RequiredFieldLabel,
    apply_clickable_affordance,
    create_section_card,
    make_inline_error_label,
    set_field_invalid,
)
from ui.runtime_mode import is_automated_runtime
from ui.widgets.new_anomaly_dialog import NewAnomalyDialog
from ui.widgets.anomaly_attachment_panel import EvidenceAttachmentPanel
from ui.widgets.close_anomaly_dialog import CloseAnomalyDialog
from ui.widgets.reopen_anomaly_dialog import ReopenAnomalyDialog
from ui.widgets.repeat_issues_panel import RepeatIssuesPanel
from ui.popup_i18n import localize_exception


class AnomalyManagementPage(QWidget):
    """案件詳情與既有工作台資料的單一主視窗入口。"""

    TAB_ANALYSIS_INDEX = 2
    TAB_ATTACHMENTS_INDEX = 5

    TAB_NAMES = (
        "案件概況",
        "處理歷程",
        "異常分析",
        "Supplier 8D",
        "處置項目",
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
        self._analysis_hypothesis_expanded = False
        self._analysis_verification_expanded = False
        self._analysis_verification_user_collapsed = False
        self._last_verification_auto_expand_status: str | None = None
        self._analysis_note_form_open = False
        self._analysis_note_evidence_expanded = False
        self._analysis_note_draft: dict | None = None
        self._analysis_cause_dirty = False
        self._analysis_cause_draft: dict | None = None
        self._analysis_promoted_from_hypothesis_id: str | None = None
        self._note_submit_inflight = False
        self._cause_save_inflight = False
        self._confirmed_tab_index = 0
        self._tab_guard_suppressed = False
        self._note_add_button: QPushButton | None = None
        self._cause_save_button: QPushButton | None = None
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
        self.tabs.currentChanged.connect(self._on_workbench_tab_changed)
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

    def load_anomaly(
        self,
        anomaly_id: str,
        *,
        edit: bool = False,
        preserve_ui: bool = False,
    ) -> None:
        anomaly_key = str(anomaly_id or "").strip()
        if not anomaly_key:
            raise ValueError("Anomaly id is required")
        saved_ui = self._capture_workbench_ui_state() if preserve_ui else None
        if preserve_ui:
            self._snapshot_analysis_cause_draft()
            self._snapshot_analysis_note_draft()
        self._anomaly_id = anomaly_key
        self._detail = _anomaly_service.get_anomaly_detail(anomaly_key)
        self._overview = _anomaly_workbench_service.get_overview_card(anomaly_key)
        self._editing = False
        self._remove_edit_form()
        self._render_header()
        self._sync_back_button_label()
        if self.stage_stepper is not None:
            self.stage_stepper.set_case_state(self._detail, self._overview)
        if hasattr(self, "repeat_issues_panel"):
            self.repeat_issues_panel.load_anomaly(anomaly_key)
        select_tab = saved_ui["tab_index"] if saved_ui is not None else None
        self._render_tabs(select_tab=select_tab)
        self._confirmed_tab_index = self.tabs.currentIndex()
        if saved_ui is not None:
            self._restore_workbench_ui_state(saved_ui)
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

    def _render_tabs(self, *, select_tab: int | None = None) -> None:
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
        if select_tab is not None:
            self.tabs.setCurrentIndex(max(0, min(select_tab, self.tabs.count() - 1)))
        else:
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
        layout.addWidget(action_card)

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
        self._build_analysis_notes_section(tab, layout)
        self._build_cause_conclusion_section(tab, layout)
        self._build_hypothesis_advanced_section(tab, layout)
        layout.addStretch(1)
        return tab

    def _build_analysis_notes_section(self, tab: QWidget, layout: QVBoxLayout) -> None:
        notes_card = create_section_card(tab)
        notes_card.layout().addWidget(self._section_title("分析紀錄"))
        notes = _anomaly_workbench_service.list_analysis_notes(self._anomaly_id)
        if not notes:
            notes_card.layout().addWidget(
                EmptyStateWidget("尚無分析紀錄", "可補充調查發現、FA 或供應商回覆。")
            )
        else:
            for row in notes:
                label = QLabel(
                    f"[{row.get('evidence_label') or row.get('evidence_type') or '—'}] "
                    f"{row.get('author_name') or '未知'}"
                    + (
                        f"　📎 {int(row.get('attachment_count') or 0)} 份附件"
                        if int(row.get("attachment_count") or 0) > 0
                        else ""
                    )
                    + f"\n{row.get('content') or '—'}"
                )
                label.setWordWrap(True)
                label.setProperty("role", "value")
                label.setToolTip(label.text())
                notes_card.layout().addWidget(label)
        layout.addWidget(notes_card)

        self._note_form_container = QWidget()
        note_form_layout = QVBoxLayout(self._note_form_container)
        note_form_layout.setContentsMargins(0, 0, 0, 0)
        note_form_layout.setSpacing(FORM_VERTICAL_SPACING)
        if self._analysis_note_draft:
            self._analysis_note_evidence_expanded = bool(
                self._analysis_note_draft.get("evidence_expanded")
            )
        self._note_content_input = BulletListWidget(
            placeholder="輸入新的分析結果、發現或回覆……"
        )
        if self._analysis_note_draft:
            self._note_content_input.set_formatted_text(
                str(self._analysis_note_draft.get("content") or "")
            )
        note_form_layout.addWidget(self._note_content_input)
        self._note_error_label = make_inline_error_label()
        note_form_layout.addWidget(self._note_error_label)

        self._note_evidence_toggle = QPushButton(
            "▸ 補充資訊" if not self._analysis_note_evidence_expanded else "▼ 補充資訊"
        )
        self._note_evidence_toggle.setProperty("variant", "secondary")
        self._note_evidence_toggle.clicked.connect(self._toggle_note_evidence_section)
        note_form_layout.addWidget(self._note_evidence_toggle)

        self._note_evidence_container = QWidget()
        evidence_layout = QFormLayout(self._note_evidence_container)
        evidence_layout.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        evidence_layout.setVerticalSpacing(FORM_VERTICAL_SPACING)
        self._note_evidence_combo = QComboBox()
        for value in ANOMALY_EVIDENCE_TYPES:
            label = ANOMALY_EVIDENCE_LABELS[value]
            self._note_evidence_combo.addItem(f"{label}（{value}）", value)
        unknown_index = self._note_evidence_combo.findData("UNKNOWN")
        draft_evidence = (
            str(self._analysis_note_draft.get("evidence_type") or "UNKNOWN")
            if self._analysis_note_draft
            else "UNKNOWN"
        )
        evidence_index = self._note_evidence_combo.findData(draft_evidence)
        self._note_evidence_combo.setCurrentIndex(
            evidence_index if evidence_index >= 0 else max(unknown_index, 0)
        )
        evidence_layout.addRow("證據分類", self._note_evidence_combo)
        self._note_evidence_container.setVisible(self._analysis_note_evidence_expanded)
        note_form_layout.addWidget(self._note_evidence_container)

        note_actions = QHBoxLayout()
        note_actions.setSpacing(CONTROL_ROW_SPACING)
        cancel_note = QPushButton("取消")
        cancel_note.setProperty("variant", "secondary")
        cancel_note.clicked.connect(self._close_note_form)
        add_note = QPushButton("加入")
        add_note.setProperty("variant", "primary")
        add_note.clicked.connect(self._submit_inline_analysis_note)
        self._note_add_button = add_note
        note_actions.addWidget(cancel_note)
        note_actions.addWidget(add_note)
        note_actions.addStretch(1)
        note_form_layout.addLayout(note_actions)
        self._note_form_container.setVisible(self._analysis_note_form_open)
        layout.addWidget(self._note_form_container)

        if not self._analysis_note_form_open:
            self._add_action_button(layout, "＋補充紀錄", self._open_note_form)

    def _build_cause_conclusion_section(self, tab: QWidget, layout: QVBoxLayout) -> None:
        cause_card = create_section_card(tab)
        cause_card.layout().addWidget(self._section_title("原因結論"))
        self._cause_status_hint_label = QLabel("")
        self._cause_status_hint_label.setWordWrap(True)
        self._cause_status_hint_label.setProperty("role", "value")
        cause_card.layout().addWidget(self._cause_status_hint_label)
        initial = self._analysis_cause_initial_values()

        self._cause_statement_input = BulletListWidget(
            placeholder="目前判斷原因是什麼？"
        )
        self._cause_statement_input.set_formatted_text(str(initial.get("statement") or ""))

        self._cause_status_combo = QComboBox()
        for status in ANOMALY_ROOT_CAUSE_STATUSES:
            self._cause_status_combo.addItem(status, status)
        current_status = str(initial.get("status") or ANOMALY_ROOT_CAUSE_NOT_STARTED)
        status_index = self._cause_status_combo.findData(current_status)
        self._cause_status_combo.setCurrentIndex(max(status_index, 0))

        cause_form = QFormLayout()
        cause_form.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        cause_form.setVerticalSpacing(FORM_VERTICAL_SPACING)
        cause_form.addRow(RequiredFieldLabel("目前判斷原因"), self._cause_statement_input)
        self._cause_statement_error = make_inline_error_label()
        cause_form.addRow("", self._cause_statement_error)
        cause_form.addRow(RequiredFieldLabel("結論狀態"), self._cause_status_combo)
        cause_card.layout().addLayout(cause_form)

        verification_title = (
            "▼ 驗證與佐證" if self._analysis_verification_expanded else "▸ 驗證與佐證"
        )
        self._verification_toggle = QPushButton(verification_title)
        self._verification_toggle.setProperty("variant", "secondary")
        self._verification_toggle.clicked.connect(self._toggle_verification_section)
        cause_card.layout().addWidget(self._verification_toggle)

        self._verification_container = QWidget()
        verification_form = QFormLayout(self._verification_container)
        verification_form.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        verification_form.setVerticalSpacing(FORM_VERTICAL_SPACING)
        self._cause_validation_method_input = BulletListWidget(
            placeholder="如 5-Why、Fishbone、8D D4"
        )
        self._cause_validation_method_input.set_formatted_text(
            str(initial.get("validation_method") or "")
        )
        self._cause_validation_evidence_input = BulletListWidget(
            placeholder="支持此原因的證據"
        )
        self._cause_validation_evidence_input.set_formatted_text(
            str(initial.get("validation_evidence") or "")
        )
        self._cause_conclusion_input = BulletListWidget(
            placeholder="信心程度、待確認事項、建議後續驗證"
        )
        self._cause_conclusion_input.set_formatted_text(
            str(initial.get("conclusion_note") or "")
        )
        self._cause_not_established_input = BulletListWidget(
            placeholder="結論狀態為「無法確認」時必填"
        )
        self._cause_not_established_input.set_formatted_text(
            str(initial.get("not_established_reason") or "")
        )
        verification_form.addRow("驗證方式", self._cause_validation_method_input)
        verification_form.addRow("驗證證據", self._cause_validation_evidence_input)
        verification_form.addRow("結論說明", self._cause_conclusion_input)
        verification_form.addRow(
            RequiredFieldLabel("無法確認原因說明"), self._cause_not_established_input
        )
        self._cause_not_established_error = make_inline_error_label()
        verification_form.addRow("", self._cause_not_established_error)

        note_attachments, hyp_attachments = self._count_linked_attachments()
        evidence_summary = QLabel(
            f"已關聯分析紀錄附件 {note_attachments} 筆、可能原因附件 {hyp_attachments} 筆"
        )
        evidence_summary.setWordWrap(True)
        evidence_summary.setProperty("role", "value")
        verification_form.addRow("佐證參考", evidence_summary)
        go_attachments = QPushButton("前往附件")
        go_attachments.setProperty("variant", "secondary")
        go_attachments.setAccessibleName("前往附件")
        go_attachments.clicked.connect(self._go_to_attachments_tab)
        verification_form.addRow("", go_attachments)

        self._verification_container.setVisible(self._analysis_verification_expanded)
        cause_card.layout().addWidget(self._verification_container)

        self._connect_cause_dirty_signals()
        self._update_cause_validation()
        layout.addWidget(cause_card)
        self._cause_save_button = self._add_action_button(
            layout,
            "儲存原因結論",
            self._save_cause_conclusion,
            variant="primary",
        )

    def _build_hypothesis_advanced_section(self, tab: QWidget, layout: QVBoxLayout) -> None:
        try:
            hypotheses = _anomaly_workbench_service.list_hypotheses(self._anomaly_id)
        except RuntimeError:
            hypotheses = []
        count = len(hypotheses)
        title = f"比較可能原因（{count}）"
        toggle_label = ("▼ " if self._analysis_hypothesis_expanded else "▸ ") + title
        self._hypothesis_toggle = QPushButton(toggle_label)
        self._hypothesis_toggle.setProperty("variant", "secondary")
        self._hypothesis_toggle.clicked.connect(self._toggle_hypothesis_section)
        layout.addWidget(self._hypothesis_toggle)

        self._hypothesis_container = QWidget()
        hypothesis_layout = QVBoxLayout(self._hypothesis_container)
        hypothesis_layout.setContentsMargins(0, 0, 0, 0)
        hypothesis_layout.setSpacing(FORM_VERTICAL_SPACING)
        if not hypotheses:
            hypothesis_layout.addWidget(
                EmptyStateWidget("尚無可能原因", "複雜案件可建立多個調查方向。")
            )
        else:
            for row in hypotheses:
                hypothesis_layout.addWidget(self._build_hypothesis_row_widget(row))
        self._add_action_button(
            hypothesis_layout,
            "＋可能原因",
            self._open_add_hypothesis_dialog,
        )
        self._hypothesis_container.setVisible(self._analysis_hypothesis_expanded)
        layout.addWidget(self._hypothesis_container)

    def _build_hypothesis_row_widget(self, row: dict) -> QWidget:
        row_widget = QWidget()
        row_layout = QVBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(CONTROL_ROW_SPACING)
        level = int(row.get("level") or 1)
        indent = "　" * max(level - 1, 0)
        attachment_count = int(row.get("attachment_count") or 0)
        attachment_suffix = f"　📎 {attachment_count}" if attachment_count > 0 else ""
        summary = QLabel(
            f"{indent}L{level} [{row.get('status') or '—'}] "
            f"{row.get('evidence_label') or row.get('evidence_type') or '—'}"
            f"{attachment_suffix}\n{row.get('statement') or '—'}"
        )
        summary.setWordWrap(True)
        summary.setProperty("role", "value")
        summary.setToolTip(summary.text())
        row_layout.addWidget(summary)

        actions = QHBoxLayout()
        actions.setSpacing(CONTROL_ROW_SPACING)
        edit_button = QPushButton("編輯")
        edit_button.setProperty("variant", "secondary")
        hypothesis_id = str(row.get("id") or "")
        edit_button.clicked.connect(
            lambda _checked=False, hid=hypothesis_id: self._open_edit_hypothesis_dialog_for(hid)
        )
        bring_button = QPushButton("帶入原因結論")
        bring_button.setProperty("variant", "secondary")
        bring_button.clicked.connect(
            lambda _checked=False, payload=dict(row): self._bring_hypothesis_into_cause(payload)
        )
        actions.addWidget(edit_button)
        actions.addWidget(bring_button)
        actions.addStretch(1)
        row_layout.addLayout(actions)
        return row_widget

    def _analysis_cause_initial_values(self) -> dict:
        if self._analysis_cause_dirty and self._analysis_cause_draft is not None:
            return dict(self._analysis_cause_draft)
        return _anomaly_workbench_service.get_root_cause(self._anomaly_id) or {}

    def _connect_cause_dirty_signals(self) -> None:
        for widget in (
            self._cause_statement_input,
            self._cause_status_combo,
            self._cause_validation_method_input,
            self._cause_validation_evidence_input,
            self._cause_conclusion_input,
            self._cause_not_established_input,
        ):
            if hasattr(widget, "valueChanged"):
                widget.valueChanged.connect(self._mark_analysis_cause_dirty)
            elif hasattr(widget, "currentIndexChanged"):
                widget.currentIndexChanged.connect(self._mark_analysis_cause_dirty)

    def _mark_analysis_cause_dirty(self, *_args) -> None:
        self._analysis_cause_dirty = True
        self._analysis_cause_draft = self._collect_cause_field_values()
        self._update_cause_validation()

    def _collect_cause_field_values(self) -> dict:
        return {
            "statement": self._cause_statement_input.get_formatted_text().strip(),
            "status": str(
                self._cause_status_combo.currentData() or ANOMALY_ROOT_CAUSE_NOT_STARTED
            ),
            "validation_method": self._cause_validation_method_input.get_formatted_text().strip(),
            "validation_evidence": self._cause_validation_evidence_input.get_formatted_text().strip(),
            "conclusion_note": self._cause_conclusion_input.get_formatted_text().strip(),
            "not_established_reason": self._cause_not_established_input.get_formatted_text().strip(),
        }

    def _snapshot_analysis_cause_draft(self) -> None:
        if not self._analysis_cause_dirty:
            return
        if hasattr(self, "_cause_statement_input"):
            self._analysis_cause_draft = self._collect_cause_field_values()

    def _snapshot_analysis_note_draft(self) -> None:
        if not self._analysis_note_form_open or not hasattr(self, "_note_content_input"):
            return
        self._analysis_note_draft = {
            "content": self._note_content_input.get_formatted_text(),
            "evidence_type": str(self._note_evidence_combo.currentData() or "UNKNOWN"),
            "evidence_expanded": self._analysis_note_evidence_expanded,
        }

    def _analysis_note_is_dirty(self) -> bool:
        if not self._analysis_note_form_open or not hasattr(self, "_note_content_input"):
            return False
        content = self._note_content_input.get_formatted_text().strip()
        if content:
            return True
        evidence = str(self._note_evidence_combo.currentData() or "UNKNOWN")
        return evidence != "UNKNOWN"

    def _analysis_has_unsaved_changes(self) -> bool:
        return self._analysis_cause_dirty or self._analysis_note_is_dirty()

    def _clear_analysis_drafts(self) -> None:
        self._analysis_cause_dirty = False
        self._analysis_cause_draft = None
        self._analysis_promoted_from_hypothesis_id = None
        self._analysis_note_form_open = False
        self._analysis_note_evidence_expanded = False
        self._analysis_note_draft = None

    def _count_linked_attachments(self) -> tuple[int, int]:
        try:
            attachments = _anomaly_workbench_service.list_attachments(self._anomaly_id)
        except RuntimeError:
            return 0, 0
        note_count = sum(
            1 for row in attachments if str(row.get("related_note_id") or "").strip()
        )
        hyp_count = sum(
            1
            for row in attachments
            if str(row.get("related_hypothesis_id") or "").strip()
        )
        return note_count, hyp_count

    def _expand_verification_section(self) -> None:
        self._analysis_verification_expanded = True
        if hasattr(self, "_verification_container"):
            self._verification_container.setVisible(True)
        if hasattr(self, "_verification_toggle"):
            self._verification_toggle.setText("▼ 驗證與佐證")

    def _update_cause_status_hint(self) -> None:
        if not hasattr(self, "_cause_status_hint_label"):
            return
        status = self._current_cause_status()
        statement = ""
        if hasattr(self, "_cause_statement_input"):
            statement = self._cause_statement_input.get_formatted_text().strip()
        if not statement and status == ANOMALY_ROOT_CAUSE_NOT_STARTED:
            hint = "尚未建立原因結論"
        elif statement and status in (
            ANOMALY_ROOT_CAUSE_PROPOSED,
            ANOMALY_ROOT_CAUSE_UNDER_INVESTIGATION,
        ):
            hint = "原因待進一步驗證"
        else:
            hint = ""
        self._cause_status_hint_label.setText(hint)
        self._cause_status_hint_label.setVisible(bool(hint))

    def _confirm_analysis_leave(self) -> str:
        if is_automated_runtime():
            return "discard"
        box = QMessageBox(self)
        box.setWindowTitle("未儲存變更")
        box.setText("異常分析尚有未儲存的修改，要如何處理？")
        save_button = box.addButton("儲存並離開", QMessageBox.ButtonRole.AcceptRole)
        discard_button = box.addButton("不儲存", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save_button:
            return "save"
        if clicked is discard_button:
            return "discard"
        return "cancel"

    def _prepare_cause_fields_for_save(self) -> dict | None:
        if not self._analysis_cause_dirty:
            return None
        if not hasattr(self, "_cause_statement_input"):
            return dict(self._analysis_cause_draft or {})
        self._update_cause_validation()
        values = self._collect_cause_field_values()
        status = values["status"]
        statement = values["statement"]
        if statement and status == ANOMALY_ROOT_CAUSE_NOT_STARTED:
            status = ANOMALY_ROOT_CAUSE_PROPOSED
            values["status"] = status
            status_index = self._cause_status_combo.findData(status)
            if status_index >= 0:
                self._cause_status_combo.setCurrentIndex(status_index)
            self._update_cause_validation()
        if status in (
            ANOMALY_ROOT_CAUSE_VERIFIED,
            ANOMALY_ROOT_CAUSE_NOT_ESTABLISHED,
        ) and not statement:
            return None
        if status == ANOMALY_ROOT_CAUSE_NOT_ESTABLISHED and not values[
            "not_established_reason"
        ]:
            return None
        return values

    def _prepare_pending_note_for_save(self) -> dict | None:
        if not self._analysis_note_is_dirty() or not hasattr(self, "_note_content_input"):
            return None
        content = self._note_content_input.get_formatted_text().strip()
        if not content:
            return None
        return {
            "content": content,
            "evidence_type": str(self._note_evidence_combo.currentData() or "UNKNOWN"),
        }

    def _save_analysis_pending_for_leave(self) -> bool:
        cause_fields = self._prepare_cause_fields_for_save()
        pending_note = self._prepare_pending_note_for_save()
        if cause_fields is None and self._analysis_cause_dirty:
            QMessageBox.warning(self, "儲存失敗", "原因結論資料不完整，無法儲存。")
            return False
        if not cause_fields and not pending_note:
            return True
        try:
            _anomaly_workbench_service.save_analysis_pending_changes(
                anomaly_id=self._anomaly_id,
                pending_note=pending_note,
                cause_fields=cause_fields,
                promoted_from_hypothesis_id=self._analysis_promoted_from_hypothesis_id,
            )
        except Exception as exc:
            QMessageBox.warning(self, "儲存失敗", localize_exception(exc))
            return False
        return True

    def _on_workbench_tab_changed(self, new_index: int) -> None:
        if self._tab_guard_suppressed:
            self._confirmed_tab_index = new_index
            return
        old_index = self._confirmed_tab_index
        if old_index == new_index:
            return
        if (
            old_index == self.TAB_ANALYSIS_INDEX
            and new_index != self.TAB_ANALYSIS_INDEX
            and self._analysis_has_unsaved_changes()
        ):
            self._tab_guard_suppressed = True
            self.tabs.blockSignals(True)
            self.tabs.setCurrentIndex(old_index)
            self.tabs.blockSignals(False)
            self._tab_guard_suppressed = False

            choice = self._confirm_analysis_leave()
            if choice == "cancel":
                return
            if choice == "discard":
                self._clear_analysis_drafts()
            elif choice == "save":
                if not self._save_analysis_pending_for_leave():
                    return
                self._clear_analysis_drafts()
                self.refresh_data()

            self._tab_guard_suppressed = True
            self.tabs.blockSignals(True)
            self.tabs.setCurrentIndex(new_index)
            self.tabs.blockSignals(False)
            self._tab_guard_suppressed = False

        self._confirmed_tab_index = new_index

    def _go_to_attachments_tab(self) -> None:
        target = self.TAB_ATTACHMENTS_INDEX
        if self.tabs.currentIndex() == target:
            return
        self.tabs.setCurrentIndex(target)

    def _current_cause_status(self) -> str:
        if hasattr(self, "_cause_status_combo"):
            return str(
                self._cause_status_combo.currentData() or ANOMALY_ROOT_CAUSE_NOT_STARTED
            )
        draft = self._analysis_cause_draft or {}
        return str(draft.get("status") or ANOMALY_ROOT_CAUSE_NOT_STARTED)

    def _update_cause_validation(self) -> None:
        if not hasattr(self, "_cause_statement_input"):
            return
        status = self._current_cause_status()
        statement = self._cause_statement_input.get_formatted_text().strip()
        not_established = self._cause_not_established_input.get_formatted_text().strip()
        statement_required = status in (
            ANOMALY_ROOT_CAUSE_VERIFIED,
            ANOMALY_ROOT_CAUSE_NOT_ESTABLISHED,
        )
        statement_valid = (not statement_required) or bool(statement)
        not_established_required = status == ANOMALY_ROOT_CAUSE_NOT_ESTABLISHED
        not_established_valid = (not not_established_required) or bool(not_established)
        set_field_invalid(self._cause_statement_input, not statement_valid)
        if self._cause_statement_error is not None:
            self._cause_statement_error.setText(
                ""
                if statement_valid
                else "此狀態需填寫原因說明（必填）"
            )
        set_field_invalid(self._cause_not_established_input, not not_established_valid)
        if self._cause_not_established_error is not None:
            self._cause_not_established_error.setText(
                ""
                if not_established_valid
                else "狀態為「無法確認」時需填寫原因說明（必填）"
            )
        if status in (
            ANOMALY_ROOT_CAUSE_VERIFIED,
            ANOMALY_ROOT_CAUSE_NOT_ESTABLISHED,
        ):
            if self._last_verification_auto_expand_status != status:
                self._last_verification_auto_expand_status = status
                self._analysis_verification_user_collapsed = False
            if not self._analysis_verification_user_collapsed:
                self._expand_verification_section()
        self._update_cause_status_hint()

    def _open_note_form(self) -> None:
        self._analysis_note_form_open = True
        self._analysis_note_evidence_expanded = False
        self.refresh_data()

    def _close_note_form(self) -> None:
        if self._analysis_note_is_dirty():
            if not is_automated_runtime():
                answer = QMessageBox.question(
                    self,
                    "未儲存變更",
                    "分析紀錄草稿尚未加入，確定要取消嗎？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
        self._analysis_note_form_open = False
        self._analysis_note_evidence_expanded = False
        self._analysis_note_draft = None
        if hasattr(self, "_note_content_input"):
            self._note_content_input.set_formatted_text("")
        self.refresh_data()

    def _toggle_note_evidence_section(self) -> None:
        self._analysis_note_evidence_expanded = not self._analysis_note_evidence_expanded
        if hasattr(self, "_note_evidence_container"):
            self._note_evidence_container.setVisible(self._analysis_note_evidence_expanded)
        if hasattr(self, "_note_evidence_toggle"):
            prefix = "▼ " if self._analysis_note_evidence_expanded else "▸ "
            self._note_evidence_toggle.setText(prefix + "補充資訊")

    def _toggle_verification_section(self) -> None:
        self._analysis_verification_expanded = not self._analysis_verification_expanded
        if not self._analysis_verification_expanded:
            self._analysis_verification_user_collapsed = True
        if hasattr(self, "_verification_container"):
            self._verification_container.setVisible(self._analysis_verification_expanded)
        if hasattr(self, "_verification_toggle"):
            prefix = "▼ " if self._analysis_verification_expanded else "▸ "
            self._verification_toggle.setText(prefix + "驗證與佐證")

    def _toggle_hypothesis_section(self) -> None:
        self._analysis_hypothesis_expanded = not self._analysis_hypothesis_expanded
        if hasattr(self, "_hypothesis_container"):
            self._hypothesis_container.setVisible(self._analysis_hypothesis_expanded)
        if hasattr(self, "_hypothesis_toggle"):
            try:
                count = len(_anomaly_workbench_service.list_hypotheses(self._anomaly_id))
            except RuntimeError:
                count = 0
            title = f"比較可能原因（{count}）"
            prefix = "▼ " if self._analysis_hypothesis_expanded else "▸ "
            self._hypothesis_toggle.setText(prefix + title)

    def _submit_inline_analysis_note(self) -> None:
        if self._note_submit_inflight:
            return
        content = self._note_content_input.get_formatted_text().strip()
        if not content:
            set_field_invalid(self._note_content_input, True)
            if self._note_error_label is not None:
                self._note_error_label.setText("請輸入分析紀錄內容（必填）")
            return
        evidence = str(self._note_evidence_combo.currentData() or "UNKNOWN")
        self._note_submit_inflight = True
        if self._note_add_button is not None:
            self._note_add_button.setEnabled(False)
        try:
            _anomaly_workbench_service.create_analysis_note(
                anomaly_id=self._anomaly_id,
                content=content,
                evidence_type=evidence,
            )
        except Exception as exc:
            set_field_invalid(self._note_content_input, True)
            if self._note_error_label is not None:
                self._note_error_label.setText(localize_exception(exc))
            return
        finally:
            self._note_submit_inflight = False
            if self._note_add_button is not None:
                self._note_add_button.setEnabled(True)
        self._analysis_note_form_open = False
        self._analysis_note_evidence_expanded = False
        self._analysis_note_draft = None
        self.refresh_data()

    def _save_cause_conclusion(self) -> None:
        if self._cause_save_inflight:
            return
        self._update_cause_validation()
        values = self._collect_cause_field_values()
        status = values["status"]
        statement = values["statement"]
        if statement and status == ANOMALY_ROOT_CAUSE_NOT_STARTED:
            status = ANOMALY_ROOT_CAUSE_PROPOSED
            values["status"] = status
            status_index = self._cause_status_combo.findData(status)
            if status_index >= 0:
                self._cause_status_combo.setCurrentIndex(status_index)
            self._update_cause_validation()
        if status in (
            ANOMALY_ROOT_CAUSE_VERIFIED,
            ANOMALY_ROOT_CAUSE_NOT_ESTABLISHED,
        ) and not statement:
            return
        if status == ANOMALY_ROOT_CAUSE_NOT_ESTABLISHED and not values["not_established_reason"]:
            return
        self._cause_save_inflight = True
        if self._cause_save_button is not None:
            self._cause_save_button.setEnabled(False)
        try:
            _anomaly_workbench_service.save_root_cause(
                anomaly_id=self._anomaly_id,
                statement=statement,
                status=status,
                validation_method=values["validation_method"],
                validation_evidence=values["validation_evidence"],
                conclusion_note=values["conclusion_note"],
                not_established_reason=values["not_established_reason"],
                promoted_from_hypothesis_id=self._analysis_promoted_from_hypothesis_id,
            )
        except Exception as exc:
            QMessageBox.warning(self, "儲存失敗", localize_exception(exc))
            return
        finally:
            self._cause_save_inflight = False
            if self._cause_save_button is not None:
                self._cause_save_button.setEnabled(True)
        self._analysis_cause_dirty = False
        self._analysis_cause_draft = None
        self._analysis_promoted_from_hypothesis_id = None
        self.refresh_data()

    def _bring_hypothesis_into_cause(self, hypothesis: dict) -> None:
        incoming = str(hypothesis.get("statement") or "").strip()
        if not incoming:
            return
        current_values = (
            self._collect_cause_field_values()
            if hasattr(self, "_cause_statement_input")
            else dict(self._analysis_cause_draft or {})
        )
        existing = str(current_values.get("statement") or "").strip()
        mode = "replace"
        if existing and existing != incoming:
            if is_automated_runtime():
                mode = "replace"
            else:
                box = QMessageBox(self)
                box.setWindowTitle("帶入原因結論")
                box.setText("目前已有原因結論。要如何帶入所選可能原因？")
                replace_button = box.addButton(
                    "取代目前內容", QMessageBox.ButtonRole.AcceptRole
                )
                append_button = box.addButton(
                    "附加至目前內容", QMessageBox.ButtonRole.ActionRole
                )
                box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
                box.exec()
                clicked = box.clickedButton()
                if clicked is replace_button:
                    mode = "replace"
                elif clicked is append_button:
                    mode = "append"
                else:
                    return
        if mode == "append" and existing:
            new_statement = f"{existing}\n{incoming}"
        else:
            new_statement = incoming
        status = str(current_values.get("status") or ANOMALY_ROOT_CAUSE_NOT_STARTED)
        if new_statement and status == ANOMALY_ROOT_CAUSE_NOT_STARTED:
            status = ANOMALY_ROOT_CAUSE_PROPOSED
        self._analysis_promoted_from_hypothesis_id = str(hypothesis.get("id") or "") or None
        draft = dict(current_values)
        draft["statement"] = new_statement
        draft["status"] = status
        self._analysis_cause_draft = draft
        self._analysis_cause_dirty = True
        if hasattr(self, "_cause_statement_input"):
            self._cause_statement_input.set_formatted_text(new_statement)
            status_index = self._cause_status_combo.findData(status)
            if status_index >= 0:
                self._cause_status_combo.setCurrentIndex(status_index)
            self._update_cause_validation()

    def _capture_workbench_ui_state(self) -> dict:
        scroll_positions: dict[int, int] = {}
        for index in range(self.tabs.count()):
            tab = self.tabs.widget(index)
            if tab is None:
                continue
            scroll = tab.findChild(QScrollArea, "AnomalyManagementTabScroll")
            if scroll is not None:
                scroll_positions[index] = scroll.verticalScrollBar().value()
        return {
            "tab_index": self.tabs.currentIndex(),
            "scroll_positions": scroll_positions,
        }

    def _restore_workbench_ui_state(self, saved: dict) -> None:
        scroll_positions = saved.get("scroll_positions") or {}

        def apply_scroll() -> None:
            try:
                tabs = getattr(self, "tabs", None)
                if tabs is None:
                    return
                for index, position in scroll_positions.items():
                    tab = tabs.widget(int(index))
                    if tab is None:
                        continue
                    scroll = tab.findChild(QScrollArea, "AnomalyManagementTabScroll")
                    if scroll is not None:
                        scroll.verticalScrollBar().setValue(int(position))
            except RuntimeError:
                return

        QTimer.singleShot(0, apply_scroll)

    def _open_edit_hypothesis_dialog_for(self, hypothesis_id: str) -> None:
        from ui.widgets.anomaly_hypothesis_dialog import AnomalyHypothesisDialog

        rows = {
            str(row.get("id") or ""): row
            for row in _anomaly_workbench_service.list_hypotheses(self._anomaly_id)
        }
        initial = rows.get(str(hypothesis_id or "").strip())
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
        variant: str = "secondary",
    ) -> QPushButton:
        row = QHBoxLayout()
        row.setSpacing(CONTROL_ROW_SPACING)
        button = QPushButton(text)
        button.setAccessibleName(text)
        button.setProperty("variant", variant)
        apply_clickable_affordance(button, tooltip=text)
        button.clicked.connect(callback)
        if requires_open_case:
            button.setEnabled(self._allows_case_action_commands())
        row.addWidget(button)
        row.addStretch(1)
        layout.addLayout(row)
        return button

    def _open_add_hypothesis_dialog(self) -> None:
        from ui.widgets.anomaly_hypothesis_dialog import AnomalyHypothesisDialog

        dialog = AnomalyHypothesisDialog(self._anomaly_id, parent=self)
        dialog.hypothesis_saved.connect(lambda _id: self.refresh_data())
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
        if self._edit_form is not None and getattr(self._edit_form, "_dirty", False):
            if not self._edit_form._confirm_discard():
                return False
        if not self._analysis_has_unsaved_changes():
            return True
        choice = self._confirm_analysis_leave()
        if choice == "cancel":
            return False
        if choice == "discard":
            self._clear_analysis_drafts()
            return True
        if not self._save_analysis_pending_for_leave():
            return False
        self._clear_analysis_drafts()
        self.refresh_data()
        return True

    def _open_repeat_issue_anomaly(self, anomaly_id: str) -> None:
        peer_id = str(anomaly_id or "").strip()
        if not peer_id or peer_id == self._anomaly_id:
            return
        if not self.can_leave():
            return
        if hasattr(self.main_window, "open_anomaly_management"):
            self.main_window.open_anomaly_management(peer_id)

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
            self.load_anomaly(self._anomaly_id, preserve_ui=True)

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
