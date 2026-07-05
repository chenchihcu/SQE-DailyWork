from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QAction, QColor, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QMenu,
    QMessageBox,
)
from PySide6.QtWidgets import QStyledItemDelegate

# Single source of truth for the CJK font fallback chain lives in ui.theme; the NCR
# module reuses it instead of maintaining a second, divergent list.
from ui.theme import (
    CJK_FONT_FAMILY_CSS,
    PREFERRED_CJK_FONT_FAMILIES as PREFERRED_CJK_FONT_FAMILIES,
)
from ui.status_colors import get_status_tone
from ui.layout_constants import HERO_BANNER_MARGINS, INLINE_SPACING


PAGE_MARGIN = 8
SECTION_SPACING = 22
FIELD_SPACING_X = 20
FIELD_SPACING_Y = 16
FORM_TWO_COLUMN_SPACING = 24
DEFECT_FORM_CONTENT_MARGINS = (16, 12, 16, 12)
# Edit-dialog main-card inner padding; slightly roomier than the embedded
# form card (audit finding D15: was hardcoded inline in DefectEditDialog).
EDIT_DIALOG_CARD_MARGINS = (18, 16, 18, 16)
LABEL_MIN_WIDTH = 92
LABEL_TEXT_HORIZONTAL_PADDING = 18
LABEL_WIDTH = LABEL_MIN_WIDTH
DEFAULT_INPUT_MIN_WIDTH = 250
INPUT_HEIGHT = 30
BUTTON_HEIGHT = 30
ACTION_BUTTON_MIN_WIDTH = 96
DIALOG_ACTION_BUTTON_MIN_WIDTH = 112
# Filter-toolbar buttons (重置/查詢) are narrower than action buttons and get a
# max width so the filter row stays compact (audit finding D14: was hardcoded
# per-widget in defect_list.py).
FILTER_BUTTON_MIN_WIDTH = 90
FILTER_BUTTON_MAX_WIDTH = 110
# Min width so "yyyy-MM-dd" + the calendar drop-down stay intact at 150% DPI
# (geometry-audited via qt_visual_probe --scale 1.5; do not lower without re-checking).
DATE_FIELD_MIN_WIDTH = 150
QUICK_ADD_BUTTON_MIN_WIDTH = 76
TABLE_ROW_HEIGHT = 28
DASHBOARD_CHART_CARD_MIN_HEIGHT = 400
EMPTY_PLACEHOLDER = "—"
ITEMS_PER_PAGE = 12
WINDOW_SCREEN_WIDTH_RATIO = 0.94
WINDOW_SCREEN_HEIGHT_RATIO = 0.92
# PREFERRED_CJK_FONT_FAMILIES and CJK_FONT_FAMILY_CSS are imported from ui.theme
# (single source of truth). Re-exported here for existing call sites and probes.


def configure_qt_font_environment() -> None:
    if os.name != "nt" or os.environ.get("QT_QPA_FONTDIR"):
        return
    windows_dir = Path(os.environ.get("WINDIR", str(Path.home().drive) + r"\Windows"))
    font_dir = windows_dir / "Fonts"
    if font_dir.exists():
        os.environ["QT_QPA_FONTDIR"] = str(font_dir)


configure_qt_font_environment()

# Semantic typography tokens
BASE_TEXT_PX = 13
SECONDARY_TEXT_PX = 13
PAGE_TITLE_TEXT_PX = 24
SECTION_TITLE_TEXT_PX = 16
SUMMARY_VALUE_TEXT_PX = 26
MONOSPACE_TEXT_PX = 11

# Semantic color tokens — re-sourced from the unified design_tokens.PALETTE so
# the NCR module shares one light palette with the SQE DailyWork shell. Constant NAMES
# are unchanged, so app_stylesheet() and the badge/chart dicts below rebuild
# automatically. See src/ui/design_tokens.py.
from ui.design_tokens import PALETTE as _P

COLOR_SURFACE_APP = _P["app_bg"]
COLOR_SURFACE_BASE = _P["surface"]
COLOR_SURFACE_SUBTLE = _P["surface_sunken"]
COLOR_SURFACE_MUTED = _P["surface_alt"]
COLOR_SURFACE_DISABLED = _P["surface_disabled"]
COLOR_TEXT_PRIMARY = _P["text_primary"]
COLOR_TEXT_SECONDARY = _P["text_secondary"]
COLOR_TEXT_MUTED = _P["text_muted"]
COLOR_TEXT_DISABLED = _P["text_disabled"]
COLOR_TEXT_INVERSE = _P["text_inverse"]
COLOR_BORDER_DEFAULT = _P["border"]
COLOR_BORDER_SOFT = _P["border_soft"]
COLOR_ACCENT = _P["primary"]
COLOR_ACCENT_HOVER = _P["primary_hover"]
COLOR_INFO_TEXT = _P["info_fg"]
COLOR_INFO_BG = _P["info_bg"]
COLOR_INFO_BORDER = _P["info_border"]
COLOR_WARNING_TEXT = _P["pending_fg"]
COLOR_WARNING_BG = _P["pending_bg"]
COLOR_WARNING_BORDER = _P["pending_border"]
COLOR_DANGER_TEXT = _P["danger_fg"]
COLOR_DANGER_BORDER = _P["danger_border"]
COLOR_DANGER_BG_HOVER = _P["danger_bg"]
COLOR_SUCCESS_TEXT = _P["success_fg"]
COLOR_SUCCESS_BG = _P["success_bg"]
COLOR_SUCCESS_BORDER = _P["success_border"]
COLOR_SELECTION_BG = _P["selection_bg"]
COLOR_TABLE_ALT_BG = _P["surface_alt"]
COLOR_GRID = _P["grid"]
COLOR_TAB_BG = _P["surface_sunken"]
COLOR_ACCENT_OVERLAY = _P["accent_overlay"]
COLOR_ACCENT_OVERLAY_HOVER = _P["accent_overlay_hover"]
COLOR_ACCENT_FAINT = _P["primary_faint"]
COLOR_HERO_START = _P["hero_start"]
COLOR_HERO_END = _P["hero_end"]
COLOR_SIDEBAR_BG = _P["sidebar_bg"]
COLOR_SIDEBAR_PANEL = _P["sidebar_panel"]
COLOR_SIDEBAR_TEXT = _P["sidebar_text"]
COLOR_SIDEBAR_MUTED = _P["sidebar_muted"]

