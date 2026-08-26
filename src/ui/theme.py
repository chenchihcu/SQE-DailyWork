"""應用層主題套用入口。

從 theme_tokens / theme_qss 匯入設計 Token 與 QSS 樣式表，
提供 apply_app_theme 與 apply_preferred_cjk_font 作為核心 API。
"""

from __future__ import annotations

from functools import lru_cache
import re

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QBrush, QColor, QFont, QFontDatabase, QPalette, QPen
from PySide6.QtWidgets import QAbstractItemView, QApplication, QCalendarWidget, QComboBox, QTableView, QWidget

from ui.appearance_preferences import AppearancePreferences

# ── 向後相容的重新匯出 (Re-exports for backward compatibility) ─────
# 外部呼叫端仍可 `from ui.theme import TOKENS, get_theme_qss, asset_path`。
from ui.theme_tokens import (
    CJK_FONT_FAMILY_CSS as CJK_FONT_FAMILY_CSS,
    PREFERRED_CJK_FONT_FAMILIES as PREFERRED_CJK_FONT_FAMILIES,
    TOKENS as TOKENS,
    TYPOGRAPHY as TYPOGRAPHY,
)
from ui.theme_qss import asset_path as asset_path, get_theme_qss as _build_theme_qss
from ui._qss_appearance import get_appearance_metrics


_active_preferences = AppearancePreferences.default()
_BASE_TOKENS = dict(TOKENS)
_HIGH_CONTRAST_TOKEN_OVERRIDES = {
    "page_bg": "#FFFFFF",
    "panel_bg": "#FFFFFF",
    "panel_alt_bg": "#F3F4F6",
    "subtle_bg": "#F3F4F6",
    "surface_hover": "#F3F4F6",
    "surface_active": "#D9E7FF",
    "border": "#1F2937",
    "border_soft": "#4B5563",
    "border_strong": "#000000",
    "grid": "#1F2937",
    "text_primary": "#000000",
    "text_secondary": "#111827",
    "text_muted": "#374151",
    "text_disabled": "#4B5563",
    "focus_ring": "#005FCC",
    "primary_btn": "#0037B3",
    "primary_btn_hover": "#002B8A",
    "selection_bg": "#D9E7FF",
    "sidebar_bg": "#000000",
    "sidebar_panel": "#1F2937",
    "sidebar_hover_bg": "#1F2937",
    "sidebar_active_bg": "#0037B3",
    "sidebar_active_indicator": "#FFFFFF",
    "sidebar_text": "#FFFFFF",
    "sidebar_text_active": "#FFFFFF",
    "chart_axis_text": "#000000",
    "chart_grid": "#1F2937",
    "chart_plot_bg": "#FFFFFF",
}


_ACCENT_COLOR_TOKEN_OVERRIDES = {
    "electric_blue": {
        "primary_btn": "#1D4ED8",
        "primary_btn_hover": "#1E40AF",
        "brand_blue": "#1D4ED8",
        "focus_ring": "#2563EB",
        "sidebar_active_bg": "#1D4ED8",
        "toolbar_primary": "#1D4ED8",
        "toolbar_primary_hover": "#1E40AF",
    },
    "slate_navy": {
        "primary_btn": "#1E293B",
        "primary_btn_hover": "#0F172A",
        "brand_blue": "#1E293B",
        "focus_ring": "#334155",
        "sidebar_active_bg": "#1E293B",
        "toolbar_primary": "#1E293B",
        "toolbar_primary_hover": "#0F172A",
    },
    "emerald": {
        "primary_btn": "#047857",
        "primary_btn_hover": "#065F46",
        "brand_blue": "#047857",
        "focus_ring": "#059669",
        "sidebar_active_bg": "#047857",
        "toolbar_primary": "#047857",
        "toolbar_primary_hover": "#065F46",
    },
    "amber": {
        "primary_btn": "#B45309",
        "primary_btn_hover": "#92400E",
        "brand_blue": "#B45309",
        "focus_ring": "#D97706",
        "sidebar_active_bg": "#B45309",
        "toolbar_primary": "#B45309",
        "toolbar_primary_hover": "#92400E",
    },
    "violet": {
        "primary_btn": "#7C3AED",
        "primary_btn_hover": "#6D28D9",
        "brand_blue": "#7C3AED",
        "focus_ring": "#8B5CF6",
        "sidebar_active_bg": "#7C3AED",
        "toolbar_primary": "#7C3AED",
        "toolbar_primary_hover": "#6D28D9",
    },
    "rose": {
        "primary_btn": "#E11D48",
        "primary_btn_hover": "#BE123C",
        "brand_blue": "#E11D48",
        "focus_ring": "#F43F5E",
        "sidebar_active_bg": "#E11D48",
        "toolbar_primary": "#E11D48",
        "toolbar_primary_hover": "#BE123C",
    },
}


def get_active_appearance_preferences() -> AppearancePreferences:
    """Return the validated profile currently applied to the running app."""
    return _active_preferences


