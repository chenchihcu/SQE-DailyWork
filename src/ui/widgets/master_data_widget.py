"""主資料管理 Widget — 供應商或產品主檔 CRUD（固定 scope 單頁）。

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
    QVBoxLayout,
    QWidget,
)

from database.product_item_category import (
    ITEM_CATEGORY_RAW_MATERIAL,
    MASTER_SEMI_FINISHED_CATEGORIES,
)
from database.supplier_category import SUPPLIER_CATEGORY_RAW_MATERIAL
from services.event import _product_service, _supplier_service
from ui.layout_constants import (
    MASTER_SEARCH_MAX_WIDTH,
    MASTER_SEARCH_MIN_WIDTH,
    ROOT_SECTION_SPACING,
    TOOLBAR_CONTROL_MIN_HEIGHT,
    TOOLBAR_ITEM_SPACING,
)
from ui.widgets.common_widgets import apply_clickable_affordance
from ui.widgets.master_data_product_mixin import _MasterDataProductMixin
from ui.widgets.master_data_supplier_mixin import _MasterDataSupplierMixin
from ui.widgets.product_form_dialog import ProductFormDialog as ProductFormDialog
from ui.widgets.product_stage_log_dialog import (
    ProductStageLogDialog as ProductStageLogDialog,
)


class MasterDataWidget(QWidget, _MasterDataSupplierMixin, _MasterDataProductMixin):
    MODE_SUPPLIER = "supplier"
    MODE_PRODUCT = "product"

    def __init__(
        self,
        main_window,
        *,
        lazy_load: bool = False,
        master_mode: str = MODE_SUPPLIER,
        supplier_category: str | None = None,
        item_categories: tuple[str, ...] | None = None,
        page_label: str = "",
    ):
        super().__init__()
        self.main_window = main_window
        self._master_mode = master_mode
        self._supplier_category = supplier_category
        self._item_categories = tuple(item_categories or ())
        self._page_label = page_label.strip()
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
        self.query_input.setMinimumWidth(MASTER_SEARCH_MIN_WIDTH)
        self.query_input.setMaximumWidth(MASTER_SEARCH_MAX_WIDTH)
        if self._master_mode == self.MODE_SUPPLIER:
            placeholder = "輸入供應商名稱"
        else:
            placeholder = "輸入料號、品名或供應商"
        self.query_input.setPlaceholderText(placeholder)
        self.query_input.setAccessibleName("搜尋主資料")
        self.query_input.setProperty("role", "masterQuery")
        self.query_input.returnPressed.connect(self._on_query_submitted)

        empty_label = self._page_label or (
            "供應商" if self._master_mode == self.MODE_SUPPLIER else "產品"
        )
        self.selection_status_label = QLabel(f"未選取{empty_label}")
        self.selection_status_label.setObjectName("MasterSelectionStatus")
        self.selection_status_label.setProperty("role", "selectionStatus")
        self.selection_status_label.setToolTip("目前管理動作的選取對象")
        self.selection_status_label.setMinimumWidth(190)

        primary_layout.addWidget(self.query_input)
        primary_layout.addWidget(self.selection_status_label)
        primary_layout.addStretch(1)

        if self._master_mode == self.MODE_SUPPLIER:
            primary_layout.addWidget(self._build_supplier_actions_row())
        else:
            primary_layout.addWidget(self._build_product_actions_row())

        toolbar_outer.addWidget(primary_row)

        self.content_host = QWidget()
        content_layout = QVBoxLayout(self.content_host)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        if self._master_mode == self.MODE_SUPPLIER:
            content_layout.addWidget(self._build_supplier_tab(), 1)
        else:
            content_layout.addWidget(self._build_product_tab(), 1)

        root.addWidget(self.inline_toolbar)
        root.addWidget(self.content_host, 1)

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
        button.setCursor(Qt.PointingHandCursor)
        button.setAccessibleName(text)
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
        if self._master_mode == self.MODE_SUPPLIER:
            self._supplier_query_keyword = text
            self._supplier_page = 1
            self._render_supplier_table()
        else:
            self._product_query_keyword = text
            self._product_page = 1
            self._render_product_table()
        self._displayed_query_keyword = text

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
                row.get("item_category"),
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

    # ── 資料重新整理 ──────────────────────────────────────

    def refresh_data(self):
        self._has_loaded = True
        if self._master_mode == self.MODE_SUPPLIER:
            self._supplier_rows = _supplier_service.list_suppliers(
                include_inactive=True,
                category=self._supplier_category,
            )
            self._render_supplier_table()
            self._sync_action_buttons()
        else:
            self._product_rows = _product_service.list_products(
                include_inactive=True,
                item_categories=self._item_categories or None,
            )
            self._supplier_rows = _supplier_service.list_suppliers(
                include_inactive=True,
                category=SUPPLIER_CATEGORY_RAW_MATERIAL,
            )
            self._render_product_table()
            self._sync_action_buttons()

    # ── 按鈕同步 ──────────────────────────────────────────

    def _sync_action_buttons(self):
        if self._master_mode == self.MODE_SUPPLIER:
            supplier_selection_count = len(self._selected_table_ids(self.supplier_table))
            has_supplier = supplier_selection_count > 0
            has_single_supplier = supplier_selection_count == 1
            self.btn_supplier_update.setEnabled(has_single_supplier)
            self.btn_supplier_toggle.setEnabled(has_single_supplier)
            self.btn_supplier_delete.setEnabled(has_supplier)
            self.btn_supplier_delete_selected.setEnabled(has_supplier)
            self._sync_selection_status()
        else:
            has_product = self._selected_product_id is not None
            self.btn_product_update.setEnabled(has_product)
            self.btn_product_toggle.setEnabled(has_product)
            self.btn_product_delete.setEnabled(has_product)
            self.btn_product_stage_logs.setEnabled(has_product)
            self._sync_selection_status()

    def _sync_selection_status(self) -> None:
        if not hasattr(self, "selection_status_label"):
            return
        entity = self._page_label or (
            "供應商" if self._master_mode == self.MODE_SUPPLIER else "產品"
        )
        if self._master_mode == self.MODE_SUPPLIER:
            selected_ids = self._selected_table_ids(self.supplier_table)
            if not selected_ids:
                text = f"未選取{entity}"
            elif len(selected_ids) == 1:
                text = f"已選取{entity}：{self._supplier_label(selected_ids[0])}"
            else:
                text = f"已選取{entity}：{len(selected_ids)} 筆"
        else:
            if self._selected_product_id:
                text = f"已選取{entity}：{self._product_label(self._selected_product_id)}"
            else:
                text = f"未選取{entity}"
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

    def _selected_table_ids(self, table) -> list[str]:
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

    def _selected_table_id(self, table) -> str | None:
        selected_ids = self._selected_table_ids(table)
        if not selected_ids:
            return None
        return selected_ids[0]

    def _table_menu_pos(self, table, row_idx: int):
        index = table.model().index(row_idx, 0)
        rect = table.visualRect(index)
        if rect.isValid():
            return table.viewport().mapToGlobal(rect.center())
        return table.mapToGlobal(table.rect().center())

    def _select_single_row(self, table, row_idx: int):
        table.clearSelection()
        table.selectRow(row_idx)
        table.setCurrentCell(row_idx, 0)

    @property
    def _show_item_category_column(self) -> bool:
        return len(self._item_categories) > 1

    def _fixed_item_category(self) -> str | None:
        if self._item_categories == (ITEM_CATEGORY_RAW_MATERIAL,):
            return ITEM_CATEGORY_RAW_MATERIAL
        return None

    def _allow_item_category_choice(self) -> bool:
        return set(self._item_categories) == set(MASTER_SEMI_FINISHED_CATEGORIES)


def MasterDataSupplierPage(
    main_window,
    supplier_category: str,
    *,
    page_label: str,
    lazy_load: bool = True,
) -> MasterDataWidget:
    return MasterDataWidget(
        main_window,
        lazy_load=lazy_load,
        master_mode=MasterDataWidget.MODE_SUPPLIER,
        supplier_category=supplier_category,
        page_label=page_label,
    )


def MasterDataProductPage(
    main_window,
    item_categories: tuple[str, ...],
    *,
    page_label: str,
    lazy_load: bool = True,
) -> MasterDataWidget:
    return MasterDataWidget(
        main_window,
        lazy_load=lazy_load,
        master_mode=MasterDataWidget.MODE_PRODUCT,
        item_categories=item_categories,
        page_label=page_label,
    )