# Status-bar feedback timeouts (ms). 0 = persist until replaced.
STATUS_TIMEOUT_NORMAL = 3000
STATUS_TIMEOUT_SUCCESS = 5000
STATUS_TIMEOUT_ERROR = 7000
STATUS_TIMEOUT_PERSIST = 0

# Compact form layout (defect_form's denser variant — kept here for reuse / consistency).
FORM_COMPACT_LABEL_WIDTH = 96
FORM_COMPACT_FIELD_MIN_WIDTH = 120
FORM_FIELD_MAX_WIDTH = 400
DATE_ICON_PATH = Path(__file__).resolve().parent / "assets" / "calendar.svg"

ICON_PIXMAP_NAMES: dict[str, str] = {
    "save": "SP_DialogSaveButton",
    "clear": "SP_DialogResetButton",
    "reset": "SP_BrowserReload",
    "search": "SP_FileDialogStart",
    "export": "SP_DialogOpenButton",
    "delete": "SP_TrashIcon",
    "cancel": "SP_DialogCancelButton",
    "edit_save": "SP_DialogApplyButton",
    "section_description": "SP_MessageBoxInformation",
    "sync": "SP_ArrowDown",
    "import": "SP_DialogOpenButton",
}


def stylesheet_url(path: Path) -> str:
    return path.resolve().as_posix()


def available_screen_geometry_for(widget: QWidget | None = None) -> QRect | None:
    screen = None
    if widget is not None:
        handle = widget.windowHandle()
        if handle is not None:
            screen = handle.screen()

    if screen is None:
        app = QApplication.instance()
        if isinstance(app, QApplication):
            active_window = app.activeWindow()
            if active_window is not None:
                handle = active_window.windowHandle()
                if handle is not None:
                    screen = handle.screen()

    if screen is None:
        screen = QGuiApplication.primaryScreen()

    if screen is None:
        return None
    return screen.availableGeometry()