def get_active_appearance_metrics() -> dict[str, int]:
    return get_appearance_metrics(_active_preferences)


def get_active_theme_tokens() -> dict[str, object]:
    """Return the active token map used by QSS and QtCharts alike."""
    return TOKENS


def _set_token_profile(preferences: AppearancePreferences) -> None:
    TOKENS.clear()
    TOKENS.update(_BASE_TOKENS)
    accent_map = _ACCENT_COLOR_TOKEN_OVERRIDES.get(preferences.accent_color)
    if accent_map:
        TOKENS.update(accent_map)
    if preferences.contrast_mode == "high":
        TOKENS.update(_HIGH_CONTRAST_TOKEN_OVERRIDES)


def get_theme_qss(preferences: AppearancePreferences | None = None) -> str:
    """Build QSS from the requested profile without leaking a previous contrast mode."""
    normalized = preferences or AppearancePreferences.default()
    normalized = AppearancePreferences.from_mapping(normalized.to_mapping())
    _set_token_profile(normalized)
    return _build_theme_qss(normalized)


def _supports_cjk_writing_system(font_db: type[QFontDatabase], family: str) -> bool:
    systems = font_db.writingSystems(family)
    return (
        font_db.WritingSystem.TraditionalChinese in systems
        or font_db.WritingSystem.SimplifiedChinese in systems
        or font_db.WritingSystem.Japanese in systems
        or font_db.WritingSystem.Korean in systems
    )


@lru_cache(maxsize=1)
def _resolve_preferred_cjk_font_family() -> str:
    available_families = set(QFontDatabase.families())
    for family in PREFERRED_CJK_FONT_FAMILIES:
        if family in available_families and _supports_cjk_writing_system(QFontDatabase, family):
            return family
    for family in available_families:
        if _supports_cjk_writing_system(QFontDatabase, family):
            return family
    return "Segoe UI"


def apply_preferred_cjk_font(app: QApplication | None = None, *, scale: float = 1.0) -> None:
    target_app = app or QApplication.instance()
    if not isinstance(target_app, QApplication):
        return

    selected_family = _resolve_preferred_cjk_font_family()

    app_font = target_app.font()
    app_font.setFamily(selected_family)
    base_point_size = getattr(target_app, "_sqe_base_font_point_size", None)
    if not isinstance(base_point_size, (int, float)) or base_point_size <= 0:
        base_point_size = app_font.pointSizeF()
        if base_point_size <= 0:
            base_point_size = 9.0
        target_app._sqe_base_font_point_size = base_point_size
    app_font.setPointSizeF(float(base_point_size) * scale)
    prefer_antialias = getattr(QFont.StyleStrategy, "PreferAntialias", None)
    if prefer_antialias is not None:
        app_font.setStyleStrategy(app_font.styleStrategy() | prefer_antialias)
    target_app.setFont(app_font)


def _palette_color(value: str) -> QColor:
    rgba_match = re.fullmatch(
        r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*[\d.]+\s*\)",
        value,
    )
    if rgba_match is not None:
        # Native popup Base roles must be opaque; translucent surfaces otherwise
        # composite against a black Windows backing store.
        return QColor(*(int(component) for component in rgba_match.groups()))
    return QColor(value)


def _apply_calendar_palette(calendar: QCalendarWidget) -> None:
    """Force a light native calendar grid on Windows, where QSS alone is ignored."""

    palette = calendar.palette()
    tokens = get_active_theme_tokens()
    role_colors = {
        QPalette.ColorRole.Window: tokens["panel_bg"],
        QPalette.ColorRole.Base: tokens["panel_bg"],
        QPalette.ColorRole.AlternateBase: tokens["panel_bg"],
        QPalette.ColorRole.WindowText: tokens["text_primary"],
        QPalette.ColorRole.Text: tokens["text_primary"],
        QPalette.ColorRole.Highlight: tokens["primary_btn"],
        QPalette.ColorRole.HighlightedText: "#FFFFFF",
    }
    for role, color in role_colors.items():
        palette.setColor(role, _palette_color(color))
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        _palette_color(tokens["text_disabled"]),
    )
    calendar.setPalette(palette)

    view = calendar.findChild(QAbstractItemView)
    if view is not None:
        view.setPalette(palette)
        view.viewport().setPalette(palette)
        view.viewport().setAutoFillBackground(True)


def _apply_combo_popup_palette(combo: QComboBox) -> None:
    """Force an opaque light popup palette for native Windows combo views."""
    palette = combo.view().palette()
    tokens = get_active_theme_tokens()
    role_colors = {
        QPalette.ColorRole.Window: tokens["panel_bg"],
        QPalette.ColorRole.Base: tokens["panel_bg"],
        QPalette.ColorRole.AlternateBase: tokens["panel_bg"],
        QPalette.ColorRole.WindowText: tokens["text_primary"],
        QPalette.ColorRole.Text: tokens["text_primary"],
        QPalette.ColorRole.Highlight: tokens["primary_btn"],
        QPalette.ColorRole.HighlightedText: "#FFFFFF",
    }
    for role, color in role_colors.items():
        palette.setColor(role, _palette_color(color))
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        _palette_color(tokens["text_disabled"]),
    )

    view = combo.view()
    view.setPalette(palette)
    view.viewport().setPalette(palette)
    view.viewport().setAutoFillBackground(True)


