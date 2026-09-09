"""Per-row Action item editor with description, owner, and due date."""

from __future__ import annotations

from PySide6.QtCore import QDate, QSize, Signal, Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from database.repo_helpers import parse_numbered_description_lines
from ui.layout_constants import (
    ACTION_ITEM_DELETE_WIDTH,
    ACTION_ITEM_DUE_DATE_WIDTH,
    ACTION_ITEM_HEADER_GAP,
    ACTION_ITEM_INDEX_WIDTH,
    ACTION_ITEM_OWNER_WIDTH,
    ACTION_ITEM_ROW_MIN_HEIGHT,
    ACTION_ITEM_ROW_SPACING,
    ACTION_ITEM_ROW_V_HALF_MARGIN,
    ACTION_ITEM_ROW_V_MARGIN,
)
from ui.widgets.common_widgets import set_field_invalid


def _make_action_item_row_layout(parent: QWidget) -> QHBoxLayout:
    layout = QHBoxLayout(parent)
    layout.setContentsMargins(
        0,
        ACTION_ITEM_ROW_V_HALF_MARGIN,
        0,
        ACTION_ITEM_ROW_V_HALF_MARGIN,
    )
    layout.setSpacing(ACTION_ITEM_ROW_SPACING)
    return layout


def _apply_action_item_control_height(widget: QWidget) -> None:
    widget.setMinimumHeight(ACTION_ITEM_ROW_MIN_HEIGHT)
    widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)


def _configure_editable_field_width(widget: QWidget, width: int) -> None:
    widget.setFixedWidth(width)
    widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


def _add_index_spacer(layout: QHBoxLayout) -> QLabel:
    spacer = QLabel("")
    spacer.setFixedWidth(ACTION_ITEM_INDEX_WIDTH)
    layout.addWidget(spacer)
    return spacer


def _add_delete_spacer(layout: QHBoxLayout) -> QLabel:
    spacer = QLabel("")
    spacer.setFixedWidth(ACTION_ITEM_DELETE_WIDTH)
    layout.addWidget(spacer)
    return spacer


