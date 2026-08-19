from __future__ import annotations

import sqlite3
from datetime import datetime

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
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
    LABEL_DATA_COUNT,
    LABEL_OPEN_COUNT,
    LABEL_CLOSED_COUNT,
    MSG_DELETE_CONFIRM,
)
from ncr.services import export_service
from ncr.ui.defect_form import DefectEditDialog
from ncr.ui.defect_list_paging import _DefectListPagingMixin
from services import appearance_preferences_service
from ui.widgets.common_widgets import (
    EmptyStateWidget,
    QueryWorkflowShell,
    apply_clickable_affordance,
    apply_table_action_affordance,
    style_table,
)
from ncr.ui.ui_style import (
    align_table_header_left,
    apply_form_inputs,
    create_page_shell,
    make_hint_label,
    make_notice_label,
    set_button_role,
    NCR_ITEMS_PER_PAGE,
    setup_column_persistence,
)
from ui.widgets.pagination_bar import PaginationBar
from ui.layout_constants import (
    CONTROL_ROW_SPACING,
    FILTER_MONTH_INPUT_WIDTH,
    FILTER_STATUS_COMBO_WIDTH,
    INLINE_SPACING,
    PANEL_MARGINS,
    ROOT_SECTION_SPACING,
    ROW_GAP,
    SUBPANEL_TOOLBAR_MARGINS,
)


