"""應用層主題套用入口。

從 theme_tokens / theme_qss 匯入設計 Token 與 QSS 樣式表，
提供 apply_app_theme 與 apply_preferred_cjk_font 作為核心 API。
"""

from __future__ import annotations

import re

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QAbstractItemView, QApplication, QCalendarWidget, QComboBox

# ── 向後相容的重新匯出 (Re-exports for backward compatibility) ─────
# 外部呼叫端仍可 `from ui.theme import TOKENS, get_theme_qss, asset_path`。
from ui.theme_tokens import (
    CJK_FONT_FAMILY_CSS as CJK_FONT_FAMILY_CSS,
    PREFERRED_CJK_FONT_FAMILIES as PREFERRED_CJK_FONT_FAMILIES,
    TOKENS as TOKENS,
    TYPOGRAPHY as TYPOGRAPHY,
)
from ui.theme_qss import asset_path as asset_path, get_theme_qss as get_theme_qss


def _supports_cjk_writing_system(font_db: type[QFontDatabase], family: str) -> bool:
    systems = font_db.writingSystems(family)
    return (
        font_db.WritingSystem.TraditionalChinese in systems
        or font_db.WritingSystem.SimplifiedChinese in systems
        or font_db.WritingSystem.Japanese in systems
        or font_db.WritingSystem.Korean in systems
    )


def apply_preferred_cjk_font(app: QApplication | None = None) -> None:
    target_app = app or QApplication.instance()
    if not isinstance(target_app, QApplication):
        return

    available_families = set(QFontDatabase.families())
    selected_family: str | None = None
    for family in PREFERRED_CJK_FONT_FAMILIES:
        if family in available_families and _supports_cjk_writing_system(QFontDatabase, family):
            selected_family = family
            break
    if selected_family is None:
        for family in QFontDatabase.families():
            if _supports_cjk_writing_system(QFontDatabase, family):
                selected_family = family
                break
    if selected_family is None:
        selected_family = "Segoe UI"

    app_font = target_app.font()
    app_font.setFamily(selected_family)
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
    role_colors = {
        QPalette.ColorRole.Window: TOKENS["panel_bg"],
        QPalette.ColorRole.Base: TOKENS["panel_bg"],
        QPalette.ColorRole.AlternateBase: TOKENS["panel_bg"],
        QPalette.ColorRole.WindowText: TOKENS["text_primary"],
        QPalette.ColorRole.Text: TOKENS["text_primary"],
        QPalette.ColorRole.Highlight: TOKENS["primary_btn"],
        QPalette.ColorRole.HighlightedText: "#FFFFFF",
    }
    for role, color in role_colors.items():
        palette.setColor(role, _palette_color(color))
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        _palette_color(TOKENS["text_disabled"]),
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
    role_colors = {
        QPalette.ColorRole.Window: TOKENS["panel_bg"],
        QPalette.ColorRole.Base: TOKENS["panel_bg"],
        QPalette.ColorRole.AlternateBase: TOKENS["panel_bg"],
        QPalette.ColorRole.WindowText: TOKENS["text_primary"],
        QPalette.ColorRole.Text: TOKENS["text_primary"],
        QPalette.ColorRole.Highlight: TOKENS["primary_btn"],
        QPalette.ColorRole.HighlightedText: "#FFFFFF",
    }
    for role, color in role_colors.items():
        palette.setColor(role, _palette_color(color))
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        _palette_color(TOKENS["text_disabled"]),
    )

    view = combo.view()
    view.setPalette(palette)
    view.viewport().setPalette(palette)
    view.viewport().setAutoFillBackground(True)


class _CalendarPaletteFilter(QObject):
    def eventFilter(self, watched, event):
        if isinstance(watched, QCalendarWidget) and event.type() in {
            QEvent.Type.Polish,
            QEvent.Type.Show,
        }:
            _apply_calendar_palette(watched)
        return super().eventFilter(watched, event)


class _ComboPopupPaletteFilter(QObject):
    def eventFilter(self, watched, event):
        if isinstance(watched, QComboBox) and event.type() in {
            QEvent.Type.Polish,
            QEvent.Type.Show,
        }:
            _apply_combo_popup_palette(watched)
        return super().eventFilter(watched, event)


def apply_app_theme(app: QApplication) -> None:
    apply_preferred_cjk_font(app)
    app.setStyleSheet(get_theme_qss())
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
