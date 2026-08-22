"""Reusable full-page entry surface for supplier-event creation.

The existing dialog classes remain the owner of form fields, validation and
service calls.  This page embeds a new-record instance so the create workflow
can live in the shell without duplicating business logic or styling.
"""

from __future__ import annotations

from typing import Literal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from database import repository
from ui.layout_constants import (
    CONTROL_ROW_SPACING,
    PANEL_MARGINS,
)
from ui.widgets.common_widgets import CreateWorkflowShell
from ui.widgets.new_anomaly_dialog import NewAnomalyDialog
from ui.widgets.new_visit_dialog import NewVisitDialog


CreateKind = Literal["anomaly", "visit"]


class EventCreatePage(QWidget):
    """Full-page create flow with an explicit success decision and dirty guard."""

    def __init__(
        self,
        main_window,
        kind: CreateKind,
        parent: QWidget | None = None,
        *,
        lazy_load: bool = True,
        initial_data: dict | None = None,
    ) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self.kind = kind
        self.initial_data = dict(initial_data or {})
        self.target_scope = (
            repository.EVENT_SCOPE_ANOMALY_ONLY
            if kind == "anomaly"
            else repository.EVENT_SCOPE_VISIT_ONLY
        )
        self.setObjectName(f"EventCreate{kind.title()}Page")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.workflow_shell = CreateWorkflowShell(self)
        root.addWidget(self.workflow_shell)

        self.success_panel = QFrame()
        self.success_panel.setObjectName("EventCreateSuccessPanel")
        success_layout = QHBoxLayout(self.success_panel)
        success_layout.setContentsMargins(*PANEL_MARGINS)
        success_layout.setSpacing(CONTROL_ROW_SPACING)
        self.success_message = QLabel()
        self.success_message.setProperty("role", "messageText")
        self.success_message.setProperty("tone", "success")
        self.success_message.setWordWrap(True)
        success_layout.addWidget(self.success_message, 1)
        self.view_list_button = QPushButton("查看清單")
        self.view_list_button.setProperty("variant", "primary")
        self.view_list_button.setCursor(Qt.PointingHandCursor)
        self.view_list_button.setAccessibleName("查看剛建立的供應商事件清單")
        self.continue_button = QPushButton("繼續新增")
        self.continue_button.setProperty("variant", "secondary")
        self.continue_button.setCursor(Qt.PointingHandCursor)
        self.continue_button.setAccessibleName("清除已儲存表單並繼續新增")
        success_layout.addWidget(self.view_list_button)
        success_layout.addWidget(self.continue_button)
        self.workflow_shell.command_panel.layout().addWidget(self.success_panel)
        # Add first, then hide: this avoids a transient command-row allocation
        # when Qt recalculates the layout at high DPI.
        self.success_panel.hide()

        self.reset_button = QPushButton("重置")
        self.reset_button.setProperty("variant", "secondary")
        self.reset_button.setCursor(Qt.PointingHandCursor)
        self.reset_button.setAccessibleName("重置目前表單")
        self.return_button = QPushButton("返回清單")
        self.return_button.setProperty("variant", "secondary")
        self.return_button.setCursor(Qt.PointingHandCursor)
        self.return_button.setAccessibleName("放棄或返回供應商事件清單")
        self.save_button = QPushButton("儲存")
        self.save_button.setProperty("variant", "primary")
        self.save_button.setCursor(Qt.PointingHandCursor)
        self.save_button.setAccessibleName("儲存目前供應商事件")
        self.workflow_shell.add_context(self.reset_button)
        self.workflow_shell.add_action(self.return_button)
        self.workflow_shell.add_action(self.save_button)

        self._form = None
        self.view_list_button.clicked.connect(self._open_target_list)
        self.continue_button.clicked.connect(self.reset_form)
        self.reset_button.clicked.connect(self.reset_form)
        self.return_button.clicked.connect(self.request_cancel)
        self.save_button.clicked.connect(self._submit_form)

        if not lazy_load:
            self._ensure_form_installed()

    @property
    def form(self):
        if self._form is None:
            self._ensure_form_installed()
        return self._form

    @form.setter
    def form(self, val):
        self._form = val

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self._ensure_form_installed()

    def _ensure_form_installed(self) -> None:
        if self._form is None:
            self._install_form()

    def _install_form(self) -> None:
        if self.kind == "anomaly":
            form = NewAnomalyDialog(
                self.workflow_shell,
                embedded=True,
                page_mode=True,
                initial_data=self.initial_data,
            )
        else:
            form = NewVisitDialog(
                self.workflow_shell,
                embedded=True,
                page_mode=True,
                initial_data=self.initial_data,
            )
        form.setObjectName("EventCreateForm")
        form.form_saved.connect(self._on_form_saved)
        page_content = getattr(form, "page_content", None)
        if page_content is None:
            raise RuntimeError("全頁建立表單必須提供 page_content")
        self.workflow_shell.set_content(page_content)
        self._form = form
        self._bind_page_submit_state(form)

    def _bind_page_submit_state(self, form: QWidget) -> None:
        """Mirror the existing form eligibility on the page-level save action."""
        for name in ("supplier_combo", "product_combo"):
            combo = getattr(form, name, None)
            if combo is not None:
                combo.currentIndexChanged.connect(self._refresh_page_submit_state)
        self._refresh_page_submit_state()

    def _refresh_page_submit_state(self, *_args: object) -> None:
        if self._form is not None and hasattr(self._form, "can_submit"):
            self.save_button.setEnabled(self._form.can_submit())

    def _submit_form(self) -> None:
        self._ensure_form_installed()
        if self._form is not None:
            self._form._on_submit()

    def _on_form_saved(self, message: str) -> None:
        self.success_message.setText(message)
        self.success_panel.show()
        self.workflow_shell.show_feedback(message, tone="success")
        self.main_window.refresh_all_views()

    def can_leave(self) -> bool:
        if self._form is None:
            return True
        if not getattr(self._form, "_dirty", False):
            return True
        if not self._form._confirm_discard():
            return False
        self._form._dirty = False
        return True

    def request_cancel(self) -> None:
        if self.can_leave():
            self._open_target_list()

    def _open_target_list(self) -> None:
        self.main_window.open_event_query_with_filters(event_scope=self.target_scope)

    def reset_form(self) -> None:
        old_content = self.workflow_shell.content_scroll.takeWidget()
        if old_content is not None:
            old_content.setParent(None)
            old_content.deleteLater()
        if self._form is not None and self._form is not old_content:
            self._form.setParent(None)
            self._form.deleteLater()
            self._form = None
        self.success_panel.hide()
        self.workflow_shell.show_feedback("")
        self._install_form()
