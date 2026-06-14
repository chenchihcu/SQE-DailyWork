from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollBar,
    QSizePolicy,
    QStyle,
    QStyleOptionSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QPainter, QPen, QColor, QBrush

from ui.layout_constants import (
    GRID_GUTTER,
    PANEL_MARGINS,
    ROW_GAP,
    TABLE_ITEM_MIN_HEIGHT,
)
from ui.status_colors import get_status_palette, get_status_tone
from ui.theme import TOKENS

EMPTY_DISPLAY = "—"


def create_page_shell(parent: QWidget | None = None) -> QWidget:
    shell = QWidget(parent)
    layout = QVBoxLayout(shell)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(22)
    return shell


def create_section_card(parent: QWidget | None = None) -> QFrame:
    card = QFrame(parent)
    card.setProperty("role", "panel")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(*PANEL_MARGINS)
    layout.setSpacing(12)
    return card


def create_form_grid() -> QGridLayout:
    grid = QGridLayout()
    grid.setHorizontalSpacing(GRID_GUTTER)
    grid.setVerticalSpacing(ROW_GAP)
    return grid


def set_button_role(button: QPushButton, role: str) -> None:
    role_to_variant = {
        "primary": "primary",
        "secondary": "secondary",
        "reset": "secondary",
        "danger": "danger",
    }
    button.setProperty("variant", role_to_variant.get(role, role))
    style = button.style()
    style.unpolish(button)
    style.polish(button)
    apply_clickable_affordance(button)


class _ClickableCursorFilter(QObject):
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in (
            QEvent.Type.EnabledChange,
            QEvent.Type.Enter,
            QEvent.Type.Leave,
        ) and isinstance(watched, QWidget):
            _sync_clickable_cursor(watched)
        return False


def _sync_clickable_cursor(widget: QWidget) -> None:
    cursor = (
        Qt.CursorShape.PointingHandCursor
        if widget.isEnabled()
        else Qt.CursorShape.ArrowCursor
    )
    widget.setCursor(cursor)


def apply_clickable_affordance(
    widget: QWidget,
    *,
    tooltip: str | None = None,
    status_tip: str | None = None,
) -> QWidget:
    if tooltip and not widget.toolTip():
        widget.setToolTip(tooltip)
    status_text = status_tip if status_tip is not None else tooltip
    if status_text and not widget.statusTip():
        widget.setStatusTip(status_text)
    widget.setMouseTracking(True)
    _sync_clickable_cursor(widget)
    if getattr(widget, "_clickable_cursor_filter", None) is None:
        cursor_filter = _ClickableCursorFilter(widget)
        widget.installEventFilter(cursor_filter)
        setattr(widget, "_clickable_cursor_filter", cursor_filter)
    return widget


def apply_table_action_affordance(table: QTableWidget, tooltip: str) -> None:
    table.setMouseTracking(True)
    table.setToolTip(tooltip)
    table.setStatusTip(tooltip)
    viewport = table.viewport()
    viewport.setMouseTracking(True)
    apply_clickable_affordance(viewport, tooltip=tooltip, status_tip=tooltip)


def style_table(table: QTableWidget, *, single_selection: bool = True) -> None:
    table.setAlternatingRowColors(True)
    table.setShowGrid(True)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(TABLE_ITEM_MIN_HEIGHT)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    if single_selection:
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    align_table_header_left(table)
    table.horizontalHeader().setStretchLastSection(False)


def align_table_header_left(table: QTableWidget) -> None:
    table.horizontalHeader().setDefaultAlignment(
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )


def display_text(value: object) -> str:
    text = str(value or "").strip()
    return text or EMPTY_DISPLAY


def create_status_badge(status: str) -> "StatusBadge":
    return StatusBadge(status)


def create_status_item(status: str) -> QTableWidgetItem:
    text = str(status or "").strip() or EMPTY_DISPLAY
    palette = get_status_palette(text)
    item = QTableWidgetItem(text)
    item.setForeground(QBrush(QColor(palette.foreground)))
    item.setBackground(QBrush(QColor(palette.background)))
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    return item


