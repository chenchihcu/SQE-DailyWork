from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QAction, QColor, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
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
from ui.widgets.common_widgets import EMPTY_PLACEHOLDER
from ui.layout_constants import (
    HERO_BANNER_MARGINS,
    NCR_PAGE_MARGIN,
    NCR_SECTION_SPACING,
    NCR_FIELD_SPACING_X,
    NCR_FIELD_SPACING_Y,
    NCR_FORM_COMPACT_FIELD_MIN_WIDTH,
    NCR_FORM_TWO_COLUMN_SPACING,
    NCR_DEFECT_FORM_CONTENT_MARGINS,
    NCR_EDIT_DIALOG_CARD_MARGINS,
    NCR_LABEL_MIN_WIDTH,
    NCR_LABEL_TEXT_HORIZONTAL_PADDING,
    NCR_LABEL_WIDTH,
    NCR_DEFAULT_INPUT_MIN_WIDTH,
    NCR_INPUT_HEIGHT,
    NCR_BUTTON_HEIGHT,
    NCR_ACTION_BUTTON_MIN_WIDTH,
    NCR_FILTER_BUTTON_MIN_WIDTH,
    NCR_FILTER_BUTTON_MAX_WIDTH,
    NCR_DATE_FIELD_MIN_WIDTH,
    NCR_QUICK_ADD_BUTTON_MIN_WIDTH,
    NCR_TABLE_ROW_HEIGHT,
    NCR_DASHBOARD_CHART_CARD_MIN_HEIGHT,
    NCR_ITEMS_PER_PAGE,
    NCR_WINDOW_SCREEN_WIDTH_RATIO,
    NCR_WINDOW_SCREEN_HEIGHT_RATIO,
)


# Layout constants — imported from ui.layout_constants (single source of truth)
# NCR-specific constants are prefixed with NCR_ in layout_constants.py
PAGE_MARGIN = NCR_PAGE_MARGIN
SECTION_SPACING = NCR_SECTION_SPACING
FIELD_SPACING_X = NCR_FIELD_SPACING_X
FIELD_SPACING_Y = NCR_FIELD_SPACING_Y
FORM_TWO_COLUMN_SPACING = NCR_FORM_TWO_COLUMN_SPACING
FORM_COMPACT_FIELD_MIN_WIDTH = NCR_FORM_COMPACT_FIELD_MIN_WIDTH
DEFECT_FORM_CONTENT_MARGINS = NCR_DEFECT_FORM_CONTENT_MARGINS
EDIT_DIALOG_CARD_MARGINS = NCR_EDIT_DIALOG_CARD_MARGINS
LABEL_MIN_WIDTH = NCR_LABEL_MIN_WIDTH
LABEL_TEXT_HORIZONTAL_PADDING = NCR_LABEL_TEXT_HORIZONTAL_PADDING
LABEL_WIDTH = NCR_LABEL_WIDTH
DEFAULT_INPUT_MIN_WIDTH = NCR_DEFAULT_INPUT_MIN_WIDTH
INPUT_HEIGHT = NCR_INPUT_HEIGHT
BUTTON_HEIGHT = NCR_BUTTON_HEIGHT
ACTION_BUTTON_MIN_WIDTH = NCR_ACTION_BUTTON_MIN_WIDTH
DIALOG_ACTION_BUTTON_MIN_WIDTH = NCR_ACTION_BUTTON_MIN_WIDTH
FILTER_BUTTON_MIN_WIDTH = NCR_FILTER_BUTTON_MIN_WIDTH
FILTER_BUTTON_MAX_WIDTH = NCR_FILTER_BUTTON_MAX_WIDTH
DATE_FIELD_MIN_WIDTH = NCR_DATE_FIELD_MIN_WIDTH
QUICK_ADD_BUTTON_MIN_WIDTH = NCR_QUICK_ADD_BUTTON_MIN_WIDTH
TABLE_ROW_HEIGHT = NCR_TABLE_ROW_HEIGHT
DASHBOARD_CHART_CARD_MIN_HEIGHT = NCR_DASHBOARD_CHART_CARD_MIN_HEIGHT
ITEMS_PER_PAGE = NCR_ITEMS_PER_PAGE
WINDOW_SCREEN_WIDTH_RATIO = NCR_WINDOW_SCREEN_WIDTH_RATIO
WINDOW_SCREEN_HEIGHT_RATIO = NCR_WINDOW_SCREEN_HEIGHT_RATIO
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
    import warnings
    warnings.warn("app_stylesheet() is deprecated. Use the main theme system.", DeprecationWarning)
    return ""


def set_button_role(button: QPushButton, role: str) -> None:
    button.setProperty("buttonRole", role)
    button.style().unpolish(button)
    button.style().polish(button)


def create_section_title(title: str, *, required: bool = False) -> QLabel:
    """Plain bold section title -- no icon, matching the supplier-event side's
    convention (e.g. new_anomaly_dialog.py's 基本資訊/問題描述 titles)."""
    title_label = QLabel(title)
    title_label.setProperty("role", "sectionTitle")
    if required:
        title_label.setProperty("required", True)
        title_label.setTextFormat(Qt.TextFormat.RichText)
        title_label.setText(f'{title}&nbsp;<span style="color:{COLOR_DANGER_TEXT}">*</span>')
    return title_label


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
        header_card.setProperty("role", "panel")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(*HERO_BANNER_MARGINS)
        header_layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setProperty("role", "pageTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setProperty("role", "helperText")
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
    card.setProperty("role", "panel")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(16)

    if title:
        title_label = QLabel(title)
        title_label.setProperty("role", "sectionTitle")
        layout.addWidget(title_label)

    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setProperty("role", "helperText")
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
    label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    if label_width_override is not None:
        target_width = label_width_override
    else:
        dynamic_width = label.fontMetrics().horizontalAdvance(label_text) + LABEL_TEXT_HORIZONTAL_PADDING
        target_width = max(label_min_width, dynamic_width)
    if required:
        # Unify the required marker with the main app's red asterisk (ui-ux-universal §2).
        # Render the asterisk inline via RichText using the shared danger token so we
        # drop the tooltip-only "必填欄位" convention.
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


def make_notice_label(text: str, role: str = "messageText") -> QLabel:
    label = QLabel(text)
    label.setProperty("role", role)
    label.setWordWrap(True)
    label.hide()
    return label


def make_hint_label(text: str, role: str = "helperText") -> QLabel:
    label = QLabel(text)
    label.setProperty("role", role)
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
    table.setSortingEnabled(True)
    table.horizontalHeader().setSortIndicatorShown(True)
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


from ui.widgets.common_widgets import SortableTableWidgetItem


def create_table_item(text: str, is_numeric: bool = False, sort_key: Any = None) -> SortableTableWidgetItem:
    item = SortableTableWidgetItem(text, sort_key=sort_key)
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
