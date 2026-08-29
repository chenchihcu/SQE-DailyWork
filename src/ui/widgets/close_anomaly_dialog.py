"""Close-anomaly dialog with evidence metadata attachment panel."""

from __future__ import annotations

import logging
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from services.appearance_preferences_service import load_application_preferences
from services.event import _anomaly_service as event_service
from ui.layout_constants import (
    CLOSE_DIALOG_ATTACHMENT_SCROLL_MAX_HEIGHT,
    CLOSE_DIALOG_IMPROVEMENT_VISIBLE_ROWS,
    CLOSE_DIALOG_PROBLEM_MIN_HEIGHT,
    CLOSE_DIALOG_REF_MARGINS,
    COMPACT_PAGE_SPACING,
    CONTROL_ROW_SPACING,
    DIALOG_OUTER_MARGINS,
    FORM_HORIZONTAL_SPACING,
    FORM_MAX_WIDTH,
    FORM_VERTICAL_SPACING,
    WORKBENCH_DIALOG_WIDE_MIN_WIDTH,
)
from ui.popup_i18n import localize_exception, localize_popup_message
from ui.widgets.anomaly_attachment_panel import EvidenceAttachmentPanel
from ui.widgets.anomaly_attachment_editor import AttachmentEditor  # noqa: F401  # re-export
from ui.widgets.common_widgets import (
    DirtyTrackingMixin,
    RequiredFieldLabel,
)
from ui.widgets.defect_form_widgets import (
    apply_dialog_layout,
    set_text_edit_visible_rows,
    set_tone,
    style_dialog_buttons,
)

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────
IMPROVEMENT_DESC_MAX_LEN = 1000


