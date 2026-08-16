from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QCheckBox,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QDateEdit,
    QTabWidget,
)

from ncr.db import crud
from ncr.ui.supplier_combo_utils import (
    SUPPLIER_CATEGORY_FORMAL,
    SUPPLIER_CATEGORY_OUTSOURCE,
    apply_supplier_exclusion_lock,
    block_signals,
    load_supplier_names_by_category,
)
from ncr.models.defect import (
    LIST_FIELD_ORDER,
    LIST_HEADERS,
    PROCESSING_LINE_MATERIAL,
    PROCESSING_LINE_OUTSOURCE,
    PROCESSING_LINE_STORAGE_OPTIONS,
    PROCESSING_LINE_UNCLASSIFIED,
    STATUS_OPTIONS,
)
from ncr.models.labels import (
    HINT_EMPTY_RESULT,
    HINT_RESET_FILTER,
    HEADER_EVENT_MONTH,
    LABEL_DATA_COUNT,
    LABEL_OPEN_COUNT,
    LABEL_CLOSED_COUNT,
    LABEL_ITEM_NO,
    LABEL_OUTSOURCE_SUPPLIER_NAME,
    LABEL_STATUS,
    LABEL_SUPPLIER_NAME,
    MSG_DELETE_CONFIRM,
)
from ncr.services import export_service
from ncr.ui.defect_form import DefectEditDialog
from ncr.ui.defect_list_paging import _DefectListPagingMixin
from ui.widgets.common_widgets import EmptyStateWidget
from ncr.ui.ui_style import (
    ACTION_BUTTON_MIN_WIDTH,
    FILTER_BUTTON_MAX_WIDTH,
    FILTER_BUTTON_MIN_WIDTH,
    add_labeled_field,
    align_table_header_left,
    apply_form_inputs,
    create_form_grid,
    create_page_shell,
    create_section_card,
    make_hint_label,
    make_notice_label,
    set_button_role,
    style_table,
    NCR_ITEMS_PER_PAGE,
    setup_column_persistence,
)
from ui.widgets.pagination_bar import PaginationBar
from ui.layout_constants import GRID_GUTTER, INLINE_SPACING, ROW_GAP


VALID_WORKFLOWS = {"combined", "tracking", "trace"}


BASE_DIR = Path(__file__).resolve().parents[3] / "Outputs"

DESCRIPTION_COLUMN = LIST_FIELD_ORDER.index("defect_desc")
STATUS_COLUMN = LIST_FIELD_ORDER.index("status")
DISPOSITION_COLUMN = LIST_FIELD_ORDER.index("disposition")
QTY_COLUMN = LIST_FIELD_ORDER.index("qty")
EVENT_DATE_COLUMN = LIST_FIELD_ORDER.index("event_date")
PROCESSING_LINE_COLUMN = LIST_FIELD_ORDER.index("processing_line")
RETURN_SLIP_TYPE_COLUMN = LIST_FIELD_ORDER.index("return_slip_type")
DEFECT_NO_COLUMN = LIST_FIELD_ORDER.index("defect_no")
WORK_ORDER_COLUMN = LIST_FIELD_ORDER.index("work_order_no")
INTERNAL_WORK_ORDER_COLUMN = LIST_FIELD_ORDER.index("internal_work_order_no")
TRANSFER_SLIP_COLUMN = LIST_FIELD_ORDER.index("transfer_slip_no")
ITEM_NO_COLUMN = LIST_FIELD_ORDER.index("item_no")
PRODUCT_NAME_COLUMN = LIST_FIELD_ORDER.index("product_name")
CATEGORY_COLUMN = LIST_FIELD_ORDER.index("category")
SUPPLIER_COLUMN = LIST_FIELD_ORDER.index("supplier_name")
OUTSOURCE_SUPPLIER_COLUMN = LIST_FIELD_ORDER.index("outsource_supplier_name")
RESPONSIBILITY_COLUMN = LIST_FIELD_ORDER.index("responsibility")