class KpiCard(QFrame):
    """Compact KPI card with horizontal layout and left accent stripe."""

    def __init__(
        self,
        title: str,
        color_hex: str | None = None,
        parent=None,
        *,
        tone: str | None = None,
    ):
        super().__init__(parent)
        self.setProperty("role", "kpiCard")
        if tone:
            self.setProperty("tone", tone)

        self.setMinimumHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        stripe = QFrame()
        stripe.setFixedWidth(6)
        stripe.setStyleSheet(
            f"background: {color_hex or TOKENS['border']};"
            f"border-top-left-radius: {TOKENS['radius_md']}px;"
            f"border-bottom-left-radius: {TOKENS['radius_md']}px;"
            f"border: none;"
        )
        outer.addWidget(stripe)

        content = QWidget()
        layout = QHBoxLayout(content)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setProperty("role", "kpiTitle")
        self.title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self.value_label = QLabel("0")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.value_label.setProperty("role", "kpiValue")

        layout.addWidget(self.title_label)
        layout.addStretch(1)
        layout.addWidget(self.value_label)
        outer.addWidget(content, 1)

    def set_value(self, value: str | int):
        self.value_label.setText(str(value))


class StatusBadge(QWidget):
    """Pill-style status badge for table cells. Container is transparent so row colors show through."""

    def __init__(self, status_text: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAutoFillBackground(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel(status_text or "—")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setProperty("role", "statusBadge")
        label.setProperty("tone", get_status_tone(status_text))
        layout.addWidget(label)


class RequiredFieldLabel(QLabel):
    """Label with a trailing red asterisk for required form fields.

    Use in QFormLayout: form.addRow(RequiredFieldLabel("供應商"), widget)
    """

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "requiredLabel")
        self.setTextFormat(Qt.TextFormat.RichText)
        self._set_text(text)

    def _set_text(self, text: str) -> None:
        super().setText(
            f"{text}<span style='color:{TOKENS['danger']};'>&nbsp;*</span>"
        )

    def setText(self, text: str) -> None:  # type: ignore[override]
        self._set_text(text)


class EmptyStateWidget(QFrame):
    """Shared empty-state placeholder for list/table pages."""

    def __init__(
        self,
        title: str,
        hint: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", "emptyState")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 32, 24, 32)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._title_label = QLabel(title)
        self._title_label.setProperty("role", "title")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title_label)

        self._hint_label = QLabel(hint)
        self._hint_label.setProperty("role", "hint")
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint_label.setWordWrap(True)
        self._hint_label.setVisible(bool(hint))
        layout.addWidget(self._hint_label)

    def set_message(self, title: str, hint: str = "") -> None:
        self._title_label.setText(title)
        self._hint_label.setText(hint)
        self._hint_label.setVisible(bool(hint))


class BrandDivider(QWidget):
    """Mitcorp 雙色品牌矩形裝飾分隔線（深青 + 綠）。

    用於頁面 section 標題下方，呼應 Mitcorp 官網的雙矩形品牌識別元素。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        from ui.layout_constants import BRAND_ACCENT_DOT_H, BRAND_ACCENT_DOT_W
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 4)
        layout.setSpacing(5)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        for obj_name in ("BrandDot1", "BrandDot2"):
            dot = QLabel()
            dot.setObjectName(obj_name)
            dot.setFixedSize(BRAND_ACCENT_DOT_W, BRAND_ACCENT_DOT_H)
            layout.addWidget(dot)

        layout.addStretch(1)


class NavigatorScrollBar(QScrollBar):
    """A premium scrollbar that paints a data summary (minimap) on its track.
    
    The background displays a vertical 'sparkline' or color-coded segments 
    representing the entire dataset, allowing for high-level navigation.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._nav_data: list[str] = []  # List of colors for each data point
        self.setMouseTracking(True)

    def set_navigation_data(self, colors: list[str]):
        """Update the minimap with a list of hex colors representing the rows."""
        self._nav_data = colors
        self.update()

    def paintEvent(self, event):
        # 1. Draw the standard scrollbar parts (handle, etc.)
        # Note: Track is transparent via QSS, so we can draw behind it.
        super().paintEvent(event)
        
        if not self._nav_data:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        
        # 2. Identify the track area
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        
        # We want to draw in the 'groove' (the background track)
        track_rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_ScrollBar, 
            opt, 
            QStyle.SubControl.SC_ScrollBarGroove, 
            self
        )
        
        if track_rect.isEmpty():
            return
            
        # 3. Draw the segments
        n = len(self._nav_data)
        item_h = track_rect.height() / n
        
        # Draw small markers on the right edge of the track for a sleek look
        # or full width for a bolder look. Let's go with full width but subtle alpha.
        x = track_rect.x()
        w = track_rect.width()
        
        for i, color_str in enumerate(self._nav_data):
            color = QColor(color_str)
            color.setAlpha(120) # Semi-transparent for 'background' feel
            
            y_start = track_rect.y() + (i * item_h)
            
            painter.fillRect(
                int(x), 
                int(y_start), 
                int(w), 
                int(max(1, item_h)), 
                QBrush(color)
            )
        
        painter.end()
