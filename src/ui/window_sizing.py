from __future__ import annotations

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget

from ui.layout_constants import (
    DIALOG_SCREEN_FRACTION,
    DIALOG_SCREEN_MARGIN_X,
    DIALOG_SCREEN_MARGIN_Y,
    WINDOW_SCREEN_FRACTION,
    WINDOW_SCREEN_MARGIN,
)


def _available_geometry(widget: QWidget) -> QRect | None:
    window = widget.windowHandle()
    screen = window.screen() if window is not None else None

    if screen is None and widget.parentWidget() is not None:
        parent_window = widget.parentWidget().windowHandle()
        screen = parent_window.screen() if parent_window is not None else None

    if screen is None:
        screen = QGuiApplication.primaryScreen()

    return screen.availableGeometry() if screen is not None else None


def _usable_extent(
    available: int,
    *,
    margin: int,
    fraction: float,
    maximum: int | None,
) -> int:
    margin_limit = max(1, available - margin)
    fraction_limit = max(1, int(available * fraction))
    usable = min(margin_limit, fraction_limit)
    if maximum is not None and maximum > 0:
        usable = min(usable, maximum)
    return max(1, usable)


def _target_extent(
    preferred: int,
    *,
    minimum: int,
    usable: int,
    shrink_minimum_to_screen: bool,
) -> tuple[int, int]:
    effective_minimum = min(minimum, usable) if shrink_minimum_to_screen else minimum
    target = max(effective_minimum, min(preferred, usable))
    return effective_minimum, target


def fit_widget_to_available_screen(
    widget: QWidget,
    *,
    preferred_width: int,
    preferred_height: int,
    minimum_width: int,
    minimum_height: int,
    maximum_width: int | None = None,
    maximum_height: int | None = None,
    margin_x: int = WINDOW_SCREEN_MARGIN,
    margin_y: int = WINDOW_SCREEN_MARGIN,
    fraction: float = WINDOW_SCREEN_FRACTION,
    shrink_minimum_to_screen: bool = False,
    center: bool = True,
) -> None:
    geometry = _available_geometry(widget)
    if geometry is None:
        widget.setMinimumSize(minimum_width, minimum_height)
        widget.resize(preferred_width, preferred_height)
        return

    usable_width = _usable_extent(
        geometry.width(),
        margin=margin_x,
        fraction=fraction,
        maximum=maximum_width,
    )
    usable_height = _usable_extent(
        geometry.height(),
        margin=margin_y,
        fraction=fraction,
        maximum=maximum_height,
    )

    effective_min_width, target_width = _target_extent(
        preferred_width,
        minimum=minimum_width,
        usable=usable_width,
        shrink_minimum_to_screen=shrink_minimum_to_screen,
    )
    effective_min_height, target_height = _target_extent(
        preferred_height,
        minimum=minimum_height,
        usable=usable_height,
        shrink_minimum_to_screen=shrink_minimum_to_screen,
    )

    widget.setMinimumSize(effective_min_width, effective_min_height)
    widget.resize(target_width, target_height)

    if center:
        widget.move(
            geometry.x() + (geometry.width() - target_width) // 2,
            geometry.y() + (geometry.height() - target_height) // 2,
        )


def fit_dialog_to_available_screen(
    dialog: QWidget,
    *,
    preferred_width: int | None = None,
    preferred_height: int | None = None,
    minimum_width: int | None = None,
    minimum_height: int | None = None,
    maximum_width: int | None = None,
    maximum_height: int | None = None,
) -> None:
    hint = dialog.sizeHint()
    current_min = dialog.minimumSize()
    current_max = dialog.maximumSize()
    min_height = (
        current_min.height()
        if minimum_height is None
        else max(minimum_height, current_min.height())
    )

    max_width = maximum_width
    if max_width is None and current_max.width() < 16_777_215:
        max_width = current_max.width()

    max_height = maximum_height
    if max_height is None and current_max.height() < 16_777_215:
        max_height = current_max.height()

    fit_widget_to_available_screen(
        dialog,
        preferred_width=preferred_width or max(current_min.width(), hint.width()),
        preferred_height=preferred_height or max(min_height, hint.height()),
        minimum_width=minimum_width or current_min.width(),
        minimum_height=min_height,
        maximum_width=max_width,
        maximum_height=max_height,
        margin_x=DIALOG_SCREEN_MARGIN_X,
        margin_y=DIALOG_SCREEN_MARGIN_Y,
        fraction=DIALOG_SCREEN_FRACTION,
        shrink_minimum_to_screen=True,
    )


