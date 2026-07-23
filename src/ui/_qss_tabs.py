"""QSS section: QTabWidget, QTabBar, and tab variants."""

from __future__ import annotations

from textwrap import dedent

from ui.theme_tokens import TOKENS, TYPOGRAPHY
from ui.layout_constants import (
    MASTER_TAB_BAR_TAB_PADDING_HORIZONTAL,
    MASTER_TAB_BAR_TAB_PADDING_VERTICAL,
    TAB_BAR_TAB_MIN_HEIGHT,
    TAB_BAR_TAB_PADDING_HORIZONTAL,
    TAB_BAR_TAB_PADDING_VERTICAL,
)


def get_tabs_qss() -> str:
    return dedent(f"""\
        QTabWidget#MainWorkflowTabs::pane {{
            border: 1px solid {TOKENS["border"]};
            border-radius: {TOKENS["radius_lg"]}px;
            background: {TOKENS["panel_bg"]};
            top: -1px;
        }}

        QTabWidget#MainWorkflowTabs QTabBar {{
            background: {TOKENS["nav_dark_bg"]};
        }}

        QTabWidget#MainWorkflowTabs QTabBar::tab {{
            min-width: 106px;
            min-height: {TAB_BAR_TAB_MIN_HEIGHT}px;
            padding: {TAB_BAR_TAB_PADDING_VERTICAL}px 12px;
            margin-right: 2px;
            border: none;
            border-bottom: 3px solid transparent;
            background: {TOKENS["nav_dark_bg"]};
            color: {TOKENS["nav_dark_text"]};
            font-size: {TYPOGRAPHY["tab_label"]}px;
            font-weight: 400;
        }}

        QTabWidget#MainWorkflowTabs QTabBar::tab:hover:!selected {{
            background: {TOKENS["nav_dark_hover_bg"]};
            color: {TOKENS["nav_dark_text_active"]};
            border-bottom: 3px solid {TOKENS["focus_ring"]};
        }}

        QTabWidget#MainWorkflowTabs QTabBar::tab:selected {{
            background: {TOKENS["nav_dark_bg"]};
            color: {TOKENS["nav_dark_text_active"]};
            border-bottom: 3px solid {TOKENS["nav_dark_selected_indicator"]};
            font-weight: 700;
        }}

        QTabWidget::pane {{
            border: 1px solid {TOKENS["border"]};
            border-radius: {TOKENS["radius_md"]}px;
            top: -1px;
            background: {TOKENS["panel_bg"]};
        }}

        QTabBar::tab {{
            min-width: 120px;
            min-height: {TAB_BAR_TAB_MIN_HEIGHT}px;
            border: 1px solid {TOKENS["border"]};
            border-top-left-radius: {TOKENS["radius_sm"]}px;
            border-top-right-radius: {TOKENS["radius_sm"]}px;
            background: {TOKENS["page_bg"]};
            color: {TOKENS["text_secondary"]};
            padding: {TAB_BAR_TAB_PADDING_VERTICAL}px {TAB_BAR_TAB_PADDING_HORIZONTAL}px;
            margin-right: 3px;
            font-size: {TYPOGRAPHY["tab_label"]}px;
            font-weight: 400;
        }}

        QTabBar::tab:selected {{
            background: {TOKENS["panel_bg"]};
            color: {TOKENS["primary_btn"]};
            border-bottom: 1px solid {TOKENS["panel_bg"]};
            font-weight: 700;
        }}

        QTabBar::tab:hover:!selected {{
            background: {TOKENS["subtle_bg"]};
            color: {TOKENS["text_primary"]};
        }}

        QTabBar::tab:disabled {{
            color: {TOKENS["text_disabled"]};
            background: {TOKENS["page_bg"]};
        }}

        QWidget#StatsView,
        QWidget#NcrStatsView {{
            background: {TOKENS["page_bg"]};
        }}

        QTabWidget#MasterDataTabs QTabBar::tab {{
            min-width: 100px;
            padding: {MASTER_TAB_BAR_TAB_PADDING_VERTICAL}px {MASTER_TAB_BAR_TAB_PADDING_HORIZONTAL}px;
            margin-right: 3px;
        }}

        QFrame[role="topNavBar"] {{
            background: {TOKENS["page_bg"]};
            border-bottom: 1px solid {TOKENS["border_soft"]};
        }}

        QLabel[role="navBrandLabel"] {{
            background: transparent;
            font-size: {TYPOGRAPHY["section_title"]}px;
            font-weight: 700;
            color: {TOKENS["text_primary"]};
            padding-left: 16px;
            padding-right: 8px;
        }}
    """).strip()
