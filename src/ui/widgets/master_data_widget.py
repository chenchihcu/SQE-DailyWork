"""主資料管理 Widget — 共用供應商與產品基礎資料 CRUD。

透過 _MasterDataSupplierMixin 與 _MasterDataProductMixin 注入
供應商與產品專屬的 UI 建構、表格渲染與 CRUD 操作。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from services import event_service
from ui.layout_constants import (
    PANEL_MARGINS,
    ROOT_SECTION_SPACING,
    TOOLBAR_CONTROL_MIN_HEIGHT,
    TOOLBAR_ITEM_SPACING,
)
from ui.widgets.common_widgets import apply_clickable_affordance
from ui.widgets.master_data_product_mixin import _MasterDataProductMixin
from ui.widgets.master_data_supplier_mixin import _MasterDataSupplierMixin


class MasterDataWidget(QWidget, _MasterDataSupplierMixin, _MasterDataProductMixin):
    def __init__(self, main_window, *, lazy_load: bool = False):
        super().__init__()
        self.main_window = main_window
        self._supplier_rows: list[dict] = []
        self._product_rows: list[dict] = []
        self._selected_supplier_id: str | None = None
        self._selected_product_id: str | None = None
        self._supplier_query_keyword = ""
        self._product_query_keyword = ""
        self._displayed_query_keyword = ""
        self._supplier_page = 1
        self._supplier_page_size = 13
        self._product_page = 1
        self._product_page_size = 13
        self._setup_ui()
        self._has_loaded = False
        if not lazy_load:
            self.refresh_data()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(ROOT_SECTION_SPACING)

        tabs_panel = QFrame()
        tabs_panel.setProperty("role", "panel")
        tabs_layout = QVBoxLayout(tabs_panel)
        tabs_layout.setContentsMargins(*PANEL_MARGINS)
        tabs_layout.setSpacing(8)

        self.inline_toolbar = QFrame()
        self.inline_toolbar.setObjectName("MasterInlineToolbar")
        self.inline_toolbar.setProperty("role", "masterToolbar")
        toolbar_outer = QVBoxLayout(self.inline_toolbar)
        toolbar_outer.setContentsMargins(0, 0, 0, 0)
        toolbar_outer.setSpacing(0)

        primary_row = QWidget()
        primary_row.setObjectName("MasterPrimaryRow")
        primary_layout = QHBoxLayout(primary_row)
        primary_layout.setContentsMargins(0, 0, 0, 0)
        primary_layout.setSpacing(TOOLBAR_ITEM_SPACING)

        self.query_input = QLineEdit()
        self.query_input.setMinimumWidth(220)
        self.query_input.setMaximumWidth(340)
        self.query_input.setPlaceholderText("輸入供應商名稱")
        self.query_input.setProperty("role", "masterQuery")
        self.query_input.returnPressed.connect(self._on_query_submitted)

        self.selection_status_label = QLabel("未選取供應商")
        self.selection_status_label.setObjectName("MasterSelectionStatus")
        self.selection_status_label.setProperty("role", "selectionStatus")
        self.selection_status_label.setToolTip("目前管理動作的選取對象")
        self.selection_status_label.setMinimumWidth(190)

        self.action_stack = QStackedWidget()
        self.action_stack.setObjectName("MasterActionStack")
        self.action_stack.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.action_stack.addWidget(self._build_supplier_actions_row())
        self.action_stack.addWidget(self._build_product_actions_row())

        primary_layout.addWidget(self.query_input)
        primary_layout.addWidget(self.selection_status_label)
        primary_layout.addStretch(1)
        primary_layout.addWidget(self.action_stack)

        toolbar_outer.addWidget(primary_row)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("MasterDataTabs")
        self.tabs.addTab(self._build_supplier_tab(), "供應商")
        self.tabs.addTab(self._build_product_tab(), "產品")
        apply_clickable_affordance(
            self.tabs.tabBar(),
            tooltip="切換供應商與產品清單",
        )

        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._last_tab_index = 0

        tabs_layout.addWidget(self.inline_toolbar)
        tabs_layout.addWidget(self.tabs)
        root.addWidget(tabs_panel, 1)
        self._on_tab_changed(self.tabs.currentIndex())

    # ── 共用工具方法 ──────────────────────────────────────

    def _create_toolbar_button(
        self,
        text: str,
        *,
        tooltip: str,
        variant: str,
        on_click,
    ) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("variant", variant)
        button.setToolTip(tooltip)
        apply_clickable_affordance(button, status_tip=tooltip)
        button.setMinimumHeight(TOOLBAR_CONTROL_MIN_HEIGHT)
        button.clicked.connect(on_click)
        return button

    def _focus_master_query(self) -> None:
        self.query_input.setFocus()
        self.query_input.selectAll()

    def _on_query_submitted(self) -> None:
        text = self.query_input.text().strip()
        if self.tabs.currentIndex() == 0:
            self._supplier_query_keyword = text
            self._supplier_page = 1
        else:
            self._product_query_keyword = text
            self._product_page = 1
        self._displayed_query_keyword = text
        self._render_supplier_table()
        self._render_product_table()

    # ── 過濾 ──────────────────────────────────────────────

    def _filtered_supplier_rows(self) -> list[dict]:
        keyword = self._supplier_query_keyword.strip().lower()
        if not keyword:
            return list(self._supplier_rows)
        return [
            row
            for row in self._supplier_rows
            if keyword in str(row.get("supplier_name") or "").lower()
        ]

    def _filtered_product_rows(self) -> list[dict]:
        keyword = self._product_query_keyword.strip().lower()
        if not keyword:
            return list(self._product_rows)

        def matches(row: dict) -> bool:
            fields = (
                row.get("product_code"),
                row.get("product_name"),
                row.get("product_stage"),
                row.get("supplier_name"),
                row.get("secondary_supplier_name"),
            )
            return any(keyword in str(f or "").lower() for f in fields)

        return [row for row in self._product_rows if matches(row)]

    # ── Toggle 按鈕輔助 ──────────────────────────────────

    def _set_toggle_button_state(
        self, button: QPushButton, *, is_active: bool, entity: str
    ) -> None:
        action_text = "停用" if is_active else "啟用"
        button.setText(action_text)
        button.setToolTip(f"{action_text}{entity}")

    # ── 分頁切換 ──────────────────────────────────────────

    def _on_tab_changed(self, index: int) -> None:
        current_text = self.query_input.text().strip()
        if current_text != self._displayed_query_keyword:
            if self._last_tab_index == 0:
                self._supplier_query_keyword = current_text
            else:
                self._product_query_keyword = current_text

        self._last_tab_index = index
        tab_index = 0 if index <= 0 else 1
        self.action_stack.setCurrentIndex(tab_index)
        if index == 0:
            self.query_input.setPlaceholderText("輸入供應商名稱")
            next_keyword = self._supplier_query_keyword
        else:
            self.query_input.setPlaceholderText("輸入料號、品名或供應商")
            next_keyword = self._product_query_keyword
        self.query_input.setText(next_keyword)
        self._displayed_query_keyword = next_keyword

        try:
            self._render_supplier_table()
            self._render_product_table()
            self._sync_action_buttons()
        except RuntimeError:
            return

    # ── 資料重新整理 ──────────────────────────────────────

    def refresh_data(self):
        self._has_loaded = True
        self._supplier_rows = event_service.list_suppliers(include_inactive=True)
        self._product_rows = event_service.list_products(include_inactive=True)
        self._render_supplier_table()
        self._render_product_table()
        self._sync_action_buttons()
        self._on_tab_changed(self.tabs.currentIndex())

    # ── 按鈕同步 ──────────────────────────────────────────

    def _sync_action_buttons(self):
        supplier_selection_count = len(self._selected_table_ids(self.supplier_table))
        has_supplier = supplier_selection_count > 0
        has_single_supplier = supplier_selection_count == 1
        has_product = self._selected_product_id is not None
        self.btn_supplier_update.setEnabled(has_single_supplier)
        self.btn_supplier_toggle.setEnabled(has_single_supplier)
        self.btn_supplier_delete.setEnabled(has_supplier)
        self.btn_supplier_delete_selected.setEnabled(has_supplier)
        self.btn_product_update.setEnabled(has_product)
        self.btn_product_toggle.setEnabled(has_product)
        self.btn_product_delete.setEnabled(has_product)
        self.btn_product_stage_logs.setEnabled(has_product)
        self._sync_selection_status()

    def _sync_selection_status(self) -> None:
        if not hasattr(self, "selection_status_label"):
            return
        if self.tabs.currentIndex() == 0:
            selected_ids = self._selected_table_ids(self.supplier_table)
            if not selected_ids:
                text = "未選取供應商"
            elif len(selected_ids) == 1:
                text = f"已選取供應商：{self._supplier_label(selected_ids[0])}"
            else:
                text = f"已選取供應商：{len(selected_ids)} 筆"
        else:
            if self._selected_product_id:
                text = f"已選取產品：{self._product_label(self._selected_product_id)}"
            else:
                text = "未選取產品"
        self.selection_status_label.setText(text)

    # ── 資料列查詢 ────────────────────────────────────────

    def _find_supplier_row(self, supplier_id: str | None) -> dict | None:
        if not supplier_id:
            return None
        for row in self._supplier_rows:
            if row["id"] == supplier_id:
                return row
        return None

    def _find_product_row(self, product_id: str | None) -> dict | None:
        if not product_id:
            return None
        for row in self._product_rows:
            if row["id"] == product_id:
                return row
        return None

    # ── 表格選取輔助 ──────────────────────────────────────

    def _selected_table_ids(self, table: QTableWidget) -> list[str]:
        indexes = table.selectionModel().selectedRows() if table.selectionModel() else []
        selected_ids: list[str] = []
        seen: set[str] = set()
        for model_index in sorted(indexes, key=lambda idx: idx.row()):
            item = table.item(model_index.row(), 0)
            if item is None:
                continue
            value = item.data(Qt.ItemDataRole.UserRole)
            if not value:
                continue
            item_id = str(value)
            if item_id in seen:
                continue
            seen.add(item_id)
            selected_ids.append(item_id)
        return selected_ids

    def _selected_table_id(self, table: QTableWidget) -> str | None:
        selected_ids = self._selected_table_ids(table)
        if not selected_ids:
            return None
        return selected_ids[0]

    def _table_menu_pos(self, table: QTableWidget, row_idx: int):
        index = table.model().index(row_idx, 0)
        rect = table.visualRect(index)
        if rect.isValid():
            return table.viewport().mapToGlobal(rect.center())
        return table.mapToGlobal(table.rect().center())

    def _select_single_row(self, table: QTableWidget, row_idx: int):
        table.clearSelection()
        table.selectRow(row_idx)
        table.setCurrentCell(row_idx, 0)