def _refresh_chart_visuals(widget: QWidget) -> None:
    """Reapply token-driven chart surfaces after a live contrast preview."""
    chart_getter = getattr(widget, "chart", None)
    chart = chart_getter() if callable(chart_getter) else None
    if chart is None:
        return
    tokens = get_active_theme_tokens()
    set_background_brush = getattr(widget, "setBackgroundBrush", None)
    if callable(set_background_brush):
        set_background_brush(QBrush(QColor(tokens["panel_bg"])))
    chart.setPlotAreaBackgroundBrush(QBrush(QColor(tokens["chart_plot_bg"])))
    chart.setPlotAreaBackgroundVisible(True)
    chart.legend().setLabelColor(QColor(tokens["chart_axis_text"]))
    for axis in chart.axes():
        set_labels_color = getattr(axis, "setLabelsColor", None)
        if callable(set_labels_color):
            set_labels_color(QColor(tokens["chart_axis_text"]))
        set_grid_pen = getattr(axis, "setGridLinePen", None)
        if callable(set_grid_pen):
            set_grid_pen(QPen(QColor(tokens["chart_grid"])))
    chart.update()


class _CalendarPaletteFilter(QObject):
    def eventFilter(self, watched, event):
        if isinstance(watched, QCalendarWidget) and event.type() in {
            QEvent.Type.Polish,
            QEvent.Type.Show,
        }:
            _apply_calendar_palette(watched)
        return False


class _ComboPopupPaletteFilter(QObject):
    def eventFilter(self, watched, event):
        if isinstance(watched, QComboBox) and event.type() in {
            QEvent.Type.Polish,
            QEvent.Type.Show,
        }:
            _apply_combo_popup_palette(watched)
        return False


def _refresh_existing_widgets(app: QApplication) -> None:
    """Re-polish live surfaces after a preview without recreating workflow state."""
    metrics = get_active_appearance_metrics()
    for top_level in app.topLevelWidgets():
        for calendar in top_level.findChildren(QCalendarWidget):
            _apply_calendar_palette(calendar)
        for combo in top_level.findChildren(QComboBox):
            _apply_combo_popup_palette(combo)
        for view in top_level.findChildren(QTableView):
            view.verticalHeader().setDefaultSectionSize(metrics["table_item_height"])
            view.horizontalHeader().setMinimumHeight(metrics["header_height"])
            view.setShowGrid(_active_preferences.table_grid_lines)
            view.setAlternatingRowColors(_active_preferences.alternating_row_colors)

        if isinstance(top_level, QTableView):
            top_level.verticalHeader().setDefaultSectionSize(metrics["table_item_height"])
            top_level.horizontalHeader().setMinimumHeight(metrics["header_height"])
            top_level.setShowGrid(_active_preferences.table_grid_lines)
            top_level.setAlternatingRowColors(_active_preferences.alternating_row_colors)

        for child in top_level.findChildren(QWidget):
            if child.metaObject().className().endswith("ChartView"):
                _refresh_chart_visuals(child)
            apply_appearance = getattr(child, "apply_appearance_metrics", None)
            if callable(apply_appearance):
                apply_appearance(metrics)

        apply_appearance_top = getattr(top_level, "apply_appearance_metrics", None)
        if callable(apply_appearance_top):
            apply_appearance_top(metrics)

        top_level.update()


def apply_app_theme(
    app: QApplication,
    preferences: AppearancePreferences | None = None,
) -> None:
    """Apply one validated profile to the whole running desktop application."""
    global _active_preferences
    preferences = preferences or AppearancePreferences.default()
    normalized = AppearancePreferences.from_mapping(preferences.to_mapping())
    if normalized != preferences:
        preferences = AppearancePreferences.default()
    _active_preferences = preferences
    _set_token_profile(preferences)
    font_scale = 1.15 if preferences.text_scale == "large" else 1.0
    apply_preferred_cjk_font(app, scale=font_scale)
    app.setStyleSheet(get_theme_qss(preferences))
    calendar_filter = getattr(app, "_sqe_calendar_palette_filter", None)
    if calendar_filter is None:
        calendar_filter = _CalendarPaletteFilter(app)
        app._sqe_calendar_palette_filter = calendar_filter
        app.installEventFilter(calendar_filter)
    combo_filter = getattr(app, "_sqe_combo_popup_palette_filter", None)
    if combo_filter is None:
        combo_filter = _ComboPopupPaletteFilter(app)
        app._sqe_combo_popup_palette_filter = combo_filter
        app.installEventFilter(combo_filter)
    _refresh_existing_widgets(app)
