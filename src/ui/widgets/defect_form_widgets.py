from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QTableWidget,
    QTableWidgetItem,
)

from services.event import _visit_service as event_service
from ui.layout_constants import (
    DIALOG_OUTER_MARGINS,
    DIALOG_MIN_HEIGHT,
    INLINE_SPACING,
    TECH_CARD_INNER_MARGINS,
)
from ui.window_sizing import fit_dialog_to_available_screen
from ui.widgets.common_widgets import (
    mark_button_variant as _mark_button_variant,
    style_table,
    text_table_item,
)


# ── Constants ──────────────────────────────────────────────────────────────────

ROOT_CAUSE_PARETO_OPTIONS = [
    "",
    "製程參數失控",
    "規範文件缺漏",
    "檢驗把關失靈",
    "設計匹配不良",
    "設備能力不符",
    "包裝防護不足",
    "來料品質不良",
    "標準作業不落實",
    "供應商改善不力",
    "其他",
]

ANOMALY_CATEGORY_OPTIONS = ROOT_CAUSE_PARETO_OPTIONS

VISIT_TECH_TRANSFER_ITEMS = [
    ("tech_transfer_doc", "作業標準書"),
    ("carrier_requirement", "載具要求"),
    ("dispensing_process", "Underfill要求"),
    ("functional_test", "電訊測試"),
    ("packaging_requirement", "包裝規範"),
]

# 異常表單「參考資料（技轉）」卡片列：已技轉 + 技轉要目（與 VISIT_TECH_TRANSFER_ITEMS 對齊）。
ANOMALY_TECH_REF_CARD_DEFS: tuple[tuple[str, str], ...] = (
    ("tech_transfer", "已技轉"),
    *VISIT_TECH_TRANSFER_ITEMS,
)

TECH_TRANSFER_STATE_YES = "yes"
TECH_TRANSFER_STATE_NO = "no"
TECH_TRANSFER_STATE_NA = "na"

VISIT_TIME_SLOT_OPTIONS = ["上午", "下午", "全天"]


def create_status_pill(text: str, tone: str = "info") -> QLabel:
    """Create a styled pill label for status indicator using design tokens."""
    pill = QLabel(text)
    pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
    pill.setProperty("role", "statusBadge")
    pill.setProperty("tone", tone)
    return pill


def get_due_date_status_tone(due_date_str: str, is_closed: bool = False) -> tuple[str, str]:
    """Calculate status text and tone ('success', 'warning', 'danger', 'neutral') based on due date."""
    if is_closed:
        return ("已結案", "success")
    if not due_date_str or not due_date_str.strip():
        return ("待處理", "info")

    try:
        from PySide6.QtCore import QDate

        parts = [int(p) for p in due_date_str.strip().replace("-", "/").split("/")]
        due_qdate = QDate(parts[0], parts[1], parts[2])
        today = QDate.currentDate()
        days_left = today.daysTo(due_qdate)

        if days_left < 0:
            return (f"逾期 {abs(days_left)} 天", "danger")
        elif days_left <= 3:
            return (f"即將到期 ({days_left}天)", "warning")
        else:
            return (f"進行中 ({days_left}天)", "info")
    except Exception:
        return ("進行中", "info")



# ── Shared Helper Functions ────────────────────────────────────────────────────


def product_label(item: dict) -> str:
    code = str(item.get("product_code") or "").strip()
    name = str(item.get("product_name") or "").strip()
    if code and name:
        return f"[{code}] {name}"
    return name or code or "(未命名產品)"


def set_combo_current_text(combo: QComboBox, value: str) -> None:
    text = (value or "").strip()
    if not text:
        combo.setCurrentIndex(0)
        return
    idx = combo.findText(text)
    if idx >= 0:
        combo.setCurrentIndex(idx)
        return
    combo.setEditText(text)


def set_tone(widget: QWidget, tone: str) -> None:
    widget.setProperty("tone", tone)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


def style_dialog_buttons(buttons: QDialogButtonBox) -> QPushButton:
    save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
    cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
    _mark_button_variant(save_button, "primary")
    _mark_button_variant(cancel_button, "secondary")
    if save_button:
        save_button.setText("儲存")
    if cancel_button:
        cancel_button.setText("取消")
    return save_button


def set_text_edit_visible_rows(editor: QWidget, rows: int) -> None:
    if hasattr(editor, "document"):
        line_height = editor.fontMetrics().lineSpacing()
        document_margin = int(editor.document().documentMargin() * 2)
        frame_height = editor.frameWidth() * 2
        vertical_padding = 14
        editor.setFixedHeight(
            line_height * max(rows, 1) + vertical_padding + document_margin + frame_height
        )
    else:
        # Custom widgets such as BulletListWidget
        editor.setFixedHeight(22 * max(rows, 1) + 20)