class DefectListWidget(_DefectListPagingMixin, QWidget):
    changed = Signal()
    data_changed = Signal()
    # Emitted when the user clicks the「另有 N 筆未分流待整理」link on a formal
    # processing-line pending page; the host wires this to open the cleanup list.
    unclassified_link_requested = Signal()

    def __init__(
        self,
        conn: sqlite3.Connection,
        parent: QWidget | None = None,
        *,
        workflow: str = "combined",
        processing_line: str | None = None,
        lazy_load: bool = False,
    ):
        super().__init__(parent)
        if workflow not in VALID_WORKFLOWS:
            raise ValueError(
                f"Unsupported DefectListWidget workflow: {workflow!r}. "
                f"Expected one of: {', '.join(sorted(VALID_WORKFLOWS))}."
            )
        if processing_line is not None and processing_line not in PROCESSING_LINE_STORAGE_OPTIONS:
            raise ValueError(
                f"Unsupported processing_line: {processing_line!r}. "
                f"Expected one of: {', '.join(PROCESSING_LINE_STORAGE_OPTIONS)}."
            )
        self.conn = conn
        self.workflow = workflow
        self.processing_line = processing_line
        self.open_results: list[sqlite3.Row] = []
        self.closed_results: list[sqlite3.Row] = []
        self._open_count = 0
        self._closed_count = 0
        self._open_filters: dict[str, str] = {}
        self._closed_filters: dict[str, str] = {}
        self._open_exclude_status: str | None = None
        self._closed_exclude_status: str | None = None
        self.current_page = 1
        self._page_size = NCR_ITEMS_PER_PAGE
        self._is_compact_profile = True
        self.tabs: QTabWidget | None = None
        self._has_loaded = False
        self._build_ui()
        self._update_column_profile()
        if not lazy_load:
            self.refresh_data()

    def _build_ui(self) -> None:
        page, content_layout = create_page_shell(show_header=False)
        content_layout.setSpacing(GRID_GUTTER)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(page)

        from ui.widgets.common_widgets import QueryWorkflowShell

        # Control panel: filters + action buttons (mirrors defect_list_widget.py's
        # control_panel/role=subpanel convention on the supplier-event side).
        control_panel = QueryWorkflowShell()
        main_layout = QVBoxLayout(control_panel)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(ROW_GAP)

        # Filters Section
        filter_grid = create_form_grid(field_count=3)
        filter_grid.setVerticalSpacing(ROW_GAP)

        self.month_edit = QDateEdit()
        self.month_edit.setDisplayFormat("yyyy-MM")
        self.month_edit.setCalendarPopup(True)
        self.month_edit.setDate(QDate.currentDate())
        self.month_edit.setEnabled(self.workflow != "tracking")
        self.month_filter_checkbox = QCheckBox("套用月份")
        self.month_filter_checkbox.setChecked(self.workflow == "combined")

        self.item_no_input = QLineEdit()
        self.item_no_input.setPlaceholderText("輸入料號")
        self.item_no_input.setAccessibleName("搜尋料號")
        self.supplier_combo = QComboBox()
        self.supplier_combo.setEditable(False)
        self.supplier_combo.setAccessibleName("供應商篩選")
        self.outsource_supplier_combo = QComboBox()
        self.outsource_supplier_combo.setEditable(False)
        self.outsource_supplier_combo.setAccessibleName("委外加工廠篩選")

        self.status_combo = QComboBox()
        self.status_combo.addItem("全部")
        self.status_combo.addItems(STATUS_OPTIONS)
        self.status_combo.setVisible(self.workflow == "combined")
        self.status_combo.setAccessibleName("狀態篩選")

        apply_form_inputs(
            [
                self.month_edit,
                self.item_no_input,
                self.supplier_combo,
                self.outsource_supplier_combo,
                self.status_combo,
            ]
        )

        # Row 0: Month (0, 1), Item No (2, 3), Status (4, 5)
        self.month_label = add_labeled_field(
            filter_grid, 0, HEADER_EVENT_MONTH, self.month_edit, field_minimum_width=120, field_maximum_width=200
        )
        add_labeled_field(
            filter_grid,
            0,
            LABEL_ITEM_NO,
            self.item_no_input,
            column_offset=2,
            field_minimum_width=150,
            field_maximum_width=250,
        )
        self.status_label = add_labeled_field(
            filter_grid,
            0,
            LABEL_STATUS,
            self.status_combo,
            column_offset=4,
            field_minimum_width=120,
            field_maximum_width=200,
        )
        if self.workflow != "combined":
            self.status_label.hide()

        # Row 1: Supplier (0, 1), Outsource Supplier (2, 3), Buttons Layout (4, 5)
        add_labeled_field(
            filter_grid,
            1,
            LABEL_SUPPLIER_NAME,
            self.supplier_combo,
            column_offset=0,
            field_minimum_width=180,
            field_maximum_width=250,
        )
        add_labeled_field(
            filter_grid,
            1,
            LABEL_OUTSOURCE_SUPPLIER_NAME,
            self.outsource_supplier_combo,
            column_offset=2,
            field_minimum_width=180,
            field_maximum_width=250,
        )

        # 4. Action Buttons (Search & Reset on row 1)
        self.reset_button = QPushButton("重置")
        self.search_button = QPushButton("查詢")
        self.reset_button.setCursor(Qt.PointingHandCursor)
        self.search_button.setCursor(Qt.PointingHandCursor)
        self.reset_button.setAccessibleName("重置篩選")
        self.reset_button.setToolTip("重置所有篩選條件")
        self.search_button.setAccessibleName("執行查詢")
        self.search_button.setToolTip("執行篩選查詢")
        for btn, role in [
            (self.reset_button, "reset"),
            (self.search_button, "primary"),
        ]:
            btn.setMinimumWidth(FILTER_BUTTON_MIN_WIDTH)
            btn.setMaximumWidth(FILTER_BUTTON_MAX_WIDTH)
            set_button_role(btn, role)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(INLINE_SPACING)
        button_layout.addStretch(1)
        button_layout.addWidget(self.reset_button)
        button_layout.addWidget(self.search_button)

        filter_grid.addLayout(button_layout, 1, 4, 1, 2)

        main_layout.addLayout(filter_grid)

        self.processing_line_scope_notice = make_notice_label("", role="helperText")
        self.processing_line_scope_notice.setWordWrap(False)
        if self.processing_line:
            self.processing_line_scope_notice.setText(
                f"目前頁面固定處理線：{self.processing_line}（未結案，不限月份）"
            )
            self.processing_line_scope_notice.show()
        else:
            self.processing_line_scope_notice.hide()
        main_layout.addWidget(self.processing_line_scope_notice)

        # 未分流待整理提示連結:只在兩條正式處理線的待處理頁出現。當仍有「未分流 +
        # 未結案」紀錄時顯示「另有 N 筆未分流待整理 →」,點擊導向整理清單,避免
        # 遷移/匯入產生的未分流資料被誤認為遺失(discoverability 缺口)。
        self.unclassified_link_button: QPushButton | None = None
        if self.workflow == "tracking" and self.processing_line in (
            PROCESSING_LINE_MATERIAL,
            PROCESSING_LINE_OUTSOURCE,
        ):
            self.unclassified_link_button = QPushButton("")
            self.unclassified_link_button.setObjectName("UnclassifiedCleanupLink")
            set_button_role(self.unclassified_link_button, "secondary")
            self.unclassified_link_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.unclassified_link_button.setToolTip("開啟未分流待整理清單")
            self.unclassified_link_button.setAccessibleName("未分流待整理連結")
            self.unclassified_link_button.clicked.connect(
                self.unclassified_link_requested.emit
            )
            self.unclassified_link_button.hide()
            link_row = QHBoxLayout()
            link_row.setContentsMargins(0, 0, 0, 0)
            link_row.addWidget(self.unclassified_link_button)
            link_row.addStretch(1)
            main_layout.addLayout(link_row)

        # Summary and actions are split so status text cannot force all buttons
        # off-screen on smaller displays.
        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(12)
        action_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # 1. Stats Summary
        self.total_count_label = make_hint_label(LABEL_DATA_COUNT.format(0))
        self.open_count_label = make_hint_label(LABEL_OPEN_COUNT.format(0))
        self.closed_count_label = make_hint_label(LABEL_CLOSED_COUNT.format(0))
        for lbl in (self.total_count_label, self.open_count_label, self.closed_count_label):
            lbl.setWordWrap(False)
            action_row.addWidget(lbl)

        # 2. Context Notices
        self.month_scope_notice = make_notice_label("", role="helperText")
        self.filter_notice = make_notice_label("", role="helperText")
        self.month_scope_notice.setWordWrap(False)
        self.filter_notice.setWordWrap(False)
        for _n in (self.month_scope_notice, self.filter_notice):
            _n.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        action_row.addWidget(self.month_scope_notice)
        action_row.addWidget(self.filter_notice)

        # 3. Reset Hint
        hint_label = make_hint_label(HINT_RESET_FILTER)
        hint_label.setWordWrap(False)
        # 高 DPI 時讓次要重置提示優先讓位，避免右側「匯出 Excel / 刪除選取」動作鈕被擠到裁字
        hint_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        if self.workflow == "trace":
            action_row.addWidget(self.month_filter_checkbox)
            self.month_filter_checkbox.stateChanged.connect(self.refresh_data)
        else:
            self.month_filter_checkbox.hide()
        action_row.addWidget(hint_label)

        action_row.addStretch(1)

        # 4. Action Buttons (Export & Delete on row 2)
        self.export_button = QPushButton("匯出 Excel")
        self.delete_button = QPushButton("刪除選取")
        self.add_button = QPushButton("登錄不合格品")
        self.export_button.setCursor(Qt.PointingHandCursor)
        self.delete_button.setCursor(Qt.PointingHandCursor)
        self.add_button.setCursor(Qt.PointingHandCursor)
        self.export_button.setAccessibleName("匯出 Excel")
        self.export_button.setToolTip("匯出目前篩選清單至 Excel")
        self.delete_button.setAccessibleName("刪除選取")
        self.delete_button.setToolTip("刪除勾選紀錄")
        self.add_button.setAccessibleName("登錄不合格品紀錄")
        self.add_button.setToolTip("建立新的不合格品紀錄")

        buttons_to_add = []
        if self.workflow != "trace":
            buttons_to_add.append((self.export_button, "secondary"))
        else:
            self.export_button.hide()

        buttons_to_add.append((self.delete_button, "danger"))
        buttons_to_add.append((self.add_button, "primary"))

        if hasattr(self, "main_window") and hasattr(self.main_window, "open_defect_form"):
            self.add_button.clicked.connect(self.main_window.open_defect_form)

        self.column_profile_button = QPushButton("顯示完整欄位")
        self.column_profile_button.setCursor(Qt.PointingHandCursor)
        self.column_profile_button.setAccessibleName("欄位顯示模式")
        self.column_profile_button.setToolTip("切換精簡/完整欄位顯示")
        self.column_profile_button.clicked.connect(self._toggle_column_profile)
        buttons_to_add.append((self.column_profile_button, "secondary"))

        for btn, role in buttons_to_add:
            btn.setMinimumWidth(ACTION_BUTTON_MIN_WIDTH)
            btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            set_button_role(btn, role)
            action_row.addWidget(btn)

        self.search_button.clicked.connect(self.refresh_data)
        self.reset_button.clicked.connect(self.reset_filters)
        self.export_button.clicked.connect(self.export_current_results)
        self.delete_button.clicked.connect(self.delete_selected_record)

        # 互斥邏輯：供應商與委外供應商只能選擇一個
        self.supplier_combo.currentIndexChanged.connect(self._handle_supplier_selection)
        self.outsource_supplier_combo.currentIndexChanged.connect(self._handle_outsource_selection)

        main_layout.addLayout(action_row)
        content_layout.addWidget(control_panel)

        # Results panel: table(s) + pagination (mirrors defect_list_widget.py's
        # result_panel/role=panel convention on the supplier-event side).
        result_panel = QFrame()
        result_panel.setProperty("role", "panel")
        result_layout = QVBoxLayout(result_panel)
        result_layout.setContentsMargins(16, 12, 16, 12)
        result_layout.setSpacing(ROW_GAP)

        self.empty_state = EmptyStateWidget("", parent=self)
        self.empty_state.setVisible(False)
        # Stretch=1 so this (or the table below) always claims the panel's
        # leftover vertical space, keeping the pagination bar pinned to its
        # natural height instead of stretching when the table is hidden.
        result_layout.addWidget(self.empty_state, 1)

        self.open_table = QTableWidget(0, len(LIST_HEADERS))
        self.open_table.setAccessibleName("待處理不合格品表格")
        self.open_table.setHorizontalHeaderLabels(LIST_HEADERS)
        align_table_header_left(self.open_table)
        style_table(self.open_table)
        self.open_table.cellDoubleClicked.connect(self.open_edit_dialog)
        self.open_table.setToolTip("雙擊任一列以開啟編輯視窗")
        self._setup_table_headers(self.open_table)
        self.open_table.setMinimumHeight(370)

        self.closed_table = QTableWidget(0, len(LIST_HEADERS))
        self.closed_table.setAccessibleName("已結案不合格品表格")
        self.closed_table.setHorizontalHeaderLabels(LIST_HEADERS)
        align_table_header_left(self.closed_table)
        style_table(self.closed_table)
        self.closed_table.cellDoubleClicked.connect(self.open_edit_dialog)
        self.closed_table.setToolTip("雙擊任一列以開啟編輯視窗")
        self._setup_table_headers(self.closed_table)
        self.closed_table.setMinimumHeight(370)

        if self.workflow == "combined":
            self.tabs = QTabWidget()
            self.tabs.setDocumentMode(True)
            self.tabs.addTab(self.open_table, "未結案")
            self.tabs.addTab(self.closed_table, "已結案")
            result_layout.addWidget(self.tabs, 1)
        elif self.workflow == "tracking":
            result_layout.addWidget(self.open_table, 1)
        else:
            result_layout.addWidget(self.closed_table, 1)

        self.pagination = PaginationBar(
            on_page_changed=self._on_page_changed,
            on_page_size_changed=self._on_page_size_changed,
            default_page_size=self._page_size,
        )
        result_layout.addWidget(self.pagination)

        content_layout.addWidget(result_panel, 1)

        # Connect after initial construction to avoid currentChanged firing before pagination exists.
        if self.tabs is not None:
            self.tabs.currentChanged.connect(self._on_tab_changed)

    def _uses_month_filter(self) -> bool:
        if self.workflow == "tracking":
            return False
        if self.workflow == "trace":
            return self.month_filter_checkbox.isChecked()
        return True

    def _toggle_column_profile(self) -> None:
        self._is_compact_profile = not getattr(self, "_is_compact_profile", True)
        self._update_column_profile()

    def _update_column_profile(self) -> None:
        is_compact = getattr(self, "_is_compact_profile", True)
        core_fields = {
            "defect_no",
            "event_date",
            "item_no",
            "product_name",
            "defect_desc",
            "status",
        }
        if getattr(self, "workflow", None) == "trace":
            core_fields.add("processing_line")
        if hasattr(self, "column_profile_button"):
            self.column_profile_button.setText("使用重點欄位" if not is_compact else "顯示完整欄位")
        for table in (getattr(self, "open_table", None), getattr(self, "closed_table", None)):
            if table is None:
                continue
            for column_index, field_name in enumerate(LIST_FIELD_ORDER):
                table.setColumnHidden(column_index, is_compact and (field_name not in core_fields))
            if is_compact:
                compact_widths = {
                    DEFECT_NO_COLUMN: 120,
                    EVENT_DATE_COLUMN: 90,
                    ITEM_NO_COLUMN: 90,
                    PRODUCT_NAME_COLUMN: 130,
                    DESCRIPTION_COLUMN: 150,
                    STATUS_COLUMN: 80,
                }
                for col, width in compact_widths.items():
                    table.setColumnWidth(col, width)

    def _setup_table_headers(self, table: QTableWidget) -> None:
        setup_column_persistence(table, "defect_list_columns", self.conn, LIST_FIELD_ORDER)

        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        for column_index in range(table.columnCount()):
            header.setSectionResizeMode(column_index, QHeaderView.ResizeMode.ResizeToContents)
        table.resizeColumnsToContents()

        for column_index in range(table.columnCount()):
            header.setSectionResizeMode(column_index, QHeaderView.ResizeMode.Interactive)

        preferred_widths = {
            DEFECT_NO_COLUMN: 170,
            PROCESSING_LINE_COLUMN: 110,
            RETURN_SLIP_TYPE_COLUMN: 120,
            WORK_ORDER_COLUMN: 140,
            INTERNAL_WORK_ORDER_COLUMN: 140,
            TRANSFER_SLIP_COLUMN: 140,
            ITEM_NO_COLUMN: 130,
            PRODUCT_NAME_COLUMN: 260,
            DESCRIPTION_COLUMN: 320,
        }
        for column_index, preferred_width in preferred_widths.items():
            table.setColumnWidth(
                column_index, max(table.columnWidth(column_index), preferred_width)
            )

    def build_filters(self) -> dict[str, str]:
        filters: dict[str, str] = {
            "month": self.month_edit.date().toString("yyyy-MM"),
        }
        if not self._uses_month_filter():
            filters.pop("month", None)
        if self.item_no_input.text().strip():
            filters["item_no"] = self.item_no_input.text().strip()
        if self.supplier_combo.currentText().strip():
            filters["supplier_name"] = self.supplier_combo.currentText().strip()
        if self.outsource_supplier_combo.currentText().strip():
            filters["outsource_supplier_name"] = self.outsource_supplier_combo.currentText().strip()
        status = self.status_combo.currentText()
        if self.workflow == "combined" and status and status != "全部":
            filters["status"] = status
        if self.processing_line:
            filters["processing_line"] = self.processing_line
        return filters

    @property
    def table(self) -> QTableWidget:
        """Compatibility property for tests."""
        return self._get_active_table()

    def refresh_filter_options(self) -> None:
        """從資料庫獲取現有的供應商清單並更新篩選選單。"""
        # 更新供應商選單
        curr_supplier = self.supplier_combo.currentText()
        suppliers = load_supplier_names_by_category(self.conn, SUPPLIER_CATEGORY_FORMAL)
        with block_signals(self.supplier_combo):
            self.supplier_combo.clear()
            self.supplier_combo.addItem("")
            self.supplier_combo.addItems(suppliers)
            self.supplier_combo.setCurrentText(curr_supplier)

        # 更新委外供應商選單
        curr_outsource = self.outsource_supplier_combo.currentText()
        outsources = load_supplier_names_by_category(
            self.conn, SUPPLIER_CATEGORY_OUTSOURCE
        )
        with block_signals(self.outsource_supplier_combo):
            self.outsource_supplier_combo.clear()
            self.outsource_supplier_combo.addItem("")
            self.outsource_supplier_combo.addItems(outsources)
            self.outsource_supplier_combo.setCurrentText(curr_outsource)
        self._sync_filter_lock_state()

    def _sync_filter_lock_state(self) -> None:
        def is_selected(combo: QComboBox) -> bool:
            return combo.currentIndex() > 0 and bool(combo.currentText().strip())

        apply_supplier_exclusion_lock(
            supplier_combo=self.supplier_combo,
            outsource_combo=self.outsource_supplier_combo,
            hint_label=self.filter_notice,
            is_filled=is_selected,
        )

    def _handle_supplier_selection(self, index: int) -> None:
        """若選擇了供應商，則停用委外供應商欄位並顯示提示。"""
        if index > 0:
            with block_signals(self.outsource_supplier_combo):
                self.outsource_supplier_combo.setCurrentIndex(0)
        self._sync_filter_lock_state()

    def _handle_outsource_selection(self, index: int) -> None:
        """若選擇了委外供應商，則停用正式供應商欄位並顯示提示。"""
        if index > 0:
            with block_signals(self.supplier_combo):
                self.supplier_combo.setCurrentIndex(0)
        self._sync_filter_lock_state()


    def reset_filters(self) -> None:
        self.month_edit.setDate(QDate.currentDate())
        self.month_filter_checkbox.setChecked(self.workflow == "combined")
        self.item_no_input.clear()
        self.supplier_combo.setCurrentIndex(0)
        self.outsource_supplier_combo.setCurrentIndex(0)
        self.status_combo.setCurrentIndex(0)
        self._sync_filter_lock_state()
        self.refresh_data()

    def _selected_row_index(self) -> int | None:
        table = self._get_active_table()
        model = table.selectionModel()
        if model is None:
            return None
        selected_rows = model.selectedRows()
        if not selected_rows:
            return None
        return selected_rows[0].row()

    def open_edit_dialog(self, row: int, _column: int) -> None:
        results = self._get_active_results()
        if row < 0 or row >= len(results):
            self.refresh_data()
            return
        defect_id = int(results[row]["id"])
        try:
            dialog = DefectEditDialog(self.conn, defect_id, self)
        except ValueError:
            QMessageBox.warning(self, "提示", "此筆資料已不存在，可能已被刪除，將重新整理列表。")
            self.refresh_data()
            return
        if dialog.exec():
            self.refresh_data()
            self.changed.emit()
            self.data_changed.emit()

    def delete_selected_record(self) -> None:
        row_index = self._selected_row_index()
        if row_index is None:
            QMessageBox.warning(self, "未選取資料", "請先選取要刪除的資料列。")
            return

        results = self._get_active_results()
        if row_index < 0 or row_index >= len(results):
            self.refresh_data()
            return
        defect = results[row_index]
        box = QMessageBox(self)
        box.setWindowTitle("確認刪除")
        box.setText(MSG_DELETE_CONFIRM.format(defect['defect_no']))
        box.setIcon(QMessageBox.Icon.Warning)
        btn_delete = box.addButton("刪除", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(btn_delete)
        box.exec()
        if box.clickedButton() is not btn_delete:
            return

        try:
            crud.delete_defect(self.conn, int(defect["id"]))
        except sqlite3.Error as exc:
            QMessageBox.critical(self, "資料庫錯誤", str(exc))
            return

        self.refresh_data()
        self.changed.emit()
        self.data_changed.emit()

    def export_current_results(self) -> None:
        filters, exclude_status = self._active_query()
        result_count = self._active_count()
        if result_count == 0:
            QMessageBox.warning(self, "無可匯出資料", HINT_EMPTY_RESULT)
            return

        from ui.export_helpers import get_default_export_filepath, handle_export_completion
        default_name = f"defect_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        default_path = get_default_export_filepath(default_name)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "匯出 Excel",
            str(default_path),
            "Excel Files (*.xlsx)",
        )
        if not file_path:
            return

        try:
            from ncr.services import export_service

            results = crud.get_defects(
                self.conn,
                filters,
                exclude_status=exclude_status,
            )
            output_path = export_service.export_to_excel(
                results,
                self._build_product_stats(results),
                self._build_supplier_stats(results),
                self._build_outsource_stats(results),
                file_path=file_path,
            )
        except OSError as exc:
            QMessageBox.critical(self, "匯出失敗", str(exc))
            return

        handle_export_completion(output_path, f"Excel 已輸出至：\n{output_path}", self)

    @staticmethod
    def _summarize_rows(
        rows: list[sqlite3.Row], key_name: str, *, skip_blank: bool
    ) -> list[dict[str, object]]:
        summary: dict[tuple[str, str, str, str, str], tuple[int, int]] = {}
        for row in rows:
            row_dict = dict(row)
            name = str(row_dict.get(key_name, "") or "").strip()
            if skip_blank and (not name or name == "N/A"):
                continue
            disposition = str(row_dict.get("disposition", "") or "").strip()
            category = str(row_dict.get("category", "") or "").strip()
            status = str(row_dict.get("status", "") or "").strip()
            event_date = str(row_dict.get("event_date", "") or "").strip()
            event_month = event_date[:7] if len(event_date) >= 7 else ""
            try:
                qty_value = int(row_dict.get("qty", 0) or 0)
            except (TypeError, ValueError):
                qty_value = 0

            group_key = (name, disposition, category, event_month, status)
            existing = summary.setdefault(group_key, (0, 0))
            case_count, total_qty = existing
            summary[group_key] = (case_count + 1, total_qty + qty_value)

        def _month_sort_token(value: str) -> int:
            token = value.replace("-", "")
            return int(token) if token.isdigit() else 0

        sorted_rows = sorted(
            summary.items(),
            key=lambda item: (
                -item[1][1],
                item[0][0],
                -_month_sort_token(item[0][3]),
                item[0][1],
                item[0][2],
                item[0][4],
            ),
        )
        return [
            {
                key_name: name,
                "disposition": disposition,
                "category": category,
                "event_month": event_month,
                "status": status,
                "case_count": case_count,
                "total_qty": total_qty,
            }
            for (
                name,
                disposition,
                category,
                event_month,
                status,
            ), (case_count, total_qty) in sorted_rows
        ]

    def _build_product_stats(self, rows: list[sqlite3.Row]) -> list[dict[str, object]]:
        return self._summarize_rows(rows, "product_name", skip_blank=False)

    def _build_supplier_stats(self, rows: list[sqlite3.Row]) -> list[dict[str, object]]:
        return self._summarize_rows(rows, "supplier_name", skip_blank=True)

    def _build_outsource_stats(
        self, rows: list[sqlite3.Row]
    ) -> list[dict[str, object]]:
        return self._summarize_rows(rows, "outsource_supplier_name", skip_blank=True)
