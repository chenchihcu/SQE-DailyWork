"""主視窗內嵌的供應商異常案件管理頁。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from services.event import (
    _anomaly_action_service,
    _anomaly_service,
    _anomaly_workbench_service,
)
from services.process_keyword_codec import format_process_keywords_display
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
        self.edit_button = QPushButton("編輯")
        self.edit_button.setAccessibleName("編輯異常")
        self.edit_button.setProperty("variant", "primary")
        self.edit_button.clicked.connect(self.begin_edit)
        header_layout.addWidget(self.edit_button)
        root.addWidget(self.header)

        self.stage_stepper = CaseStageStepper()
        root.addWidget(self.stage_stepper)

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
        self._editing = False
        self._remove_edit_form()
        self._render_header()
        if self.stage_stepper is not None:
            overview = _anomaly_workbench_service.get_overview_card(anomaly_key)
            self.stage_stepper.set_case_state(self._detail, overview)
        self._render_tabs()
        if edit:
            self.begin_edit()

    def _render_header(self) -> None:
        number = self._detail.get("anomaly_no") or self._anomaly_id
        status = self._detail.get("status") or "—"
        supplier = self._detail.get("supplier_name") or "—"
        problem = self._detail.get("problem_desc") or "—"
        self.header_text.setText(
            f"{number}  [{status}]\n"
            f"{problem}\n"
            f"供應商：{supplier}　負責人：{self._detail.get('responsible_person') or '—'}"
        )

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
            ("到期日", self._detail.get("due_date")),
            ("結案日期", self._detail.get("closed_at")),
        )
        for label, value in fields:
            card_layout.addWidget(self._kv(label, value))
        card_layout.addWidget(self._kv("不良現象", self._detail.get("problem_desc")))
        layout.addWidget(card)

        overview = _anomaly_workbench_service.get_overview_card(self._anomaly_id)
        action_card = create_section_card(tab)
        action_layout = action_card.layout()
        action_layout.addWidget(self._section_title("目前處置"))
        current = overview.get("current_action") or {}
        action_layout.addWidget(
            self._kv("處置內容", current.get("description") or self._detail.get("pending_items"))
        )
        action_layout.addWidget(self._kv("負責人", current.get("owner") or self._detail.get("responsible_person")))
        action_layout.addWidget(self._kv("逾期", "是" if overview.get("overdue") else "否"))
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
        self._add_rows(
            layout,
            "分析紀錄",
            _anomaly_workbench_service.list_analysis_notes(self._anomaly_id),
            lambda row: f"[{row.get('evidence_label') or row.get('evidence_type') or '—'}] "
            f"{row.get('author_name') or '未知'}\n{row.get('content') or '—'}",
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
        self._add_action_button(layout, "新增分析紀錄", self._open_add_note_dialog)
        return tab

    def _build_eight_d_tab(self) -> QWidget:
        tab, layout = self._base_tab()
        self._add_rows(
            layout,
            "Supplier 8D 審查",
            _anomaly_workbench_service.list_eight_d_reviews(self._anomaly_id),
            lambda row: f"{row.get('revision') or '—'}　{row.get('review_status') or '—'}\n"
            f"{row.get('review_comment') or '—'}",
        )
        self._add_action_button(layout, "追加 Supplier 8D 審查", self._open_add_8d_dialog)
        return tab

    def _build_corrective_tab(self) -> QWidget:
        tab, layout = self._base_tab()
        actions = _anomaly_workbench_service.list_corrective_actions(self._anomaly_id)
        self._add_rows(
            layout,
            "改善措施",
            actions,
            lambda row: f"{row.get('description') or '—'}　[{row.get('status') or '—'}]\n"
            f"負責人：{row.get('responsible_party') or '—'}　預計完成：{row.get('target_date') or '—'}",
        )
        self._add_action_button(layout, "新增改善措施", self._open_add_corrective_action_dialog)
        return tab

    def _build_attachments_tab(self) -> QWidget:
        tab, layout = self._base_tab()
        self._add_rows(
            layout,
            "附件",
            _anomaly_workbench_service.list_attachments(self._anomaly_id),
            lambda row: f"{row.get('file_name') or '—'}　{row.get('category') or '其他'}",
        )
        return tab

    def _build_history_tab(self) -> QWidget:
        tab, layout = self._base_tab()
        self._add_rows(
            layout,
            "變更紀錄",
            _anomaly_workbench_service.list_audit_logs(self._anomaly_id),
            lambda row: f"{row.get('created_at') or '—'}　{row.get('action') or '—'}　"
            f"{row.get('actor_name') or '未知'}\n{row.get('after_value') or '—'}",
        )
        self._add_action_button(layout, "新增處理紀錄", self._open_add_audit_log_dialog)
        return tab

    def _add_action_button(self, layout: QVBoxLayout, text: str, callback) -> None:
        row = QHBoxLayout()
        row.setSpacing(CONTROL_ROW_SPACING)
        button = QPushButton(text)
        button.setAccessibleName(text)
        button.setProperty("variant", "secondary")
        apply_clickable_affordance(button, tooltip=text)
        button.clicked.connect(callback)
        row.addWidget(button)
        row.addStretch(1)
        layout.addLayout(row)

    def _open_add_note_dialog(self) -> None:
        from ui.widgets.anomaly_note_dialog import AnomalyNoteDialog

        dialog = AnomalyNoteDialog(self._anomaly_id, self)
        dialog.note_created.connect(lambda _id: self.refresh_data())
        dialog.exec()

    def _open_add_corrective_action_dialog(self) -> None:
        from ui.widgets.add_corrective_action_dialog import AddCorrectiveActionDialog

        dialog = AddCorrectiveActionDialog(self._anomaly_id, self)
        dialog.ca_created.connect(lambda _id: self.refresh_data())
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
