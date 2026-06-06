from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QDate, QSize, Qt
from PySide6.QtGui import QIcon, QIntValidator, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListView,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
)

from database.product_stage import (
    PRODUCT_STAGE_MASS_PRODUCTION,
    PRODUCT_STAGE_OPTIONS,
    normalize_product_stage_ui,
)
from services import attachment_manager, event_service
from ui.layout_constants import (
    DIALOG_OUTER_MARGINS,
    FORM_HORIZONTAL_SPACING,
    FORM_MAX_WIDTH,
    FORM_VERTICAL_SPACING,
    GRID_GUTTER,
    GROUPBOX_CONTENT_MARGINS,
    INLINE_SPACING,
    REF_CELL_MARGINS,
    REF_GRID_SPACING_H,
    REF_GRID_SPACING_V,
    ROW_GAP,
    TECH_CARD_INNER_MARGINS,
    DIALOG_MIN_HEIGHT,
)
from ui.popup_i18n import localize_exception, localize_popup_message
from ui.window_sizing import fit_dialog_to_available_screen
from ui.widgets.common_widgets import RequiredFieldLabel, apply_clickable_affordance

logger = logging.getLogger(__name__)

ANOMALY_CATEGORY_OPTIONS = [
    "",
    "來料品質不良",
    "尺寸/規格不符",
    "外觀不良",
    "功能異常",
    "製程參數異常",
    "材料異常",
    "組裝不良",
    "包裝/標示異常",
    "文件/追溯異常",
    "數量異常",
    "交期異常",
    "安全/法規風險",
    "其他",
]

ROOT_CAUSE_CATEGORY_OPTIONS = [
    "",
    "設計缺陷",
    "製程參數異常",
    "物料/來料問題",
    "人為操作疏失",
    "設備/治具異常",
    "環境因素",
    "文件/SOP 不足",
    "其他",
]

IMPROVEMENT_DESC_MAX_LEN = 1000
ANOMALY_ATTACHMENT_FILTER = "Images (*.jpg *.jpeg *.png)"
ATTACHMENT_PREVIEW_SIZE = QSize(132, 92)
ATTACHMENT_ITEM_SIZE = QSize(164, 142)

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


def _product_label(item: dict) -> str:
    code = str(item.get("product_code") or "").strip()
    name = str(item.get("product_name") or "").strip()
    if code and name:
        return f"[{code}] {name}"
    return name or code or "(未命名產品)"


def _set_combo_current_data(combo: QComboBox, value: str) -> bool:
    idx = combo.findData(value)
    if idx < 0:
        return False
    combo.setCurrentIndex(idx)
    return True


def _set_combo_current_text(combo: QComboBox, value: str) -> None:
    text = (value or "").strip()
    if not text:
        combo.setCurrentIndex(0)
        return
    idx = combo.findText(text)
    if idx >= 0:
        combo.setCurrentIndex(idx)
        return
    combo.setEditText(text)


def _mark_button_variant(button: QPushButton | None, variant: str) -> None:
    if button is None:
        return
    button.setProperty("variant", variant)
    apply_clickable_affordance(button)
    style = button.style()
    style.unpolish(button)
    style.polish(button)


def _set_tone(widget: QWidget, tone: str) -> None:
    widget.setProperty("tone", tone)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


def _style_dialog_buttons(buttons: QDialogButtonBox) -> QPushButton:
    save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
    cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
    _mark_button_variant(save_button, "primary")
    _mark_button_variant(cancel_button, "secondary")
    if save_button:
        save_button.setText("儲存")
    if cancel_button:
        cancel_button.setText("取消")
    return save_button


def _make_divider_title(text: str) -> QLabel:
    title = QLabel(text)
    title.setProperty("role", "dividerTitle")
    return title


def _set_text_edit_visible_rows(editor: QTextEdit, rows: int) -> None:
    line_height = editor.fontMetrics().lineSpacing()
    document_margin = int(editor.document().documentMargin() * 2)
    frame_height = editor.frameWidth() * 2
    vertical_padding = 14
    editor.setFixedHeight(
        line_height * max(rows, 1) + vertical_padding + document_margin + frame_height
    )


def _paired_label(label: str | QWidget | None) -> QWidget | None:
    if label is None:
        return None
    if isinstance(label, QWidget):
        return label
    return QLabel(label)


def _make_paired_form_row(
    object_name: str,
    left_label: str | QWidget,
    left_field: QWidget,
    right_label: str | QWidget | None,
    right_field: QWidget,
) -> QWidget:
    row = QWidget()
    row.setObjectName(object_name)
    grid = QGridLayout(row)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
    grid.setVerticalSpacing(0)

    left_label_widget = _paired_label(left_label)
    right_label_widget = _paired_label(right_label)
    if left_label_widget is not None:
        grid.addWidget(left_label_widget, 0, 0)
    grid.addWidget(left_field, 0, 1)
    if right_label_widget is not None:
        grid.addWidget(right_label_widget, 0, 2)
        grid.addWidget(right_field, 0, 3)
    else:
        grid.addWidget(right_field, 0, 2, 1, 2)
    grid.setColumnStretch(1, 1)
    grid.setColumnStretch(3, 1)
    return row