def restore_or_fit_window_geometry(
    widget: QWidget,
    *,
    geometry_mode: str = "remember",
    geometry_data: object | None = None,
    preferred_width: int,
    preferred_height: int,
    minimum_width: int,
    minimum_height: int,
    maximum_width: int | None = None,
    maximum_height: int | None = None,
    margin_x: int = WINDOW_SCREEN_MARGIN,
    margin_y: int = WINDOW_SCREEN_MARGIN,
    fraction: float = WINDOW_SCREEN_FRACTION,
) -> None:
    """Restores saved geometry with screen boundary clamping or fits the window to the available screen."""
    geometry = _available_geometry(widget)
    if geometry is None:
        widget.setMinimumSize(minimum_width, minimum_height)
        if geometry_mode == "remember" and geometry_data:
            try:
                if not widget.restoreGeometry(geometry_data):
                    widget.resize(preferred_width, preferred_height)
            except Exception:
                widget.resize(preferred_width, preferred_height)
        else:
            widget.resize(preferred_width, preferred_height)
            if geometry_mode == "maximized":
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, widget.showMaximized)
        return

    usable_width = _usable_extent(
        geometry.width(),
        margin=margin_x,
        fraction=fraction,
        maximum=maximum_width,
    )
    usable_height = _usable_extent(
        geometry.height(),
        margin=margin_y,
        fraction=fraction,
        maximum=maximum_height,
    )

    effective_min_width, target_width = _target_extent(
        preferred_width,
        minimum=minimum_width,
        usable=usable_width,
        shrink_minimum_to_screen=False,
    )
    effective_min_height, target_height = _target_extent(
        preferred_height,
        minimum=minimum_height,
        usable=usable_height,
        shrink_minimum_to_screen=False,
    )

    widget.setMinimumSize(effective_min_width, effective_min_height)

    if geometry_mode == "maximized":
        widget.resize(target_width, target_height)
        widget.move(
            geometry.x() + (geometry.width() - target_width) // 2,
            geometry.y() + (geometry.height() - target_height) // 2,
        )
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, widget.showMaximized)
        return

    if geometry_mode == "remember" and geometry_data:
        restored = False
        try:
            restored = bool(widget.restoreGeometry(geometry_data))
        except Exception:
            restored = False

        if restored:
            if not widget.isMaximized() and not widget.isFullScreen():
                w = widget.width()
                h = widget.height()
                clamped_w = max(effective_min_width, min(w, usable_width))
                clamped_h = max(effective_min_height, min(h, usable_height))

                x = widget.x()
                y = widget.y()

                max_x = geometry.x() + geometry.width() - clamped_w
                max_y = geometry.y() + geometry.height() - clamped_h

                if (
                    x > (geometry.x() + geometry.width() - 50)
                    or (x + w) < (geometry.x() + 50)
                    or y > (geometry.y() + geometry.height() - 50)
                    or (y + h) < (geometry.y() + 50)
                ):
                    new_x = geometry.x() + (geometry.width() - clamped_w) // 2
                    new_y = geometry.y() + (geometry.height() - clamped_h) // 2
                else:
                    new_x = max(geometry.x(), min(x, max_x))
                    new_y = max(geometry.y(), min(y, max_y))

                widget.resize(clamped_w, clamped_h)
                widget.move(new_x, new_y)
            return

    widget.resize(target_width, target_height)
    widget.move(
        geometry.x() + (geometry.width() - target_width) // 2,
        geometry.y() + (geometry.height() - target_height) // 2,
    )
