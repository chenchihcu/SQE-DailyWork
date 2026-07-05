"""QSS section: dialogs, calendar, checkbox, radio, cards, badges, scrollbars."""

from __future__ import annotations

from textwrap import dedent

from ui.theme_tokens import TOKENS, TYPOGRAPHY
from ui.layout_constants import (
    CALENDAR_SPINBOX_MIN_HEIGHT,
    CALENDAR_TOOLBUTTON_MIN_HEIGHT,
    SCROLLBAR_WIDTH,
)


def get_dialogs_etc_qss(checkbox_tick_url: str) -> str:
    return dedent(f"""\
        QDialog,
        QMessageBox {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(243, 244, 246, 0.96), stop:1 rgba(229, 231, 235, 0.96));
        }}

        QCalendarWidget {{
            background: {TOKENS["panel_bg"]};
            border: 1px solid {TOKENS["border"]};
            border-radius: {TOKENS["radius_sm"]}px;
        }}

        QCalendarWidget QWidget#qt_calendar_navigationbar {{
            background: {TOKENS["panel_alt_bg"]};
            border: none;
            border-bottom: 1px solid {TOKENS["border"]};
        }}

        QCalendarWidget QToolButton {{
            min-height: {CALENDAR_TOOLBUTTON_MIN_HEIGHT}px;
            border: none;
            background: {TOKENS["panel_alt_bg"]};
            color: {TOKENS["text_primary"]};
            font-weight: 700;
            border-radius: {TOKENS["radius_sm"]}px;
            padding: 0 8px;
        }}

        QCalendarWidget QToolButton:hover {{
            background: {TOKENS["subtle_bg"]};
        }}

        QCalendarWidget QSpinBox {{
            min-height: {CALENDAR_SPINBOX_MIN_HEIGHT}px;
            border: 1px solid {TOKENS["border"]};
            border-radius: {TOKENS["radius_sm"]}px;
            background: {TOKENS["panel_bg"]};
            color: {TOKENS["text_primary"]};
        }}

        QCalendarWidget QAbstractItemView {{
            background: {TOKENS["panel_bg"]};
            selection-background-color: {TOKENS["primary_btn"]};
            selection-color: #FFFFFF;
            border: none;
        }}

        QCheckBox {{
            background: transparent;
            spacing: 8px;
        }}

        QCheckBox::indicator {{
            width: 14px;
            height: 14px;
            border: 1px solid {TOKENS["text_secondary"]};
            border-radius: 3px;
            background: {TOKENS["panel_bg"]};
        }}

        QCheckBox::indicator:checked {{
            border: 1px solid {TOKENS["primary_btn"]};
            background: {TOKENS["primary_btn"]};
            image: url("{checkbox_tick_url}");
        }}

        QCheckBox::indicator:unchecked:disabled {{
            border: 1px solid {TOKENS["border"]};
            background: {TOKENS["page_bg"]};
        }}

        QCheckBox::indicator:checked:disabled {{
            border: 1px solid {TOKENS["border"]};
            background: {TOKENS["text_disabled"]};
            image: url("{checkbox_tick_url}");
        }}

        QRadioButton {{
            color: {TOKENS["text_primary"]};
            spacing: 6px;
            padding: 2px 0;
        }}

        QRadioButton::indicator {{
            width: 13px;
            height: 13px;
            border-radius: 6px;
            border: 1px solid {TOKENS["text_secondary"]};
            background: {TOKENS["panel_bg"]};
        }}

        QRadioButton::indicator:checked {{
            border: 1px solid {TOKENS["primary_btn"]};
            background: {TOKENS["primary_btn"]};
        }}

        QCheckBox::indicator:hover:!disabled,
        QRadioButton::indicator:hover:!disabled {{
            border: 1px solid {TOKENS["primary_btn"]};
        }}

        QFrame#techTransferCard {{
            background: {TOKENS["panel_alt_bg"]};
            border: 1px solid {TOKENS["border"]};
            border-radius: {TOKENS["radius_sm"]}px;
        }}

        QFrame#techTransferCard[state="normal"] {{
            background: {TOKENS["panel_alt_bg"]};
            border: 1px solid {TOKENS["border"]};
        }}

        QFrame#techTransferCard[state="selected"] {{
            background: {TOKENS["status_success_bg"]};
            border: 2px solid {TOKENS["status_success_border"]};
        }}

        QFrame#techTransferCard[state="na"] {{
            background: {TOKENS["status_na_bg"]};
            border: 1px solid {TOKENS["status_na_border"]};
        }}

        QLabel#techCardTitle {{
            color: {TOKENS["text_secondary"]};
            font-weight: 700;
        }}

        QFrame#techTransferCard[state="selected"] QLabel#techCardTitle {{
            color: {TOKENS["status_success_fg"]};
            font-weight: 700;
        }}

        QFrame#techTransferCard[state="na"] QLabel#techCardTitle {{
            color: {TOKENS["status_na_fg"]};
            font-weight: 700;
        }}

        QFrame#refDataCard {{
            background: {TOKENS["panel_alt_bg"]};
            border: 1px solid {TOKENS["border_soft"]};
            border-radius: {TOKENS["radius_sm"]}px;
        }}

        QLabel[role="refCardName"] {{
            color: {TOKENS["text_secondary"]};
            font-weight: 700;
        }}

        QLabel[role="refCardValue"] {{
            color: {TOKENS["status_unknown_fg"]};
            background: {TOKENS["status_unknown_bg"]};
            border: 1px solid {TOKENS["status_unknown_border"]};
            border-radius: {TOKENS["radius_sm"]}px;
            padding: 2px 8px;
            font-weight: 700;
        }}

        QLabel[role="refCardValue"][status="success"] {{
            color: {TOKENS["status_success_fg"]};
            background: {TOKENS["status_success_bg"]};
            border: 1px solid {TOKENS["status_success_border"]};
            font-weight: 700;
        }}

        QLabel[role="refCardValue"][status="muted"] {{
            color: {TOKENS["status_unknown_fg"]};
            background: {TOKENS["status_unknown_bg"]};
            border: 1px solid {TOKENS["status_unknown_border"]};
        }}

        QLabel[role="refCardValue"][status="na"] {{
            color: {TOKENS["status_na_fg"]};
            background: {TOKENS["status_na_bg"]};
            border: 1px solid {TOKENS["status_na_border"]};
        }}

        QListWidget#AttachmentPreviewList {{
            background: {TOKENS["attachment_bg"]};
            border: 1px solid {TOKENS["border"]};
            border-radius: {TOKENS["radius_sm"]}px;
            padding: 6px;
            selection-background-color: {TOKENS["attachment_selected_bg"]};
            selection-color: {TOKENS["text_primary"]};
        }}

        QListWidget#AttachmentPreviewList::item {{
            background: {TOKENS["panel_bg"]};
            border: 1px solid {TOKENS["border_soft"]};
            border-radius: {TOKENS["radius_sm"]}px;
            color: {TOKENS["text_secondary"]};
            padding: 4px;
        }}

        QListWidget#AttachmentPreviewList::item:hover {{
            background: {TOKENS["attachment_hover_bg"]};
            border: 1px solid {TOKENS["focus_ring"]};
            color: {TOKENS["text_primary"]};
        }}

        QListWidget#AttachmentPreviewList::item:selected {{
            background: {TOKENS["attachment_selected_bg"]};
            border: 1px solid {TOKENS["attachment_selected_border"]};
            color: {TOKENS["text_primary"]};
        }}

        QDialog#VisitDetailDialog {{
            background: {TOKENS["page_bg"]};
        }}

        QFrame#VisitDetailHeader {{
            background: {TOKENS["primary_btn"]};
            border: none;
        }}

        QFrame#VisitDetailHeader QLabel {{
            background: transparent;
            border: none;
            color: #FFFFFF;
        }}

        QFrame#VisitDetailHeader QLabel[role="title"] {{
            font-size: {TYPOGRAPHY["section_title"]}px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}

        QFrame#VisitDetailBody {{
            background: {TOKENS["page_bg"]};
            border: none;
        }}

        QFrame#VisitDetailFooter {{
            background: {TOKENS["page_bg"]};
            border-top: 1px solid {TOKENS["border_soft"]};
            border-left: none;
            border-right: none;
            border-bottom: none;
        }}

        QFrame[role="visitDetailCard"] {{
            background: {TOKENS["panel_bg"]};
            border: 1px solid {TOKENS["border_soft"]};
            border-radius: {TOKENS["radius_lg"]}px;
        }}

        QFrame[role="visitDetailCard"] QLabel,
        QFrame[role="visitDetailCard"] QFrame {{
            background: transparent;
            border: none;
        }}

        QFrame[role="visitDetailCard"] QFrame[role="separator"] {{
            background: {TOKENS["border_soft"]};
        }}

        QFrame[role="visitDetailCard"] QLabel[role="meta"] {{
            color: {TOKENS["text_muted"]};
            font-size: {TYPOGRAPHY["caption"]}px;
            font-weight: 700;
            letter-spacing: 0.3px;
        }}

        QFrame[role="visitDetailCard"] QLabel[role="value"] {{
            color: {TOKENS["text_primary"]};
            font-size: {TYPOGRAPHY["label_strong"]}px;
            font-weight: 700;
        }}

        QFrame[role="visitDetailCard"] QLabel[role="summary"] {{
            color: {TOKENS["text_primary"]};
            font-size: {TYPOGRAPHY["body"]}px;
        }}

        QFrame[role="visitDetailCard"] QLabel[role="techDot"] {{
            font-size: {TYPOGRAPHY["body_small"]}px;
            font-weight: 700;
            color: {TOKENS["text_disabled"]};
        }}

        QFrame[role="visitDetailCard"] QLabel[role="techDot"][state="on"] {{
            color: {TOKENS["status_success_fg"]};
        }}

        QFrame[role="visitDetailCard"] QLabel[role="techName"] {{
            color: {TOKENS["text_disabled"]};
            font-size: {TYPOGRAPHY["body"]}px;
        }}

        QFrame[role="visitDetailCard"] QLabel[role="techName"][state="on"] {{
            color: {TOKENS["text_primary"]};
        }}

        QFrame[role="visitDetailCard"] QLabel[role="techValue"] {{
            color: {TOKENS["text_disabled"]};
            font-size: {TYPOGRAPHY["body_small"]}px;
            font-weight: 400;
        }}

        QFrame[role="visitDetailCard"] QLabel[role="techValue"][state="on"] {{
            color: {TOKENS["status_success_fg"]};
        }}

        QLabel[role="statusBadge"] {{
            background: {TOKENS["status_unknown_bg"]};
            color: {TOKENS["status_unknown_fg"]};
            border: 1px solid {TOKENS["status_unknown_border"]};
            font-size: {TYPOGRAPHY["caption"]}px;
            font-weight: 700;
            border-radius: 9px;
            padding: 1px 6px;
        }}

        QLabel[role="statusBadge"][tone="success"] {{
            background: {TOKENS["status_success_bg"]};
            color: {TOKENS["status_success_fg"]};
            border: 1px solid {TOKENS["status_success_border"]};
        }}

        QLabel[role="statusBadge"][tone="pending"] {{
            background: {TOKENS["status_pending_bg"]};
            color: {TOKENS["status_pending_fg"]};
            border: 1px solid {TOKENS["status_pending_border"]};
        }}

        QLabel[role="statusBadge"][tone="danger"] {{
            background: {TOKENS["status_danger_bg"]};
            color: {TOKENS["status_danger_fg"]};
            border: 1px solid {TOKENS["status_danger_border"]};
        }}

        QLabel[role="statusBadge"][tone="info"] {{
            background: {TOKENS["status_info_bg"]};
            color: {TOKENS["status_info_fg"]};
            border: 1px solid {TOKENS["status_info_border"]};
        }}

        QLabel[role="statusBadge"][tone="na"] {{
            background: {TOKENS["status_na_bg"]};
            color: {TOKENS["status_na_fg"]};
            border: 1px solid {TOKENS["status_na_border"]};
        }}

        QPushButton[role="visitDetailClose"] {{
            background: {TOKENS["primary_btn"]};
            border: 1px solid {TOKENS["primary_btn"]};
            color: #FFFFFF;
            font-weight: 700;
            border-radius: {TOKENS["radius_sm"]}px;
            min-height: 34px;
            padding: 0 20px;
        }}

        QPushButton[role="visitDetailClose"]:hover {{
            background: {TOKENS["primary_btn_hover"]};
            border-color: {TOKENS["primary_btn_hover"]};
        }}

        QFrame[role="emptyState"] {{
            background: {TOKENS["empty_state_bg"]};
            border: 1px dashed {TOKENS["empty_state_border"]};
            border-radius: {TOKENS["radius_lg"]}px;
        }}

        QFrame[role="emptyState"] QLabel[role="title"] {{
            color: {TOKENS["text_secondary"]};
            font-size: {TYPOGRAPHY["section_title"]}px;
            font-weight: 700;
            background: transparent;
        }}

        QFrame[role="emptyState"] QLabel[role="hint"] {{
            color: {TOKENS["text_muted"]};
            font-size: {TYPOGRAPHY["body"]}px;
            background: transparent;
        }}

        QLabel[role="requiredLabel"] {{
            color: {TOKENS["text_primary"]};
            font-weight: 700;
        }}

        QLabel[role="requiredLabel"] QLabel[role="requiredMark"] {{
            color: {TOKENS["danger"]};
        }}

        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: {SCROLLBAR_WIDTH}px;
            margin: 4px 1px 4px 1px;
            border-radius: 3px;
        }}

        QScrollBar::handle:vertical {{
            background: rgba(160, 185, 205, 0.4);
            min-height: 30px;
            border-radius: 3px;
        }}

        QScrollBar::handle:vertical:hover {{
            background: {TOKENS["primary_btn"]};
        }}

        QScrollBar::handle:vertical:pressed {{
            background: {TOKENS["primary_btn_hover"]};
        }}

        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical,
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {{
            width: 0;
            height: 0;
            background: none;
            border: none;
        }}

        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical,
        QScrollBar::add-page:horizontal,
        QScrollBar::sub-page:horizontal {{
            background: none;
        }}

        QScrollBar:horizontal {{
            border: none;
            background: transparent;
            height: {SCROLLBAR_WIDTH}px;
            margin: 1px 4px 1px 4px;
            border-radius: 3px;
        }}

        QScrollBar::handle:horizontal {{
            background: rgba(160, 185, 205, 0.4);
            min-width: 30px;
            border-radius: 3px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background: {TOKENS["primary_btn"]};
        }}

        QScrollBar::handle:horizontal:pressed {{
            background: {TOKENS["primary_btn_hover"]};
        }}
    """).strip()
