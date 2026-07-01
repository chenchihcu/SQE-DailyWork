"""Close-anomaly dialog with its inline attachment editor."""

from __future__ import annotations

import logging
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from services import event_service
from ui.layout_constants import (
    DIALOG_MIN_HEIGHT,
    DIALOG_OUTER_MARGINS,
    FORM_MAX_WIDTH,
)
from ui.popup_i18n import localize_exception, localize_popup_message
from ui.window_sizing import fit_dialog_to_available_screen
from ui.widgets.common_widgets import (
    RequiredFieldLabel,
    make_paired_form_row as _make_paired_form_row,
    mark_button_variant as _mark_button_variant,
)
from ui.widgets.defect_form_widgets import set_text_edit_visible_rows

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────
ROOT_CAUSE_CATEGORY_OPTIONS = [
    "",
    "設計缺陷",
    "製程參數異常",
    "物料/來料問題",
    "人為操作疏失",
    "設備/治具異常",
    "環境因素",
    "文件/SOP 不足",
    "其他",
]

IMPROVEMENT_DESC_MAX_LEN = 1000


# ── Layout helpers (duplicated from defect_form_widget to avoid circular imports) ──
def _set_tone(widget: QWidget, tone: str) -> None:
    widget.setProperty("tone", tone)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


def _style_dialog_buttons(buttons: QDialogButtonBox) -> QPushButton:
    save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
    cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
    _mark_button_variant(save_button, "primary")
    _mark_button_variant(cancel_button, "secondary")
    if save_button:
        save_button.setText("儲存")
    if cancel_button:
        cancel_button.setText("取消")
    return save_button


def _apply_dialog_layout(
    dialog: QDialog,
    content: QWidget,
    button_box: QDialogButtonBox,
) -> None:
    """Standardize dialog layout with a fixed bottom button row."""
    outer = QVBoxLayout(dialog)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)
    outer.addWidget(content, 1)

    bar = QWidget()
    bar_layout = QHBoxLayout(bar)
    bar_layout.setContentsMargins(
        DIALOG_OUTER_MARGINS[0], 8, DIALOG_OUTER_MARGINS[2], DIALOG_OUTER_MARGINS[3]
    )
    bar_layout.addStretch(1)
    bar_layout.addWidget(button_box)
    bar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    outer.addWidget(bar)
    dialog.setSizeGripEnabled(True)
    hint = dialog.sizeHint()
    fit_dialog_to_available_screen(
        dialog,
        preferred_width=hint.width(),
        preferred_height=hint.height() + 20,
        minimum_height=DIALOG_MIN_HEIGHT,
    )



# ── CloseAnomalyDialog ─────────────────────────────────────────────────────
class CloseAnomalyDialog(QDialog):
    def __init__(self, anomaly_id: str, problem_desc: str, parent=None):
        super().__init__(parent)
        self.anomaly_id = anomaly_id
        self.problem_desc = problem_desc
        self.setWindowTitle("異常結案")
        self.setMinimumWidth(720)
        self.setMaximumWidth(FORM_MAX_WIDTH)
        self._setup_ui()
        self.attachment_editor.load_existing_attachments(self.anomaly_id)
        self._update_validation()

        self._dirty = False
        self._connect_dirty_signals()

    def _setup_ui(self):
        self.problem_view = QTextEdit()
        self.problem_view.setReadOnly(True)
        self.problem_view.setPlainText(self.problem_desc)
        self.problem_view.setMinimumHeight(240)

        self.improvement_input = QTextEdit()
        self.improvement_input.setPlaceholderText("請輸入改善內容（必填）")
        # Row-based height keeps the field compact and consistent with the other
        # long-text inputs (min==max via the shared helper) instead of a fixed 240px.
        set_text_edit_visible_rows(self.improvement_input, 10)

        self.improvement_counter = QLabel(f"0 / {IMPROVEMENT_DESC_MAX_LEN}")
        self.improvement_counter.setProperty("role", "counterText")
        self.improvement_counter.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        self.closer_input = QLineEdit()
        self.closer_input.setPlaceholderText("請輸入結案人員姓名（必填）")

        self.root_cause_combo = QComboBox()
        self.root_cause_combo.setEditable(True)
        for option in ROOT_CAUSE_CATEGORY_OPTIONS:
            self.root_cause_combo.addItem(option)

        self.attachment_editor = AttachmentEditor(self)

        self.tabs = QTabWidget()

        tab_action = QWidget()
        action_layout = QVBoxLayout(tab_action)
        action_layout.setContentsMargins(*DIALOG_OUTER_MARGINS)

        form = QFormLayout()
        form.addRow(RequiredFieldLabel("改善內容"), self.improvement_input)
        form.addRow("", self.improvement_counter)
        form.addRow(
            _make_paired_form_row(
                "CloseAnomalyCloserCauseRow",
                RequiredFieldLabel("結案人員"),
                self.closer_input,
                "原因分類",
                self.root_cause_combo,
            )
        )
        action_layout.addLayout(form)
        action_layout.addStretch(1)
        self.tabs.addTab(tab_action, "改善處理")

        tab_media = QWidget()
        media_layout = QVBoxLayout(tab_media)
        media_layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        media_layout.addWidget(QLabel("原始問題描述："))
        media_layout.addWidget(self.problem_view)
        media_layout.addWidget(QLabel("現場照片附件："))
        media_layout.addWidget(self.attachment_editor)
        self.tabs.addTab(tab_media, "Context & 照片")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        self._save_button = _style_dialog_buttons(buttons)
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)

        _apply_dialog_layout(self, self.tabs, buttons)

        self.improvement_input.textChanged.connect(self._update_validation)
        self.closer_input.textChanged.connect(self._update_validation)

    def _mark_dirty(self) -> None:
        self._dirty = True

    def _confirm_discard(self) -> bool:
        return QMessageBox.question(
            self,
            "未儲存變更",
            "有未儲存的變更，確定要放棄嗎？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes

    def closeEvent(self, event):
        if self._dirty and not self._confirm_discard():
            event.ignore()
            return
        event.accept()

    def _connect_dirty_signals(self) -> None:
        self.improvement_input.textChanged.connect(self._mark_dirty)
        self.closer_input.textChanged.connect(self._mark_dirty)
        self.root_cause_combo.currentTextChanged.connect(self._mark_dirty)
        self.attachment_editor.add_button.clicked.connect(self._mark_dirty)
        self.attachment_editor.remove_button.clicked.connect(self._mark_dirty)

    def _update_validation(self) -> None:
        text = self.improvement_input.toPlainText()
        length = len(text)
        over_limit = length > IMPROVEMENT_DESC_MAX_LEN
        self.improvement_counter.setText(
            f"{length} / {IMPROVEMENT_DESC_MAX_LEN}"
        )
        _set_tone(self.improvement_counter, "danger" if over_limit else "normal")
        valid = (
            bool(text.strip())
            and not over_limit
            and bool(self.closer_input.text().strip())
        )
        if self._save_button is not None:
            self._save_button.setEnabled(valid)

    def _on_submit(self):
        text = self.improvement_input.toPlainText().strip()
        closer = self.closer_input.text().strip()
        root_cause = self.root_cause_combo.currentText().strip()
        try:
            event_service.close_anomaly(
                self.anomaly_id,
                text,
                closed_by=closer,
                root_cause_category=root_cause,
            )
            self.attachment_editor.save_to_anomaly(self.anomaly_id)
            QMessageBox.information(self, "成功", localize_popup_message("異常已結案"))
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