def _apply_dialog_layout(
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


class AttachmentEditor(QWidget):
    """Reusable picker + caption editor for anomaly image attachments.

    Tracks pending source paths and a per-file caption. Once the owning dialog
    has an anomaly_id (after create / before close), it calls ``save_to_anomaly``
    to copy files into the anomaly folder and persist captions.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pending_attachments: list[Path] = []
        self._pending_captions: dict[str, str] = {}
        self._existing_attachments: list[Path] = []  # Paths already in anomaly folder
        self._deleted_attachments: list[str] = []   # Filenames marked for deletion

        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("AttachmentPreviewList")
        self.list_widget.setMinimumHeight(172)
        self.list_widget.setViewMode(QListView.ViewMode.IconMode)
        self.list_widget.setResizeMode(QListView.ResizeMode.Adjust)
        self.list_widget.setMovement(QListView.Movement.Static)
        self.list_widget.setWrapping(True)
        self.list_widget.setSpacing(8)
        self.list_widget.setIconSize(ATTACHMENT_PREVIEW_SIZE)
        self.list_widget.setToolTip("雙擊縮圖或檔名可編輯圖說")
        self.list_widget.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.list_widget.itemChanged.connect(self._on_item_changed)

        hint = QLabel(
            "雙擊縮圖或檔名以新增／編輯圖說（檔名與圖說都會輸出至報告）"
        )
        hint.setProperty("role", "messageText")
        hint.setProperty("tone", "info")

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)
        self.add_button = QPushButton("選擇圖片…")
        self.remove_button = QPushButton("移除選取")
        _mark_button_variant(self.add_button, "secondary")
        _mark_button_variant(self.remove_button, "secondary")
        self.add_button.clicked.connect(self._pick)
        self.remove_button.clicked.connect(self._remove_selected)
        button_row.addWidget(self.add_button)
        button_row.addWidget(self.remove_button)
        button_row.addStretch(1)

        col.addWidget(self.list_widget)
        col.addWidget(hint)
        col.addLayout(button_row)

    def set_read_only(self, read_only: bool) -> None:
        """Disable all editing capabilities in the attachment editor."""
        self.add_button.setEnabled(not read_only)
        self.remove_button.setEnabled(not read_only)
        if read_only:
            self.list_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.list_widget.setToolTip("預覽模式下不可編輯圖說")
        else:
            self.list_widget.setEditTriggers(
                QAbstractItemView.EditTrigger.DoubleClicked
                | QAbstractItemView.EditTrigger.EditKeyPressed
            )
            self.list_widget.setToolTip("雙擊縮圖或檔名可編輯圖說")

    @staticmethod
    def _format_text(filename: str, caption: str) -> str:
        caption = (caption or "").strip()
        return f"{filename} — {caption}" if caption else filename

    @staticmethod
    def _preview_icon(path: Path) -> QIcon:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return QIcon()
        scaled = pixmap.scaled(
            ATTACHMENT_PREVIEW_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        return QIcon(scaled)

    def _pick(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "選擇附件圖片", "", ANOMALY_ATTACHMENT_FILTER
        )
        if not paths:
            return
        existing = {str(p) for p in self._pending_attachments}
        for raw in paths:
            path = Path(raw)
            if path.suffix.lower() not in attachment_manager.ALLOWED_IMAGE_SUFFIXES:
                continue
            if str(path) in existing:
                continue
            self._pending_attachments.append(path)
            existing.add(str(path))
            self._pending_captions[str(path)] = ""
            item = QListWidgetItem(
                self._preview_icon(path), self._format_text(path.name, "")
            )
            item.setSizeHint(ATTACHMENT_ITEM_SIZE)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setData(Qt.ItemDataRole.UserRole + 1, path.name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            item.setToolTip(path.name)
            self.list_widget.addItem(item)

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        stored = item.data(Qt.ItemDataRole.UserRole)
        old_display_name = item.data(Qt.ItemDataRole.UserRole + 1) or ""
        text = item.text().strip()

        # 1. Parsing: Support multiple common separators
        new_filename = text
        caption = ""
        # Candidates sorted by specificity
        for candidate in [" — ", " - ", " -", "- "]:
            if candidate in text:
                parts = text.split(candidate, 1)
                new_filename = parts[0].strip()
                caption = parts[1].strip()
                break

        # 2. Extension Recovery: If user deleted suffix, restore it from old name
        old_p = Path(old_display_name)
        new_p = Path(new_filename)
        if not new_p.suffix and old_p.suffix:
            # Only restore if it looks like a stem change
            new_filename = f"{new_filename}{old_p.suffix}"

        # 3. Validation: Fallback if filename is empty
        if not new_filename:
            new_filename = old_display_name or "image.jpg"

        # Update metadata and internal tracking
        stored_path = Path(str(stored))
        old_path_str = str(stored_path)
        new_path = stored_path.parent / new_filename
        new_path_str = str(new_path)

        if old_path_str in self._pending_captions:
            cap = self._pending_captions.pop(old_path_str)
            self._pending_captions[new_path_str] = caption if caption else cap
        else:
            self._pending_captions[new_path_str] = caption

        item.setData(Qt.ItemDataRole.UserRole, new_path_str)
        item.setData(Qt.ItemDataRole.UserRole + 1, new_filename)

        formatted = self._format_text(new_filename, caption)
        if item.text() != formatted:
            self.list_widget.blockSignals(True)
            try:
                item.setText(formatted)
            finally:
                self.list_widget.blockSignals(False)
        item.setToolTip(formatted)

    def _remove_selected(self) -> None:
        for item in self.list_widget.selectedItems():
            stored = item.data(Qt.ItemDataRole.UserRole)
            filename = item.data(Qt.ItemDataRole.UserRole + 1) or ""
            row = self.list_widget.row(item)
            self.list_widget.takeItem(row)
            
            # If it was a pending (new) attachment
            self._pending_attachments = [
                p for p in self._pending_attachments if str(p) != stored
            ]
            self._pending_captions.pop(str(stored), None)
            
            # If it was an existing attachment
            is_existing = any(str(p) == stored for p in self._existing_attachments)
            if is_existing:
                self._existing_attachments = [
                    p for p in self._existing_attachments if str(p) != stored
                ]
                if filename:
                    self._deleted_attachments.append(filename)

    def load_existing_attachments(self, anomaly_id: str) -> None:
        """Read files and captions already stored for this anomaly."""
        self._pending_attachments.clear()
        self._pending_captions.clear()
        self._existing_attachments.clear()
        self._deleted_attachments.clear()
        self.list_widget.clear()

        key = (anomaly_id or "").strip()
        if not key:
            return

        files = attachment_manager.list_anomaly_attachments(key)
        captions = attachment_manager.get_anomaly_captions(key)

        for path in files:
            self._existing_attachments.append(path)
            caption = captions.get(path.name, "")
            # We use the path string as the key in _pending_captions even for existing ones
            # to keep consistency with the 'itemChanged' logic.
            self._pending_captions[str(path)] = caption
            
            item = QListWidgetItem(
                self._preview_icon(path), self._format_text(path.name, caption)
            )
            item.setSizeHint(ATTACHMENT_ITEM_SIZE)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setData(Qt.ItemDataRole.UserRole + 1, path.name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            item.setToolTip(self._format_text(path.name, caption))
            self.list_widget.addItem(item)

    def save_to_anomaly(self, anomaly_id: str) -> None:
        key = (anomaly_id or "").strip()
        if not key:
            return

        # 1. Handle Deletions
        for filename in self._deleted_attachments:
            attachment_manager.delete_anomaly_attachment(key, filename)
        self._deleted_attachments.clear()

        # 2. Import New Attachments & Handle Renames
        # We iterate through the list widget to see what needs to be imported or renamed.
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            stored_path_str = item.data(Qt.ItemDataRole.UserRole)
            display_name = item.data(Qt.ItemDataRole.UserRole + 1)
            
            # Check if this was a brand-new (pending) attachment
            is_pending = any(str(p) == stored_path_str for p in self._pending_attachments)
            if is_pending:
                attachment_manager.import_single_anomaly_attachment(
                    key, stored_path_str, display_name
                )
            else:
                # It's an existing attachment; check if the filename was changed
                p = Path(stored_path_str)
                if p.name != display_name:
                    attachment_manager.rename_anomaly_attachment(key, p.name, display_name)

        self._pending_attachments.clear()

        # 3. Update All Captions (for both existing and newly imported)
        # We need to map filenames to captions.
        # Since _pending_captions uses absolute path strings as keys, 
        # we iterate through the current list items.
        all_captions: dict[str, str] = {}
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            stored_path_str = item.data(Qt.ItemDataRole.UserRole)
            filename = item.data(Qt.ItemDataRole.UserRole + 1)
            caption = self._pending_captions.get(stored_path_str, "").strip()
            if filename:
                all_captions[filename] = caption
        
        # Note: attachment_manager.set_anomaly_captions merges/updates.
        attachment_manager.set_anomaly_captions(key, all_captions)
        # Refresh the editor state to reflect the new "existing" status
        self.load_existing_attachments(key)


TECH_TRANSFER_STATE_YES = "yes"
TECH_TRANSFER_STATE_NO = "no"
TECH_TRANSFER_STATE_NA = "na"


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

    # ---- Legacy bool-shaped API kept for other callers / tests --------------
    def set_value(self, has_value: bool) -> None:
        self.set_state(
            TECH_TRANSFER_STATE_YES if has_value else TECH_TRANSFER_STATE_NO
        )

    def get_value(self) -> bool:
        return self._state == TECH_TRANSFER_STATE_YES


class VisitSelectionDialog(QDialog):
    def __init__(self, supplier_id: str, supplier_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"選擇訪廠紀錄 - {supplier_name}")
        self.setMinimumSize(640, 400)
        self.selected_visit_id: str | None = None
        self.selected_visit_date: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*DIALOG_OUTER_MARGINS)

        from ui.widgets.common_widgets import style_table
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
            self.table.setItem(idx, 1, QTableWidgetItem(v.get("product_name") or "-"))
            self.table.setItem(idx, 2, QTableWidgetItem(v.get("work_order_no") or "-"))
            self.table.setItem(idx, 3, QTableWidgetItem(v.get("summary") or "-"))

    def _on_accept(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "提示", "請選取一個訪廠紀錄")
            return
        row = selected[0].row()
        self.selected_visit_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        self.selected_visit_date = self.table.item(row, 0).text()
        self.accept()


class DefectNoteTable(QTableWidget):
    HEADERS = ("缺失內容", "改善內容", "備註")

    def __init__(self, parent=None):
        super().__init__(0, len(self.HEADERS), parent)
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setMinimumHeight(150)

    def add_empty_note(self) -> None:
        row = self.rowCount()
        self.insertRow(row)
        for col in range(len(self.HEADERS)):
            self.setItem(row, col, QTableWidgetItem(""))
        self.setCurrentCell(row, 0)

    def remove_selected_note(self) -> None:
        row = self.currentRow()
        if row >= 0:
            self.removeRow(row)

    def load_notes(self, notes: list[dict]) -> None:
        self.setRowCount(0)
        for note in notes:
            row = self.rowCount()
            self.insertRow(row)
            values = (
                note.get("defect_desc", ""),
                note.get("improvement_desc", ""),
                note.get("note", ""),
            )
            for col, value in enumerate(values):
                self.setItem(row, col, QTableWidgetItem(str(value or "")))

    def notes(self) -> list[dict]:
        result: list[dict] = []
        for row in range(self.rowCount()):
            defect = self._cell_text(row, 0)
            improvement = self._cell_text(row, 1)
            note = self._cell_text(row, 2)
            if not any((defect, improvement, note)):
                continue
            if not defect:
                raise ValueError("缺失內容為必填")
            result.append(
                {
                    "defect_desc": defect,
                    "improvement_desc": improvement,
                    "note": note,
                    "sort_order": len(result),
                }
            )
        return result

    def _cell_text(self, row: int, col: int) -> str:
        item = self.item(row, col)
        return item.text().strip() if item is not None else ""


class ProductSectionEditor(QGroupBox):
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self._product_stage_by_id: dict[str, str] = {}
        self._product_code_by_id: dict[str, str] = {}
        self.product_combo = QComboBox()
        self.product_combo.currentIndexChanged.connect(self._on_product_changed)
        self.product_stage_combo = QComboBox()
        self.product_stage_combo.addItems(PRODUCT_STAGE_OPTIONS)
        self.product_stage_combo.setCurrentText(PRODUCT_STAGE_MASS_PRODUCTION)
        self.product_stage_combo.setEnabled(False)
        self.product_code_input = QLineEdit()
        self.product_code_input.setReadOnly(True)
        self.time_slot_input = QLineEdit()
        self.time_slot_input.setPlaceholderText("上午 / 下午 / 產線時段")
        self.work_order_input = QLineEdit()
        self.qty_input = QLineEdit()
        self.qty_input.setValidator(QIntValidator(0, 10_000_000))
        self.summary_input = QTextEdit()
        self.summary_input.setPlaceholderText("產品區段摘要（選填）")
        _set_text_edit_visible_rows(self.summary_input, 3)
        self.defect_table = DefectNoteTable()
        add_note_button = QPushButton("新增缺失")
        add_note_button.setProperty("variant", "secondary")
        add_note_button.clicked.connect(self.defect_table.add_empty_note)
        remove_note_button = QPushButton("刪除缺失")
        remove_note_button.setProperty("tone", "warning")
        remove_note_button.clicked.connect(self.defect_table.remove_selected_note)

        form = QFormLayout()
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(INLINE_SPACING)
        row_layout.addWidget(self.product_combo, 3)
        row_layout.addWidget(self.product_stage_combo, 1)
        form.addRow(RequiredFieldLabel("品名"), row)
        form.addRow("料號", self.product_code_input)
        form.addRow(
            _make_paired_form_row(
                "ProductSectionTimeOrderRow",
                "時段",
                self.time_slot_input,
                "工單",
                self.work_order_input,
            )
        )
        form.addRow("數量", self.qty_input)
        form.addRow("摘要", self.summary_input)

        note_buttons = QHBoxLayout()
        note_buttons.addWidget(add_note_button)
        note_buttons.addWidget(remove_note_button)
        note_buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("缺失 / 改善紀錄"))
        layout.addWidget(self.defect_table)
        layout.addLayout(note_buttons)

    def set_products(self, products: list[dict]) -> None:
        current = (self.product_combo.currentData() or "").strip()
        self.product_combo.blockSignals(True)
        self.product_combo.clear()
        self.product_combo.addItem("請選擇產品", "")
        self._product_stage_by_id = {}
        self._product_code_by_id = {}
        for item in products:
            product_id = str(item.get("id") or "").strip()
            self.product_combo.addItem(_product_label(item), product_id)
            if product_id:
                self._product_stage_by_id[product_id] = normalize_product_stage_ui(
                    item.get("product_stage")
                )
                self._product_code_by_id[product_id] = str(item.get("product_code") or "").strip()
        self.product_combo.blockSignals(False)
        if current:
            _set_combo_current_data(self.product_combo, current)
        self._on_product_changed()

    def load_data(self, section: dict) -> None:
        product_id = str(section.get("product_id") or "").strip()
        if product_id and not _set_combo_current_data(self.product_combo, product_id):
            self.product_combo.addItem(str(section.get("product_name") or product_id), product_id)
            self._product_stage_by_id[product_id] = normalize_product_stage_ui(
                section.get("product_stage")
            )
            self._product_code_by_id[product_id] = str(section.get("product_code") or "")
            _set_combo_current_data(self.product_combo, product_id)
        self.product_stage_combo.setCurrentText(
            normalize_product_stage_ui(section.get("product_stage"))
        )
        self.product_code_input.setText(str(section.get("product_code") or ""))
        self.time_slot_input.setText(str(section.get("time_slot") or ""))
        self.work_order_input.setText(str(section.get("work_order_no") or ""))
        qty = int(section.get("production_qty") or 0)
        self.qty_input.setText(str(qty) if qty else "")
        self.summary_input.setPlainText(str(section.get("summary") or ""))
        self.defect_table.load_notes(list(section.get("defect_notes") or []))

    def section_data(self) -> dict | None:
        product_id = (self.product_combo.currentData() or "").strip()
        notes = self.defect_table.notes()
        has_content = any(
            (
                product_id,
                self.time_slot_input.text().strip(),
                self.work_order_input.text().strip(),
                self.qty_input.text().strip(),
                self.summary_input.toPlainText().strip(),
                notes,
            )
        )
        if not has_content:
            return None
        if not product_id:
            raise ValueError("產品區段需選擇品名")
        return {
            "product_id": product_id,
            "product_name": self.product_combo.currentText().strip(),
            "product_stage": self.product_stage_combo.currentText(),
            "product_code": self.product_code_input.text().strip(),
            "time_slot": self.time_slot_input.text().strip(),
            "work_order_no": self.work_order_input.text().strip(),
            "production_qty": int(self.qty_input.text().strip() or 0),
            "summary": self.summary_input.toPlainText().strip(),
            "defect_notes": notes,
        }

    def set_read_only(self) -> None:
        for widget in (
            self.product_combo,
            self.product_stage_combo,
            self.time_slot_input,
            self.work_order_input,
            self.qty_input,
        ):
            widget.setEnabled(False)
        self.product_code_input.setReadOnly(True)
        self.summary_input.setReadOnly(True)
        self.defect_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

    def _on_product_changed(self, _index: int = -1) -> None:
        product_id = (self.product_combo.currentData() or "").strip()
        self.product_stage_combo.setCurrentText(
            self._product_stage_by_id.get(product_id, PRODUCT_STAGE_MASS_PRODUCTION)
        )
        self.product_code_input.setText(self._product_code_by_id.get(product_id, ""))


class NewAnomalyDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        anomaly_id: str | None = None,
        initial_data: dict | None = None,
        read_only: bool = False,
    ):
        super().__init__(parent)
        self._anomaly_id = (anomaly_id or "").strip()
        self._is_edit = bool(self._anomaly_id)
        self._read_only = read_only
        self._initial_data = initial_data or {}
        self._fixed_anomaly_no = str(self._initial_data.get("anomaly_no") or "").strip()
        self._product_stage_by_id: dict[str, str] = {}
        self._product_code_by_id: dict[str, str] = {}
        self._ref_data_labels: dict[str, QLabel] = {}
        self._same_day_visit_autofill: dict[str, object] = {
            "product_id": "",
            "work_order_no": "",
            "batch_qty": None,
        }
        self.setWindowTitle("預覽異常" if self._read_only else ("編輯異常" if self._is_edit else "新增異常"))
        self.setMinimumWidth(760)
        self.setMaximumWidth(FORM_MAX_WIDTH)
        self._setup_ui()
        self._load_suppliers()
        if self._is_edit:
            self._apply_initial_data()
        if self._read_only:
            self._apply_read_only()

    def _setup_ui(self):
        # 1. 初始化所有控制項 (保持不變)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.dateChanged.connect(self._on_date_changed)
        
        self.anomaly_no_preview_input = QLineEdit()
        self.anomaly_no_preview_input.setReadOnly(True)
        
        self.supplier_combo = QComboBox()
        self.supplier_combo.currentIndexChanged.connect(self._on_supplier_changed)

        self.product_combo = QComboBox()
        self.product_combo.currentIndexChanged.connect(self._on_product_changed)
        self.product_stage_combo = QComboBox()
        self.product_stage_combo.addItems(PRODUCT_STAGE_OPTIONS)
        self.product_stage_combo.setCurrentText(PRODUCT_STAGE_MASS_PRODUCTION)
        self.product_stage_combo.setEnabled(False)
        
        self.product_code_input = QLineEdit()
        self.product_code_input.setReadOnly(True)
        self.product_code_input.setPlaceholderText("選取產品後自動帶入")
        
        self.outsource_work_order_input = QLineEdit()
        self.batch_qty_input = QLineEdit()
        self.batch_qty_input.setValidator(QIntValidator(0, 10_000_000))
        self.responsible_person_input = QLineEdit()
        
        self.due_date_check = QCheckBox("啟用")
        self.due_date_edit = QDateEdit()
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDate(QDate.currentDate().addDays(7))
        self.due_date_edit.setEnabled(False)
        self.due_date_check.toggled.connect(self.due_date_edit.setEnabled)
        
        self.is_tech_transfer_check = QCheckBox("技轉訪廠")
        self.category_input = QComboBox()
        self.category_input.setEditable(True)
        self.category_input.addItems(ANOMALY_CATEGORY_OPTIONS)
        
        self.problem_input = QTextEdit()
        self.problem_input.setPlaceholderText("輸入不良現象、異常描述與補充說明（必填）")
        _set_text_edit_visible_rows(self.problem_input, 7)
        
        self.pending_items_input = QTextEdit()
        self.pending_items_input.setPlaceholderText("確認事項（選填，每行一項）")
        _set_text_edit_visible_rows(self.pending_items_input, 4)
        
        self.sync_visit_check = QCheckBox("同步建立訪廠紀錄")
        self.sync_visit_check.setChecked(True)
        self.sync_visit_check.setVisible(not self._is_edit)
        self._sync_visit_hint_label = QLabel("")
        self._sync_visit_hint_label.setProperty("role", "messageText")
        self._sync_visit_hint_label.setProperty("tone", "info")
        self._sync_visit_hint_label.setVisible(not self._is_edit)
        self.sync_visit_check.toggled.connect(self._update_sync_visit_hint)
        self.date_edit.dateChanged.connect(lambda _d: self._update_sync_visit_hint())

        # 2. 建立分頁系統
        self.tabs = QTabWidget()
        self.tabs.setObjectName("AnomalyFormTabs")

        # --- Tab 1: 基本資訊 ---
        tab_basic = QWidget()
        basic_layout = QVBoxLayout(tab_basic)
        basic_layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        
        grid = QGridLayout()
        grid.setHorizontalSpacing(GRID_GUTTER)
        grid.setVerticalSpacing(ROW_GAP)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(4, 1)
        grid.setColumnStretch(5, 1)

        _LEFT_TOP = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        grid.addWidget(QLabel("供應商 *"), 0, 0)
        grid.addWidget(self.supplier_combo, 0, 1, 1, 2)
        grid.addWidget(QLabel("日期 *"), 0, 3)
        grid.addWidget(self.date_edit, 0, 4)
        grid.addWidget(self.is_tech_transfer_check, 0, 5)

        product_row = QWidget()
        pr_layout = QHBoxLayout(product_row)
        pr_layout.setContentsMargins(0, 0, 0, 0)
        pr_layout.setSpacing(INLINE_SPACING)
        pr_layout.addWidget(self.product_combo, 3)
        pr_layout.addWidget(self.product_stage_combo, 1)

        grid.addWidget(QLabel("品名 *"), 1, 0)
        grid.addWidget(product_row, 1, 1, 1, 2)
        grid.addWidget(QLabel("料號"), 1, 3)
        grid.addWidget(self.product_code_input, 1, 4, 1, 2)

        grid.addWidget(QLabel("異常類別"), 2, 0)
        grid.addWidget(self.category_input, 2, 1, 1, 2)
        grid.addWidget(QLabel("數量"), 2, 3)
        grid.addWidget(self.batch_qty_input, 2, 4, 1, 2)

        self._lbl_order = QLabel("委外工單")
        grid.addWidget(self._lbl_order, 3, 0)
        grid.addWidget(self.outsource_work_order_input, 3, 1, 1, 2)
        grid.addWidget(QLabel("責任人"), 3, 3)
        grid.addWidget(self.responsible_person_input, 3, 4, 1, 2)

        due_row = QWidget()
        dr_layout = QHBoxLayout(due_row)
        dr_layout.setContentsMargins(0, 0, 0, 0)
        dr_layout.setSpacing(INLINE_SPACING)
        dr_layout.addWidget(self.due_date_check)
        dr_layout.addWidget(self.due_date_edit, 1)
        grid.addWidget(QLabel("異常單號"), 4, 0)
        grid.addWidget(self.anomaly_no_preview_input, 4, 1, 1, 2)
        grid.addWidget(QLabel("預計回覆日"), 4, 3)
        grid.addWidget(due_row, 4, 4, 1, 2)

        basic_layout.addLayout(grid)
        self._product_guard_label = QLabel("")
        self._product_guard_label.setProperty("role", "messageText")
        self._product_guard_label.setVisible(False)
        basic_layout.addWidget(self._product_guard_label)
        basic_layout.addWidget(self.sync_visit_check)
        basic_layout.addWidget(self._sync_visit_hint_label)

        self._same_day_visit_hint_label = QLabel("")
        self._same_day_visit_hint_label.setProperty("role", "messageText")
        self._same_day_visit_hint_label.setProperty("tone", "info")
        self._same_day_visit_hint_label.setWordWrap(True)
        self._same_day_visit_hint_label.setVisible(False)
        basic_layout.addWidget(self._same_day_visit_hint_label)

        basic_layout.addStretch(1)
        self.tabs.addTab(tab_basic, "基本資訊")

        # --- Tab 2: 異常描述 ---
        tab_desc = QWidget()
        desc_layout = QVBoxLayout(tab_desc)
        desc_layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        desc_layout.setSpacing(8)
        desc_layout.addWidget(QLabel("不良現象描述 *"))
        desc_layout.addWidget(self.problem_input)
        desc_layout.addWidget(QLabel("確認事項 / 待追蹤"))
        desc_layout.addWidget(self.pending_items_input)
        self.tabs.addTab(tab_desc, "問題描述")

        # --- Tab 3: 風險與參考 ---
        tab_ref = QWidget()
        ref_root = QVBoxLayout(tab_ref)
        ref_root.setContentsMargins(*DIALOG_OUTER_MARGINS)
        ref_root.setSpacing(12)

        # 技轉參考
        self._ref_group = QGroupBox("最近技轉訪廠參考")
        ref_layout = QVBoxLayout(self._ref_group)
        ref_layout.setContentsMargins(*GROUPBOX_CONTENT_MARGINS)
        self._linked_visit_label = QLabel("")
        self._linked_visit_label.setProperty("role", "messageText")
        self._linked_visit_label.setWordWrap(True)
        self._linked_visit_label.setVisible(False)
        self.link_visit_button = QPushButton("關聯 / 變更訪廠紀錄…")
        self.link_visit_button.clicked.connect(self._on_link_visit_clicked)
        self.unlink_visit_button = QPushButton("取消連結")
        self.unlink_visit_button.setProperty("tone", "warning")
        self.unlink_visit_button.setVisible(False)
        self.unlink_visit_button.clicked.connect(self._on_unlink_visit_clicked)
        link_row = QHBoxLayout()
        link_row.addWidget(self.link_visit_button, 3)
        link_row.addWidget(self.unlink_visit_button, 1)
        ref_layout.addWidget(self._linked_visit_label)
        ref_layout.addLayout(link_row)

        self._ref_header_label = QLabel("請先選擇供應商以載入技轉參考資料")
        self._ref_header_label.setProperty("role", "messageText")
        self._ref_header_label.setWordWrap(True)
        ref_layout.addWidget(self._ref_header_label)

        ref_cards_widget = QWidget()
        ref_cards_grid = QGridLayout(ref_cards_widget)
        ref_cards_grid.setContentsMargins(0, 0, 0, 0)
        ref_cards_grid.setHorizontalSpacing(REF_GRID_SPACING_H)
        ref_cards_grid.setVerticalSpacing(REF_GRID_SPACING_V)
        for idx, (field_key, field_label) in enumerate(ANOMALY_TECH_REF_CARD_DEFS):
            cell = QFrame()
            cell.setObjectName("refDataCard")
            cl = QHBoxLayout(cell)
            cl.setContentsMargins(*REF_CELL_MARGINS)
            val_lbl = QLabel("—")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            cl.addWidget(QLabel(field_label), 1)
            cl.addWidget(val_lbl)
            ref_cards_grid.addWidget(cell, idx // 3, idx % 3)
            self._ref_data_labels[field_key] = val_lbl
        ref_layout.addWidget(ref_cards_widget)
        ref_root.addWidget(self._ref_group)

        # 風險調查
        self._rc_group = QGroupBox("風險控管調查")
        rc_layout = QGridLayout(self._rc_group)
        rc_layout.setContentsMargins(*GROUPBOX_CONTENT_MARGINS)
        rc_options = ["未確認", "已確認", "不適用"]
        self.rc_supplier_inv_combo = QComboBox()
        self.rc_supplier_inv_combo.addItems(rc_options)
        self.rc_supplier_wip_combo = QComboBox()
        self.rc_supplier_wip_combo.addItems(rc_options)
        self.rc_in_transit_combo = QComboBox()
        self.rc_in_transit_combo.addItems(rc_options)
        self.rc_internal_inv_combo = QComboBox()
        self.rc_internal_inv_combo.addItems(rc_options)
        rc_layout.addWidget(QLabel("供應商廠內庫存"), 0, 0)
        rc_layout.addWidget(self.rc_supplier_inv_combo, 0, 1)
        rc_layout.addWidget(QLabel("供應商在線生產"), 0, 2)
        rc_layout.addWidget(self.rc_supplier_wip_combo, 0, 3)
        rc_layout.addWidget(QLabel("在途風險"), 1, 0)
        rc_layout.addWidget(self.rc_in_transit_combo, 1, 1)
        rc_layout.addWidget(QLabel("公司廠內庫存"), 1, 2)
        rc_layout.addWidget(self.rc_internal_inv_combo, 1, 3)
        ref_root.addWidget(self._rc_group)
        ref_root.addStretch(1)
        self.tabs.addTab(tab_ref, "風險與參考")

        # --- Tab 4: 現場照片 ---
        tab_photo = QWidget()
        photo_layout = QVBoxLayout(tab_photo)
        photo_layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        self.attachment_editor = AttachmentEditor(self)
        photo_layout.addWidget(self.attachment_editor)
        self.tabs.addTab(tab_photo, "現場照片")

        # 3. 按鈕與對話框佈局
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        self.save_button = _style_dialog_buttons(buttons)
        self._button_box = buttons
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)
        
        _apply_dialog_layout(self, self.tabs, buttons)
        self._update_anomaly_no_preview()
        self.product_stage_combo.currentTextChanged.connect(
            lambda _: self._update_outsource_row_visibility()
        )
        self.is_tech_transfer_check.toggled.connect(self._update_ref_group_visibility)
        self._update_outsource_row_visibility()
        self._update_ref_group_visibility()

    def _update_outsource_row_visibility(self) -> None:
        """委外工單列只在委外階段或已有值時顯示；委外階段未啟用前維持顯示。"""
        stage = self.product_stage_combo.currentText()
        is_outsource_stage_known = "委外" in PRODUCT_STAGE_OPTIONS
        show = (
            not is_outsource_stage_known
            or stage == "委外"
            or bool(self.outsource_work_order_input.text().strip())
        )
        self._lbl_order.setVisible(show)
        self.outsource_work_order_input.setVisible(show)

    def _update_ref_group_visibility(self) -> None:
        """技轉參考資料群組只在勾選技轉訪廠時顯示。"""
        checked = self.is_tech_transfer_check.isChecked()
        self._ref_group.setVisible(checked)
        if checked and not self._is_edit:
            self.sync_visit_check.setChecked(True)

    def _apply_read_only(self) -> None:
        """Disable all input widgets to prevent modification."""
        self.date_edit.setEnabled(False)
        self.supplier_combo.setEnabled(False)
        self.product_combo.setEnabled(False)
        self.product_stage_combo.setEnabled(False)
        self.outsource_work_order_input.setReadOnly(True)
        self.batch_qty_input.setReadOnly(True)
        self.category_input.setEnabled(False)
        self.responsible_person_input.setReadOnly(True)
        self.due_date_check.setEnabled(False)
        self.due_date_edit.setEnabled(False)
        self.is_tech_transfer_check.setEnabled(False)
        self.problem_input.setReadOnly(True)
        self.pending_items_input.setReadOnly(True)

        # Risk control combos
        self.rc_supplier_inv_combo.setEnabled(False)
        self.rc_supplier_wip_combo.setEnabled(False)
        self.rc_in_transit_combo.setEnabled(False)
        self.rc_internal_inv_combo.setEnabled(False)

        # Hide sync visit options in preview
        self.sync_visit_check.setVisible(False)
        self._sync_visit_hint_label.setVisible(False)

        # Link visit buttons
        self.link_visit_button.setEnabled(False)
        self.unlink_visit_button.setEnabled(False)

        # Attachment editor
        self.attachment_editor.set_read_only(True)

        # Change Save button to Close and hide Cancel (redundant in read-only mode)
        if self.save_button:
            self.save_button.setText("關閉")
            # Disconnect from _on_submit and just accept (close)
            self._button_box.accepted.disconnect(self._on_submit)
            self._button_box.accepted.connect(self.accept)
        cancel_btn = self._button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setVisible(False)

    def _on_date_changed(self, _date: QDate | None = None) -> None:
        self._update_anomaly_no_preview()
        self._apply_same_day_visit_defaults()

    def _update_sync_visit_hint(self) -> None:
        if self._is_edit:
            return
        if self.sync_visit_check.isChecked():
            visit_date = self.date_edit.date().toString("yyyy-MM-dd")
            self._sync_visit_hint_label.setText(
                f"勾選後將同時建立／重用 {visit_date} 的訪廠紀錄"
            )
            _set_tone(self._sync_visit_hint_label, "info")
        else:
            self._sync_visit_hint_label.setText(
                "未勾選：本異常單將不關聯任何訪廠紀錄"
            )
            _set_tone(self._sync_visit_hint_label, "warning")

    def _update_anomaly_no_preview(self, _date: QDate | None = None):
        if self._is_edit:
            self.anomaly_no_preview_input.setText(self._fixed_anomaly_no or "-")
            return
        anomaly_date = self.date_edit.date().toString("yyyy-MM-dd")
        try:
            preview = event_service.preview_anomaly_no(anomaly_date)
        except Exception:
            logger.exception("preview_anomaly_no failed for date %s", anomaly_date)
            preview = "-"
        self.anomaly_no_preview_input.setText(preview)

    def _load_suppliers(self):
        suppliers = (
            event_service.list_suppliers(include_inactive=True)
            if self._is_edit
            else event_service.list_active_suppliers()
        )
        self.supplier_combo.blockSignals(True)
        self.supplier_combo.clear()
        self.supplier_combo.addItem("請選擇供應商", "")
        for item in suppliers:
            name = item["supplier_name"]
            if self._is_edit and not item.get("is_active", True):
                name = f"{name}（停用）"
            self.supplier_combo.addItem(name, item["id"])
        self.supplier_combo.blockSignals(False)
        self._on_supplier_changed()

    def _on_supplier_changed(self):
        supplier_id = (self.supplier_combo.currentData() or "").strip()
        products = event_service.list_active_products_for_supplier(supplier_id)
        self._product_items = products
        self._product_stage_by_id = {}
        self.product_combo.clear()
        self.product_combo.addItem("請選擇產品 *", "")
        for item in products:
            product_id = str(item.get("id") or "").strip()
            self.product_combo.addItem(_product_label(item), product_id)
            if product_id:
                self._product_stage_by_id[product_id] = normalize_product_stage_ui(
                    item.get("product_stage")
                )
                self._product_code_by_id[product_id] = str(item.get("product_code") or "").strip()
        self._on_product_changed()
        self._refresh_submit_state()
        self._load_tech_transfer_ref(supplier_id)
        self._apply_same_day_visit_defaults()

    def _load_tech_transfer_ref(self, supplier_id: str) -> None:
        """查詢該供應商最新技轉訪廠資料並更新參考資料卡片。"""
        # 重置所有 label
        for lbl in self._ref_data_labels.values():
            lbl.setText("—")
            lbl.setProperty("status", "muted")
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)
        if not supplier_id:
            self._ref_header_label.setText("請先選擇供應商以載入技轉參考資料")
            return
        try:
            ref = event_service.get_latest_tech_transfer_for_supplier(supplier_id)
        except Exception:
            logger.exception(
                "get_latest_tech_transfer_for_supplier failed for supplier_id=%s",
                supplier_id,
            )
            ref = None
        if ref is None:
            self._ref_header_label.setText("此供應商目前無技轉訪廠紀錄")
            return
        visit_date = str(ref.get("visit_date") or "").strip() or "?"
        self._ref_header_label.setText(f"資料來源：{visit_date} 訪廠紀錄")
        for field_key, _label in ANOMALY_TECH_REF_CARD_DEFS:
            lbl = self._ref_data_labels.get(field_key)
            if lbl is None:
                continue
            if field_key == "tech_transfer":
                has_val = bool(ref.get(field_key, False))
                lbl.setText("是" if has_val else "否")
                lbl.setProperty("status", "success" if has_val else "muted")
            else:
                state_val = (
                    str(ref.get(f"{field_key}_state") or "").strip().lower()
                    or (
                        TECH_TRANSFER_STATE_YES
                        if bool(ref.get(field_key, False))
                        else TECH_TRANSFER_STATE_NO
                    )
                )
                if state_val == TECH_TRANSFER_STATE_YES:
                    lbl.setText("有")
                    lbl.setProperty("status", "success")
                elif state_val == TECH_TRANSFER_STATE_NA:
                    lbl.setText("不適用")
                    lbl.setProperty("status", "na")
                else:
                    lbl.setText("沒有")
                    lbl.setProperty("status", "muted")
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)

    def _on_unlink_visit_clicked(self) -> None:
        if not self._is_edit or not self._anomaly_id:
            return
        ans = QMessageBox.question(
            self,
            "取消連結",
            "確定要取消本異常單與訪廠紀錄的連結嗎？\n(本單將變為單獨異常)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return

        try:
            event_service.update_anomaly_link(self._anomaly_id, None)
            self._initial_data["visit_id"] = None
            self._rc_group.setTitle("風險控管調查 (單獨異常 / 無訪廠紀錄適用)")
            self._linked_visit_label.setVisible(False)
            self.unlink_visit_button.setVisible(False)
            QMessageBox.information(self, "成功", "已取消連結訪廠紀錄")
        except Exception as exc:
            logger.exception("Failed to unlink visit")
            QMessageBox.critical(self, "錯誤", f"取消連結失敗：{exc}")

    def _on_link_visit_clicked(self) -> None:
        if not self._is_edit:
            return
        supplier_id = (self.supplier_combo.currentData() or "").strip()
        supplier_name = self.supplier_combo.currentText()
        if not supplier_id:
            QMessageBox.warning(self, "提示", "請先選擇供應商")
            return

        dialog = VisitSelectionDialog(supplier_id, supplier_name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            visit_id = dialog.selected_visit_id
            visit_date = dialog.selected_visit_date

            try:
                # 1. Update linkage in DB
                event_service.update_anomaly_link(self._anomaly_id, visit_id)

                # 2. Ask to sync date if different
                current_date = self.date_edit.date().toString("yyyy-MM-dd")
                if visit_date and visit_date != current_date:
                    ans = QMessageBox.question(
                        self,
                        "同步日期",
                        f"所選訪廠日期為 {visit_date}，是否將本異常日期也同步變更？",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    )
                    if ans == QMessageBox.StandardButton.Yes:
                        self.date_edit.setDate(QDate.fromString(visit_date, "yyyy-MM-dd"))

                # 3. Ask to sync product/lot info
                ans_sync = QMessageBox.question(
                    self,
                    "同步資訊",
                    "是否同步沿用該訪廠的產品、工單及批量資訊？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if ans_sync == QMessageBox.StandardButton.Yes:
                    v_detail = event_service.get_visit_detail(visit_id)
                    v_product_id = v_detail.get("product_id")
                    if v_product_id:
                        _set_combo_current_data(self.product_combo, v_product_id)
                    v_order = str(v_detail.get("work_order_no") or "").strip()
                    if v_order:
                        self.outsource_work_order_input.setText(v_order)
                    v_qty = int(v_detail.get("production_qty") or 0)
                    if v_qty > 0:
                        self.batch_qty_input.setText(str(v_qty))

                # 4. Manually update UI labels instead of full _apply_initial_data
                # to avoid resetting other unsaved fields the user might be editing.
                self._initial_data["visit_id"] = visit_id
                if visit_id:
                    self.unlink_visit_button.setVisible(True)
                    self._rc_group.setTitle("風險控管調查 (已關聯訪廠)")
                    v_detail = event_service.get_visit_detail(visit_id)
                    v_date = v_detail.get("visit_date") or "?"
                    v_summary = (v_detail.get("summary") or "").strip() or "(無摘要)"
                    self._linked_visit_label.setText(
                        f"【本單已關聯訪廠紀錄】\n日期：{v_date}\n摘要：{v_summary}"
                    )
                    self._linked_visit_label.setVisible(True)
                else:
                    self._rc_group.setTitle("風險控管調查 (單獨異常 / 無訪廠紀錄適用)")
                    self._linked_visit_label.setVisible(False)

                QMessageBox.information(self, "成功", "已成功關聯訪廠紀錄")
            except Exception as exc:
                logger.exception("Failed to update anomaly link")
                QMessageBox.critical(self, "錯誤", f"關聯失敗：{exc}")

    def _clear_same_day_visit_defaults_if_owned(self) -> None:
        current_product_id = (self.product_combo.currentData() or "").strip()
        previous_product_id = str(self._same_day_visit_autofill.get("product_id") or "")
        if previous_product_id and current_product_id == previous_product_id:
            self.product_combo.setCurrentIndex(0)

        previous_work_order = str(
            self._same_day_visit_autofill.get("work_order_no") or ""
        )
        current_work_order = self.outsource_work_order_input.text().strip()
        if previous_work_order and current_work_order == previous_work_order:
            self.outsource_work_order_input.clear()

        previous_qty = self._same_day_visit_autofill.get("batch_qty")
        if previous_qty is not None and self.batch_qty_input.text().strip() == str(previous_qty):
            self.batch_qty_input.clear()

        self._same_day_visit_autofill = {
            "product_id": "",
            "work_order_no": "",
            "batch_qty": None,
        }
        self._same_day_visit_hint_label.setText("")
        self._same_day_visit_hint_label.setVisible(False)

    def _apply_same_day_visit_defaults(self) -> None:
        if self._is_edit:
            return
        supplier_id = (self.supplier_combo.currentData() or "").strip()
        visit_date = self.date_edit.date().toString("yyyy-MM-dd")
        if not supplier_id:
            self._clear_same_day_visit_defaults_if_owned()
            return
        try:
            ref = event_service.get_latest_visit_for_supplier_on_date(
                supplier_id,
                visit_date,
            )
        except Exception:
            logger.exception(
                "get_latest_visit_for_supplier_on_date failed for supplier_id=%s date=%s",
                supplier_id,
                visit_date,
            )
            ref = None
        if ref is None:
            self._clear_same_day_visit_defaults_if_owned()
            return

        applied: list[str] = []
        product_id = str(ref.get("product_id") or "").strip()
        current_product_id = (self.product_combo.currentData() or "").strip()
        previous_product_id = str(self._same_day_visit_autofill.get("product_id") or "")
        if product_id and (
            not current_product_id or current_product_id == previous_product_id
        ):
            if _set_combo_current_data(self.product_combo, product_id):
                self._same_day_visit_autofill["product_id"] = product_id
                applied.append("品名")

        work_order_no = str(ref.get("work_order_no") or "").strip()
        current_work_order = self.outsource_work_order_input.text().strip()
        previous_work_order = str(
            self._same_day_visit_autofill.get("work_order_no") or ""
        )
        if work_order_no and (
            not current_work_order or current_work_order == previous_work_order
        ):
            self.outsource_work_order_input.setText(work_order_no)
            self._same_day_visit_autofill["work_order_no"] = work_order_no
            applied.append("工單")
            self._update_outsource_row_visibility()

        production_qty = int(ref.get("production_qty") or 0)
        current_qty_text = self.batch_qty_input.text().strip()
        previous_qty = self._same_day_visit_autofill.get("batch_qty")
        if production_qty > 0 and (
            not current_qty_text
            or (previous_qty is not None and current_qty_text == str(previous_qty))
        ):
            self.batch_qty_input.setText(str(production_qty))
            self._same_day_visit_autofill["batch_qty"] = production_qty
            applied.append("數量")

        if applied:
            self._same_day_visit_hint_label.setText(
                f"已沿用 {visit_date} 訪廠資料：{'、'.join(applied)}"
            )
            _set_tone(self._same_day_visit_hint_label, "info")
            self._same_day_visit_hint_label.setVisible(True)
        elif not any(self._same_day_visit_autofill.values()):
            self._same_day_visit_hint_label.setText("")
            self._same_day_visit_hint_label.setVisible(False)

    def _on_product_changed(self, _index: int = -1) -> None:
        product_id = (self.product_combo.currentData() or "").strip()
        product_stage = self._product_stage_by_id.get(
            product_id, PRODUCT_STAGE_MASS_PRODUCTION
        )
        self.product_stage_combo.setCurrentText(normalize_product_stage_ui(product_stage))
        self.product_code_input.setText(self._product_code_by_id.get(product_id, ""))
        self._refresh_submit_state()

    def _refresh_submit_state(self) -> None:
        supplier_id = (self.supplier_combo.currentData() or "").strip()
        product_id = (self.product_combo.currentData() or "").strip()
        has_products = self.product_combo.count() > 1
        message = ""
        tone = "info"
        if not supplier_id:
            message = "請先選擇供應商。"
        elif not has_products and not product_id:
            message = "此供應商尚未建立產品，請先到基礎資料新增產品。"
            tone = "warning"
        elif not product_id:
            message = "請選擇產品後再儲存。"
        self._product_guard_label.setText(message)
        _set_tone(self._product_guard_label, tone)
        self._product_guard_label.setVisible(bool(message))
        self.save_button.setEnabled(bool(supplier_id and product_id))

    def _apply_initial_data(self):
        anomaly_date = str(self._initial_data.get("anomaly_date") or "").strip()
        parsed_date = QDate.fromString(anomaly_date, "yyyy-MM-dd")
        if parsed_date.isValid():
            self.date_edit.setDate(parsed_date)
        self._fixed_anomaly_no = str(self._initial_data.get("anomaly_no") or "").strip()
        self._update_anomaly_no_preview()

        supplier_id = str(self._initial_data.get("supplier_id") or "").strip()
        supplier_name = str(self._initial_data.get("supplier_name") or "").strip()
        if supplier_id and not _set_combo_current_data(self.supplier_combo, supplier_id):
            self.supplier_combo.addItem(f"{supplier_name or supplier_id}（目前值）", supplier_id)
            _set_combo_current_data(self.supplier_combo, supplier_id)
        self._on_supplier_changed()

        product_id = str(self._initial_data.get("product_id") or "").strip()
        product_name = str(self._initial_data.get("product_name") or "").strip()
        product_code = str(self._initial_data.get("product_code") or "").strip()
        if product_id and not _set_combo_current_data(self.product_combo, product_id):
            self._product_stage_by_id[product_id] = normalize_product_stage_ui(
                self._initial_data.get("product_stage")
            )
            self._product_code_by_id[product_id] = product_code
            self.product_combo.addItem(f"{product_name or product_id}（目前值）", product_id)
            _set_combo_current_data(self.product_combo, product_id)
        
        if product_id:
            # Sync product code display
            self.product_code_input.setText(self._product_code_by_id.get(product_id, product_code))
        else:
            self.product_code_input.clear()
        self.product_stage_combo.setCurrentText(
            normalize_product_stage_ui(self._initial_data.get("product_stage"))
        )

        self.outsource_work_order_input.setText(
            str(self._initial_data.get("outsource_work_order") or "")
        )
        self.batch_qty_input.setText(str(self._initial_data.get("batch_qty") or ""))
        self.problem_input.setPlainText(str(self._initial_data.get("problem_desc") or ""))
        _set_combo_current_text(self.category_input, str(self._initial_data.get("category") or ""))
        self.responsible_person_input.setText(
            str(self._initial_data.get("responsible_person") or "")
        )
        due_date_value = str(self._initial_data.get("due_date") or "").strip()
        if due_date_value:
            parsed_due = QDate.fromString(due_date_value, "yyyy-MM-dd")
            if parsed_due.isValid():
                self.due_date_check.setChecked(True)
                self.due_date_edit.setDate(parsed_due)
        self.pending_items_input.setPlainText(
            str(self._initial_data.get("pending_items") or "")
        )
        self.is_tech_transfer_check.setChecked(
            bool(self._initial_data.get("is_tech_transfer", False))
        )
        self._update_ref_group_visibility()
        self._update_outsource_row_visibility()

        def _get_rc_val(key: str) -> str:
            val = str(self._initial_data.get(key) or "未確認")
            if val == "unconfirmed": return "未確認"
            if val == "confirmed": return "已確認"
            if val == "na": return "不適用"
            return val

        _set_combo_current_text(self.rc_supplier_inv_combo, _get_rc_val("rc_supplier_inventory"))
        _set_combo_current_text(self.rc_supplier_wip_combo, _get_rc_val("rc_supplier_wip"))
        _set_combo_current_text(self.rc_in_transit_combo, _get_rc_val("rc_in_transit"))
        _set_combo_current_text(self.rc_internal_inv_combo, _get_rc_val("rc_internal_inventory"))

        self._linked_visit_label.setVisible(False)
        self._linked_visit_label.setText("")

        visit_id = str(self._initial_data.get("visit_id") or "").strip()
        if visit_id:
            self._rc_group.setTitle("風險控管調查 (已關聯訪廠)")
            try:
                v_detail = event_service.get_visit_detail(visit_id)
                v_date = v_detail.get("visit_date") or "?"
                v_summary = (v_detail.get("summary") or "").strip() or "(無摘要)"
                self._linked_visit_label.setText(
                    f"【本單已關聯訪廠紀錄】\n日期：{v_date}\n摘要：{v_summary}"
                )
                self._linked_visit_label.setVisible(True)
                self.unlink_visit_button.setVisible(True)
            except Exception:
                logger.exception("Failed to load linked visit %s", visit_id)
                self._linked_visit_label.setText("【本單已關聯訪廠紀錄】(無法載入詳細資訊)")
                self._linked_visit_label.setVisible(True)
        else:
            self._rc_group.setTitle("風險控管調查 (單獨異常 / 無訪廠紀錄適用)")

        self._refresh_submit_state()
        if self._is_edit:
            self.attachment_editor.load_existing_attachments(self._anomaly_id)


    def _on_submit(self):
        product_id = (self.product_combo.currentData() or "").strip()
        if not product_id:
            QMessageBox.warning(self, "驗證失敗", localize_popup_message("產品為必填"))
            return
        due_date_value = ""
        if self.due_date_check.isChecked():
            due_date_value = self.due_date_edit.date().toString("yyyy-MM-dd")
        payload = {
            "anomaly_date": self.date_edit.date().toString("yyyy-MM-dd"),
            "supplier_id": (self.supplier_combo.currentData() or "").strip(),
            "product_id": product_id,
            "problem_desc": self.problem_input.toPlainText().strip(),
            "category": self.category_input.currentText().strip(),
            "outsource_work_order": self.outsource_work_order_input.text().strip(),
            "batch_qty": int(self.batch_qty_input.text().strip() or 0),
            "responsible_person": self.responsible_person_input.text().strip(),
            "due_date": due_date_value,
            "pending_items": self.pending_items_input.toPlainText().strip(),
            "sync_visit": self.sync_visit_check.isChecked(),
            "visit_summary": "由新增異常流程同步建立。",
            "rc_supplier_inventory": self.rc_supplier_inv_combo.currentText(),
            "rc_supplier_wip": self.rc_supplier_wip_combo.currentText(),
            "rc_in_transit": self.rc_in_transit_combo.currentText(),
            "rc_internal_inventory": self.rc_internal_inv_combo.currentText(),
            "is_tech_transfer": self.is_tech_transfer_check.isChecked(),
        }
        try:
            if self._is_edit:
                event_service.update_anomaly(self._anomaly_id, payload)
                self.attachment_editor.save_to_anomaly(self._anomaly_id)
                QMessageBox.information(self, "成功", localize_popup_message("異常資料已更新"))
            else:
                result = event_service.create_anomaly_with_visit_link(payload)
                anomaly_id = str(result.get("anomaly_id") or "").strip()
                if anomaly_id:
                    self.attachment_editor.save_to_anomaly(anomaly_id)
                visit_action = result.get("visit_action", "none")
                if visit_action == "created":
                    visit_text = "訪廠已新建"
                elif visit_action == "reused":
                    visit_text = "訪廠已重用（同供應商同日期）"
                else:
                    visit_text = "未同步訪廠"
                QMessageBox.information(
                    self,
                    "成功",
                    localize_popup_message(f"已建立異常單：{result['anomaly_no']}\n{visit_text}"),
                )
            self.accept()
        except ValueError as exc:
            QMessageBox.warning(self, "驗證失敗", localize_exception(exc))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "錯誤",
                localize_popup_message(f"建立異常失敗：{localize_exception(exc)}"),
            )


class NewVisitDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        visit_id: str | None = None,
        initial_data: dict | None = None,
        read_only: bool = False,
        focus_defect_note: bool = False,
    ):
        super().__init__(parent)
        self._visit_id = (visit_id or "").strip()
        self._is_edit = bool(self._visit_id)
        self._read_only = read_only
        self._initial_data = initial_data or {}
        self._product_stage_by_id: dict[str, str] = {}
        self._product_code_by_id: dict[str, str] = {}
        self._product_items: list[dict] = []
        self._extra_section_editors: list[ProductSectionEditor] = []
        self._focus_defect_note = focus_defect_note
        self._tech_transfer_groups: dict[str, QButtonGroup] = {}
        self._tech_transfer_cards: dict[str, TechTransferCard] = {}
        self._syncing_tech_transfer = False
        self.setWindowTitle("預覽訪廠" if self._read_only else ("編輯訪廠" if self._is_edit else "新增訪廠"))
        self.setMinimumWidth(760)
        self.setMaximumWidth(FORM_MAX_WIDTH)
        self._setup_ui()
        if self._is_edit:
            self.confirm_supplier_anomaly_check.setVisible(False)
        self._load_suppliers()
        if self._is_edit:
            self._apply_initial_data()
        elif self._focus_defect_note:
            self.visit_defect_table.add_empty_note()
            self.tabs.setCurrentIndex(2)
            self.visit_defect_table.setFocus()
        if self._read_only:
            self._apply_read_only()

    def _setup_ui(self):
        # 1. 控制項初始化
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.supplier_combo = QComboBox()
        self.supplier_combo.currentIndexChanged.connect(self._on_supplier_changed)
        self.product_combo = QComboBox()
        self.product_combo.currentIndexChanged.connect(self._on_product_changed)
        self.product_stage_combo = QComboBox()
        self.product_stage_combo.addItems(PRODUCT_STAGE_OPTIONS)
        self.product_stage_combo.setCurrentText(PRODUCT_STAGE_MASS_PRODUCTION)
        self.product_stage_combo.setEnabled(False)
        self.product_code_input = QLineEdit()
        self.product_code_input.setReadOnly(True)
        self.visitor_input = QLineEdit()
        self.visitor_input.setPlaceholderText("訪廠人員（選填）")
        self.summary_input = QTextEdit()
        self.summary_input.setPlaceholderText("活動摘要（選填）")
        _set_text_edit_visible_rows(self.summary_input, 5)

        self.work_order_input = QLineEdit()
        self.time_slot_input = QLineEdit()
        self.time_slot_input.setPlaceholderText("上午 / 下午 / 產線時段")
        self.qty_input = QLineEdit()
        self.qty_input.setValidator(QIntValidator(0, 10_000_000))
        self.tech_transfer_check = QCheckBox("已技轉")
        self.tech_transfer_check.toggled.connect(self._on_tech_transfer_toggled)

        # 2. 建立分頁
        self.tabs = QTabWidget()
        self.tabs.setObjectName("VisitFormTabs")

        # --- Tab 1: 基本資訊 ---
        tab_basic = QWidget()
        basic_layout = QVBoxLayout(tab_basic)
        basic_layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        form = QFormLayout()
        form.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        form.setVerticalSpacing(FORM_VERTICAL_SPACING)

        product_row = QWidget()
        pr_layout = QHBoxLayout(product_row)
        pr_layout.setContentsMargins(0, 0, 0, 0)
        pr_layout.setSpacing(INLINE_SPACING)
        pr_layout.addWidget(self.product_combo, 3)
        pr_layout.addWidget(self.product_stage_combo, 1)

        form.addRow(
            _make_paired_form_row(
                "VisitBasicDateVisitorRow",
                RequiredFieldLabel("日期"),
                self.date_edit,
                "訪廠人員",
                self.visitor_input,
            )
        )
        form.addRow(RequiredFieldLabel("供應商"), self.supplier_combo)
        form.addRow("主要產品", product_row)
        form.addRow("料號", self.product_code_input)
        
        self._product_guard_label = QLabel("")
        self._product_guard_label.setProperty("role", "messageText")
        self._product_guard_label.setVisible(False)
        form.addRow("", self._product_guard_label)
        form.addRow("活動摘要", self.summary_input)
        basic_layout.addLayout(form)
        self.tabs.addTab(tab_basic, "基本資訊")

        # --- Tab 2: 進階與技轉 ---
        tab_adv = QWidget()
        adv_layout = QVBoxLayout(tab_adv)
        adv_layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        
        adv_form = QFormLayout()
        adv_form.addRow(
            _make_paired_form_row(
                "VisitAdvancedTimeOrderRow",
                "時段",
                self.time_slot_input,
                "工單",
                self.work_order_input,
            )
        )
        adv_form.addRow(
            _make_paired_form_row(
                "VisitAdvancedQtyTransferRow",
                "數量",
                self.qty_input,
                None,
                self.tech_transfer_check,
            )
        )
        adv_layout.addLayout(adv_form)

        cards_container = QWidget()
        cards_grid = QGridLayout(cards_container)
        cards_grid.setContentsMargins(0, 4, 0, 4)
        cards_grid.setHorizontalSpacing(REF_GRID_SPACING_H)
        cards_grid.setVerticalSpacing(REF_GRID_SPACING_V)
        for idx, (field_key, field_label) in enumerate(VISIT_TECH_TRANSFER_ITEMS):
            card = TechTransferCard(field_key, field_label, self)
            card.yes_radio.toggled.connect(self._on_any_tech_transfer_item_toggled)
            cards_grid.addWidget(card, idx // 3, idx % 3)
            self._tech_transfer_cards[field_key] = card
            self._tech_transfer_groups[field_key] = card.group
        
        adv_layout.addWidget(QLabel("技轉要目確認"))
        adv_layout.addWidget(cards_container)
        adv_layout.addStretch(1)
        self.tabs.addTab(tab_adv, "進階與技轉")

        # --- Tab 3: 輕量缺失紀錄 ---
        tab_defects = QWidget()
        defect_layout = QVBoxLayout(tab_defects)
        defect_layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        defect_layout.setSpacing(ROW_GAP)

        visit_defect_group = QGroupBox("訪廠層級缺失（不限定產品）")
        visit_defect_layout = QVBoxLayout(visit_defect_group)
        self.visit_defect_table = DefectNoteTable()
        self.confirm_supplier_anomaly_check = QCheckBox("確認後建立正式供應商異常事件")
        self.confirm_supplier_anomaly_check.setObjectName("VisitConfirmSupplierAnomalyCheck")
        self.confirm_supplier_anomaly_check.setToolTip(
            "僅將訪廠/稽核缺失轉成供應商異常事件，不寫入倉庫不合格品追蹤。"
        )
        visit_defect_buttons = QHBoxLayout()
        btn_add_visit_defect = QPushButton("新增缺失")
        btn_add_visit_defect.setProperty("variant", "secondary")
        btn_add_visit_defect.clicked.connect(self.visit_defect_table.add_empty_note)
        btn_remove_visit_defect = QPushButton("刪除缺失")
        btn_remove_visit_defect.setProperty("tone", "warning")
        btn_remove_visit_defect.clicked.connect(self.visit_defect_table.remove_selected_note)
        visit_defect_buttons.addWidget(btn_add_visit_defect)
        visit_defect_buttons.addWidget(btn_remove_visit_defect)
        visit_defect_buttons.addStretch(1)
        visit_defect_layout.addWidget(self.visit_defect_table)
        visit_defect_layout.addLayout(visit_defect_buttons)
        visit_defect_layout.addWidget(self.confirm_supplier_anomaly_check)

        primary_defect_group = QGroupBox("主要產品缺失")
        primary_defect_layout = QVBoxLayout(primary_defect_group)
        self.primary_defect_table = DefectNoteTable()
        primary_defect_buttons = QHBoxLayout()
        btn_add_primary_defect = QPushButton("新增缺失")
        btn_add_primary_defect.setProperty("variant", "secondary")
        btn_add_primary_defect.clicked.connect(self.primary_defect_table.add_empty_note)
        btn_remove_primary_defect = QPushButton("刪除缺失")
        btn_remove_primary_defect.setProperty("tone", "warning")
        btn_remove_primary_defect.clicked.connect(self.primary_defect_table.remove_selected_note)
        primary_defect_buttons.addWidget(btn_add_primary_defect)
        primary_defect_buttons.addWidget(btn_remove_primary_defect)
        primary_defect_buttons.addStretch(1)
        primary_defect_layout.addWidget(self.primary_defect_table)
        primary_defect_layout.addLayout(primary_defect_buttons)

        extra_header = QHBoxLayout()
        extra_header.addWidget(QLabel("其他產品區段"))
        extra_header.addStretch(1)
        btn_add_section = QPushButton("新增產品區段")
        btn_add_section.setProperty("variant", "secondary")
        btn_add_section.clicked.connect(self._add_extra_product_section)
        btn_remove_section = QPushButton("刪除最後區段")
        btn_remove_section.setProperty("tone", "warning")
        btn_remove_section.clicked.connect(self._remove_last_extra_product_section)
        extra_header.addWidget(btn_add_section)
        extra_header.addWidget(btn_remove_section)
        self.extra_sections_container = QWidget()
        self.extra_sections_layout = QVBoxLayout(self.extra_sections_container)
        self.extra_sections_layout.setContentsMargins(0, 0, 0, 0)
        self.extra_sections_layout.setSpacing(ROW_GAP)

        defect_layout.addWidget(visit_defect_group)
        defect_layout.addWidget(primary_defect_group)
        defect_layout.addLayout(extra_header)
        defect_layout.addWidget(self.extra_sections_container)
        defect_layout.addStretch(1)
        self.tabs.addTab(tab_defects, "缺失紀錄")

        # 3. 按鈕與佈局
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        self.save_button = _style_dialog_buttons(buttons)
        self._button_box = buttons
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)
        
        _apply_dialog_layout(self, self.tabs, buttons)

    def _apply_read_only(self) -> None:
        """Disable all input widgets to prevent modification."""
        self.date_edit.setEnabled(False)
        self.supplier_combo.setEnabled(False)
        self.product_combo.setEnabled(False)
        self.product_stage_combo.setEnabled(False)
        self.product_code_input.setReadOnly(True)
        self.visitor_input.setReadOnly(True)
        self.summary_input.setReadOnly(True)
        self.work_order_input.setReadOnly(True)
        self.time_slot_input.setReadOnly(True)
        self.qty_input.setReadOnly(True)
        self.tech_transfer_check.setEnabled(False)
        self.visit_defect_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.primary_defect_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.confirm_supplier_anomaly_check.setEnabled(False)
        for editor in self._extra_section_editors:
            editor.set_read_only()

        # Tech transfer cards
        for card in self._tech_transfer_cards.values():
            card.yes_radio.setEnabled(False)
            card.no_radio.setEnabled(False)
            card.na_radio.setEnabled(False)

        # Change Save button to Close and hide Cancel (redundant in read-only mode)
        if self.save_button:
            self.save_button.setText("關閉")
            self._button_box.accepted.disconnect(self._on_submit)
            self._button_box.accepted.connect(self.accept)
        cancel_btn = self._button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setVisible(False)

    def _add_extra_product_section(self, data: dict | None = None) -> ProductSectionEditor:
        editor = ProductSectionEditor(f"產品區段 {len(self._extra_section_editors) + 2}", self)
        editor.set_products(self._product_items)
        if data:
            editor.load_data(data)
        if self._read_only:
            editor.set_read_only()
        self._extra_section_editors.append(editor)
        self.extra_sections_layout.addWidget(editor)
        self._refresh_submit_state()
        return editor

    def _remove_last_extra_product_section(self) -> None:
        if not self._extra_section_editors or self._read_only:
            return
        editor = self._extra_section_editors.pop()
        self.extra_sections_layout.removeWidget(editor)
        editor.deleteLater()
        self._refresh_submit_state()

    def _load_suppliers(self):
        suppliers = (
            event_service.list_suppliers(include_inactive=True)
            if self._is_edit
            else event_service.list_active_suppliers()
        )
        self.supplier_combo.blockSignals(True)
        self.supplier_combo.clear()
        self.supplier_combo.addItem("請選擇供應商", "")
        for item in suppliers:
            name = item["supplier_name"]
            if self._is_edit and not item.get("is_active", True):
                name = f"{name}（停用）"
            self.supplier_combo.addItem(name, item["id"])
        self.supplier_combo.blockSignals(False)
        self._on_supplier_changed()

    def _on_supplier_changed(self):
        supplier_id = (self.supplier_combo.currentData() or "").strip()
        products = event_service.list_active_products_for_supplier(supplier_id)
        self._product_items = list(products)
        self._product_stage_by_id = {}
        self._product_code_by_id = {}
        self.product_combo.clear()
        self.product_combo.addItem("請選擇產品 *", "")
        for item in products:
            product_id = str(item.get("id") or "").strip()
            self.product_combo.addItem(_product_label(item), product_id)
            if product_id:
                self._product_stage_by_id[product_id] = normalize_product_stage_ui(
                    item.get("product_stage")
                )
                self._product_code_by_id[product_id] = str(item.get("product_code") or "").strip()
        self._on_product_changed()
        for editor in self._extra_section_editors:
            editor.set_products(products)
        self._refresh_submit_state()

    def _on_product_changed(self, _index: int = -1) -> None:
        product_id = (self.product_combo.currentData() or "").strip()
        product_stage = self._product_stage_by_id.get(
            product_id, PRODUCT_STAGE_MASS_PRODUCTION
        )
        self.product_stage_combo.setCurrentText(normalize_product_stage_ui(product_stage))
        self.product_code_input.setText(self._product_code_by_id.get(product_id, ""))
        self._refresh_submit_state()

    def _refresh_submit_state(self) -> None:
        supplier_id = (self.supplier_combo.currentData() or "").strip()
        product_id = (self.product_combo.currentData() or "").strip()
        has_products = self.product_combo.count() > 1
        message = ""
        tone = "info"
        if not supplier_id:
            message = "請先選擇供應商。"
        elif not has_products and not product_id:
            message = "此供應商尚未建立產品；仍可先記錄訪廠層級缺失。"
            tone = "info"
        elif not product_id:
            message = "可選擇主要產品，或直接在缺失紀錄分頁新增訪廠層級缺失。"
        self._product_guard_label.setText(message)
        _set_tone(self._product_guard_label, tone)
        self._product_guard_label.setVisible(bool(message))
        if self.save_button is not None:
            self.save_button.setEnabled(bool(supplier_id))

    def _apply_initial_data(self):
        visit_date = str(self._initial_data.get("visit_date") or "").strip()
        parsed_date = QDate.fromString(visit_date, "yyyy-MM-dd")
        if parsed_date.isValid():
            self.date_edit.setDate(parsed_date)

        supplier_id = str(self._initial_data.get("supplier_id") or "").strip()
        supplier_name = str(self._initial_data.get("supplier_name") or "").strip()
        if supplier_id and not _set_combo_current_data(self.supplier_combo, supplier_id):
            self.supplier_combo.addItem(f"{supplier_name or supplier_id}（目前值）", supplier_id)
            _set_combo_current_data(self.supplier_combo, supplier_id)
        self._on_supplier_changed()

        product_id = str(self._initial_data.get("product_id") or "").strip()
        product_name = str(self._initial_data.get("product_name") or "").strip()
        product_code = str(self._initial_data.get("product_code") or "").strip()
        if product_id and not _set_combo_current_data(self.product_combo, product_id):
            self._product_stage_by_id[product_id] = normalize_product_stage_ui(
                self._initial_data.get("product_stage")
            )
            self._product_code_by_id[product_id] = product_code
            self.product_combo.addItem(f"{product_name or product_id}（目前值）", product_id)
            _set_combo_current_data(self.product_combo, product_id)
        
        if product_id:
            self.product_code_input.setText(self._product_code_by_id.get(product_id, product_code))
        else:
            self.product_code_input.clear()
            
        self.product_stage_combo.setCurrentText(
            normalize_product_stage_ui(self._initial_data.get("product_stage"))
        )

        self.visitor_input.setText(str(self._initial_data.get("visitor_name") or ""))
        self.summary_input.setPlainText(str(self._initial_data.get("summary") or ""))
        self.work_order_input.setText(str(self._initial_data.get("work_order_no") or ""))
        self.time_slot_input.setText(str(self._initial_data.get("time_slot") or ""))
        self.qty_input.setText(str(self._initial_data.get("production_qty") or ""))
        sections = list(self._initial_data.get("product_sections") or [])
        visit_level_notes = [
            item
            for item in list(self._initial_data.get("defect_notes") or [])
            if not str(item.get("visit_product_section_id") or "").strip()
        ]
        self.visit_defect_table.load_notes(visit_level_notes)
        if sections:
            first_section = sections[0]
            self.primary_defect_table.load_notes(
                list(first_section.get("defect_notes") or [])
            )
            section_time = str(first_section.get("time_slot") or "").strip()
            if section_time:
                self.time_slot_input.setText(section_time)
            section_summary = str(first_section.get("summary") or "").strip()
            if section_time or section_summary:
                prefix = f"[{section_time}] " if section_time else ""
                current_summary = self.summary_input.toPlainText().strip()
                merged = "\n".join(
                    part
                    for part in (current_summary, f"{prefix}{section_summary}".strip())
                    if part
                )
                self.summary_input.setPlainText(merged)
            for section in sections[1:]:
                self._add_extra_product_section(section)
        initial_states: dict[str, str] = {}
        for key, _ in VISIT_TECH_TRANSFER_ITEMS:
            state_val = str(self._initial_data.get(f"{key}_state") or "").strip().lower()
            if state_val in (
                TECH_TRANSFER_STATE_YES,
                TECH_TRANSFER_STATE_NO,
                TECH_TRANSFER_STATE_NA,
            ):
                initial_states[key] = state_val
            else:
                initial_states[key] = (
                    TECH_TRANSFER_STATE_YES
                    if bool(self._initial_data.get(key, False))
                    else TECH_TRANSFER_STATE_NO
                )
        self._apply_tech_transfer_payload(
            tech_transfer=bool(self._initial_data.get("tech_transfer", False)),
            item_states=initial_states,
        )
        self._refresh_submit_state()

    def _set_tech_transfer_item(self, field_key: str, has_value: bool) -> None:
        # Legacy bool setter — preserved for callers passing bools.
        card = self._tech_transfer_cards.get(field_key)
        if card is not None:
            card.set_value(has_value)
            return
        group = self._tech_transfer_groups.get(field_key)
        if group is None:
            return
        button = group.button(1 if has_value else 0)
        if button is not None:
            button.setChecked(True)

    def _set_tech_transfer_state(self, field_key: str, state: str) -> None:
        card = self._tech_transfer_cards.get(field_key)
        if card is not None:
            card.set_state(state)

    def _get_tech_transfer_item(self, field_key: str) -> bool:
        # Legacy bool getter for any caller that still expects True/False.
        return self._get_tech_transfer_state(field_key) == TECH_TRANSFER_STATE_YES

    def _get_tech_transfer_state(self, field_key: str) -> str:
        card = self._tech_transfer_cards.get(field_key)
        if card is not None:
            return card.get_state()
        group = self._tech_transfer_groups.get(field_key)
        if group is None:
            return TECH_TRANSFER_STATE_NO
        checked = group.checkedButton()
        if checked is None:
            return TECH_TRANSFER_STATE_NO
        btn_id = group.id(checked)
        if btn_id == 1:
            return TECH_TRANSFER_STATE_YES
        if btn_id == 2:
            return TECH_TRANSFER_STATE_NA
        return TECH_TRANSFER_STATE_NO

    def _normalized_tech_transfer_payload(
        self, *, tech_transfer: bool, item_states: dict[str, str]
    ) -> dict:
        normalized_states = {
            key: (
                item_states.get(key)
                if item_states.get(key)
                in (TECH_TRANSFER_STATE_YES, TECH_TRANSFER_STATE_NO, TECH_TRANSFER_STATE_NA)
                else TECH_TRANSFER_STATE_NO
            )
            for key, _ in VISIT_TECH_TRANSFER_ITEMS
        }
        normalized_tech_transfer = bool(tech_transfer) or any(
            v == TECH_TRANSFER_STATE_YES for v in normalized_states.values()
        )
        if not normalized_tech_transfer:
            normalized_states = {
                key: TECH_TRANSFER_STATE_NO for key, _ in VISIT_TECH_TRANSFER_ITEMS
            }
        result: dict = {key: normalized_states[key] for key in normalized_states}
        # Preserve the legacy boolean-shaped keys callers used to read from this
        # mapping; the new `states` key is the canonical tri-state map.
        for key, _ in VISIT_TECH_TRANSFER_ITEMS:
            result[f"_{key}_bool"] = (
                normalized_states[key] == TECH_TRANSFER_STATE_YES
            )
        result["tech_transfer"] = normalized_tech_transfer
        result["states"] = dict(normalized_states)
        # Backwards-compat boolean keys (drop underscore prefix) for older
        # callers; equal to states[key] == 'yes'.
        for key, _ in VISIT_TECH_TRANSFER_ITEMS:
            result.pop(f"_{key}_bool", None)
            result[key] = normalized_states[key] == TECH_TRANSFER_STATE_YES
        return result

    def _apply_tech_transfer_payload(
        self,
        *,
        tech_transfer: bool,
        item_states: dict[str, str] | None = None,
        item_flags: dict[str, bool] | None = None,
    ) -> None:
        if item_states is None:
            states = {
                key: (
                    TECH_TRANSFER_STATE_YES
                    if (item_flags or {}).get(key)
                    else TECH_TRANSFER_STATE_NO
                )
                for key, _ in VISIT_TECH_TRANSFER_ITEMS
            }
        else:
            states = dict(item_states)
        normalized = self._normalized_tech_transfer_payload(
            tech_transfer=tech_transfer,
            item_states=states,
        )
        self._syncing_tech_transfer = True
        try:
            self.tech_transfer_check.setChecked(normalized["tech_transfer"])
            for key, _ in VISIT_TECH_TRANSFER_ITEMS:
                self._set_tech_transfer_state(key, normalized["states"][key])
        finally:
            self._syncing_tech_transfer = False

    def _on_tech_transfer_toggled(self, checked: bool) -> None:
        if self._syncing_tech_transfer:
            return
        if checked:
            return
        self._syncing_tech_transfer = True
        try:
            for key, _ in VISIT_TECH_TRANSFER_ITEMS:
                self._set_tech_transfer_item(key, False)
        finally:
            self._syncing_tech_transfer = False

    def _on_any_tech_transfer_item_toggled(self, checked: bool) -> None:
        if not checked or self._syncing_tech_transfer:
            return
        if self.tech_transfer_check.isChecked():
            return
        self._syncing_tech_transfer = True
        try:
            self.tech_transfer_check.setChecked(True)
        finally:
            self._syncing_tech_transfer = False

    def _on_submit(self):
        product_id = (self.product_combo.currentData() or "").strip()
        try:
            visit_level_notes = self.visit_defect_table.notes()
            primary_notes = self.primary_defect_table.notes()
            product_sections: list[dict] = []
            if (
                product_id
                or self.time_slot_input.text().strip()
                or self.work_order_input.text().strip()
                or self.qty_input.text().strip()
                or primary_notes
            ):
                if not product_id:
                    QMessageBox.warning(self, "驗證失敗", "主要產品區段需選擇品名")
                    return
                product_sections.append(
                    {
                        "product_id": product_id,
                        "product_name": self.product_combo.currentText().strip(),
                        "product_stage": self.product_stage_combo.currentText(),
                        "product_code": self.product_code_input.text().strip(),
                        "time_slot": self.time_slot_input.text().strip(),
                        "work_order_no": self.work_order_input.text().strip(),
                        "production_qty": int(self.qty_input.text().strip() or 0),
                        "summary": "",
                        "defect_notes": primary_notes,
                        "sort_order": 0,
                    }
                )
            for editor in self._extra_section_editors:
                section = editor.section_data()
                if section is not None:
                    section["sort_order"] = len(product_sections)
                    product_sections.append(section)
            if self.confirm_supplier_anomaly_check.isChecked():
                self._validate_supplier_anomaly_conversion(
                    product_id=product_id,
                    visit_level_notes=visit_level_notes,
                    product_sections=product_sections,
                )
            if not product_sections and not visit_level_notes:
                QMessageBox.warning(
                    self,
                    "驗證失敗",
                    "請至少選擇一個產品區段，或新增一筆訪廠層級缺失。",
                )
                return
        except ValueError as exc:
            QMessageBox.warning(self, "驗證失敗", str(exc))
            return
        tech_payload = self._normalized_tech_transfer_payload(
            tech_transfer=self.tech_transfer_check.isChecked(),
            item_states={
                key: self._get_tech_transfer_state(key)
                for key, _ in VISIT_TECH_TRANSFER_ITEMS
            },
        )
        payload = {
            "visit_date": self.date_edit.date().toString("yyyy-MM-dd"),
            "supplier_id": (self.supplier_combo.currentData() or "").strip(),
            "product_id": product_id,
            "visitor_name": self.visitor_input.text().strip(),
            "summary": self.summary_input.toPlainText().strip(),
            "time_slot": self.time_slot_input.text().strip(),
            "work_order_no": self.work_order_input.text().strip(),
            "production_qty": int(self.qty_input.text().strip() or 0),
            "product_sections": product_sections,
            "defect_notes": visit_level_notes,
            "tech_transfer": tech_payload["tech_transfer"],
            "tech_transfer_doc": tech_payload["tech_transfer_doc"],
            "carrier_requirement": tech_payload["carrier_requirement"],
            "dispensing_process": tech_payload["dispensing_process"],
            "functional_test": tech_payload["functional_test"],
            "packaging_requirement": tech_payload["packaging_requirement"],
            "tech_transfer_states": tech_payload["states"],
        }
        try:
            if self._is_edit:
                event_service.update_visit(self._visit_id, payload)
                QMessageBox.information(self, "成功", localize_popup_message("訪廠紀錄已更新"))
            else:
                visit_id = event_service.create_visit(payload)
                created_anomalies = self._create_confirmed_supplier_anomalies(
                    visit_id=visit_id,
                    payload=payload,
                    visit_level_notes=visit_level_notes,
                    product_sections=product_sections,
                )
                if created_anomalies:
                    QMessageBox.information(
                        self,
                        "成功",
                        localize_popup_message(
                            f"訪廠紀錄已完成，並建立 {created_anomalies} 筆正式供應商異常事件"
                        ),
                    )
                else:
                    QMessageBox.information(self, "成功", localize_popup_message("訪廠紀錄已完成"))
            self.accept()
        except ValueError as exc:
            QMessageBox.warning(self, "驗證失敗", localize_exception(exc))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "錯誤",
                localize_popup_message(f"建立訪廠失敗：{localize_exception(exc)}"),
            )

    def _validate_supplier_anomaly_conversion(
        self,
        *,
        product_id: str,
        visit_level_notes: list[dict],
        product_sections: list[dict],
    ) -> None:
        if not (visit_level_notes or any(section.get("defect_notes") for section in product_sections)):
            return
        if visit_level_notes and not product_id:
            raise ValueError("建立正式供應商異常事件需選擇主要產品。")
        for section in product_sections:
            if section.get("defect_notes") and not str(section.get("product_id") or "").strip():
                raise ValueError("建立正式供應商異常事件需選擇缺失所屬產品。")

    def _create_confirmed_supplier_anomalies(
        self,
        *,
        visit_id: str,
        payload: dict,
        visit_level_notes: list[dict],
        product_sections: list[dict],
    ) -> int:
        if self._is_edit or not self.confirm_supplier_anomaly_check.isChecked():
            return 0
        count = 0
        for note in visit_level_notes:
            event_service.create_anomaly_with_visit_link(
                {
                    "visit_id": visit_id,
                    "sync_visit": False,
                    "anomaly_date": payload["visit_date"],
                    "supplier_id": payload["supplier_id"],
                    "product_id": payload["product_id"],
                    "product_stage": self.product_stage_combo.currentText(),
                    "problem_desc": note.get("defect_desc", ""),
                    "pending_items": note.get("improvement_desc", ""),
                    "category": "訪廠/稽核缺失",
                    "visit_summary": payload.get("summary", ""),
                }
            )
            count += 1
        for section in product_sections:
            section_product_id = str(section.get("product_id") or "").strip()
            for note in section.get("defect_notes") or []:
                event_service.create_anomaly_with_visit_link(
                    {
                        "visit_id": visit_id,
                        "sync_visit": False,
                        "anomaly_date": payload["visit_date"],
                        "supplier_id": payload["supplier_id"],
                        "product_id": section_product_id,
                        "product_stage": section.get("product_stage") or PRODUCT_STAGE_MASS_PRODUCTION,
                        "problem_desc": note.get("defect_desc", ""),
                        "pending_items": note.get("improvement_desc", ""),
                        "category": "訪廠/稽核缺失",
                        "outsource_work_order": section.get("work_order_no", ""),
                        "batch_qty": section.get("production_qty", 0),
                        "visit_summary": payload.get("summary", ""),
                    }
                )
                count += 1
        return count


class CloseAnomalyDialog(QDialog):
    def __init__(self, anomaly_id: str, problem_desc: str, parent=None):
        super().__init__(parent)
        self.anomaly_id = anomaly_id
        self.problem_desc = problem_desc
        self.setWindowTitle("異常結案")
        self.setMinimumWidth(720)
        self.setMaximumWidth(FORM_MAX_WIDTH)
        self._setup_ui()
        self.attachment_editor.load_existing_attachments(self.anomaly_id)
        self._update_validation()

    def _setup_ui(self):
        # 1. 控制項初始化
        self.problem_view = QTextEdit()
        self.problem_view.setReadOnly(True)
        self.problem_view.setPlainText(self.problem_desc)
        self.problem_view.setMinimumHeight(240)

        self.improvement_input = QTextEdit()
        self.improvement_input.setPlaceholderText("請輸入改善內容（必填）")
        self.improvement_input.setFixedHeight(240)

        self.improvement_counter = QLabel(f"0 / {IMPROVEMENT_DESC_MAX_LEN}")
        self.improvement_counter.setProperty("role", "counterText")
        self.improvement_counter.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        self.closer_input = QLineEdit()
        self.closer_input.setPlaceholderText("請輸入結案人員姓名（必填）")

        self.root_cause_combo = QComboBox()
        self.root_cause_combo.setEditable(True)
        for option in ROOT_CAUSE_CATEGORY_OPTIONS:
            self.root_cause_combo.addItem(option)

        self.attachment_editor = AttachmentEditor(self)

        # 2. 建立分頁
        self.tabs = QTabWidget()
        
        # --- Tab 1: 改善處理 ---
        tab_action = QWidget()
        action_layout = QVBoxLayout(tab_action)
        action_layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        
        form = QFormLayout()
        form.addRow(RequiredFieldLabel("改善內容"), self.improvement_input)
        form.addRow("", self.improvement_counter)
        form.addRow(
            _make_paired_form_row(
                "CloseAnomalyCloserCauseRow",
                RequiredFieldLabel("結案人員"),
                self.closer_input,
                "原因分類",
                self.root_cause_combo,
            )
        )
        action_layout.addLayout(form)
        action_layout.addStretch(1)
        self.tabs.addTab(tab_action, "改善處理")

        # --- Tab 2: 現場照片與回顧 ---
        tab_media = QWidget()
        media_layout = QVBoxLayout(tab_media)
        media_layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        media_layout.addWidget(QLabel("原始問題描述："))
        media_layout.addWidget(self.problem_view)
        media_layout.addWidget(QLabel("現場照片附件："))
        media_layout.addWidget(self.attachment_editor)
        self.tabs.addTab(tab_media, "Context & 照片")

        # 3. 按鈕與佈局
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        self._save_button = _style_dialog_buttons(buttons)
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)
        
        _apply_dialog_layout(self, self.tabs, buttons)

        self.improvement_input.textChanged.connect(self._update_validation)
        self.closer_input.textChanged.connect(self._update_validation)


    def _update_validation(self) -> None:
        text = self.improvement_input.toPlainText()
        length = len(text)
        over_limit = length > IMPROVEMENT_DESC_MAX_LEN
        self.improvement_counter.setText(
            f"{length} / {IMPROVEMENT_DESC_MAX_LEN}"
        )
        _set_tone(self.improvement_counter, "danger" if over_limit else "normal")
        valid = (
            bool(text.strip())
            and not over_limit
            and bool(self.closer_input.text().strip())
        )
        if self._save_button is not None:
            self._save_button.setEnabled(valid)

    def _on_submit(self):
        text = self.improvement_input.toPlainText().strip()
        closer = self.closer_input.text().strip()
        root_cause = self.root_cause_combo.currentText().strip()
        try:
            event_service.close_anomaly(
                self.anomaly_id,
                text,
                closed_by=closer,
                root_cause_category=root_cause,
            )
            self.attachment_editor.save_to_anomaly(self.anomaly_id)
            QMessageBox.information(self, "成功", localize_popup_message("異常已結案"))
            self.accept()
        except ValueError as exc:
            QMessageBox.warning(self, "驗證失敗", localize_exception(exc))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "錯誤",
                localize_popup_message(f"結案失敗：{localize_exception(exc)}"),
            )
