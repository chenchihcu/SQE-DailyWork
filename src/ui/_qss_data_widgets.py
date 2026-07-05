"""QSS section: tables, lists, menus, scrollbars, and charts."""

from __future__ import annotations

from textwrap import dedent

from ui.theme_tokens import TOKENS, TYPOGRAPHY
from ui.layout_constants import (
    HEADER_SECTION_PADDING,
    MENU_ITEM_PADDING_HORIZONTAL,
    MENU_ITEM_PADDING_VERTICAL,
    MENU_PADDING,
    TABLE_CELL_PADDING,
    TABLE_ITEM_MIN_HEIGHT,
    SCROLLBAR_WIDTH,
)


def get_data_widgets_qss() -> str:
    return dedent(f"""\
        QTableWidget {{
            border: 1px solid {TOKENS["border"]};
            border-radius: {TOKENS["radius_sm"]}px;
            gridline-color: {TOKENS["grid"]};
            background: {TOKENS["panel_bg"]};
            selection-background-color: {TOKENS["selection_bg"]};
            selection-color: {TOKENS["text_primary"]};
            alternate-background-color: {TOKENS["panel_alt_bg"]};
        }}

        QTableWidget::item {{
            padding: {TABLE_CELL_PADDING}px;
            min-height: {TABLE_ITEM_MIN_HEIGHT}px;
            border: none;
        }}

        QTableWidget::item:hover {{
            background: {TOKENS["primary_faint"]};
        }}

        QTableWidget::item:selected {{
            background: {TOKENS["surface_active"]};
            color: {TOKENS["text_primary"]};
        }}

        QTableWidget QPushButton[role="tableCellAction"] {{
            min-height: 0;
            padding: 0 2px;
            border: none;
            border-radius: 0;
            background: transparent;
            color: {TOKENS["primary_btn"]};
            font-weight: 700;
        }}

        QTableWidget QPushButton[role="tableCellAction"]:hover {{
            background: transparent;
            color: {TOKENS["primary_btn_hover"]};
        }}

        QHeaderView::section {{
            background: {TOKENS["surface_active"]};
            color: {TOKENS["text_primary"]};
            font-weight: 700;
            border: none;
            border-right: 1px solid {TOKENS["grid"]};
            border-bottom: 1px solid {TOKENS["border"]};
            padding: {HEADER_SECTION_PADDING}px;
        }}

        QChartView {{
            background: transparent;
            border: 1px solid transparent;
            border-radius: {TOKENS["radius_sm"]}px;
        }}

        QChartView:hover {{
            border: 1px solid {TOKENS["border_soft"]};
            background: {TOKENS["surface_hover"]};
        }}

        QMenu {{
            background: {TOKENS["panel_bg"]};
            border: 1px solid {TOKENS["border"]};
            padding: {MENU_PADDING}px;
        }}

        QMenu::item {{
            padding: {MENU_ITEM_PADDING_VERTICAL}px {MENU_ITEM_PADDING_HORIZONTAL}px;
            border-radius: 6px;
        }}

        QMenu::item:selected {{
            background: {TOKENS["filter_active_bg"]};
            color: {TOKENS["filter_active_text"]};
        }}
    """).strip()
