"""Consolidated supplier-event operational queues (overdue / RCA / actions / manager)."""

from __future__ import annotations

import logging
from typing import Literal

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from services import supplier_event_queue_service
from ui.layout_constants import CONTROL_ROW_SPACING, INLINE_SPACING, PAGE_OUTER_MARGINS
from ui.sidebar_nav import (
    NAV_LABEL_EVENT_OPEN_ACTIONS,
    NAV_LABEL_EVENT_OVERDUE,
    NAV_LABEL_EVENT_ROOT_CAUSE,
    NAV_LABEL_MANAGER_VIEW,
    NAV_SUBTITLE_EVENT_OPEN_ACTIONS,
    NAV_SUBTITLE_EVENT_OVERDUE,
    NAV_SUBTITLE_EVENT_ROOT_CAUSE,
    NAV_SUBTITLE_MANAGER_VIEW,
    PAGE_EVENT_OPEN_ACTIONS,
    PAGE_EVENT_OPS,
    PAGE_EVENT_OVERDUE,
    PAGE_EVENT_ROOT_CAUSE,
    PAGE_MANAGER_VIEW,
)
from ui.widgets.manager_view_page import ManagerViewPage
from ui.widgets.supplier_event_queue_page import SupplierEventQueuePage

logger = logging.getLogger(__name__)

OpsChipKey = Literal["overdue", "root_cause", "open_actions", "manager_view"]

_CHIP_ORDER: tuple[OpsChipKey, ...] = (
    "overdue",
    "root_cause",
    "open_actions",
    "manager_view",
)

_CHIP_PAGE_KEYS: dict[OpsChipKey, str] = {
    "overdue": PAGE_EVENT_OVERDUE,
    "root_cause": PAGE_EVENT_ROOT_CAUSE,
    "open_actions": PAGE_EVENT_OPEN_ACTIONS,
    "manager_view": PAGE_MANAGER_VIEW,
}

_PAGE_KEY_TO_CHIP: dict[str, OpsChipKey] = {
    value: key for key, value in _CHIP_PAGE_KEYS.items()
}

_CHIP_LABELS: dict[OpsChipKey, str] = {
    "overdue": NAV_LABEL_EVENT_OVERDUE,
    "root_cause": NAV_LABEL_EVENT_ROOT_CAUSE,
    "open_actions": NAV_LABEL_EVENT_OPEN_ACTIONS,
    "manager_view": NAV_LABEL_MANAGER_VIEW,
}

_CHIP_SUBTITLES: dict[OpsChipKey, str] = {
    "overdue": NAV_SUBTITLE_EVENT_OVERDUE,
    "root_cause": NAV_SUBTITLE_EVENT_ROOT_CAUSE,
    "open_actions": NAV_SUBTITLE_EVENT_OPEN_ACTIONS,
    "manager_view": NAV_SUBTITLE_MANAGER_VIEW,
}

_CHIP_COUNT_KEYS: dict[OpsChipKey, str] = {
    "overdue": "overdue_anomaly_count",
    "root_cause": "root_cause_pending_count",
    "open_actions": "open_queue_action_count",
}

_COMPAT_PAGE_KEYS = frozenset(_PAGE_KEY_TO_CHIP)


class SupplierEventOpsPage(QWidget):
    """Shell page with scope chips for supplier-event operational work queues."""

    header_changed = Signal(str, str)

    def __init__(self, main_window, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self.setObjectName("SupplierEventOpsPage")
        self._current_chip: OpsChipKey = "overdue"
        self._remembered_chip: OpsChipKey = "overdue"
        self._chip_buttons: dict[OpsChipKey, QPushButton] = {}
        self._child_pages: dict[OpsChipKey, QWidget | None] = {
            key: None for key in _CHIP_ORDER
        }
        self._stack = QStackedWidget(self)
        self._stack.setObjectName("SupplierEventOpsStack")
        self._build_ui()
        self._sync_chip_selection_ui("overdue")

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(*PAGE_OUTER_MARGINS)
        root.setSpacing(CONTROL_ROW_SPACING)

        chip_row = QHBoxLayout()
        chip_row.setSpacing(INLINE_SPACING)
        chip_group = QButtonGroup(self)
        chip_group.setExclusive(True)
        for chip_key in _CHIP_ORDER:
            button = QPushButton(_CHIP_LABELS[chip_key])
            button.setObjectName("EventScopeChip")
            button.setProperty("role", "scopeChip")
            button.setCheckable(True)
            button.setToolTip(_CHIP_SUBTITLES[chip_key])
            button.clicked.connect(
                lambda _checked=False, selected=chip_key: self._select_chip(
                    selected,
                    remember=True,
                )
            )
            chip_group.addButton(button)
            self._chip_buttons[chip_key] = button
            chip_row.addWidget(button)
        chip_row.addStretch(1)
        root.addLayout(chip_row)
        root.addWidget(self._stack, 1)

    def _ensure_child(self, chip_key: OpsChipKey) -> QWidget:
        existing = self._child_pages.get(chip_key)
        if existing is not None:
            return existing
        if chip_key == "manager_view":
            page: QWidget = ManagerViewPage(self.main_window, embedded=True)
        else:
            page = SupplierEventQueuePage(
                self.main_window,
                queue=chip_key,
                page_key=_CHIP_PAGE_KEYS[chip_key],
                embedded=True,
            )
        self._child_pages[chip_key] = page
        self._stack.addWidget(page)
        return page

    def _sync_chip_selection_ui(self, chip_key: OpsChipKey) -> None:
        button = self._chip_buttons.get(chip_key)
        if button is None:
            return
        button.blockSignals(True)
        try:
            button.setChecked(True)
        finally:
            button.blockSignals(False)

    def _select_chip(self, chip_key: OpsChipKey, *, remember: bool) -> None:
        widget = self._ensure_child(chip_key)
        self._stack.setCurrentWidget(widget)
        self._current_chip = chip_key
        if remember:
            self._remembered_chip = chip_key
        self._sync_chip_selection_ui(chip_key)
        self.sync_header()

    def activate_page_key(self, page_key: str) -> None:
        """Activate a chip from sidebar routing (compat keys force their chip)."""
        if page_key in _COMPAT_PAGE_KEYS:
            chip = _PAGE_KEY_TO_CHIP[page_key]
            self._select_chip(chip, remember=True)
            return
        if page_key == PAGE_EVENT_OPS:
            self._select_chip(self._remembered_chip, remember=False)
            return
        self._select_chip("overdue", remember=True)

    def sync_header(self) -> None:
        subtitle = _CHIP_SUBTITLES[self._current_chip]
        self.header_changed.emit("作業佇列", subtitle)

    def refresh_data(self) -> None:
        try:
            counts = supplier_event_queue_service.get_supplier_event_queue_counts()
        except Exception:
            logger.exception("讀取供應商事件佇列件數失敗")
            counts = {}
        for chip_key in ("overdue", "root_cause", "open_actions"):
            button = self._chip_buttons.get(chip_key)
            if button is None:
                continue
            count = int(counts.get(_CHIP_COUNT_KEYS[chip_key], 0))
            button.setText(f"{_CHIP_LABELS[chip_key]} ({count})")
        manager_button = self._chip_buttons.get("manager_view")
        if manager_button is not None:
            manager_button.setText(_CHIP_LABELS["manager_view"])
        current = self._child_pages.get(self._current_chip)
        if current is not None and hasattr(current, "refresh_data"):
            current.refresh_data()
        self.update()