# ── CloseAnomalyDialog ─────────────────────────────────────────────────────
class CloseAnomalyDialog(DirtyTrackingMixin, QDialog):
    def __init__(
        self,
        anomaly_id: str,
        problem_desc: str,
        parent=None,
        *,
        date_adjustment_only: bool = False,
    ):
        super().__init__(parent)
        self.anomaly_id = anomaly_id
        self.problem_desc = problem_desc
        self.date_adjustment_only = date_adjustment_only
        self.setModal(True)
        self.setWindowTitle("調整結案日期" if date_adjustment_only else "異常結案")
        self.setMinimumWidth(WORKBENCH_DIALOG_WIDE_MIN_WIDTH)
        self.setMaximumWidth(FORM_MAX_WIDTH)

        # 取得異常詳情以設定預設值
        self.initial_anomaly_date = ""
        self.initial_closed_at = ""
        self.initial_closed_by = ""
        self.initial_improvement_desc = ""
        try:
            detail = event_service.get_anomaly_detail(self.anomaly_id)
            self.initial_anomaly_date = str(detail.get("anomaly_date") or "")
            self.initial_closed_at = str(detail.get("closed_at") or "")
            self.initial_closed_by = str(detail.get("closed_by") or "")
            self.initial_improvement_desc = str(detail.get("improvement_desc") or "")
        except Exception:
            logger.exception("Failed to get initial anomaly detail for anomaly %s", self.anomaly_id)

        self._setup_ui()
        self._update_validation()

        self._connect_dirty_signals()

    def _setup_ui(self):
        self.improvement_input = QTextEdit()
        self.improvement_input.setPlaceholderText("請輸入改善內容（必填）")
        self.improvement_input.setAccessibleName("改善內容")
        set_text_edit_visible_rows(
            self.improvement_input, CLOSE_DIALOG_IMPROVEMENT_VISIBLE_ROWS
        )

        self.improvement_counter = QLabel(f"0 / {IMPROVEMENT_DESC_MAX_LEN}")
        self.improvement_counter.setProperty("role", "counterText")
        self.improvement_counter.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        self.closed_at_input = QDateEdit()
        self.closed_at_input.setDisplayFormat("yyyy-MM-dd")
        self.closed_at_input.setCalendarPopup(True)
        self.closed_at_input.setAccessibleName("結案日期")
        self.closed_at_input.setMaximumDate(QDate.currentDate())
        initial_anomaly_qdate = QDate.fromString(self.initial_anomaly_date, "yyyy-MM-dd")
        if initial_anomaly_qdate.isValid():
            self.closed_at_input.setMinimumDate(initial_anomaly_qdate)
        initial_close_qdate = QDate.fromString(self.initial_closed_at, "yyyy-MM-dd")
        if initial_close_qdate.isValid():
            self.closed_at_input.setDate(initial_close_qdate)
        else:
            self.closed_at_input.setDate(QDate.currentDate())

        if self.initial_improvement_desc:
            self.improvement_input.setPlainText(self.initial_improvement_desc)
        if self.date_adjustment_only:
            self.improvement_input.setReadOnly(True)

        self.evidence_panel = EvidenceAttachmentPanel(self)
        self.evidence_panel.set_anomaly(self.anomaly_id)
        if self.date_adjustment_only:
            self.evidence_panel.setEnabled(False)

        prefs = load_application_preferences()
        self.closed_by_input = QLineEdit()
        self.closed_by_input.setPlaceholderText("例如：陳主管 / SQE_LEAD（選填）")
        self.closed_by_input.setAccessibleName("結案驗證人")
        if self.initial_closed_by:
            self.closed_by_input.setText(self.initial_closed_by)
        elif prefs.default_closer_name:
            self.closed_by_input.setText(prefs.default_closer_name)
        if self.date_adjustment_only:
            self.closed_by_input.setReadOnly(True)

        # 單一連續表單內容區（消除分頁切換摩擦）
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        content_layout.setSpacing(CONTROL_ROW_SPACING)

        # 原始問題對照摘要（讓使用者填寫改善措施時可直接對照）
        problem_ref_box = QFrame()
        problem_ref_box.setObjectName("CloseAnomalyProblemRef")
        problem_ref_box.setProperty("role", "infoCard")
        pref_layout = QVBoxLayout(problem_ref_box)
        pref_layout.setContentsMargins(*CLOSE_DIALOG_REF_MARGINS)
        pref_layout.setSpacing(COMPACT_PAGE_SPACING)
        pref_lbl = QLabel("🔍 原始問題描述：")
        pref_lbl.setProperty("role", "meta")
        pref_text = QLabel(self.problem_desc.strip() if self.problem_desc else "（無問題描述）")
        pref_text.setWordWrap(True)
        pref_text.setProperty("role", "summary")
        pref_text.setMaximumHeight(CLOSE_DIALOG_PROBLEM_MIN_HEIGHT)
        pref_layout.addWidget(pref_lbl)
        pref_layout.addWidget(pref_text)
        content_layout.addWidget(problem_ref_box)

        improvement_field = QWidget()
        improvement_field_layout = QVBoxLayout(improvement_field)
        improvement_field_layout.setContentsMargins(0, 0, 0, 0)
        improvement_field_layout.setSpacing(COMPACT_PAGE_SPACING)
        improvement_field_layout.addWidget(self.improvement_input)
        improvement_field_layout.addWidget(self.improvement_counter)

        form = QFormLayout()
        form.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        form.setVerticalSpacing(FORM_VERTICAL_SPACING)
        form.addRow(RequiredFieldLabel("📝 改善內容"), improvement_field)
        form.addRow(RequiredFieldLabel("結案日期"), self.closed_at_input)
        form.addRow("結案驗證人", self.closed_by_input)
        content_layout.addLayout(form)

        attach_label = QLabel("改善佐證附件（上傳後立即寫入案件附件）：")
        attach_label.setProperty("role", "meta")
        content_layout.addWidget(attach_label)

        panel_scroll = QScrollArea()
        panel_scroll.setWidgetResizable(True)
        panel_scroll.setFrameShape(QFrame.Shape.NoFrame)
        panel_scroll.setWidget(self.evidence_panel)
        panel_scroll.setMaximumHeight(CLOSE_DIALOG_ATTACHMENT_SCROLL_MAX_HEIGHT)
        content_layout.addWidget(panel_scroll)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        self._save_button = style_dialog_buttons(buttons)
        if self._save_button:
            self._save_button.setCursor(Qt.PointingHandCursor)
            self._save_button.setAccessibleName("確認結案")
        buttons.accepted.connect(self._on_submit)
        apply_dialog_layout(self, content, buttons)
        self._button_box = buttons

        self.improvement_input.textChanged.connect(self._update_validation)
        self.closed_at_input.dateChanged.connect(self._update_validation)
        self._setup_tab_order()

    def _setup_tab_order(self) -> None:
        """Tab follows visual reading order across improvement input, dates, and buttons."""
        order = [
            self.improvement_input,
            self.closed_at_input,
            self.closed_by_input,
            self.evidence_panel,
        ]
        if hasattr(self, "_button_box") and self._button_box is not None:
            save_btn = self._button_box.button(QDialogButtonBox.StandardButton.Save)
            cancel_btn = self._button_box.button(QDialogButtonBox.StandardButton.Cancel)
            if save_btn is not None:
                order.append(save_btn)
            if cancel_btn is not None:
                order.append(cancel_btn)

        valid_widgets = [w for w in order if w is not None]
        for earlier, later in zip(valid_widgets, valid_widgets[1:], strict=False):
            self.setTabOrder(earlier, later)

    def _connect_dirty_signals(self) -> None:
        self._init_dirty_tracking([
            self.improvement_input.textChanged,
            self.closed_at_input.dateChanged,
            self.evidence_panel.changed,
        ])

    def _update_validation(self) -> None:
        text = self.improvement_input.toPlainText()
        length = len(text)
        over_limit = length > IMPROVEMENT_DESC_MAX_LEN
        self.improvement_counter.setText(
            f"{length} / {IMPROVEMENT_DESC_MAX_LEN}"
        )
        set_tone(self.improvement_counter, "danger" if over_limit else "normal")
        date_valid = self.closed_at_input.date().isValid()
        if self.date_adjustment_only:
            valid = date_valid
        else:
            valid = (
                bool(text.strip())
                and not over_limit
                and date_valid
            )
        if self._save_button is not None:
            self._save_button.setEnabled(valid)

    def _on_submit(self):
        text = self.improvement_input.toPlainText().strip()
        closed_at = self.closed_at_input.date().toString("yyyy-MM-dd")
        closed_by = self.closed_by_input.text().strip()
        try:
            if self.date_adjustment_only:
                result = event_service.update_anomaly_closed_at(
                    self.anomaly_id,
                    closed_at=closed_at,
                )
                completion_text = "結案日期已更新"
            else:
                close_kwargs = {"closed_at": closed_at}
                if closed_by:
                    close_kwargs["closed_by"] = closed_by
                    close_kwargs["actor_name"] = closed_by
                result = event_service.close_anomaly(
                    self.anomaly_id,
                    text,
                    **close_kwargs,
                )
                completion_text = "異常已結案"
            warnings = list(result.get("warnings") or [])
            if warnings:
                QMessageBox.warning(
                    self,
                    "完成但有警告",
                    localize_popup_message(
                        completion_text + "\n\n" + "\n".join(str(item) for item in warnings)
                    ),
                )
            else:
                QMessageBox.information(
                    self,
                    "成功",
                    localize_popup_message(completion_text),
                )
            self._dirty = False
            self.accept()
        except ValueError as exc:
            QMessageBox.warning(self, "驗證失敗", localize_exception(exc))
        except Exception as exc:
            logger.exception("結案失敗")
            QMessageBox.critical(
                self,
                "錯誤",
                localize_popup_message(f"結案失敗：{localize_exception(exc)}"),
            )