def fit_window_to_available_screen(
    widget: QWidget,
    default_width: int,
    default_height: int,
    *,
    width_ratio: float = WINDOW_SCREEN_WIDTH_RATIO,
    height_ratio: float = WINDOW_SCREEN_HEIGHT_RATIO,
    center: bool = True,
    enable_size_grip: bool = False,
) -> None:
    if enable_size_grip:
        set_size_grip_enabled = getattr(widget, "setSizeGripEnabled", None)
        if callable(set_size_grip_enabled):
            set_size_grip_enabled(True)

    geometry = available_screen_geometry_for(widget)
    if geometry is None:
        widget.resize(default_width, default_height)
        return

    max_width = max(1, int(geometry.width() * width_ratio))
    max_height = max(1, int(geometry.height() * height_ratio))
    target_width = min(default_width, max_width)
    target_height = min(default_height, max_height)
    widget.resize(target_width, target_height)

    if center:
        x = geometry.x() + max(0, (geometry.width() - target_width) // 2)
        y = geometry.y() + max(0, (geometry.height() - target_height) // 2)
        widget.move(x, y)


def app_stylesheet() -> str:
    date_icon_url = stylesheet_url(DATE_ICON_PATH)
    return f"""
    QWidget {{
        background: {COLOR_SURFACE_APP};
        color: {COLOR_TEXT_PRIMARY};
        font-family: {CJK_FONT_FAMILY_CSS};
        font-size: {BASE_TEXT_PX}px;
    }}
    QMainWindow {{
        background: {COLOR_SURFACE_APP};
    }}
    QDialog {{
        background: {COLOR_SURFACE_APP};
        color: {COLOR_TEXT_PRIMARY};
    }}
    QStatusBar {{
        background: {COLOR_SIDEBAR_BG};
        color: {COLOR_TEXT_SECONDARY};
        border-top: 1px solid {COLOR_BORDER_SOFT};
    }}
    QFrame#appSidebar {{
        background: {COLOR_SIDEBAR_BG};
        border-right: 1px solid {COLOR_BORDER_SOFT};
    }}
    QLabel[uiRole="sidebarBrandTitle"] {{
        color: {COLOR_TEXT_PRIMARY};
        font-size: 21px;
        font-weight: 700;
        letter-spacing: 1px;
        background: transparent;
    }}
    QLabel[uiRole="sidebarBrandSubtitle"] {{
        color: {COLOR_INFO_TEXT};
        font-size: 11px;
        font-weight: 700;
        background: transparent;
    }}
    QLabel[uiRole="sidebarGroupLabel"] {{
        color: {COLOR_SIDEBAR_MUTED};
        font-size: 11px;
        font-weight: 700;
        padding: 14px 4px 4px 6px;
        background: transparent;
    }}
    QLabel[uiRole="sidebarFooter"] {{
        color: {COLOR_SIDEBAR_MUTED};
        background: {COLOR_SIDEBAR_PANEL};
        border: 1px solid {COLOR_BORDER_SOFT};
        border-radius: 12px;
        padding: 10px 12px;
        font-size: 11px;
    }}
    QFrame[uiRole="sidebarDivider"] {{
        background: {COLOR_BORDER_SOFT};
        border: none;
        min-height: 1px;
        max-height: 1px;
        margin: 10px 0px 8px 0px;
    }}
    QPushButton[navRole="sidebarItem"] {{
        min-height: 38px;
        text-align: left;
        padding: 0 12px 0 14px;
        border-radius: 12px;
        border: 1px solid transparent;
        border-left: 3px solid transparent;
        background: transparent;
        color: {COLOR_SIDEBAR_TEXT};
        font-weight: 700;
    }}
    QPushButton[navRole="sidebarItem"]:hover {{
        background: {COLOR_ACCENT_OVERLAY};
        border-color: {COLOR_BORDER_SOFT};
        border-left: 3px solid {COLOR_ACCENT_HOVER};
    }}
    QPushButton[navRole="sidebarItem"]:checked {{
        background: {COLOR_ACCENT_OVERLAY};
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_INFO_BORDER};
        border-left: 3px solid {COLOR_ACCENT};
    }}
    QStackedWidget#workflowStack {{
        background: {COLOR_SURFACE_APP};
    }}
    QTabWidget::pane {{
        border: 1px solid {COLOR_BORDER_DEFAULT};
        background: {COLOR_SURFACE_BASE};
        top: -1px;
        border-radius: 12px;
    }}
    QTabBar::tab {{
        background: {COLOR_TAB_BG};
        color: {COLOR_TEXT_SECONDARY};
        border: 1px solid {COLOR_BORDER_DEFAULT};
        padding: 8px 16px;
        min-width: 0;
        font-weight: 700;
        margin-right: 2px;
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
    }}
    QTabBar::tab:hover {{
        background: {COLOR_SURFACE_SUBTLE};
        color: {COLOR_TEXT_PRIMARY};
        border-bottom-color: {COLOR_BORDER_DEFAULT};
    }}
    QTabBar::tab:selected {{
        background: {COLOR_SURFACE_BASE};
        color: {COLOR_ACCENT};
        border-bottom-color: {COLOR_SURFACE_BASE};
        border-top: 2px solid {COLOR_ACCENT};
        font-weight: 700;
    }}
    QLabel[uiRole="pageTitle"] {{
        font-size: {PAGE_TITLE_TEXT_PX}px;
        font-weight: 700;
        color: {COLOR_TEXT_PRIMARY};
    }}
    QLabel[uiRole="pageSubtitle"] {{
        color: {COLOR_TEXT_MUTED};
        font-size: {SECONDARY_TEXT_PX}px;
    }}
    QLabel[uiRole="sectionTitle"] {{
        font-size: {SECTION_TITLE_TEXT_PX}px;
        font-weight: 700;
        color: {COLOR_TEXT_PRIMARY};
        background: transparent;
    }}
    QLabel[uiRole="sectionSubtitle"] {{
        color: {COLOR_TEXT_MUTED};
        font-size: {SECONDARY_TEXT_PX}px;
        background: transparent;
    }}
    QLabel[uiRole="fieldLabel"] {{
        font-weight: 700;
        color: {COLOR_TEXT_SECONDARY};
        background: transparent;
        font-size: {BASE_TEXT_PX}px;
        padding-right: 12px;
    }}
    QLabel[uiRole="metaLabel"] {{
        font-weight: 700;
        color: {COLOR_TEXT_SECONDARY};
        background: transparent;
    }}
    QLabel[uiRole="metaValue"] {{
        font-weight: 400;
        color: {COLOR_TEXT_PRIMARY};
        background: transparent;
    }}
    QLabel[uiRole="hint"] {{
        color: {COLOR_TEXT_MUTED};
        font-size: {SECONDARY_TEXT_PX}px;
        background: transparent;
    }}
    QLabel[uiRole="notice"] {{
        color: {COLOR_INFO_TEXT};
        background: {COLOR_INFO_BG};
        border: 1px solid {COLOR_INFO_BORDER};
        border-radius: 12px;
        padding: 10px 14px;
    }}
    QLabel[uiRole="paginationStatus"] {{
        color: {COLOR_TEXT_PRIMARY};
        font-weight: 700;
        font-size: {BASE_TEXT_PX}px;
    }}
    QLabel[uiRole="compactNotice"] {{
        color: {COLOR_INFO_TEXT};
        background: {COLOR_INFO_BG};
        border: 1px solid {COLOR_INFO_BORDER};
        border-radius: 8px;
        padding: 6px 12px;
        font-size: {SECONDARY_TEXT_PX}px;
    }}
    QLabel[uiRole="warningHint"] {{
        color: {COLOR_WARNING_TEXT};
        background: {COLOR_WARNING_BG};
        border: 1px solid {COLOR_WARNING_BORDER};
        border-radius: 10px;
        padding: 10px 14px;
        font-size: {SECONDARY_TEXT_PX}px;
    }}
    QLabel[uiRole="successHint"] {{
        color: {COLOR_SUCCESS_TEXT};
        background: {COLOR_SUCCESS_BG};
        border: 1px solid {COLOR_SUCCESS_BORDER};
        border-radius: 10px;
        padding: 10px 14px;
        font-size: {SECONDARY_TEXT_PX}px;
    }}
    QLabel[role="statusBadge"] {{
        background: {COLOR_SURFACE_MUTED};
        color: {COLOR_TEXT_SECONDARY};
        border: 1px solid {COLOR_BORDER_SOFT};
        border-radius: 9px;
        padding: 1px 6px;
        font-weight: 700;
        font-size: {MONOSPACE_TEXT_PX}px;
    }}
    QLabel[role="statusBadge"][tone="pending"] {{
        background: {COLOR_WARNING_BG};
        color: {COLOR_WARNING_TEXT};
        border: 1px solid {COLOR_WARNING_BORDER};
    }}
    QLabel[role="statusBadge"][tone="success"] {{
        background: {COLOR_SUCCESS_BG};
        color: {COLOR_SUCCESS_TEXT};
        border: 1px solid {COLOR_SUCCESS_BORDER};
    }}
    QLabel[role="statusBadge"][tone="danger"] {{
        background: {COLOR_DANGER_BG_HOVER};
        color: {COLOR_DANGER_TEXT};
        border: 1px solid {COLOR_DANGER_BORDER};
    }}
    QLabel[role="statusBadge"][tone="info"] {{
        background: {COLOR_INFO_BG};
        color: {COLOR_INFO_TEXT};
        border: 1px solid {COLOR_INFO_BORDER};
    }}
    QLabel[role="statusBadge"][tone="na"] {{
        background: {COLOR_SURFACE_MUTED};
        color: {COLOR_TEXT_MUTED};
        border: 1px solid {COLOR_BORDER_SOFT};
    }}
    QLabel[uiRole="emptyStateTitle"] {{
        color: {COLOR_TEXT_SECONDARY};
        font-size: {SECTION_TITLE_TEXT_PX}px;
        font-weight: 700;
        background: transparent;
    }}
    QLabel[uiRole="emptyStateDesc"] {{
        color: {COLOR_TEXT_MUTED};
        font-size: {SECONDARY_TEXT_PX}px;
        background: transparent;
    }}
    QLabel[uiRole="summaryValue"] {{
        font-size: {SUMMARY_VALUE_TEXT_PX}px;
        font-weight: 700;
        color: {COLOR_TEXT_PRIMARY};
        background: transparent;
    }}
    QLabel[uiRole="summaryLabel"] {{
        color: {COLOR_TEXT_MUTED};
        font-size: {SECONDARY_TEXT_PX}px;
        background: transparent;
    }}
    QLabel[uiRole="summaryIcon"] {{
        background: transparent;
    }}
    QFrame[uiRole="pageCard"],
    QFrame[uiRole="sectionCard"] {{
        background: {COLOR_SURFACE_BASE};
        border: 1px solid {COLOR_BORDER_DEFAULT};
        border-radius: 16px;
    }}
    QFrame[uiRole="summaryCard"] {{
        background: {COLOR_SURFACE_BASE};
        border: 1px solid {COLOR_BORDER_DEFAULT};
        border-left: 4px solid {COLOR_ACCENT};
        border-radius: 12px;
    }}
    QFrame[uiRole="summaryCard"]:hover {{
        background: {COLOR_ACCENT_FAINT};
        border-color: {COLOR_INFO_BORDER};
    }}
    QFrame[uiRole="summaryCard"][accentRole="info"] {{
        border-left: 4px solid {COLOR_INFO_TEXT};
    }}
    QFrame[uiRole="summaryCard"][accentRole="success"] {{
        border-left: 4px solid {COLOR_SUCCESS_TEXT};
    }}
    QFrame[uiRole="summaryCard"][accentRole="warning"] {{
        border-left: 4px solid {COLOR_WARNING_TEXT};
    }}
    QFrame[uiRole="summaryCard"][accentRole="danger"] {{
        border-left: 4px solid {COLOR_DANGER_TEXT};
    }}
    QFrame[uiRole="divider"] {{
        background: {COLOR_BORDER_SOFT};
        border: none;
        min-height: 1px;
        max-height: 1px;
    }}
    QFrame[uiRole="pageCard"] {{
        padding: 0px;
    }}
    QFrame[uiRole="photoContainer"] {{
        background: {COLOR_SURFACE_MUTED};
        border: 1px dashed {COLOR_BORDER_DEFAULT};
        border-radius: 12px;
        min-height: 100px;
    }}
    QFrame[uiRole="defectDescPlaceholder"] {{
        background: {COLOR_SURFACE_MUTED};
        border: 1px dashed {COLOR_BORDER_DEFAULT};
        border-radius: 8px;
    }}
    QLabel[uiRole="thumbnail"] {{
        background: {COLOR_SURFACE_BASE};
        border: 1px solid {COLOR_BORDER_SOFT};
        border-radius: 6px;
    }}
    QLabel[uiRole="thumbnail"]:hover {{
        border: 1px solid {COLOR_ACCENT};
    }}
    QLabel[uiRole="photoHint"] {{
        color: {COLOR_TEXT_MUTED};
        font-size: {SECONDARY_TEXT_PX}px;
        font-style: italic;
    }}
    QLabel[uiRole="defectDescPlaceholderHint"] {{
        color: {COLOR_TEXT_DISABLED};
    }}
    QLineEdit,
    QTextEdit {{
        background: {COLOR_SURFACE_BASE};
        border: 1px solid {COLOR_BORDER_DEFAULT};
        border-radius: 10px;
        selection-background-color: {COLOR_SELECTION_BG};
    }}
    QComboBox,
    QDateEdit,
    QAbstractSpinBox {{
        background: {COLOR_SURFACE_BASE};
        border: 1px solid {COLOR_BORDER_DEFAULT};
        border-radius: 10px;
        selection-background-color: {COLOR_SELECTION_BG};
    }}
    QLineEdit:disabled,
    QComboBox:disabled,
    QDateEdit:disabled,
    QAbstractSpinBox:disabled,
    QTextEdit:disabled {{
        background: {COLOR_SURFACE_DISABLED};
        color: {COLOR_TEXT_DISABLED};
        border: 1px solid {COLOR_BORDER_SOFT};
    }}
    QComboBox:disabled QLineEdit {{
        color: {COLOR_TEXT_DISABLED};
    }}
    QLineEdit:hover,
    QComboBox:hover,
    QDateEdit:hover,
    QAbstractSpinBox:hover,
    QTextEdit:hover {{
        border: 1px solid {COLOR_ACCENT};
        background: {COLOR_SURFACE_BASE};
    }}
    QLineEdit,
    QTextEdit {{
        padding: 6px 14px;
    }}
    QComboBox,
    QDateEdit {{
        padding: 0 36px 0 14px;
    }}
    QAbstractSpinBox {{
        padding: 0 42px 0 14px;
    }}
    QComboBox QLineEdit {{
        border: none;
        background: transparent;
        padding: 0;
        min-height: 0px;
    }}
    QLineEdit:focus,
    QComboBox:focus,
    QDateEdit:focus,
    QAbstractSpinBox:focus,
    QTextEdit:focus {{
        border: 1px solid {COLOR_ACCENT};
        background: {COLOR_SURFACE_BASE};
    }}
    QComboBox::drop-down,
    QDateEdit::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        border: none;
        border-left: 1px solid {COLOR_BORDER_DEFAULT};
        background: {COLOR_ACCENT_OVERLAY};
        width: 34px;
        border-top-right-radius: 10px;
        border-bottom-right-radius: 10px;
    }}
    QComboBox::drop-down:hover,
    QDateEdit::drop-down:hover {{
        background: {COLOR_ACCENT_OVERLAY_HOVER};
    }}
    QDateEdit::down-arrow {{
        image: url("{date_icon_url}");
        width: 14px;
        height: 14px;
    }}
    QAbstractSpinBox::up-button,
    QAbstractSpinBox::down-button {{
        subcontrol-origin: border;
        width: 28px;
        background: {COLOR_ACCENT_OVERLAY};
        border: none;
        border-left: 1px solid {COLOR_BORDER_DEFAULT};
    }}
    QAbstractSpinBox::up-button:hover,
    QAbstractSpinBox::down-button:hover {{
        background: {COLOR_ACCENT_OVERLAY_HOVER};
    }}
    QAbstractSpinBox::up-button {{
        subcontrol-position: top right;
        border-top-right-radius: 10px;
    }}
    QAbstractSpinBox::down-button {{
        subcontrol-position: bottom right;
        border-bottom-right-radius: 10px;
    }}
    QPushButton {{
        min-height: {BUTTON_HEIGHT}px;
        padding: 0 18px;
        border-radius: 10px;
        border: 1px solid {COLOR_BORDER_DEFAULT};
        background: {COLOR_SURFACE_BASE};
        color: {COLOR_TEXT_PRIMARY};
        font-weight: 700;
    }}
    QPushButton:disabled {{
        background: {COLOR_SURFACE_DISABLED};
        color: {COLOR_TEXT_DISABLED};
        border: 1px solid {COLOR_BORDER_SOFT};
    }}
    QPushButton:hover {{
        background: {COLOR_SURFACE_SUBTLE};
        border-color: {COLOR_BORDER_DEFAULT};
    }}
    QPushButton[buttonRole="primary"] {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {COLOR_ACCENT}, stop:1 {COLOR_ACCENT_HOVER});
        color: {COLOR_TEXT_INVERSE};
        border: 1px solid {COLOR_ACCENT};
    }}
    QPushButton[buttonRole="primary"]:hover {{
        background: {COLOR_ACCENT_HOVER};
    }}
    QPushButton[buttonRole="secondary"] {{
        background: {COLOR_SURFACE_BASE};
        color: {COLOR_TEXT_SECONDARY};
        border: 1px solid {COLOR_BORDER_DEFAULT};
    }}
    QPushButton[buttonRole="utility"] {{
        background: {COLOR_ACCENT_FAINT};
        color: {COLOR_INFO_TEXT};
        border: 1px solid {COLOR_INFO_BORDER};
    }}
    QPushButton[buttonRole="utility"]:hover {{
        background: {COLOR_INFO_BG};
        border-color: {COLOR_INFO_BORDER};
    }}
    QPushButton[buttonRole="danger"] {{
        background: {COLOR_SURFACE_BASE};
        color: {COLOR_DANGER_TEXT};
        border: 1px solid {COLOR_DANGER_BORDER};
    }}
    QPushButton[buttonRole="danger"]:hover {{
        background: {COLOR_DANGER_BG_HOVER};
    }}
    QPushButton[buttonRole="reset"] {{
        background: {COLOR_SURFACE_MUTED};
        color: {COLOR_TEXT_MUTED};
        border: 1px solid {COLOR_BORDER_SOFT};
    }}
    QPushButton[buttonRole="reset"]:hover {{
        background: {COLOR_SURFACE_SUBTLE};
        border-color: {COLOR_BORDER_DEFAULT};
        color: {COLOR_TEXT_SECONDARY};
    }}
    QPushButton[buttonRole="sidebar"] {{
        background: transparent;
        color: {COLOR_SIDEBAR_TEXT};
        border: 1px solid transparent;
    }}
    QPushButton[navRole="sidebarItem"] {{
        min-height: 38px;
        text-align: left;
        padding: 0 12px 0 14px;
        border-radius: 12px;
        border: 1px solid transparent;
        border-left: 3px solid transparent;
        background: transparent;
        color: {COLOR_SIDEBAR_TEXT};
        font-weight: 700;
    }}
    QPushButton[navRole="sidebarItem"]:hover {{
        background: {COLOR_ACCENT_OVERLAY};
        border-color: {COLOR_BORDER_SOFT};
        border-left: 3px solid {COLOR_ACCENT_HOVER};
    }}
    QPushButton[navRole="sidebarItem"]:checked {{
        background: {COLOR_ACCENT_OVERLAY};
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_INFO_BORDER};
        border-left: 3px solid {COLOR_ACCENT};
    }}
    QTextBrowser {{
        background: {COLOR_SURFACE_BASE};
        color: {COLOR_TEXT_SECONDARY};
        border: 1px solid {COLOR_BORDER_DEFAULT};
        border-radius: 12px;
        font-family: {CJK_FONT_FAMILY_CSS};
        padding: 10px;
    }}
    QTableWidget {{
        background: {COLOR_SURFACE_BASE};
        alternate-background-color: {COLOR_TABLE_ALT_BG};
        gridline-color: {COLOR_GRID};
        border: 1px solid {COLOR_BORDER_DEFAULT};
        border-radius: 12px;
        selection-background-color: {COLOR_SELECTION_BG};
        selection-color: {COLOR_TEXT_PRIMARY};
    }}
    QTableCornerButton::section {{
        background: {COLOR_SURFACE_SUBTLE};
        border-top: 1px solid {COLOR_BORDER_DEFAULT};
        border-left: 1px solid {COLOR_BORDER_DEFAULT};
        border-right: 1px solid {COLOR_GRID};
        border-bottom: 1px solid {COLOR_BORDER_DEFAULT};
    }}
    QHeaderView::section {{
        background: {COLOR_SURFACE_SUBTLE};
        color: {COLOR_TEXT_SECONDARY};
        padding: 8px 10px;
        border-top: 1px solid {COLOR_BORDER_DEFAULT};
        border-right: 1px solid {COLOR_GRID};
        border-bottom: 1px solid {COLOR_BORDER_DEFAULT};
        font-weight: 700;
    }}
    QHeaderView::section:first {{
        border-left: 1px solid {COLOR_BORDER_DEFAULT};
    }}
    QPushButton:pressed {{
        background: {COLOR_SURFACE_SUBTLE};
        border-color: {COLOR_BORDER_DEFAULT};
    }}
    QPushButton[buttonRole="primary"]:pressed {{
        background: {COLOR_ACCENT_HOVER};
        border-color: {COLOR_ACCENT_HOVER};
    }}
    QPushButton[buttonRole="danger"]:pressed {{
        background: {COLOR_DANGER_BG_HOVER};
    }}
    QScrollBar:vertical {{
        background: {COLOR_SURFACE_MUTED};
        width: 8px;
        border-radius: 4px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {COLOR_BORDER_DEFAULT};
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {COLOR_TEXT_MUTED};
    }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0px;
        background: none;
    }}
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: none;
    }}
    QScrollBar:horizontal {{
        background: {COLOR_SURFACE_MUTED};
        height: 8px;
        border-radius: 4px;
        margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
        background: {COLOR_BORDER_DEFAULT};
        border-radius: 4px;
        min-width: 24px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {COLOR_TEXT_MUTED};
    }}
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {{
        width: 0px;
        background: none;
    }}
    QScrollBar::add-page:horizontal,
    QScrollBar::sub-page:horizontal {{
        background: none;
    }}
    QFrame[uiRole="heroCard"] {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {COLOR_HERO_START}, stop:1 {COLOR_HERO_END});
        border: none;
        border-top-left-radius: 14px;
        border-top-right-radius: 14px;
        border-bottom-left-radius: 0px;
        border-bottom-right-radius: 0px;
    }}
    QLabel[uiRole="heroTitle"] {{
        color: {COLOR_TEXT_INVERSE};
        font-size: {PAGE_TITLE_TEXT_PX}px;
        font-weight: 700;
        background: transparent;
    }}
    QLabel[uiRole="heroMeta"] {{
        color: {COLOR_TEXT_INVERSE};
        font-size: 12px;
        background: transparent;
    }}
    QFrame[uiRole="infoChip"] {{
        background: {COLOR_ACCENT_FAINT};
        border: 1px solid {COLOR_INFO_BORDER};
        border-radius: 8px;
    }}
    QLabel[uiRole="chipLabel"] {{
        color: {COLOR_TEXT_MUTED};
        font-size: 12px;
        font-weight: 700;
        background: transparent;
    }}
    QLabel[uiRole="chipValue"] {{
        color: {COLOR_TEXT_PRIMARY};
        font-size: 12px;
        font-weight: 700;
        background: transparent;
    }}
    """


def set_button_role(button: QPushButton, role: str) -> None:
    button.setProperty("buttonRole", role)
    button.style().unpolish(button)
    button.style().polish(button)


def _resolve_standard_pixmap(icon_key: str | None) -> QStyle.StandardPixmap:
    if not icon_key:
        return QStyle.StandardPixmap.SP_FileIcon
    if hasattr(QStyle.StandardPixmap, icon_key):
        return getattr(QStyle.StandardPixmap, icon_key)
    enum_name = ICON_PIXMAP_NAMES.get(icon_key, "SP_FileIcon")
    return getattr(QStyle.StandardPixmap, enum_name, QStyle.StandardPixmap.SP_FileIcon)


def standard_icon(icon_key: str | None) -> QIcon:
    app = QApplication.instance()
    style = app.style() if isinstance(app, QApplication) else QApplication.style()
    if style is None:
        return QIcon()
    return style.standardIcon(_resolve_standard_pixmap(icon_key))


def apply_button_icon(button: QPushButton, icon_key: str) -> None:
    icon = standard_icon(icon_key)
    if not icon.isNull():
        button.setIcon(icon)


def create_section_title_with_icon(title: str, icon_key: str, *, required: bool = False) -> QWidget:
    title_host = QWidget()
    row = QHBoxLayout(title_host)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(INLINE_SPACING)

    icon_label = QLabel()
    icon_label.setObjectName("sectionIconLabel")
    icon_label.setFixedWidth(20)
    icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon = standard_icon(icon_key)
    if not icon.isNull():
        icon_label.setPixmap(icon.pixmap(18, 18))

    title_label = QLabel(title)
    title_label.setProperty("uiRole", "sectionTitle")
    if required:
        title_label.setProperty("required", True)
        title_label.setTextFormat(Qt.TextFormat.RichText)
        title_label.setText(f'{title}&nbsp;<span style="color:{COLOR_DANGER_TEXT}">*</span>')
    row.addWidget(icon_label, 0)
    row.addWidget(title_label, 1)
    return title_host


class LeftAlignDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.displayAlignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter


def apply_input_style(widget: QWidget, *, minimum_width: int | None = None, maximum_width: int | None = None) -> None:
    if isinstance(widget, QTextEdit):
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        widget.setAlignment(Qt.AlignmentFlag.AlignLeft)
        # Honor explicit width overrides before the early return so the
        # signature's contract holds for QTextEdit too (audit finding A15).
        if minimum_width is not None:
            widget.setMinimumWidth(minimum_width)
        if maximum_width is not None:
            widget.setMaximumWidth(maximum_width)
        return
    if isinstance(widget, (QLineEdit, QComboBox, QDateEdit, QAbstractSpinBox)):
        widget.setMinimumHeight(INPUT_HEIGHT)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    
    if isinstance(widget, QLineEdit):
        widget.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    elif isinstance(widget, QComboBox):
        # Set delegate for items in list
        widget.setItemDelegate(LeftAlignDelegate(widget))
        # For non-editable combo boxes, alignment is style-dependent. 
        # Most modern styles default to left, but we can try to force it via padding.
        line_edit = widget.lineEdit()
        if line_edit is not None:
            line_edit.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    elif isinstance(widget, QDateEdit):
        widget.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    elif isinstance(widget, QAbstractSpinBox):
        line_edit = widget.lineEdit()
        if line_edit is not None:
            line_edit.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    
    if minimum_width is not None:
        widget.setMinimumWidth(minimum_width)
    else:
        # Default minimum width for common input controls
        if isinstance(widget, (QLineEdit, QComboBox, QDateEdit, QAbstractSpinBox)):
            widget.setMinimumWidth(DEFAULT_INPUT_MIN_WIDTH)
            
    if maximum_width is not None:
        widget.setMaximumWidth(maximum_width)


def apply_form_inputs(widgets: Iterable[QWidget]) -> None:
    for widget in widgets:
        apply_input_style(widget)


def create_page_shell(
    title: str = "",
    subtitle: str = "",
    *,
    body: QWidget | None = None,
    show_header: bool = True,
) -> tuple[QWidget, QVBoxLayout]:
    shell = QWidget()
    outer = QVBoxLayout(shell)
    outer.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
    outer.setSpacing(SECTION_SPACING)

    if show_header:
        header_card = QFrame()
        header_card.setProperty("uiRole", "pageCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(*HERO_BANNER_MARGINS)
        header_layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setProperty("uiRole", "pageTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setProperty("uiRole", "pageSubtitle")
        subtitle_label.setWordWrap(True)

        header_layout.addWidget(title_label)
        header_layout.addWidget(subtitle_label)
        outer.addWidget(header_card)

    content = QWidget()
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(0, 0, 0, 0)
    content_layout.setSpacing(SECTION_SPACING)
    outer.addWidget(content, 1)

    if body is not None:
        content_layout.addWidget(body)
    return shell, content_layout


def create_section_card(
    title: str | None = None, subtitle: str | None = None
) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setProperty("uiRole", "sectionCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(16)

    if title:
        title_label = QLabel(title)
        title_label.setProperty("uiRole", "sectionTitle")
        layout.addWidget(title_label)

    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setProperty("uiRole", "sectionSubtitle")
        subtitle_label.setWordWrap(True)
        layout.addWidget(subtitle_label)

    return card, layout


def create_form_grid(
    *, field_count: int = 3, horizontal_spacing: int = FIELD_SPACING_X
) -> QGridLayout:
    layout = QGridLayout()
    layout.setHorizontalSpacing(horizontal_spacing)
    layout.setVerticalSpacing(FIELD_SPACING_Y)
    for column_index in range(1, field_count * 2, 2):
        layout.setColumnStretch(column_index, 1)
    return layout


REQUIRED_ASTERISK_WIDTH = 14


def add_labeled_field(
    layout: QGridLayout,
    row: int,
    label_text: str,
    field: QWidget,
    *,
    column_offset: int = 0,
    field_column_span: int = 1,
    label_min_width: int = LABEL_MIN_WIDTH,
    label_width_override: int | None = None,
    field_minimum_width: int | None = None,
    field_maximum_width: int | None = None,
    required: bool = False,
) -> QLabel:
    label = QLabel(label_text)
    label.setProperty("uiRole", "fieldLabel")
    label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    if label_width_override is not None:
        target_width = label_width_override
    else:
        dynamic_width = label.fontMetrics().horizontalAdvance(label_text) + LABEL_TEXT_HORIZONTAL_PADDING
        target_width = max(label_min_width, dynamic_width)
    if required:
        # Unify the required marker with the main app's red asterisk (ui-ux-universal §2).
        # NCR labels carry uiRole="fieldLabel"; render the asterisk inline via RichText using
        # the shared danger token so we drop the tooltip-only "必填欄位" convention.
        # setProperty("required", True) keeps it assertable by tests.
        label.setProperty("required", True)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setText(f'{label_text}&nbsp;<span style="color:{COLOR_DANGER_TEXT}">*</span>')
        target_width += REQUIRED_ASTERISK_WIDTH
    label.setFixedWidth(target_width)
    apply_input_style(widget=field, minimum_width=field_minimum_width, maximum_width=field_maximum_width)
    layout.addWidget(label, row, column_offset)
    layout.addWidget(field, row, column_offset + 1, 1, field_column_span)
    return label


def make_notice_label(text: str, role: str = "notice") -> QLabel:
    label = QLabel(text)
    label.setProperty("uiRole", role)
    label.setWordWrap(True)
    label.hide()
    return label


def make_hint_label(text: str, role: str = "hint") -> QLabel:
    label = QLabel(text)
    label.setProperty("uiRole", role)
    label.setWordWrap(True)
    return label


def style_table(table: QTableWidget) -> None:
    table.setAlternatingRowColors(True)
    table.setShowGrid(True)
    table.setGridStyle(Qt.PenStyle.SolidLine)
    table.setWordWrap(False)
    table.setSelectionBehavior(table.SelectionBehavior.SelectRows)
    table.setSelectionMode(table.SelectionMode.SingleSelection)
    table.setEditTriggers(table.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(TABLE_ROW_HEIGHT)
    table.horizontalHeader().setMinimumHeight(TABLE_ROW_HEIGHT)
    table.horizontalHeader().setHighlightSections(False)
    table.setSortingEnabled(False)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)


def align_table_header_left(table: QTableWidget) -> None:
    alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    table.horizontalHeader().setDefaultAlignment(alignment)
    for column_index in range(table.columnCount()):
        header_item = table.horizontalHeaderItem(column_index)
        if header_item is not None:
            header_item.setTextAlignment(alignment)


def display_text(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return text or EMPTY_PLACEHOLDER


def format_datetime(value: object) -> str:
    if not value:
        return EMPTY_PLACEHOLDER
    text = str(value)
    # Handle ISO format like 2026-04-24T10:48:51
    if "T" in text:
        return text.replace("T", " ")[:16]
    return text[:16]


def is_empty_display(text: str) -> bool:
    return text == EMPTY_PLACEHOLDER


def create_status_badge(text: str) -> QLabel:
    label = QLabel(text or EMPTY_PLACEHOLDER)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setProperty("role", "statusBadge")
    label.setProperty("tone", get_status_tone(text))
    return label


def set_table_item_foreground(item: QTableWidgetItem, text: str) -> None:
    if is_empty_display(text):
        item.setForeground(QColor(COLOR_TEXT_DISABLED))


def create_table_item(text: str, is_numeric: bool = False) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    item.setTextAlignment(alignment)
    set_table_item_foreground(item, text)
    return item


def setup_column_persistence(
    table: QTableWidget,
    settings_key: str,
    conn: sqlite3.Connection,
    field_names: list[str],
) -> None:
    """啟用欄位拖拽移動並支援儲存/讀取順序設定。"""
    from ncr.services import settings_service

    header = table.horizontalHeader()
    header.setSectionsMovable(True)
    header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    # 讀取並套用已儲存的順序
    try:
        saved_order = settings_service.get_column_order(conn, settings_key)
    except sqlite3.OperationalError:
        saved_order = []
    if saved_order:
        # 逐一移動欄位到目標視覺位置
        for target_visual_idx, field_name in enumerate(saved_order):
            if field_name in field_names:
                logical_idx = field_names.index(field_name)
                current_visual_idx = header.visualIndex(logical_idx)
                if current_visual_idx != target_visual_idx:
                    header.moveSection(current_visual_idx, target_visual_idx)

    def save_order():
        current_order = []
        for visual_idx in range(header.count()):
            logical_idx = header.logicalIndex(visual_idx)
            if logical_idx >= 0 and logical_idx < len(field_names):
                current_order.append(field_names[logical_idx])

        try:
            settings_service.set_column_order(conn, settings_key, current_order)
        except sqlite3.OperationalError:
            QMessageBox.warning(table, "無法儲存", "設定資料表尚未建立，暫時無法儲存欄位順序。")
            return
        QMessageBox.information(table, "儲存成功", "欄位順序已儲存為預設值。")

    def show_header_menu(pos):
        menu = QMenu(table)
        save_action = QAction("儲存欄位順序為預設", menu)
        save_action.triggered.connect(save_order)
        menu.addAction(save_action)
        menu.exec(header.mapToGlobal(pos))

    # Prevent duplicate connections when setup_column_persistence is called repeatedly
    # (tables refresh/update often and this function is intentionally reused).
    if not bool(header.property("columnMenuConnected")):
        header.setProperty("columnMenuConnected", True)
        header.customContextMenuRequested.connect(show_header_menu)
