"""應用層主題套用入口。

從 theme_tokens / theme_qss 匯入設計 Token 與 QSS 樣式表，
提供 apply_app_theme 與 apply_preferred_cjk_font 作為核心 API。
"""

from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

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


def apply_app_theme(app: QApplication) -> None:
    apply_preferred_cjk_font(app)
    app.setStyleSheet(get_theme_qss())
