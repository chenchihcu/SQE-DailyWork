"""Generated density overrides layered after the shared theme sections."""

from __future__ import annotations

from textwrap import dedent

from ui.appearance_preferences import AppearancePreferences
from ui.theme_tokens import TOKENS


_CONTENT_DENSITY_METRICS = {
    "compact": {"control_height": 30, "table_item_height": 26, "table_padding": 4, "header_padding": 5, "nav_height": 34},
    "standard": {"control_height": 34, "table_item_height": 30, "table_padding": 6, "header_padding": 7, "nav_height": 38},
    "comfortable": {"control_height": 40, "table_item_height": 36, "table_padding": 9, "header_padding": 10, "nav_height": 44},
}

_TABLE_DENSITY_METRICS = {
    "compact": {"table_item_height": 26, "table_padding": 4, "header_padding": 5, "header_height": 30},
    "standard": {"table_item_height": 30, "table_padding": 6, "header_padding": 7, "header_height": 32},
    "comfortable": {"table_item_height": 36, "table_padding": 9, "header_padding": 10, "header_height": 40},
}

_SIDEBAR_DENSITY_METRICS = {"compact": 34, "standard": 38}


def get_appearance_metrics(preferences: AppearancePreferences) -> dict[str, int]:
    """Return the one runtime metrics map shared by QSS, sidebar and tables."""
    content = _CONTENT_DENSITY_METRICS[preferences.density]
    table = _TABLE_DENSITY_METRICS[preferences.table_density]
    return {
        "control_height": content["control_height"],
        "table_item_height": table["table_item_height"],
        "table_padding": table["table_padding"],
        "header_padding": table["header_padding"],
        "header_height": table["header_height"],
        "sidebar_height": _SIDEBAR_DENSITY_METRICS[preferences.sidebar_density],
    }


def get_appearance_qss(preferences: AppearancePreferences) -> str:
    """Return global density, grid, alternating color, and contrast overrides."""
    metrics = get_appearance_metrics(preferences)
    grid_color = str(TOKENS.get("grid", "#E5E7EB")) if preferences.table_grid_lines else "transparent"
    alt_bg = str(TOKENS.get("panel_alt_bg", "#F8FAFC")) if preferences.alternating_row_colors else "transparent"

    contrast_qss = ""
    if preferences.contrast_mode == "high":
        grid_color_hc = "#1F2937" if preferences.table_grid_lines else "transparent"
        contrast_qss = f"""
        QWidget {{ color: #000000; }}
        QMainWindow, QWidget#AppRoot, QFrame#ContentHost, QScrollArea {{ background: #FFFFFF; }}
        QLineEdit, QTextEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {{
            background: #FFFFFF; color: #000000; border: 2px solid #1F2937;
        }}
        QPushButton {{ background: #FFFFFF; color: #000000; border: 2px solid #1F2937; }}
        QPushButton[variant=\"primary\"] {{ background: {TOKENS.get("primary_btn", "#0037B3")}; color: #FFFFFF; border-color: {TOKENS.get("primary_btn", "#0037B3")}; }}
        QPushButton:focus, QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{ border: 2px solid #005FCC; }}
        QTableWidget {{ background: #FFFFFF; color: #000000; border: 2px solid #1F2937; gridline-color: {grid_color_hc}; }}
        QTableWidget::item:selected {{ background: #D9E7FF; color: #000000; }}
        QHeaderView::section {{ background: #F3F4F6; color: #000000; border-color: #1F2937; }}
        QFrame#SidebarNav {{ background: #000000; border-right: 2px solid #FFFFFF; }}
        QWidget#SidebarLogoSection, QPushButton#NavButton:hover {{ background: #1F2937; }}
        QPushButton#NavButton[nav_active=\"true\"] {{ background: {TOKENS.get("primary_btn", "#0037B3")}; border-left-color: #FFFFFF; }}
        QPushButton#NavButton QLabel, QLabel#SidebarGroupHeader {{ color: #FFFFFF; }}
        QLabel#SidebarGroupHeader {{ background: #000000; border: 1px solid #FFFFFF; }}
        QMenu, QComboBox QAbstractItemView, QCalendarWidget QWidget {{ background: #FFFFFF; color: #000000; border-color: #1F2937; }}
        """

    return dedent(
        f"""\
        QLineEdit,
        QComboBox,
        QDateEdit,
        QSpinBox,
        QDoubleSpinBox,
        QPushButton,
        QPushButton[variant="primary"],
        QPushButton[variant="secondary"],
        QPushButton[variant="toolbarPrimary"],
        QPushButton[variant="toolbarSecondary"],
        QPushButton[variant="toolbarGhost"] {{
            min-height: {metrics["control_height"]}px;
        }}

        QTableWidget {{
            gridline-color: {grid_color};
        }}

        QTableWidget::item {{
            min-height: {metrics["table_item_height"]}px;
            padding: {metrics["table_padding"]}px;
        }}

        QTableWidget::item:alternate {{
            background-color: {alt_bg};
        }}

        QHeaderView::section {{
            padding: {metrics["header_padding"]}px;
        }}

        QPushButton#NavButton {{
            min-height: {metrics["sidebar_height"]}px;
        }}

        QPushButton:focus {{
            border: 1px solid {TOKENS["focus_ring"]};
        }}
        {contrast_qss}
        """
    ).strip()

