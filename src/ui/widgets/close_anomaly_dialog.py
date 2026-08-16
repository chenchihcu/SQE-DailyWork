"""Close-anomaly dialog with its inline attachment editor."""

from __future__ import annotations

import logging
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QLabel,
    QMessageBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from services.event import _anomaly_service as event_service
from ui.layout_constants import (
    CLOSE_DIALOG_PROBLEM_MIN_HEIGHT,
    CLOSE_DIALOG_REF_MARGINS,
    CONTROL_ROW_SPACING,
    DIALOG_OUTER_MARGINS,
    FORM_HORIZONTAL_SPACING,
    FORM_MAX_WIDTH,
    FORM_VERTICAL_SPACING,
)
from ui.popup_i18n import localize_exception, localize_popup_message
from ui.widgets.common_widgets import (
    DirtyTrackingMixin,
    RequiredFieldLabel,
)
from ui.widgets.defect_form_widgets import (
    ROOT_CAUSE_PARETO_OPTIONS,
    apply_dialog_layout,
    set_combo_current_text,
    set_text_edit_visible_rows,
    set_tone,
    style_dialog_buttons,
)

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────
ROOT_CAUSE_CATEGORY_OPTIONS = ROOT_CAUSE_PARETO_OPTIONS

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
        self.setMinimumWidth(720)
        self.setMaximumWidth(FORM_MAX_WIDTH)
        
        # 取得異常詳情以設定預設的原因分類 (與原先 category 一致)
        self.detail: dict = {}
        self.initial_category = ""
        self.initial_anomaly_date = ""
        self.initial_closed_at = ""
        self.initial_improvement_desc = ""
        try:
            detail = event_service.get_anomaly_detail(self.anomaly_id)
            self.detail = detail
            self.initial_category = str(detail.get("category_raw") or detail.get("category") or "")
            self.initial_anomaly_date = str(detail.get("anomaly_date") or "")
            self.initial_closed_at = str(detail.get("closed_at") or "")
            self.initial_improvement_desc = str(detail.get("improvement_desc") or "")
        except Exception:
            logger.exception("Failed to get initial category for anomaly %s", self.anomaly_id)

        self._setup_ui()
        self.attachment_editor.load_existing_attachments(self.anomaly_id)
        self._update_validation()

        self._connect_dirty_signals()

    def _setup_ui(self):
        self.problem_view = QTextEdit()
        self.problem_view.setReadOnly(True)
        self.problem_view.setPlainText(self.problem_desc)
        self.problem_view.setPlaceholderText("原始問題描述唯讀區")
        self.problem_view.setAccessibleName("原始問題描述")
        self.problem_view.setMinimumHeight(CLOSE_DIALOG_PROBLEM_MIN_HEIGHT)

        self.improvement_input = QTextEdit()
        self.improvement_input.setPlaceholderText("請輸入改善內容（必填）")
        self.improvement_input.setAccessibleName("改善內容")
        set_text_edit_visible_rows(self.improvement_input, 6)

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

        self.attachment_editor = AttachmentEditor(self)
        if self.date_adjustment_only:
            self.attachment_editor.setEnabled(False)

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
        pref_layout.setSpacing(4)
        pref_lbl = QLabel("原始問題描述：")
        pref_lbl.setProperty("role", "meta")
        pref_text = QLabel(self.problem_desc.strip() if self.problem_desc else "（無問題描述）")
        pref_text.setWordWrap(True)
        pref_text.setProperty("role", "summary")
        pref_layout.addWidget(pref_lbl)
        pref_layout.addWidget(pref_text)
        content_layout.addWidget(problem_ref_box)

        form = QFormLayout()
        form.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        form.setVerticalSpacing(FORM_VERTICAL_SPACING)
        form.addRow(RequiredFieldLabel("改善內容"), self.improvement_input)
        form.addRow("", self.improvement_counter)
        form.addRow(RequiredFieldLabel("結案日期"), self.closed_at_input)
        content_layout.addLayout(form)

        # 現場照片附件區
        attach_label = QLabel("現場照片與改善佐證附件：")
        attach_label.setProperty("role", "meta")
        content_layout.addWidget(attach_label)
        content_layout.addWidget(self.attachment_editor)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        self._save_button = style_dialog_buttons(buttons)
        if self._save_button:
            self._save_button.setCursor(Qt.PointingHandCursor)
            self._save_button.setAccessibleName("確認結案")
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)

        apply_dialog_layout(self, content, buttons)

        self.improvement_input.textChanged.connect(self._update_validation)
        self.closed_at_input.dateChanged.connect(self._update_validation)

    def _connect_dirty_signals(self) -> None:
        self._init_dirty_tracking([
            self.improvement_input.textChanged,
            self.closed_at_input.dateChanged,
            self.attachment_editor.add_button.clicked,
            self.attachment_editor.remove_button.clicked,
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
        try:
            if self.date_adjustment_only:
                result = event_service.update_anomaly_closed_at(
                    self.anomaly_id,
                    closed_at=closed_at,
                )
                completion_text = "結案日期已更新"
            else:
                result = event_service.close_anomaly(
                    self.anomaly_id,
                    text,
                    closed_at=closed_at,
                )
                self.attachment_editor.save_to_anomaly(self.anomaly_id)
                if self.attachment_editor._last_rename_failures:
                    QMessageBox.warning(
                        self,
                        "附件改名失敗",
                        "以下附件改名未成功，檔名可能維持原狀：\n"
                        + "\n".join(self.attachment_editor._last_rename_failures),
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


# ── Re-export for backward compatibility ─────────────────────────────────
from ui.widgets.anomaly_attachment_editor import AttachmentEditor  # noqa: F401
