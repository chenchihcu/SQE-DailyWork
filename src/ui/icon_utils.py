"""Shared tinted SVG icon helpers for compact table/toolbar affordances."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from ui.theme import asset_path

_ACTION_ICON_SIZE = 16
_ACTION_ICON_COLOR = "#475569"
_ACTION_ICON_COLOR_DANGER = "#B91C1C"


def _tint_pixmap(base: QPixmap, color: str) -> QPixmap:
    tinted = QPixmap(base.size())
    tinted.fill(Qt.GlobalColor.transparent)
    painter = QPainter(tinted)
    painter.drawPixmap(0, 0, base)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), QColor(color))
    painter.end()
    return tinted


@lru_cache(maxsize=32)
def render_tinted_icon(
    asset_name: str,
    color: str = _ACTION_ICON_COLOR,
    size: int = _ACTION_ICON_SIZE,
) -> QPixmap:
    """Render a monochrome SVG asset and recolor opaque pixels to ``color``."""
    base = QPixmap(size, size)
    base.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(str(asset_path(asset_name)))
    if renderer.isValid():
        painter = QPainter(base)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
    return _tint_pixmap(base, color)


def action_icon(asset_name: str, *, danger: bool = False) -> QIcon:
    color = _ACTION_ICON_COLOR_DANGER if danger else _ACTION_ICON_COLOR
    return QIcon(render_tinted_icon(asset_name, color))