def apply_dialog_layout(
    dialog: QDialog,
    content: QWidget,
    button_box: QDialogButtonBox,
) -> None:
    """Standardize dialog layout with a fixed bottom button row and no vertical scrollbar."""
    outer = QVBoxLayout(dialog)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    # Main content area
    outer.addWidget(content, 1)

    # Bottom button bar
    bar = QWidget()
    bar_layout = QHBoxLayout(bar)
    bar_layout.setContentsMargins(
        DIALOG_OUTER_MARGINS[0], 8, DIALOG_OUTER_MARGINS[2], DIALOG_OUTER_MARGINS[3]
    )
    bar_layout.addStretch(1)
    bar_layout.addWidget(button_box)
    bar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    outer.addWidget(bar)

    dialog.setSizeGripEnabled(True)

    hint = dialog.sizeHint()
    fit_dialog_to_available_screen(
        dialog,
        preferred_width=hint.width(),
        preferred_height=hint.height() + 20,
        minimum_height=DIALOG_MIN_HEIGHT,
    )


# ── Shared Widget Classes ──────────────────────────────────────────────────────


class TechTransferCard(QFrame):
    """卡片式技轉項目：標題在上，有/沒有/不適用 radio 在下，選取時顯示高亮邊框。"""

    _STATE_BY_ID = {
        1: TECH_TRANSFER_STATE_YES,
        0: TECH_TRANSFER_STATE_NO,
        2: TECH_TRANSFER_STATE_NA,
    }
    _ID_BY_STATE = {state: btn_id for btn_id, state in _STATE_BY_ID.items()}

    def __init__(self, field_key: str, field_label: str, parent=None):
        super().__init__(parent)
        self.field_key = field_key
        self.setObjectName("techTransferCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(140)
        self._state = TECH_TRANSFER_STATE_NO

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*TECH_CARD_INNER_MARGINS)
        layout.setSpacing(6)

        title_label = QLabel(field_label)
        title_label.setObjectName("techCardTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(title_label)

        radio_row = QHBoxLayout()
        radio_row.setSpacing(INLINE_SPACING)
        radio_row.setContentsMargins(0, 0, 0, 0)

        self.yes_radio = QRadioButton("有")
        self.no_radio = QRadioButton("沒有")
        self.na_radio = QRadioButton("不適用")
        for radio in (self.yes_radio, self.no_radio, self.na_radio):
            radio.setCursor(Qt.CursorShape.PointingHandCursor)
            radio.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.group.addButton(self.yes_radio, 1)
        self.group.addButton(self.no_radio, 0)
        self.group.addButton(self.na_radio, 2)
        self.no_radio.setChecked(True)

        radio_row.addWidget(self.yes_radio)
        radio_row.addWidget(self.no_radio)
        radio_row.addWidget(self.na_radio)
        radio_row.addStretch(1)
        layout.addLayout(radio_row)

        self._apply_style()
        self.group.buttonToggled.connect(self._on_toggled)

    def _on_toggled(self, _button, _checked: bool) -> None:
        new_state = self._STATE_BY_ID.get(
            self.group.checkedId(), TECH_TRANSFER_STATE_NO
        )
        if new_state != self._state:
            self._state = new_state
            self._apply_style()

    def _apply_style(self) -> None:
        if self._state == TECH_TRANSFER_STATE_YES:
            tag = "selected"
        elif self._state == TECH_TRANSFER_STATE_NA:
            tag = "na"
        else:
            tag = "normal"
        self.setProperty("state", tag)
        style = self.style()
        style.unpolish(self)
        style.polish(self)

    def set_state(self, state: str) -> None:
        normalized = state if state in self._ID_BY_STATE else TECH_TRANSFER_STATE_NO
        btn_id = self._ID_BY_STATE[normalized]
        btn = self.group.button(btn_id)
        if btn is not None:
            btn.setChecked(True)
        self._state = normalized
        self._apply_style()

    def get_state(self) -> str:
        return self._state

    def set_value(self, has_value: bool) -> None:
        self.set_state(
            TECH_TRANSFER_STATE_YES if has_value else TECH_TRANSFER_STATE_NO
        )


class VisitSelectionDialog(QDialog):
    def __init__(self, supplier_id: str, supplier_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"選擇訪廠紀錄 - {supplier_name}")
        self.setMinimumSize(640, 400)
        self.selected_visit_id: str | None = None
        self.selected_visit_date: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*DIALOG_OUTER_MARGINS)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["日期", "品名", "工單", "摘要"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        style_table(self.table)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.table)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._load_visits(supplier_id)
        if self.table.rowCount() > 0:
            self.table.selectRow(0)
        fit_dialog_to_available_screen(self, preferred_width=720, preferred_height=480)

    def _load_visits(self, supplier_id: str):
        visits = event_service.list_visits_for_supplier(supplier_id)
        self.table.setRowCount(len(visits))
        for idx, v in enumerate(visits):
            v_date = v.get("visit_date") or "-"
            date_item = QTableWidgetItem(v_date)
            date_item.setData(Qt.ItemDataRole.UserRole, v["id"])
            self.table.setItem(idx, 0, date_item)
            self.table.setItem(idx, 1, text_table_item(v.get("product_name"), empty="-"))
            self.table.setItem(idx, 2, QTableWidgetItem(v.get("work_order_no") or "-"))
            self.table.setItem(idx, 3, text_table_item(v.get("summary"), empty="-"))

    def _on_accept(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "提示", "請選取一個訪廠紀錄")
            return
        row = selected[0].row()
        self.selected_visit_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        self.selected_visit_date = self.table.item(row, 0).text()
        self.accept()


from ui.widgets.defect_note_form_widgets import DefectNoteTable, ProductSectionEditor  # noqa: F401
