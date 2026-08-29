from __future__ import annotations

import logging
from collections.abc import Callable
from collections.abc import Mapping
from contextlib import contextmanager
from typing import Any, TypeVar

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QBrush, QColor

from ui.layout_constants import (
    BRAND_DIVIDER_MARGINS,
    BRAND_DIVIDER_SPACING,
    COMPACT_COMMAND_ROW_MARGINS,
    COMPACT_PAGE_SPACING,
    CONTROL_ROW_SPACING,
    EMPTY_STATE_MARGINS,
    FORM_HORIZONTAL_SPACING,
    FORM_VERTICAL_SPACING,
    PAGE_OUTER_MARGINS,
    PANEL_MARGINS,
    TABLE_ITEM_MIN_HEIGHT,
)
from ui.status_colors import get_status_palette
from ui.theme import TOKENS
from database.product_stage import (
    PRODUCT_STAGE_MASS_PRODUCTION,
    normalize_product_stage_ui,
)

logger = logging.getLogger(__name__)

EMPTY_DISPLAY = "—"
EMPTY_PLACEHOLDER = EMPTY_DISPLAY

T = TypeVar("T")


def safe_ui_operation(
    parent: QWidget,
    operation: Callable[[], T],
    *,
    success_msg: str | None = None,
    success_title: str = "成功",
    warning_title: str = "驗證失敗",
    error_title: str = "錯誤",
    logger_msg: str = "操作失敗",
    error_msg: str | None = None,
) -> T | None:
    """Execute *operation* with unified try/except ValueError/Exception + user feedback.

    Returns the operation's return value on success (or None if the operation
    returned None), or None when an exception was caught.
    """
    from ui.popup_i18n import localize_exception, localize_popup_message

    try:
        result = operation()
        result_warnings = (
            list(result.get("warnings") or [])
            if isinstance(result, Mapping)
            else []
        )
        if result_warnings:
            QMessageBox.warning(
                parent,
                "完成但有警告",
                localize_popup_message("\n".join(str(item) for item in result_warnings)),
            )
        elif success_msg:
            QMessageBox.information(parent, success_title, localize_popup_message(success_msg))
        return result
    except ValueError as exc:
        QMessageBox.warning(parent, warning_title, localize_exception(exc))
    except Exception as exc:
        logger.exception(logger_msg)
        QMessageBox.critical(
            parent,
            error_title,
            localize_popup_message(error_msg or f"操作失敗：{localize_exception(exc)}"),
        )
    return None


def create_section_card(parent: QWidget | None = None) -> QFrame:
    card = QFrame(parent)
    card.setProperty("role", "panel")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(*PANEL_MARGINS)
    layout.setSpacing(FORM_VERTICAL_SPACING)
    return card


class QueryWorkflowShell(QFrame):
    """Shared flat command surface for query/list pages.

    The shell intentionally owns no business controls.  Each workflow keeps its
    own filters and actions, while the shared role and spacing prevent the
    supplier-event and NCR pages from drifting into separate visual systems.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "subpanel")
        self.setObjectName("QueryWorkflowShell")


class AnalyticsWorkflowShell(QFrame):
    """Shared flat control surface for analysis dashboards."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "subpanel")
        self.setObjectName("AnalyticsWorkflowShell")


