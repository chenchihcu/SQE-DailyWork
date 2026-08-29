from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QVBoxLayout,
)

from services import global_search_service
from ui.layout_constants import (
    GLOBAL_SEARCH_DIALOG_MARGINS,
    GLOBAL_SEARCH_DIALOG_MIN_WIDTH,
    GLOBAL_SEARCH_DIALOG_SPACING,
)


logger = logging.getLogger(__name__)


class GlobalSearchDialog(QDialog):
    """Compact Ctrl+K search surface with source-aware routing."""

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent or main_window)
        self.main_window = main_window
        self.setWindowTitle("全域搜尋")
        self.setMinimumWidth(GLOBAL_SEARCH_DIALOG_MIN_WIDTH)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*GLOBAL_SEARCH_DIALOG_MARGINS)
        layout.setSpacing(GLOBAL_SEARCH_DIALOG_SPACING)

        hint = QLabel("搜尋異常單號、供應商、料號、訪廠摘要或不合格品單號")
        hint.setProperty("role", "helperText")
        layout.addWidget(hint)

        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("輸入關鍵字，按 Enter 開啟結果")
        self.query_input.setClearButtonEnabled(True)
        self.query_input.textChanged.connect(self._search)
        self.query_input.returnPressed.connect(self._open_current)
        layout.addWidget(self.query_input)

        self.results = QListWidget()
        self.results.setObjectName("GlobalSearchResults")
        self.results.itemActivated.connect(self._open_item)
        layout.addWidget(self.results, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self.reject)
        self.query_input.setFocus()

    def _search(self, text: str) -> None:
        self.results.clear()
        keyword = text.strip()
        if not keyword:
            return
        try:
            rows = global_search_service.search_global(keyword)
        except Exception:
            logger.exception("全域搜尋查詢失敗 keyword=%r", keyword)
            rows = []
        for row in rows:
            source = str(row.get("source") or "資料")
            ref_no = str(row.get("ref_no") or "—")
            title = str(row.get("title") or "—").replace("\n", " ")
            subtitle = str(row.get("subtitle") or "—")
            item = QListWidgetItem(f"[{source}] {ref_no}　{title}\n　　{subtitle}")
            item.setData(Qt.ItemDataRole.UserRole, row)
            self.results.addItem(item)
        if not rows:
            self.results.addItem(QListWidgetItem("沒有符合的資料"))

    def _open_current(self) -> None:
        item = self.results.currentItem()
        if item is not None:
            self._open_item(item)

    def _open_item(self, item: QListWidgetItem) -> None:
        row = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(row, dict):
            return
        source = row.get("source")
        if source == "異常":
            self.main_window.open_anomaly_management(str(row.get("id") or ""))
        elif source == "訪廠":
            self.main_window.open_event_query_with_filters(
                event_type="VISIT",
                supplier_keyword=str(row.get("subtitle") or ""),
                yyyymm=str(row.get("event_date") or "").replace("-", "")[:6] or None,
                event_scope="VISIT_ONLY",
            )
        elif source == "供應商":
            self.main_window.open_master_supplier_search(str(row.get("ref_no") or ""))
        elif source == "不合格品":
            status = str(row.get("status") or "").strip()
            processing_line = str(row.get("processing_line") or "").strip()
            if status == "已結案":
                self.main_window.open_warehouse_history()
            elif processing_line == "委外加工":
                self.main_window.open_warehouse_pending_outsource()
            elif processing_line == "原物料":
                self.main_window.open_warehouse_pending_material()
            elif processing_line == "未分流":
                self.main_window.open_warehouse_unclassified_pending()
            else:
                self.main_window.open_warehouse_pending_outsource()
        self.accept()
