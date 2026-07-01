"""QSS 樣式表模板 — 從 theme.py 提取的大型建構函式。

包含 get_theme_qss() 函式與 asset 輔助函式。
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from ui.theme_tokens import TOKENS, TYPOGRAPHY
from ui.layout_constants import (
    BUTTON_PADDING_HORIZONTAL,
    BUTTON_PADDING_VERTICAL,
    BUTTON_SECONDARY_PADDING_HORIZONTAL,
    BUTTON_SECONDARY_PADDING_VERTICAL,
    CALENDAR_SPINBOX_MIN_HEIGHT,
    CALENDAR_TOOLBUTTON_MIN_HEIGHT,
    CONTROL_MIN_HEIGHT,
    HEADER_SECTION_PADDING,
    MASTER_INLINE_TOOLBAR_PADDING_HORIZONTAL,
    MASTER_INLINE_TOOLBAR_PADDING_VERTICAL,
    MASTER_TAB_BAR_TAB_PADDING_HORIZONTAL,
    MASTER_TAB_BAR_TAB_PADDING_VERTICAL,
    MENU_ITEM_PADDING_HORIZONTAL,
    MENU_ITEM_PADDING_VERTICAL,
    MENU_PADDING,
    NAV_TAB_MIN_HEIGHT,
    PAGE_HEADER_HEIGHT,
    SIDEBAR_NAV_ITEM_HEIGHT,
    TAB_BAR_TAB_MIN_HEIGHT,
    TAB_BAR_TAB_PADDING_HORIZONTAL,
    TAB_BAR_TAB_PADDING_VERTICAL,
    TABLE_CELL_PADDING,
    TABLE_ITEM_MIN_HEIGHT,
    TOOLBAR_BUTTON_PADDING_VERTICAL,
    TOOLBAR_CONTROL_MIN_HEIGHT,
    TOOLBAR_GHOST_PADDING_HORIZONTAL,
    TOOLBAR_PRIMARY_PADDING_HORIZONTAL,
    TOOLBAR_SECONDARY_PADDING_HORIZONTAL,
    SCROLLBAR_WIDTH,
)


def asset_path(asset_name: str) -> Path:
    return Path(__file__).resolve().parent / "assets" / asset_name


def _asset_qss_url(asset_name: str) -> str:
    return asset_path(asset_name).as_posix()


def get_theme_qss() -> str:
    checkbox_tick_url = _asset_qss_url("checkbox_tick.svg")
    return dedent(
        f"""
        QWidget {{
            color: {TOKENS["text_primary"]};
            font-family: {TYPOGRAPHY["font_family"]};
            font-size: {TYPOGRAPHY["base"]}px;
            background: transparent;
        }}

        QMainWindow,
        QWidget#AppRoot {{
            background: {TOKENS["page_bg"]};
        }}

        QFrame[role="panel"],
        QFrame[role="subpanel"],
        QFrame[role="card"],
        QFrame[role="kpiCard"] {{
            background: {TOKENS["panel_bg"]};
            border: 1px solid {TOKENS["border_soft"]};
            border-radius: {TOKENS["radius_lg"]}px;
        }}

        QFrame[role="kpiCard"]:hover {{
            background: {TOKENS["surface_hover"]};
            border-color: {TOKENS["brand_blue"]};
        }}

        /* Visible keyboard-focus ring for interactive (clickable) KPI cards (a11y §5). */
        QFrame[role="kpiCard"][interactive="true"]:focus {{
            border: 2px solid {TOKENS["focus_ring"]};
        }}

        QFrame[role="panel"] QFrame[role="subpanel"],
        QFrame[role="panel"] QFrame[role="card"],
        QFrame[role="panel"] QFrame[role="kpiCard"] {{
            background: transparent;
        }}

        QFrame[role="panel"] QFrame[role="subpanel"][surface="raised"],
        QFrame[role="panel"] QFrame[role="card"][surface="raised"],
        QFrame[role="panel"] QFrame[role="kpiCard"][surface="raised"] {{
            background: {TOKENS["panel_bg"]};
        }}
        
        QFrame[role="card"]:hover,
        QFrame[role="kpiCard"]:hover {{
            border-color: {TOKENS["focus_ring"]};
            background: {TOKENS["surface_hover"]};
        }}

        QFrame[role="kpiCard"][tone="danger"],
        QFrame[role="panel"] QFrame[role="kpiCard"][tone="danger"] {{
            background: {TOKENS["status_danger_bg"]};
            border: 1px solid {TOKENS["status_danger_border"]};
            border-radius: {TOKENS["radius_lg"]}px;
        }}

        QFrame[role="kpiCard"][tone="info"],
        QFrame[role="panel"] QFrame[role="kpiCard"][tone="info"] {{
            background: {TOKENS["status_info_bg"]};
            border: 1px solid {TOKENS["status_info_border"]};
            border-radius: {TOKENS["radius_lg"]}px;
        }}

        QFrame[role="kpiCard"][tone="success"],
        QFrame[role="panel"] QFrame[role="kpiCard"][tone="success"] {{
            background: {TOKENS["status_success_bg"]};
            border: 1px solid {TOKENS["status_success_border"]};
            border-radius: {TOKENS["radius_lg"]}px;
        }}

        QFrame[role="kpiCard"][tone="pending"],
        QFrame[role="panel"] QFrame[role="kpiCard"][tone="pending"] {{
            background: {TOKENS["status_pending_bg"]};
            border: 1px solid {TOKENS["status_pending_border"]};
            border-radius: {TOKENS["radius_lg"]}px;
        }}

        QFrame[role="kpiCard"] {{
            min-height: 40px;
            min-width: 100px;
        }}

        QFrame#ContentHost {{
            border: none;
            border-radius: 0;
            background: transparent;
        }}

        QLabel[role="pageTitle"] {{
            background: transparent;
            font-size: {TYPOGRAPHY["page_title"]}px;
            font-weight: 700;
            color: {TOKENS["text_primary"]};
            padding: 0 2px;
        }}

        QLabel[role="sectionTitle"] {{
            background: transparent;
            font-size: {TYPOGRAPHY["section_title"]}px;
            font-weight: 700;
            color: {TOKENS["text_primary"]};
        }}

        QLabel[role="helperText"],
        QLabel[role="kpiTitle"] {{
            background: transparent;
            color: {TOKENS["text_secondary"]};
            font-size: {TYPOGRAPHY["helper_text"]}px;
            font-weight: 700;
        }}

        QLabel[role="sourceTag"],
        QLabel[role="selectionStatus"] {{
            background: {TOKENS["surface_active"]};
            border: 1px solid {TOKENS["border_soft"]};
            border-radius: {TOKENS["radius_sm"]}px;
            color: {TOKENS["text_secondary"]};
            font-size: {TYPOGRAPHY["caption"]}px;
            font-weight: 700;
            padding: 3px 8px;
        }}

        QLabel[role="kpiValue"] {{
            background: transparent;
            font-size: {TYPOGRAPHY["kpi_value"]}px;
            font-weight: 700;
        }}

        QFrame[role="kpiCard"][tone="danger"] QLabel[role="kpiValue"] {{
            color: {TOKENS["status_danger_fg"]};
        }}

        QFrame[role="kpiCard"][tone="info"] QLabel[role="kpiValue"] {{
            color: {TOKENS["status_info_fg"]};
        }}

        QFrame[role="kpiCard"][tone="success"] QLabel[role="kpiValue"] {{
            color: {TOKENS["status_success_fg"]};
        }}

        QFrame[role="kpiCard"][tone="pending"] QLabel[role="kpiValue"] {{
            color: {TOKENS["status_pending_fg"]};
        }}

        QLabel[role="statsInfoText"] {{
            background: transparent;
            border: none;
            color: {TOKENS["text_muted"]};
            font-size: {TYPOGRAPHY["caption"]}px;
        }}

        QLabel[role="insight"] {{
            font-size: {TYPOGRAPHY["body_small"]}px;
        }}

        QLabel[role="errorText"] {{
            background: transparent;
            color: {TOKENS["danger"]};
            font-weight: 700;
        }}

        QLabel[role="messageText"] {{
            background: {TOKENS["surface_accent"]};
            border: 1px solid {TOKENS["info_border"]};
            border-radius: {TOKENS["radius_sm"]}px;
            color: {TOKENS["info"]};
            font-size: {TYPOGRAPHY["helper_text"]}px;
            font-weight: 400;
            padding: 4px 8px;
        }}

        QLabel[role="messageText"][tone="warning"] {{
            background: {TOKENS["warning_bg"]};
            border: 1px solid {TOKENS["warning_border"]};
            color: {TOKENS["warning"]};
        }}

        QLabel[role="messageText"][tone="danger"] {{
            background: {TOKENS["surface_danger"]};
            border: 1px solid {TOKENS["danger_border"]};
            color: {TOKENS["danger"]};
        }}

        QLabel[role="counterText"] {{
            background: transparent;
            color: {TOKENS["text_muted"]};
            font-size: {TYPOGRAPHY["caption"]}px;
            font-weight: 400;
        }}

        QLabel[role="counterText"][tone="danger"] {{
            color: {TOKENS["danger"]};
            font-weight: 700;
        }}

        QLabel[role="dividerTitle"] {{
            background: {TOKENS["panel_alt_bg"]};
            border: 1px solid {TOKENS["border_soft"]};
            border-radius: {TOKENS["radius_sm"]}px;
            padding: 5px 10px;
            font-size: {TYPOGRAPHY["divider_title"]}px;
            font-weight: 700;
            color: {TOKENS["text_primary"]};
        }}

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

        QWidget#StatsView {{
            background: {TOKENS["page_bg"]};
        }}

        QTabWidget#StatsTabs {{
            background: {TOKENS["panel_bg"]};
        }}

        QTabWidget#StatsTabs::tab-bar {{
            background: {TOKENS["panel_bg"]};
        }}

        QTabWidget#StatsTabs::pane {{
            border: 1px solid {TOKENS["border_soft"]};
            border-radius: {TOKENS["radius_sm"]}px;
            top: -1px;
            background: {TOKENS["panel_bg"]};
        }}

        QTabWidget#StatsTabs QTabBar {{
            background: {TOKENS["panel_bg"]};
        }}

        QTabWidget#StatsTabs QTabBar::tab {{
            min-width: 132px;
            min-height: {TAB_BAR_TAB_MIN_HEIGHT}px;
            background: {TOKENS["page_bg"]};
            color: {TOKENS["text_secondary"]};
            border: 1px solid {TOKENS["border_soft"]};
            border-top-left-radius: {TOKENS["radius_sm"]}px;
            border-top-right-radius: {TOKENS["radius_sm"]}px;
            padding: {TAB_BAR_TAB_PADDING_VERTICAL}px 14px;
            margin-right: 3px;
            font-weight: 400;
        }}

        QTabWidget#StatsTabs QTabBar::tab:selected {{
            background: {TOKENS["panel_bg"]};
            color: {TOKENS["primary_btn"]};
            border-color: {TOKENS["border"]};
            border-bottom: 1px solid {TOKENS["panel_bg"]};
            font-weight: 700;
        }}

        QTabWidget#StatsTabs QTabBar::tab:hover:!selected {{
            background: {TOKENS["surface_hover"]};
            color: {TOKENS["text_primary"]};
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

        QPushButton[role="navTab"] {{
            background: transparent;
            border: none;
            border-bottom: 2px solid transparent;
            border-radius: 0;
            padding: 1px 18px 0 18px;
            min-height: {NAV_TAB_MIN_HEIGHT}px;
            font-size: {TYPOGRAPHY["nav_tab"]}px;
            font-weight: 400;
            color: {TOKENS["text_secondary"]};
            text-align: center;
        }}

        QPushButton[role="navTab"]:hover {{
            background: {TOKENS["subtle_bg"]};
            color: {TOKENS["text_primary"]};
        }}

        QPushButton[role="navTab"]:checked {{
            background: transparent;
            border-bottom: 2px solid {TOKENS["primary_btn"]};
            color: {TOKENS["text_primary"]};
            font-weight: 700;
        }}

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
            border-left: 6px solid {TOKENS["brand_steel"]};
            color: {TOKENS["text_secondary"]};
        }}

        QPushButton[role="quickActionButton"][tone="report"]:hover {{
            background: {TOKENS["surface_hover"]};
            border-color: {TOKENS["brand_steel"]};
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

        QDialog,
        QMessageBox {{
            background: {TOKENS["page_bg"]};
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

        /* ── 左側導覽側欄 ─────────────────────────────── */
        QFrame#SidebarNav {{
            background: {TOKENS["sidebar_bg"]};
            border: none;
        }}

        QWidget#SidebarLogoSection {{
            background: {TOKENS["sidebar_panel"]};
            border-bottom: 1px solid {TOKENS["sidebar_divider"]};
        }}

        QLabel#SidebarAppTitle {{
            color: {TOKENS["nav_dark_text_active"]};
            font-size: 16px;
            font-weight: 700;
            background: transparent;
        }}

        QLabel#SidebarAppSubtitle {{
            color: {TOKENS["nav_dark_text"]};
            font-size: 11px;
            background: transparent;
        }}

        QPushButton#NavButton {{
            text-align: left;
            padding: 0px 16px;
            min-height: {SIDEBAR_NAV_ITEM_HEIGHT}px;
            border: none;
            border-left: 4px solid transparent;
            border-radius: 0px;
            background: transparent;
            color: {TOKENS["sidebar_text"]};
            font-size: 13px;
            font-weight: 400;
        }}

        /* D1 fix: child QLabels inside NavButton must inherit sidebar text colour */
        QPushButton#NavButton QLabel {{
            color: {TOKENS["sidebar_text"]};
            background: transparent;
            font-size: 13px;
            font-weight: 400;
        }}

        QPushButton#NavButton:hover {{
            background: {TOKENS["sidebar_hover_bg"]};
            color: {TOKENS["sidebar_text_active"]};
        }}

        QPushButton#NavButton:hover QLabel {{
            color: {TOKENS["sidebar_text_active"]};
        }}

        /* D2 fix: stronger active state — wider indicator + higher contrast bg */
        QPushButton#NavButton[nav_active="true"] {{
            background: {TOKENS["sidebar_active_bg"]};
            color: {TOKENS["sidebar_text_active"]};
            border-left: 4px solid {TOKENS["sidebar_active_indicator"]};
            font-weight: 700;
        }}

        QPushButton#NavButton[nav_active="true"] QLabel {{
            color: {TOKENS["sidebar_text_active"]};
            font-weight: 700;
        }}

        QLabel#NavIcon {{
            background: transparent;
            border: none;
        }}

        QLabel#NavBadge {{
            background: {TOKENS["status_danger_chart"]};
            color: #FFFFFF;
            font-size: 10px;
            font-weight: 700;
            border-radius: 8px;
            padding: 1px 5px;
            min-width: 16px;
        }}

        /* 側欄領域分組標題（非按鈕，靜態語意標籤） */
        QLabel#SidebarGroupHeader {{
            color: {TOKENS["sidebar_muted"]};
            background: transparent;
            font-size: 10px;
            font-weight: 700;
            padding: 2px 16px 2px 16px;
        }}

        /* ── 頁面頂部標題列 ─────────────────────────────── */
        QFrame#PageHeaderBar {{
            background: {TOKENS["page_header_bg"]};
            border: none;
            border-bottom: 1px solid {TOKENS["page_header_shadow"]};
            min-height: {PAGE_HEADER_HEIGHT}px;
            max-height: {PAGE_HEADER_HEIGHT}px;
        }}

        QLabel#PageHeaderTitle {{
            color: {TOKENS["text_primary"]};
            font-size: 18px;
            font-weight: 700;
            background: transparent;
        }}

        QLabel#PageHeaderBreadcrumb {{
            color: {TOKENS["text_muted"]};
            font-size: 11px;
            background: transparent;
        }}

        /* ── 逾期警示橫幅 ─────────────────────────────── */
        QFrame#OverdueBanner {{
            background: {TOKENS["overdue_banner_bg"]};
            border: 1px solid {TOKENS["overdue_banner_border"]};
            border-radius: {TOKENS["radius_sm"]}px;
        }}

        QLabel#OverdueBannerIcon {{
            color: {TOKENS["overdue_banner_text"]};
            font-size: 16px;
            font-weight: 700;
            background: transparent;
            min-width: 24px;
            min-height: 24px;
            border: none;
            border-bottom: 2px solid {TOKENS["overdue_banner_border"]};
            min-height: 48px;
            max-height: 48px;
        }}

        QLabel#OverdueBannerText {{
            color: {TOKENS["overdue_banner_text"]};
            font-size: 13px;
            font-weight: 700;
            background: transparent;
        }}

        QPushButton#OverdueBannerLink {{
            color: {TOKENS["overdue_banner_link"]};
            font-size: 12px;
            font-weight: 700;
            background: transparent;
            border: none;
            text-decoration: underline;
            padding: 0px 4px;
        }}

        QPushButton#OverdueBannerLink:hover {{
            color: {TOKENS["brand_cyan"]};
        }}

        /* ── Mitcorp 雙色品牌矩形裝飾 ───────────────────── */
        QLabel#BrandDot1 {{
            background: {TOKENS["brand_primary"]};
            border-radius: 2px;
        }}

        QLabel#BrandDot2 {{
            background: {TOKENS["brand_green"]};
            border-radius: 2px;
        }}
        """
    ).strip()
