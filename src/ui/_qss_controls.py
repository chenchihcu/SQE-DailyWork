"""QSS section: input controls and buttons."""

from __future__ import annotations

from textwrap import dedent

from ui.theme_tokens import TOKENS, TYPOGRAPHY
from ui.layout_constants import (
    BUTTON_PADDING_HORIZONTAL,
    BUTTON_PADDING_VERTICAL,
    BUTTON_SECONDARY_PADDING_HORIZONTAL,
    BUTTON_SECONDARY_PADDING_VERTICAL,
    CONTROL_MIN_HEIGHT,
    MASTER_INLINE_TOOLBAR_PADDING_HORIZONTAL,
    MASTER_INLINE_TOOLBAR_PADDING_VERTICAL,
    TOOLBAR_BUTTON_PADDING_VERTICAL,
    TOOLBAR_CONTROL_MIN_HEIGHT,
    TOOLBAR_GHOST_PADDING_HORIZONTAL,
    TOOLBAR_PRIMARY_PADDING_HORIZONTAL,
    TOOLBAR_SECONDARY_PADDING_HORIZONTAL,
)


def get_controls_qss() -> str:
    return dedent(f"""\
        QLineEdit,
        QComboBox,
        QDateEdit,
        QSpinBox {{
            min-height: {CONTROL_MIN_HEIGHT}px;
            border-radius: {TOKENS["radius_sm"]}px;
            border: 1px solid {TOKENS["border"]};
            background: {TOKENS["panel_bg"]};
            color: {TOKENS["text_primary"]};
            padding: 0 10px;
            selection-background-color: {TOKENS["selection_bg"]};
        }}

        QTextEdit {{
            border-radius: {TOKENS["radius_sm"]}px;
            border: 1px solid {TOKENS["border"]};
            background: {TOKENS["panel_bg"]};
            color: {TOKENS["text_primary"]};
            padding: 8px;
            selection-background-color: {TOKENS["selection_bg"]};
        }}

        QLineEdit:focus,
        QComboBox:focus,
        QDateEdit:focus,
        QSpinBox:focus,
        QTextEdit:focus {{
            border: 2px solid {TOKENS["focus_ring"]};
            background: {TOKENS["panel_bg"]};
        }}

        QLineEdit:read-only,
        QTextEdit:read-only {{
            background: {TOKENS["page_bg"]};
            color: {TOKENS["text_secondary"]};
        }}

        /* Inline field-level validation: placed after :focus so the error border
           stays visible even while the invalid field is focused (cleared in
           real time as soon as the user edits it). */
        QLineEdit[invalid="true"],
        QComboBox[invalid="true"],
        QDateEdit[invalid="true"],
        QSpinBox[invalid="true"],
        QTextEdit[invalid="true"] {{
            border: 2px solid {TOKENS["danger"]};
        }}

        QComboBox::drop-down,
        QDateEdit::drop-down {{
            border: none;
            width: 26px;
            background: {TOKENS["panel_alt_bg"]};
            border-left: 1px solid {TOKENS["border"]};
            border-top-right-radius: {TOKENS["radius_sm"]}px;
            border-bottom-right-radius: {TOKENS["radius_sm"]}px;
        }}

        QPushButton {{
            min-height: {CONTROL_MIN_HEIGHT}px;
            padding: {BUTTON_PADDING_VERTICAL}px {BUTTON_PADDING_HORIZONTAL}px;
            border-radius: {TOKENS["radius_sm"]}px;
            border: 1px solid {TOKENS["border"]};
            background: {TOKENS["panel_alt_bg"]};
            color: {TOKENS["text_primary"]};
            font-weight: 700;
        }}

        QPushButton:hover {{
            background: {TOKENS["surface_hover"]};
            border-color: {TOKENS["border"]};
        }}

        QPushButton:pressed {{
            background: {TOKENS["border_soft"]};
        }}

        QPushButton:focus {{
            border: 2px solid {TOKENS["focus_ring"]};
        }}

        QPushButton:disabled {{
            color: {TOKENS["text_disabled"]};
            background: {TOKENS["page_bg"]};
            border-color: {TOKENS["border_soft"]};
        }}

        QPushButton[variant="primary"],
        QPushButton[variant="toolbarPrimary"] {{
            min-height: {TOOLBAR_CONTROL_MIN_HEIGHT}px;
            padding: {TOOLBAR_BUTTON_PADDING_VERTICAL}px {TOOLBAR_PRIMARY_PADDING_HORIZONTAL}px;
            border: 1px solid {TOKENS["primary_btn"]};
            background: {TOKENS["primary_btn"]};
            color: #FFFFFF;
            font-weight: 700;
        }}

        QPushButton[variant="primary"]:hover,
        QPushButton[variant="toolbarPrimary"]:hover {{
            background: {TOKENS["primary_btn_hover"]};
            border-color: {TOKENS["primary_btn_hover"]};
        }}

        QPushButton[variant="secondary"],
        QPushButton[variant="toolbarSecondary"] {{
            min-height: {TOOLBAR_CONTROL_MIN_HEIGHT}px;
            padding: {BUTTON_SECONDARY_PADDING_VERTICAL}px {BUTTON_SECONDARY_PADDING_HORIZONTAL}px;
            border: 1px solid {TOKENS["border"]};
            background: {TOKENS["panel_bg"]};
            color: {TOKENS["text_secondary"]};
            font-weight: 700;
        }}

        QPushButton[variant="secondary"]:hover,
        QPushButton[variant="toolbarSecondary"]:hover {{
            background: {TOKENS["surface_hover"]};
            color: {TOKENS["text_primary"]};
        }}

        QPushButton[role="quickActionButton"] {{
            min-height: 54px;
            padding: 12px 20px 12px 24px;
            text-align: left;
            border-radius: {TOKENS["radius_md"]}px;
            font-size: {TYPOGRAPHY["label_strong"]}px;
            font-weight: 700;
        }}

        QPushButton[role="quickActionButton"][tone="visit"] {{
            background: {TOKENS["primary_faint"]};
            border: 1px solid {TOKENS["info_border"]};
            border-left: 6px solid {TOKENS["brand_cyan"]};
            color: {TOKENS["brand_primary"]};
        }}

        QPushButton[role="quickActionButton"][tone="visit"]:hover {{
            background: {TOKENS["surface_accent"]};
            border-color: {TOKENS["brand_cyan"]};
            color: {TOKENS["brand_navy"]};
        }}

        QPushButton[role="quickActionButton"][tone="anomaly"] {{
            background: {TOKENS["primary_btn"]};
            border: 1px solid {TOKENS["primary_btn"]};
            border-left: 6px solid {TOKENS["brand_cyan"]};
            color: #FFFFFF;
        }}

        QPushButton[role="quickActionButton"][tone="anomaly"]:hover {{
            background: {TOKENS["primary_btn_hover"]};
            border-color: {TOKENS["primary_btn_hover"]};
            border-left-color: {TOKENS["brand_cyan"]};
            color: #FFFFFF;
        }}

        QPushButton[role="quickActionButton"][tone="report"] {{
            background: {TOKENS["panel_bg"]};
            border: 1px solid {TOKENS["border_strong"]};
            border-left: 6px solid {TOKENS["accent_report"]};
            color: {TOKENS["text_secondary"]};
        }}

        QPushButton[role="quickActionButton"][tone="report"]:hover {{
            background: {TOKENS["surface_hover"]};
            border-color: {TOKENS["accent_report"]};
            color: {TOKENS["text_primary"]};
        }}

        QPushButton[role="quickActionButton"]:disabled {{
            background: {TOKENS["page_bg"]};
            border: 1px solid {TOKENS["border_soft"]};
            border-left: 6px solid {TOKENS["border_soft"]};
            color: {TOKENS["text_disabled"]};
        }}

        QFrame[role="summaryStrip"] {{
            background: transparent;
            border: none;
        }}

        QPushButton[role="decisionSummary"] {{
            min-height: 36px;
            padding: 6px 10px;
            text-align: left;
            border: 1px solid {TOKENS["border_soft"]};
            border-radius: {TOKENS["radius_sm"]}px;
            background: {TOKENS["panel_bg"]};
            color: {TOKENS["text_secondary"]};
            font-size: {TYPOGRAPHY["helper_text"]}px;
            font-weight: 700;
        }}

        QPushButton[role="decisionSummary"]:hover {{
            background: {TOKENS["surface_hover"]};
            border-color: {TOKENS["focus_ring"]};
            color: {TOKENS["text_primary"]};
        }}

        QPushButton[role="decisionSummary"]:disabled {{
            background: {TOKENS["page_bg"]};
            border-color: {TOKENS["border_soft"]};
            color: {TOKENS["text_disabled"]};
        }}

        QPushButton[variant="toolbarSecondary"] {{
            padding: {TOOLBAR_BUTTON_PADDING_VERTICAL}px {TOOLBAR_SECONDARY_PADDING_HORIZONTAL}px;
        }}

        QPushButton[variant="toolbarGhost"] {{
            min-height: {TOOLBAR_CONTROL_MIN_HEIGHT}px;
            padding: {TOOLBAR_BUTTON_PADDING_VERTICAL}px {TOOLBAR_GHOST_PADDING_HORIZONTAL}px;
            border: 1px solid {TOKENS["toolbar_ghost_border"]};
            background: {TOKENS["toolbar_ghost_bg"]};
            color: {TOKENS["toolbar_ghost_text"]};
            font-weight: 700;
        }}

        QPushButton[variant="toolbarGhost"]:hover {{
            background: {TOKENS["subtle_bg"]};
            color: {TOKENS["text_primary"]};
        }}

        QPushButton[variant="danger"] {{
            background: {TOKENS["panel_bg"]};
            border: 1px solid {TOKENS["danger_border"]};
            color: {TOKENS["danger"]};
        }}

        QPushButton[variant="danger"]:hover {{
            background: {TOKENS["danger_hover"]};
        }}

        /* Variant buttons re-declare their border; being later in source with equal
           specificity they would suppress the base QPushButton:focus ring. Re-assert a
           2px focus ring at higher specificity so focus stays visible (a11y §5 / §8). */
        QPushButton[variant="primary"]:focus,
        QPushButton[variant="toolbarPrimary"]:focus,
        QPushButton[variant="secondary"]:focus,
        QPushButton[variant="toolbarSecondary"]:focus,
        QPushButton[variant="toolbarGhost"]:focus,
        QPushButton[variant="danger"]:focus {{
            border: 2px solid {TOKENS["focus_ring"]};
        }}

        QPushButton[role="pageBtn"] {{
            padding: 0;
            min-width: 32px;
            font-weight: 700;
        }}

        QFrame#MasterInlineToolbar {{
            background: {TOKENS["surface_active"]};
            border: 1px solid {TOKENS["focus_ring"]};
            border-radius: {TOKENS["radius_sm"]}px;
            padding: {MASTER_INLINE_TOOLBAR_PADDING_VERTICAL}px {MASTER_INLINE_TOOLBAR_PADDING_HORIZONTAL}px;
        }}

        QWidget#MasterInlineToolbar,
        QWidget#MasterPrimaryRow,
        QWidget#MasterQueryRow {{
            background: transparent;
        }}

        QFrame#MasterInlineToolbar QLineEdit[role="masterQuery"] {{
            min-height: {TOOLBAR_CONTROL_MIN_HEIGHT}px;
            background: {TOKENS["panel_bg"]};
            border: 1px solid {TOKENS["border"]};
            border-radius: {TOKENS["radius_sm"]}px;
            color: {TOKENS["text_primary"]};
            padding: 0 10px;
        }}

        QFrame#MasterInlineToolbar QLineEdit[role="masterQuery"]:focus {{
            border: 1px solid {TOKENS["focus_ring"]};
            background: {TOKENS["panel_bg"]};
        }}

        QGroupBox {{
            margin-top: 10px;
            border-radius: {TOKENS["radius_sm"]}px;
            border: 1px solid {TOKENS["border_soft"]};
            padding: 14px 12px 10px 12px;
            font-size: {TYPOGRAPHY["group_box_title"]}px;
            font-weight: 700;
            background: {TOKENS["panel_alt_bg"]};
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 4px;
            color: {TOKENS["text_secondary"]};
        }}
    """).strip()