class CreateWorkflowShell(QWidget):
    """A full-page create surface with one command row and one scroll owner.

    Modal dialogs retain their fixed ``QDialogButtonBox`` footer.  A route that
    opens as a sidebar page instead supplies its form content here, which keeps
    save/leave actions visible at the bottom and prevents nested form scroll areas.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        outer_margins: tuple[int, int, int, int] = PAGE_OUTER_MARGINS,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("CreateWorkflowShell")
        root = QVBoxLayout(self)
        root.setContentsMargins(*outer_margins)
        root.setSpacing(COMPACT_PAGE_SPACING)

        self.content_scroll = QScrollArea()
        self.content_scroll.setObjectName("CreateWorkflowScroll")
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.content_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        root.addWidget(self.content_scroll, 1)

        self.command_panel = QFrame()
        self.command_panel.setObjectName("CreateWorkflowCommandBar")
        self.command_panel.setProperty("role", "subpanel")
        command_layout = QVBoxLayout(self.command_panel)
        command_layout.setContentsMargins(*COMPACT_COMMAND_ROW_MARGINS)
        command_layout.setSpacing(COMPACT_PAGE_SPACING)

        self.feedback_label = QLabel()
        self.feedback_label.setObjectName("CreateWorkflowFeedback")
        self.feedback_label.setProperty("role", "messageText")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.hide()
        command_layout.addWidget(self.feedback_label)

        self.command_row = QHBoxLayout()
        self.command_row.setContentsMargins(0, 0, 0, 0)
        self.command_row.setSpacing(COMPACT_PAGE_SPACING)
        self.command_row.addStretch(1)
        self._context_count = 0
        command_layout.addLayout(self.command_row)
        root.addWidget(self.command_panel)

    def add_action(self, button: QPushButton) -> None:
        """Append a command action after the leading stretch."""
        self.command_row.addWidget(button)

    def add_context(self, widget: QWidget) -> None:
        """Insert workflow context before the flexible command-row spacer."""
        # Context is added before the initial flexible spacer.  Tracking its
        # position preserves call order while leaving later actions right-aligned.
        self.command_row.insertWidget(self._context_count, widget)
        self._context_count += 1

    def set_content(self, content: QWidget) -> None:
        old_content = self.content_scroll.takeWidget()
        if old_content is not None and old_content is not content:
            old_content.setParent(None)
            old_content.deleteLater()
        self.content_scroll.setWidget(content)

    def show_feedback(self, message: str, *, tone: str | None = None) -> None:
        self.feedback_label.setText(message)
        self.feedback_label.setProperty("tone", tone)
        repolish(self.feedback_label)
        self.feedback_label.setVisible(bool(message))


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


class SortableTableWidgetItem(QTableWidgetItem):
    """QTableWidgetItem subclass supporting type-aware custom sort keys.

    Overrides __lt__ to handle numeric values, dates, and explicit sort keys safely,
    avoiding TypeError crashes when ItemDataRole.UserRole stores dict payloads.
    """

    def __init__(self, text: Any, sort_key: Any = None) -> None:
        super().__init__(str(text if text is not None else ""))
        self._sort_key = sort_key

    def set_sort_key(self, sort_key: Any) -> None:
        self._sort_key = sort_key

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if not isinstance(other, QTableWidgetItem):
            return super().__lt__(other)

        my_key = getattr(self, "_sort_key", None)
        other_key = getattr(other, "_sort_key", None)

        if my_key is not None and other_key is not None:
            if type(my_key) is type(other_key):
                try:
                    return my_key < other_key
                except TypeError:
                    pass
            return str(my_key) < str(other_key)
        elif my_key is not None:
            return True
        elif other_key is not None:
            return False

        t1 = self.text().strip()
        t2 = other.text().strip()

        # Handle placeholders (—, -, etc.) putting them after valid values when ascending
        empty_symbols = ("—", "-", "", "無", "未指定")
        if t1 in empty_symbols and t2 not in empty_symbols:
            return False
        if t2 in empty_symbols and t1 not in empty_symbols:
            return True

        if t1.isdigit() and t2.isdigit():
            return int(t1) < int(t2)
        try:
            f1, f2 = float(t1), float(t2)
            return f1 < f2
        except ValueError:
            pass

        return t1 < t2


@contextmanager
def preserve_table_sorting(table: QTableWidget):
    """Context manager that pauses table sorting during row population and restores sort state afterwards."""
    header = table.horizontalHeader()
    current_col = header.sortIndicatorSection()
    current_order = header.sortIndicatorOrder()
    is_sorting = table.isSortingEnabled()

    table.setSortingEnabled(False)
    try:
        yield
    finally:
        if is_sorting:
            table.setSortingEnabled(True)
            if 0 <= current_col < table.columnCount():
                table.sortByColumn(current_col, current_order)


def apply_table_action_affordance(table: QTableWidget, tooltip: str) -> None:
    table.setMouseTracking(True)
    table.setToolTip(tooltip)
    table.setStatusTip(tooltip)
    viewport = table.viewport()
    viewport.setMouseTracking(True)
    apply_clickable_affordance(viewport, tooltip=tooltip, status_tip=tooltip)


def style_table(table: QTableWidget, *, single_selection: bool = True, enable_sorting: bool = True) -> None:
    from ui.theme import get_active_appearance_metrics

    appearance_metrics = get_active_appearance_metrics()
    table.setAlternatingRowColors(True)
    table.setShowGrid(True)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(appearance_metrics["table_item_height"])
    table.horizontalHeader().setMinimumHeight(appearance_metrics["header_height"])
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    if single_selection:
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    align_table_header_left(table)
    table.horizontalHeader().setStretchLastSection(False)
    if enable_sorting:
        table.setSortingEnabled(True)
        table.horizontalHeader().setSortIndicatorShown(True)


def align_table_header_left(table: QTableWidget) -> None:
    alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    table.horizontalHeader().setDefaultAlignment(alignment)
    for column_index in range(table.columnCount()):
        header_item = table.horizontalHeaderItem(column_index)
        if header_item is not None:
            header_item.setTextAlignment(alignment)


def create_status_item(status: str, sort_key: Any = None) -> SortableTableWidgetItem:
    text = str(status or "").strip() or EMPTY_DISPLAY
    palette = get_status_palette(text)
    item = SortableTableWidgetItem(text, sort_key=sort_key)
    item.setForeground(QBrush(QColor(palette.foreground)))
    item.setBackground(QBrush(QColor(palette.background)))
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    return item


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


def repolish(widget: QWidget) -> None:
    """Re-run a widget's style after a dynamic QSS property changed.

    Qt does not repaint a property-based selector (e.g. ``[invalid="true"]``)
    until the style is unpolished/polished again — every property flip that
    should change appearance must call this.
    """
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


def set_field_invalid(field: QWidget, invalid: bool = True) -> None:
    """Toggle the danger error border on an input via the ``[invalid]`` QSS hook."""
    if bool(field.property("invalid")) == bool(invalid):
        return
    field.setProperty("invalid", bool(invalid))
    repolish(field)


def apply_toolbar_label_policy(label: QLabel) -> None:
    """Keep toolbar helper labels from inflating minimum window width."""
    label.setWordWrap(True)
    label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)


def make_inline_error_label() -> QLabel:
    """Form-level inline error hint (hidden until validation fails).

    Reuses the shared ``messageText``/``danger`` role so the styling stays in
    the theme rather than per-widget setStyleSheet.
    """
    label = QLabel("")
    label.setProperty("role", "messageText")
    label.setProperty("tone", "danger")
    label.setWordWrap(True)
    label.setVisible(False)
    return label


def text_table_item(value, *, empty: str = EMPTY_DISPLAY, sort_key: Any = None) -> SortableTableWidgetItem:
    """Table cell whose tooltip shows the full CJK text when the column elides it.

    Long Traditional-Chinese names/contents must not be silently truncated
    (ui-ux-universal §6); the tooltip restores the full value on hover.
    """
    text = str(value or "").strip() or empty
    item = SortableTableWidgetItem(text, sort_key=sort_key)
    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    if text and text != empty:
        item.setToolTip(text)
    return item


class DirtyTrackingMixin:
    """Unsaved-changes guard for edit dialogs (mix in *before* QDialog).

    Call ``_init_dirty_tracking([...signals])`` after building inputs and after
    applying any initial data, so programmatic population does not flip the flag.
    The save/accept path must set ``self._dirty = False`` before closing. Mirrors
    the ``closeEvent`` guard already used by CloseAnomalyDialog so every edit
    dialog behaves consistently (ui-ux-universal §2).
    """

    def _init_dirty_tracking(self, signals) -> None:
        self._dirty = False
        for signal in signals:
            signal.connect(self._mark_dirty)

    def _mark_dirty(self, *args) -> None:
        self._dirty = True

    def _confirm_discard(self) -> bool:
        return QMessageBox.question(
            self,
            "未儲存變更",
            "有未儲存的變更，確定要放棄嗎？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if getattr(self, "_dirty", False) and not self._confirm_discard():
            event.ignore()
            return
        super().closeEvent(event)

    def reject(self) -> None:
        if getattr(self, "_dirty", False) and not self._confirm_discard():
            return
        super().reject()


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
        layout.setContentsMargins(*EMPTY_STATE_MARGINS)
        layout.setSpacing(CONTROL_ROW_SPACING)
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
        layout.setContentsMargins(*BRAND_DIVIDER_MARGINS)
        layout.setSpacing(BRAND_DIVIDER_SPACING)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        for obj_name in ("BrandDot1", "BrandDot2"):
            dot = QLabel()
            dot.setObjectName(obj_name)
            dot.setFixedSize(BRAND_ACCENT_DOT_W, BRAND_ACCENT_DOT_H)
            layout.addWidget(dot)

        layout.addStretch(1)


def set_combo_current_data(combo: QComboBox, value: str) -> bool:
    idx = combo.findData(value)
    if idx < 0:
        return False
    combo.setCurrentIndex(idx)
    return True


def mark_button_variant(button: QPushButton | None, variant: str) -> None:
    if button is None:
        return
    button.setProperty("variant", variant)
    apply_clickable_affordance(button)
    style = button.style()
    style.unpolish(button)
    style.polish(button)


def paired_label(label: str | QWidget | None) -> QWidget | None:
    if label is None:
        return None
    if isinstance(label, QWidget):
        return label
    return QLabel(label)


def make_paired_form_row(
    object_name: str,
    left_label: str | QWidget,
    left_field: QWidget,
    right_label: str | QWidget | None,
    right_field: QWidget,
    *,
    left_label_min_width: int = 76,
    right_label_min_width: int = 72,
) -> QWidget:
    row = QWidget()
    row.setObjectName(object_name)
    grid = QGridLayout(row)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
    grid.setVerticalSpacing(0)

    left_label_widget = paired_label(left_label)
    right_label_widget = paired_label(right_label)
    if left_label_widget is not None:
        left_label_widget.setMinimumWidth(left_label_min_width)
        grid.addWidget(left_label_widget, 0, 0)
    grid.addWidget(left_field, 0, 1)
    if right_label_widget is not None:
        right_label_widget.setMinimumWidth(right_label_min_width)
        grid.addWidget(right_label_widget, 0, 2)
        grid.addWidget(right_field, 0, 3)
    else:
        grid.addWidget(right_field, 0, 2, 1, 2)
    grid.setColumnStretch(1, 1)
    grid.setColumnStretch(3, 1)
    return row


class SupplierProductFormMixin:
    """Mixin for dialogs that need supplier/product combo loading."""

    def _load_suppliers(self) -> None:
        import services.event_service as _event_service
        suppliers = (
            _event_service.list_suppliers(include_inactive=True)
            if self._is_edit
            else _event_service.list_active_suppliers()
        )
        self.supplier_combo.blockSignals(True)
        try:
            self.supplier_combo.clear()
            self.supplier_combo.addItem("請選擇供應商", "")
            for item in suppliers:
                name = item["supplier_name"]
                if self._is_edit and not item.get("is_active", True):
                    name = f"{name}（停用）"
                self.supplier_combo.addItem(name, item["id"])
        finally:
            self.supplier_combo.blockSignals(False)
        self._on_supplier_changed()

    def _on_supplier_changed(self) -> None:
        import services.event_service as _event_service
        supplier_id = (self.supplier_combo.currentData() or "").strip()
        products = _event_service.list_active_products_for_supplier(supplier_id)
        self._product_stage_by_id = {}
        self._product_code_by_id = {}
        self.product_combo.clear()
        # placeholder 不帶 *：異常單以紅色「品名 *」標籤標示必填；訪廠單「主要產品」同樣必填，
        # can_submit() 與 _product_guard_label 欄位層級提示一致，故欄內不再重複放 *。
        self.product_combo.addItem("請選擇產品", "")
        for item in products:
            product_id = str(item.get("id") or "").strip()
            self.product_combo.addItem(self._product_combo_label(item), product_id)
            if product_id:
                self._product_stage_by_id[product_id] = normalize_product_stage_ui(
                    item.get("product_stage")
                )
                self._product_code_by_id[product_id] = str(item.get("product_code") or "").strip()
        self._on_product_changed()
        self._on_supplier_changed_post(supplier_id, list(products))

    def _on_product_changed(self, _index: int = -1) -> None:
        product_id = (self.product_combo.currentData() or "").strip()
        product_stage = self._product_stage_by_id.get(
            product_id, PRODUCT_STAGE_MASS_PRODUCTION
        )
        self.product_stage_combo.setCurrentText(
            normalize_product_stage_ui(product_stage)
        )
        self.product_code_input.setText(self._product_code_by_id.get(product_id, ""))
        self._on_product_changed_post()

    def _product_combo_label(self, item: dict) -> str:
        code = str(item.get("product_code") or "").strip()
        name = str(item.get("product_name") or "").strip()
        if code and name:
            return f"[{code}] {name}"
        return name or code or "(未命名產品)"

    def _on_supplier_changed_post(self, supplier_id: str, products: list[dict]) -> None:
        pass

    def _on_product_changed_post(self) -> None:
        pass

    def _apply_existing_combo_value(
        self, combo: QComboBox, item_id: str, label: str
    ) -> bool:
        """Ensure combo currently selects item_id, injecting a synthetic
        "<label>（目前值）" entry if item_id isn't among the combo's loaded
        options (e.g. the linked supplier/product was later deactivated).
        Returns True if a synthetic entry was injected, so callers know
        whether they need to populate related per-id caches like
        _product_stage_by_id for that id (audit finding D6)."""
        if not item_id:
            return False
        if set_combo_current_data(combo, item_id):
            return False
        combo.addItem(f"{label or item_id}（目前值）", item_id)
        set_combo_current_data(combo, item_id)
        return True


class CaseStageStepper(QFrame):
    """Read-only visual completion for the anomaly handling lifecycle."""

    STAGES = ("開立", "處置", "根因", "對策", "驗證", "結案")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CaseStageStepper")
        self._labels: list[QLabel] = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(*COMPACT_COMMAND_ROW_MARGINS)
        layout.setSpacing(CONTROL_ROW_SPACING)
        for stage in self.STAGES:
            label = QLabel(stage)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setProperty("role", "stagePending")
            self._labels.append(label)
            layout.addWidget(label, 1)

    def set_case_state(self, detail: Mapping[str, Any], overview: Mapping[str, Any] | None = None) -> None:
        data: Mapping[str, Any] = overview or detail
        current_action = data.get("current_action")
        has_action = bool(current_action) or str(detail.get("pending_items") or "").strip()
        root_status = str(
            data.get("root_cause_status") or detail.get("root_cause_status") or ""
        ).strip()
        ca_status = str(
            data.get("corrective_action_status") or detail.get("corrective_action_status") or ""
        ).strip()
        verify_result = str(
            data.get("verification_result") or detail.get("verification_result") or ""
        ).strip()
        completed = (
            True,
            has_action,
            root_status not in ("", "—", "尚未開始", "調查中"),
            ca_status not in ("", "—", "未建立"),
            verify_result not in ("", "—", "待驗證"),
            str(detail.get("status") or "") == "已結案",
        )
        for label, is_complete in zip(self._labels, completed, strict=True):
            label.setProperty("role", "stageComplete" if is_complete else "stagePending")
            label.style().unpolish(label)
            label.style().polish(label)
