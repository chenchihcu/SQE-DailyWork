from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.layout_constants import (
    DIALOG_MIN_HEIGHT,
    DIALOG_OUTER_MARGINS,
    INLINE_SPACING,
    TEXT_EDIT_FALLBACK_LINE_HEIGHT,
    TEXT_EDIT_FALLBACK_PADDING,
)
from ui.window_sizing import fit_dialog_to_available_screen
from ui.widgets.common_widgets import (
    mark_button_variant as _mark_button_variant,
)


# ── Constants ──────────────────────────────────────────────────────────────────

ROOT_CAUSE_PARETO_OPTIONS = [
    "",
    "製程參數失控",
    "規範文件缺漏",
    "檢驗把關失靈",
    "設計匹配不良",
    "設備能力不符",
    "包裝防護不足",
    "來料品質不良",
    "標準作業不落實",
    "供應商改善不力",
    "其他",
]

ANOMALY_CATEGORY_OPTIONS = ROOT_CAUSE_PARETO_OPTIONS


def get_anomaly_category_options() -> list[str]:
    """Return dynamic anomaly category labels from ui_settings preset library."""
    from services.anomaly_category_preset_service import all_category_labels

    return [""] + all_category_labels()

VISIT_TIME_SLOT_OPTIONS = ["上午", "下午", "全天"]


# ── Shared Helper Functions ────────────────────────────────────────────────────


def product_label(item: dict) -> str:
    code = str(item.get("product_code") or "").strip()
    name = str(item.get("product_name") or "").strip()
    if code and name:
        return f"[{code}] {name}"
    return name or code or "(未命名產品)"


def set_combo_current_text(combo: QComboBox, value: str) -> None:
    text = (value or "").strip()
    if not text:
        combo.setCurrentIndex(0)
        return
    idx = combo.findText(text)
    if idx >= 0:
        combo.setCurrentIndex(idx)
        return
    combo.setEditText(text)


def set_tone(widget: QWidget, tone: str) -> None:
    widget.setProperty("tone", tone)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


def style_dialog_buttons(buttons: QDialogButtonBox) -> QPushButton:
    save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
    cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
    _mark_button_variant(save_button, "primary")
    _mark_button_variant(cancel_button, "secondary")
    if save_button:
        save_button.setText("儲存")
    if cancel_button:
        cancel_button.setText("取消")
    return save_button


def set_text_edit_visible_rows(editor: QWidget, rows: int) -> None:
    if hasattr(editor, "document"):
        line_height = editor.fontMetrics().lineSpacing()
        document_margin = int(editor.document().documentMargin() * 2)
        frame_height = editor.frameWidth() * 2
        vertical_padding = 14
        editor.setFixedHeight(
            line_height * max(rows, 1) + vertical_padding + document_margin + frame_height
        )



def apply_dialog_layout(
    dialog: QDialog,
    content: QWidget,
    button_box: QDialogButtonBox,
) -> None:
    """Standardize dialog layout with a fixed bottom button row and no vertical scrollbar."""
    outer = QVBoxLayout(dialog)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    # Main content area
    outer.addWidget(content, 1)

    # Bottom button bar
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


# ── Shared Widget Classes ──────────────────────────────────────────────────────

from ui.widgets.defect_note_form_widgets import DefectNoteTable, ProductSectionEditor  # noqa: F401