VALID_WORKFLOWS = {"combined", "tracking", "trace"}


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

    def _source_tag_text(self) -> str:
        if self.workflow == "tracking":
            if self.processing_line == PROCESSING_LINE_OUTSOURCE:
                return "倉庫實物不合格品 / 待處理委外加工"
            elif self.processing_line == PROCESSING_LINE_MATERIAL:
                return "倉庫實物不合格品 / 待處理原物料"
            elif self.processing_line == PROCESSING_LINE_UNCLASSIFIED:
                return "倉庫實物不合格品 / 未分流待整理"
            return "倉庫實物不合格品 / 待處理追蹤"
        elif self.workflow == "trace":
            return "倉庫實物不合格品 / 歷史紀錄"
        return "倉庫實物不合格品 / 全部紀錄"

    def _build_ui(self) -> None:
        page, content_layout = create_page_shell(show_header=False)
        content_layout.setSpacing(ROOT_SECTION_SPACING)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(page)

        # Control panel: filters + action toolbar + pagination row (3-tier structure aligned with EventListWidget)
        control_panel = QueryWorkflowShell()
        control_outer = QVBoxLayout(control_panel)
        control_outer.setContentsMargins(*SUBPANEL_TOOLBAR_MARGINS)
        control_outer.setSpacing(CONTROL_ROW_SPACING)

        # Row 1: Filters Section (single compact horizontal row)
        actions_row = QHBoxLayout()
        actions_row.setSpacing(INLINE_SPACING)

        lbl_item_no = QLabel("料號")
        lbl_item_no.setProperty("role", "helperText")
        self.item_no_input = QLineEdit()
        self.item_no_input.setPlaceholderText("輸入料號")
        self.item_no_input.setAccessibleName("搜尋料號")
        self.item_no_input.setMinimumWidth(110)
        self.item_no_input.setClearButtonEnabled(True)
        self.item_no_input.returnPressed.connect(self.refresh_data)
        prefs = appearance_preferences_service.load_application_preferences()
        if prefs.search_mode == "live":
            self.item_no_input.textEdited.connect(lambda _: self.refresh_data())

        lbl_supplier = QLabel("正式供應商")
        lbl_supplier.setProperty("role", "helperText")
        self.supplier_combo = QComboBox()
        self.supplier_combo.setEditable(False)
        self.supplier_combo.setAccessibleName("供應商篩選")
        self.supplier_combo.setMinimumWidth(130)

        lbl_outsource = QLabel("委外加工廠")
        lbl_outsource.setProperty("role", "helperText")
        self.outsource_supplier_combo = QComboBox()
        self.outsource_supplier_combo.setEditable(False)
        self.outsource_supplier_combo.setAccessibleName("委外加工廠篩選")
        self.outsource_supplier_combo.setMinimumWidth(130)

        self.status_combo = QComboBox()
        self.status_combo.addItem("全部")
        self.status_combo.addItems(STATUS_OPTIONS)
        self.status_combo.setAccessibleName("狀態篩選")
        self.status_combo.setFixedWidth(FILTER_STATUS_COMBO_WIDTH)

        lbl_month = QLabel("月份")
        lbl_month.setProperty("role", "helperText")
        self.month_edit = QDateEdit()
        self.month_edit.setDisplayFormat("yyyy-MM")
        self.month_edit.setCalendarPopup(True)
        self.month_edit.setDate(QDate.currentDate())
        self.month_edit.setFixedWidth(FILTER_MONTH_INPUT_WIDTH)

        self.all_months_checkbox = QCheckBox("全部")
        self.all_months_checkbox.setChecked(self.workflow != "combined")
        self.month_edit.setEnabled(not self.all_months_checkbox.isChecked())
        apply_clickable_affordance(self.all_months_checkbox, tooltip="勾選顯示所有月份")
        self.all_months_checkbox.toggled.connect(
            lambda checked: self.month_edit.setEnabled(not checked)
        )
        self.all_months_checkbox.toggled.connect(lambda _: self.refresh_data())
        self.month_edit.dateChanged.connect(
            lambda _: self.refresh_data() if not self.all_months_checkbox.isChecked() else None
        )

        # Compatibility alias
        self.month_filter_checkbox = self.all_months_checkbox

        self.search_button = QPushButton("查詢")
        self.search_button.setProperty("variant", "primary")
        set_button_role(self.search_button, "primary")
        self.search_button.setCursor(Qt.PointingHandCursor)
        self.search_button.setAccessibleName("執行查詢")
        apply_clickable_affordance(self.search_button, tooltip="套用篩選條件")
        self.search_button.clicked.connect(self.refresh_data)

        self.reset_button = QPushButton("清除")
        self.reset_button.setProperty("variant", "secondary")
        set_button_role(self.reset_button, "reset")
        self.reset_button.setCursor(Qt.PointingHandCursor)
        self.reset_button.setAccessibleName("重置篩選")
        apply_clickable_affordance(self.reset_button, tooltip="清除目前篩選條件")
        self.reset_button.clicked.connect(self.reset_filters)

        apply_form_inputs(
            [
                self.item_no_input,
                self.supplier_combo,
                self.outsource_supplier_combo,
                self.month_edit,
                self.status_combo,
            ]
        )

        actions_row.addWidget(lbl_item_no)
        actions_row.addWidget(self.item_no_input, 1)
        actions_row.addWidget(lbl_supplier)
        actions_row.addWidget(self.supplier_combo, 1)
        actions_row.addWidget(lbl_outsource)
        actions_row.addWidget(self.outsource_supplier_combo, 1)

        if self.workflow == "combined":
            lbl_status = QLabel("狀態")
            lbl_status.setProperty("role", "helperText")
            actions_row.addWidget(lbl_status)
            actions_row.addWidget(self.status_combo)
            self.status_combo.currentIndexChanged.connect(lambda _: self.refresh_data())
        else:
            self.status_combo.hide()

        actions_row.addWidget(lbl_month)
        actions_row.addWidget(self.month_edit)
        actions_row.addWidget(self.all_months_checkbox)

        actions_row.addWidget(self.search_button)
        actions_row.addWidget(self.reset_button)

        control_outer.addLayout(actions_row)

        # Row 2: Action Toolbar (Source tag + stats on left; action buttons on right)
        toolbar_row = QHBoxLayout()
        toolbar_row.setSpacing(CONTROL_ROW_SPACING)

        self.source_tag_label = QLabel(self._source_tag_text())
        self.source_tag_label.setProperty("role", "sourceTag")
        self.source_tag_label.setToolTip("目前列表的資料流程來源")
        toolbar_row.addWidget(self.source_tag_label)

        self.total_count_label = make_hint_label(LABEL_DATA_COUNT.format(0))
        self.open_count_label = make_hint_label(LABEL_OPEN_COUNT.format(0))
        self.closed_count_label = make_hint_label(LABEL_CLOSED_COUNT.format(0))
        for lbl in (self.total_count_label, self.open_count_label, self.closed_count_label):
            lbl.setWordWrap(False)
            toolbar_row.addWidget(lbl)

        self.month_scope_notice = make_notice_label("", role="helperText")
        self.filter_notice = make_notice_label("", role="helperText")
        self.processing_line_scope_notice = make_notice_label("", role="helperText")
        self.month_scope_notice.setWordWrap(False)
        self.filter_notice.setWordWrap(False)
        self.processing_line_scope_notice.setWordWrap(False)
        if self.processing_line:
            self.processing_line_scope_notice.setText(
                f"目前頁面固定處理線：{self.processing_line}（未結案，不限月份）"
            )
            self.processing_line_scope_notice.show()
        else:
            self.processing_line_scope_notice.hide()
        for _n in (self.month_scope_notice, self.filter_notice, self.processing_line_scope_notice):
            _n.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        toolbar_row.addWidget(self.month_scope_notice)
        toolbar_row.addWidget(self.filter_notice)
        toolbar_row.addWidget(self.processing_line_scope_notice)

        self.unclassified_link_button: QPushButton | None = None
        if self.workflow == "tracking" and self.processing_line in (
            PROCESSING_LINE_MATERIAL,
            PROCESSING_LINE_OUTSOURCE,
        ):
            self.unclassified_link_button = QPushButton("")
            self.unclassified_link_button.setObjectName("UnclassifiedCleanupLink")
            self.unclassified_link_button.setProperty("variant", "secondary")
            set_button_role(self.unclassified_link_button, "secondary")
            self.unclassified_link_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.unclassified_link_button.setToolTip("開啟未分流待整理清單")
            self.unclassified_link_button.setAccessibleName("未分流待整理連結")
            self.unclassified_link_button.clicked.connect(
                self.unclassified_link_requested.emit
            )
            self.unclassified_link_button.hide()
            toolbar_row.addWidget(self.unclassified_link_button)

        toolbar_row.addStretch(1)

        self.column_profile_button = QPushButton("使用重點欄位" if not self._is_compact_profile else "顯示完整欄位")
        self.column_profile_button.setProperty("variant", "secondary")
        self.column_profile_button.setCursor(Qt.PointingHandCursor)
        self.column_profile_button.setAccessibleName("欄位顯示模式")
        self.column_profile_button.setToolTip("切換精簡/完整欄位顯示")
        self.column_profile_button.clicked.connect(self._toggle_column_profile)
        toolbar_row.addWidget(self.column_profile_button)

        self.export_button = QPushButton("匯出 Excel")
        self.export_button.setProperty("variant", "secondary")
        self.export_button.setCursor(Qt.PointingHandCursor)
        self.export_button.setAccessibleName("匯出 Excel")
        self.export_button.setToolTip("匯出目前篩選清單至 Excel")
        self.export_button.clicked.connect(self.export_current_results)
        if self.workflow != "trace":
            toolbar_row.addWidget(self.export_button)
        else:
            self.export_button.hide()

        self.delete_button = QPushButton("刪除選取")
        self.delete_button.setProperty("variant", "danger")
        set_button_role(self.delete_button, "danger")
        self.delete_button.setCursor(Qt.PointingHandCursor)
        self.delete_button.setAccessibleName("刪除選取")
        self.delete_button.setToolTip("刪除勾選紀錄")
        self.delete_button.clicked.connect(self.delete_selected_record)
        toolbar_row.addWidget(self.delete_button)

        self.add_button = QPushButton("登錄不合格品")
        self.add_button.setProperty("variant", "primary")
        set_button_role(self.add_button, "primary")
        self.add_button.setCursor(Qt.PointingHandCursor)
        self.add_button.setAccessibleName("登錄不合格品紀錄")
        self.add_button.setToolTip("建立新的不合格品紀錄")

        def _on_add_clicked():
            top = self.window()
            if hasattr(self, "main_window") and hasattr(self.main_window, "open_defect_form"):
                self.main_window.open_defect_form()
            elif hasattr(top, "open_defect_form"):
                top.open_defect_form()
            elif hasattr(top, "sidebar") and hasattr(top.sidebar, "set_current_page"):
                from ui.sidebar_nav import PAGE_NCR_CREATE
                top.sidebar.set_current_page(PAGE_NCR_CREATE)

        self.add_button.clicked.connect(_on_add_clicked)
        toolbar_row.addWidget(self.add_button)

        # 互斥邏輯：供應商與委外供應商只能選擇一個
        self.supplier_combo.currentIndexChanged.connect(self._handle_supplier_selection)
        self.outsource_supplier_combo.currentIndexChanged.connect(self._handle_outsource_selection)

        control_outer.addLayout(toolbar_row)

        # Row 3: Dedicated pagination row inside control panel
        self.pagination = PaginationBar(
            on_page_changed=self._on_page_changed,
            on_page_size_changed=self._on_page_size_changed,
            default_page_size=self._page_size,
        )
        pagination_row = QHBoxLayout()
        pagination_row.setSpacing(CONTROL_ROW_SPACING)
        pagination_row.addWidget(self.pagination, 1)
        control_outer.addLayout(pagination_row)

        content_layout.addWidget(control_panel)

        # Results panel: table(s) 100% full-width
        result_panel = QFrame()
        result_panel.setProperty("role", "panel")
        result_layout = QVBoxLayout(result_panel)
        result_layout.setContentsMargins(*PANEL_MARGINS)
        result_layout.setSpacing(ROW_GAP)

        self.empty_state = EmptyStateWidget("", parent=self)
        self.empty_state.setVisible(False)
        result_layout.addWidget(self.empty_state, 1)

        self.open_table = QTableWidget(0, len(LIST_HEADERS))
        self.open_table.setAccessibleName("待處理不合格品表格")
        self.open_table.setHorizontalHeaderLabels(LIST_HEADERS)
        self.open_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.open_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        align_table_header_left(self.open_table)
        style_table(self.open_table)
        apply_table_action_affordance(
            self.open_table,
            "點擊列選取；雙擊列以開啟編輯或結案視窗",
        )
        self.open_table.cellDoubleClicked.connect(self.open_edit_dialog)
        self._setup_table_headers(self.open_table)
        self.open_table.setMinimumHeight(370)

        self.closed_table = QTableWidget(0, len(LIST_HEADERS))
        self.closed_table.setAccessibleName("已結案不合格品表格")
        self.closed_table.setHorizontalHeaderLabels(LIST_HEADERS)
        self.closed_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.closed_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        align_table_header_left(self.closed_table)
        style_table(self.closed_table)
        apply_table_action_affordance(
            self.closed_table,
            "點擊列選取；雙擊列以開啟編輯或結案視窗",
        )
        self.closed_table.cellDoubleClicked.connect(self.open_edit_dialog)
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

        content_layout.addWidget(result_panel, 1)

        # Connect after initial construction to avoid currentChanged firing before pagination exists.
        if self.tabs is not None:
            self.tabs.currentChanged.connect(self._on_tab_changed)

    def _uses_month_filter(self) -> bool:
        # month_filter_checkbox is a compatibility alias of all_months_checkbox
        # (see __init__); checking both would always return False. Only the
        # all_months state decides whether the month filter applies.
        return not (hasattr(self, "all_months_checkbox") and self.all_months_checkbox.isChecked())

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
            header = table.horizontalHeader()
            for column_index, field_name in enumerate(LIST_FIELD_ORDER):
                table.setColumnHidden(column_index, is_compact and (field_name not in core_fields))
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(DEFECT_NO_COLUMN, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(EVENT_DATE_COLUMN, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(ITEM_NO_COLUMN, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(STATUS_COLUMN, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(PRODUCT_NAME_COLUMN, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(DESCRIPTION_COLUMN, QHeaderView.ResizeMode.Stretch)
            if is_compact:
                compact_widths = {
                    DEFECT_NO_COLUMN: 120,
                    EVENT_DATE_COLUMN: 90,
                    ITEM_NO_COLUMN: 90,
                    PRODUCT_NAME_COLUMN: 130,
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
            DEFECT_NO_COLUMN: 140,
            EVENT_DATE_COLUMN: 100,
            PROCESSING_LINE_COLUMN: 110,
            RETURN_SLIP_TYPE_COLUMN: 120,
            WORK_ORDER_COLUMN: 140,
            INTERNAL_WORK_ORDER_COLUMN: 140,
            TRANSFER_SLIP_COLUMN: 140,
            ITEM_NO_COLUMN: 120,
            PRODUCT_NAME_COLUMN: 200,
            DESCRIPTION_COLUMN: 320,
        }
        for column_index, preferred_width in preferred_widths.items():
            table.setColumnWidth(
                column_index, max(table.columnWidth(column_index), preferred_width)
            )
        header.setSectionResizeMode(DESCRIPTION_COLUMN, QHeaderView.ResizeMode.Stretch)

    def build_filters(self) -> dict[str, str]:
        filters: dict[str, str] = {}
        if self._uses_month_filter():
            filters["month"] = self.month_edit.date().toString("yyyy-MM")
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
        curr_supplier = self.supplier_combo.currentText()
        suppliers = load_supplier_names_by_category(self.conn, SUPPLIER_CATEGORY_FORMAL)
        with block_signals(self.supplier_combo):
            self.supplier_combo.clear()
            self.supplier_combo.addItem("")
            self.supplier_combo.addItems(suppliers)
            self.supplier_combo.setCurrentText(curr_supplier)

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
        self.all_months_checkbox.setChecked(self.workflow != "combined")
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