class ActionItemListRow(QWidget):
    """Single Action item row with content, owner, and scheduled date."""

    valueChanged = Signal()
    removeRequested = Signal(object)

    def __init__(
        self,
        index: int = 1,
        *,
        description: str = "",
        owner: str = "",
        due_date: str = "",
        default_due_date: QDate | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(ACTION_ITEM_ROW_MIN_HEIGHT + ACTION_ITEM_ROW_V_MARGIN)
        row_layout = _make_action_item_row_layout(self)

        self.num_label = QLabel(f"{index}.")
        self.num_label.setFixedWidth(ACTION_ITEM_INDEX_WIDTH)
        self.num_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.num_label.setProperty("uiRole", "bulletIndexLabel")

        self.description_input = QLineEdit(description)
        _apply_action_item_control_height(self.description_input)
        self.description_input.setPlaceholderText(f"處置內容 {index}")
        self.description_input.setAccessibleName(f"處置內容 {index}")
        self.description_input.textChanged.connect(self._emit_changed)

        self.owner_input = QLineEdit(owner)
        _configure_editable_field_width(self.owner_input, ACTION_ITEM_OWNER_WIDTH)
        _apply_action_item_control_height(self.owner_input)
        self.owner_input.setPlaceholderText("責任人")
        self.owner_input.setAccessibleName(f"責任人 {index}")
        self.owner_input.textChanged.connect(self._emit_changed)

        self.due_date_edit = QDateEdit()
        _configure_editable_field_width(self.due_date_edit, ACTION_ITEM_DUE_DATE_WIDTH)
        _apply_action_item_control_height(self.due_date_edit)
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.due_date_edit.setAccessibleName(f"預定日期 {index}")
        fallback = default_due_date or QDate.currentDate().addDays(7)
        parsed = QDate.fromString(str(due_date or "").strip(), "yyyy-MM-dd")
        self.due_date_edit.setDate(parsed if parsed.isValid() else fallback)
        self.due_date_edit.dateChanged.connect(self._emit_changed)

        self.btn_delete = QPushButton("刪除")
        self.btn_delete.setFixedWidth(ACTION_ITEM_DELETE_WIDTH)
        self.btn_delete.setFixedHeight(ACTION_ITEM_ROW_MIN_HEIGHT)
        self.btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_delete.setAccessibleName(f"刪除條目 {index}")
        self.btn_delete.setToolTip("刪除此列條目")
        self.btn_delete.setProperty("variant", "dangerOutline")
        self.btn_delete.clicked.connect(lambda: self.removeRequested.emit(self))

        row_layout.addWidget(self.num_label)
        row_layout.addWidget(self.description_input, 1)
        row_layout.addWidget(self.owner_input)
        row_layout.addWidget(self.due_date_edit)
        row_layout.addWidget(self.btn_delete)

    def _emit_changed(self) -> None:
        self.valueChanged.emit()

    def set_index(self, index: int) -> None:
        self.num_label.setText(f"{index}.")
        self.description_input.setPlaceholderText(f"處置內容 {index}")
        self.description_input.setAccessibleName(f"處置內容 {index}")
        self.owner_input.setAccessibleName(f"責任人 {index}")
        self.due_date_edit.setAccessibleName(f"預定日期 {index}")
        self.btn_delete.setAccessibleName(f"刪除條目 {index}")

    def as_dict(self) -> dict[str, str]:
        return {
            "description": self.description_input.text().strip(),
            "owner": self.owner_input.text().strip(),
            "due_date": self.due_date_edit.date().toString("yyyy-MM-dd"),
        }

    def set_read_only(self, read_only: bool) -> None:
        self.description_input.setReadOnly(read_only)
        self.owner_input.setReadOnly(read_only)
        self.due_date_edit.setEnabled(not read_only)
        self.btn_delete.setVisible(not read_only)


class ActionItemListWidget(QWidget):
    """Dynamic list of Action items with per-row owner and due date."""

    valueChanged = Signal()

    def __init__(
        self,
        *,
        placeholder: str = "接下來要做什麼，例如向供應商要求 8D 報告",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self._rows: list[ActionItemListRow] = []
        self._placeholder = placeholder
        self._read_only = False
        self._default_due_date = QDate.currentDate().addDays(7)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(ACTION_ITEM_HEADER_GAP)

        self._column_header = self._build_column_header()
        self.main_layout.addWidget(self._column_header)

        self.items_container = QWidget()
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(ACTION_ITEM_ROW_SPACING)
        self.main_layout.addWidget(self.items_container)

        self.btn_add = QPushButton("+ 新增條目")
        self.btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add.setAccessibleName("新增 Action 條目")
        self.btn_add.setToolTip("新增一列處置條目")
        self.btn_add.setProperty("variant", "dashedPrimary")
        self.btn_add.clicked.connect(lambda: self.add_item())
        self.main_layout.addWidget(self.btn_add)

        self.add_item()

    def _build_column_header(self) -> QWidget:
        header = QWidget()
        header_layout = _make_action_item_row_layout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        _add_index_spacer(header_layout)

        description_label = QLabel("處置內容")
        description_label.setProperty("uiRole", "bulletIndexLabel")
        header_layout.addWidget(description_label, 1)

        owner_label = QLabel("責任人")
        owner_label.setProperty("uiRole", "bulletIndexLabel")
        owner_label.setFixedWidth(ACTION_ITEM_OWNER_WIDTH)
        header_layout.addWidget(owner_label)

        due_label = QLabel("預定日期")
        due_label.setProperty("uiRole", "bulletIndexLabel")
        due_label.setFixedWidth(ACTION_ITEM_DUE_DATE_WIDTH)
        header_layout.addWidget(due_label)

        _add_delete_spacer(header_layout)
        return header

    def add_item(
        self,
        *,
        description: str = "",
        owner: str = "",
        due_date: str = "",
    ) -> ActionItemListRow:
        index = len(self._rows) + 1
        row = ActionItemListRow(
            index=index,
            description=description,
            owner=owner,
            due_date=due_date,
            default_due_date=self._default_due_date,
            parent=self,
        )
        if self._placeholder and not description:
            row.description_input.setPlaceholderText(self._placeholder)
        if self._read_only:
            row.set_read_only(True)
        row.valueChanged.connect(self._on_row_value_changed)
        row.removeRequested.connect(self._remove_row)
        self._rows.append(row)
        self.items_layout.addWidget(row)
        self._update_indices()
        self.valueChanged.emit()
        return row

    def _remove_row(self, row: ActionItemListRow) -> None:
        if len(self._rows) <= 1:
            row.description_input.setText("")
            row.owner_input.setText("")
            row.due_date_edit.setDate(self._default_due_date)
            self.valueChanged.emit()
            return

        if row in self._rows:
            self._rows.remove(row)
            self.items_layout.removeWidget(row)
            row.deleteLater()
            self._update_indices()
            self.valueChanged.emit()

    def _update_indices(self) -> None:
        for idx, row in enumerate(self._rows, start=1):
            row.set_index(idx)

    def _on_row_value_changed(self) -> None:
        self.valueChanged.emit()

    def get_items(self) -> list[dict[str, str]]:
        return [row.as_dict() for row in self._rows if row.as_dict()["description"]]

    def get_all_rows(self) -> list[dict[str, str]]:
        return [row.as_dict() for row in self._rows]

    def set_items(self, items: list[dict[str, str]]) -> None:
        for row in list(self._rows):
            self.items_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        if not items:
            self.add_item()
        else:
            for item in items:
                self.add_item(
                    description=str(item.get("description") or ""),
                    owner=str(item.get("owner") or ""),
                    due_date=str(item.get("due_date") or ""),
                )
        self.valueChanged.emit()

    def set_from_legacy_description(
        self,
        description: str,
        *,
        default_owner: str = "",
        default_due: str = "",
    ) -> None:
        parsed = parse_numbered_description_lines(description)
        if len(parsed) >= 2:
            self.set_items(
                [
                    {
                        "description": line,
                        "owner": default_owner,
                        "due_date": default_due,
                    }
                    for line in parsed
                ]
            )
            return

        single = parsed[0] if parsed else str(description or "").strip()
        self.set_items(
            [
                {
                    "description": single,
                    "owner": default_owner,
                    "due_date": default_due,
                }
            ]
        )

    def has_valid_content(self) -> bool:
        return bool(self.get_items())

    def setReadOnly(self, read_only: bool) -> None:
        self._read_only = bool(read_only)
        self._column_header.setVisible(not read_only)
        self.btn_add.setVisible(not read_only)
        for row in self._rows:
            row.set_read_only(read_only)

    def set_validation_invalid(self, invalid: bool) -> None:
        """Apply field-level invalid borders to empty description inputs."""
        for row in self._rows:
            row_invalid = invalid and not row.description_input.text().strip()
            set_field_invalid(row.description_input, row_invalid)

    def sizeHint(self):
        hint = super().sizeHint()
        row_count = max(len(self._rows), 1)
        row_block = ACTION_ITEM_ROW_MIN_HEIGHT + ACTION_ITEM_ROW_V_MARGIN
        header_block = (
            self._column_header.sizeHint().height() + ACTION_ITEM_HEADER_GAP
            if self._column_header.isVisible()
            else 0
        )
        rows_block = row_count * row_block + max(row_count - 1, 0) * ACTION_ITEM_ROW_SPACING
        add_block = (
            self.btn_add.sizeHint().height() + ACTION_ITEM_HEADER_GAP
            if self.btn_add.isVisible()
            else 0
        )
        return hint.expandedTo(
            QSize(hint.width(), header_block + rows_block + add_block)
        )
