from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QDate, Qt

logger = logging.getLogger(__name__)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database import repository
from services import event_service as event_service
from services import appearance_preferences_service
from services.event import _query_service
from services.process_keyword_codec import format_process_keywords_display
from ui.popup_i18n import localize_popup_message
from ui.list_column_contract import (
    EVENT_LIST_COMPACT_FIELDS,
    EVENT_LIST_FIELDS,
    EVENT_LIST_HEADERS,
)
from ui.layout_constants import (
    CONTROL_ROW_SPACING,
    EVENT_LIST_CORE_ANOMALY_NO_WIDTH,
    EVENT_LIST_CORE_PRODUCT_WIDTH,
    EVENT_LIST_CORE_QUALITY_REQUIREMENT_WIDTH,
    EVENT_LIST_CORE_STATUS_WIDTH,
    EVENT_LIST_CORE_SUPPLIER_WIDTH,
    EVENT_LIST_FULL_COLUMNS_MIN_WIDTH,
    EVENT_LIST_ITEMS_PER_PAGE,
    EVENT_LIST_NAME_COL_MIN_WIDTH,
    FILTER_MONTH_INPUT_WIDTH,
    FILTER_STATUS_COMBO_WIDTH,
    FILTER_SUPPLIER_MIN_WIDTH,
    INLINE_SPACING,
    PANEL_MARGINS,
    ROOT_SECTION_SPACING,
    SUBPANEL_TOOLBAR_MARGINS,
)

from ui.widgets.common_widgets import (
    EMPTY_DISPLAY,
    EmptyStateWidget,
    QueryWorkflowShell,
    SortableTableWidgetItem,
    apply_clickable_affordance,
    apply_table_action_affordance,
    apply_toolbar_label_policy,
    create_status_item,
    preserve_table_sorting,
    style_table,
    text_table_item,
)
from ui.widgets.event_actions import (
    EventActionsController,
    build_event_action_menu,
    dispatch_event_action,
)
from ui.widgets.pagination_bar import PaginationBar
from ui.widgets.event_list_filter_mixin import _EventListFilterMixin

# Consolidated event-management page: one widget; these compatibility definitions
# drive every sidebar supplier-event scope (including 已結案). Default = 單獨異常.
EVENT_QUERY_SCOPE_TABS = (
    ("單獨異常", repository.EVENT_SCOPE_ANOMALY_ONLY, "ANOMALY"),
    ("已結案", repository.EVENT_SCOPE_CLOSED_ONLY, "ANOMALY"),
)

_SORTABLE_COLS: dict[int, str] = {
    EVENT_LIST_FIELDS.index(field): field
    for field in (
        "ref_no",
        "category",
        "responsible_person",
        "supplier_name",
        "product_name",
        "product_stage",
        "quality_report_required",
        "status",
        "closed_at",
    )
}

_EVENT_LIST_CORE_WIDTHS = {
    "ref_no": EVENT_LIST_CORE_ANOMALY_NO_WIDTH,
    "supplier_name": EVENT_LIST_CORE_SUPPLIER_WIDTH,
    "product_name": EVENT_LIST_CORE_PRODUCT_WIDTH,
    "quality_report_required": EVENT_LIST_CORE_QUALITY_REQUIREMENT_WIDTH,
    "status": EVENT_LIST_CORE_STATUS_WIDTH,
}
_EVENT_LIST_COMPACT_OPTIONAL_COLUMNS = tuple(
    index for index, field in enumerate(EVENT_LIST_FIELDS)
    if field not in EVENT_LIST_COMPACT_FIELDS
)


class EventListWidget(QWidget, _EventListFilterMixin):
    def __init__(self, main_window, *, mode: str = "query", fixed_scope: str | None = None, fixed_status: str | None = None, lazy_load: bool = False):
        super().__init__()
        self.main_window = main_window
        self.mode = "query"
        self.fixed_scope = self._normalize_event_scope(fixed_scope) if fixed_scope else None
        self.fixed_status = fixed_status
        self._all_rows: list[dict] = []
        self._current_page = 1
        self._page_size = EVENT_LIST_ITEMS_PER_PAGE
        self._filter_event_type = "ALL"
        self._sort_col: int | None = None
        self._sort_asc: bool = True
        if self.fixed_scope:
            self._filter_event_scope = self.fixed_scope
            if self.fixed_scope == repository.EVENT_SCOPE_CLOSED_ONLY:
                self._filter_event_type = "ANOMALY"
            else:
                self._filter_event_type = self._event_type_for_scope(self.fixed_scope)
        else:
            # Consolidated event page defaults to the first scope tab (單獨異常),
            # matching the anomaly sidebar badge count.
            self._filter_event_scope = EVENT_QUERY_SCOPE_TABS[0][1]
            self._filter_event_type = self._event_type_for_scope(
                self._filter_event_scope
            )
        self._filter_status = fixed_status if fixed_status else "ALL"
        self._filter_supplier = ""
        self._filter_yyyymm: str | None = None
        self.event_type_combo: QComboBox | None = None
        self.event_scope_tab_bar: QTabBar | None = None
        self.scope_chip_buttons: dict[str, QPushButton] = {}
        self.scope_chip_labels: dict[str, str] = {
            scope: label for label, scope, _event_type in EVENT_QUERY_SCOPE_TABS
        }
        self.status_combo: QComboBox | None = None
        self.supplier_filter_input: QLineEdit | None = None
        self.month_input: QDateEdit | None = None
        self.all_months_checkbox: QCheckBox | None = None
        self.export_pdf_button: QPushButton | None = None
        self.column_profile_notice: QLabel | None = None
        self.column_profile_button: QPushButton | None = None
        self._compact_column_profile_override: bool | None = None
        self._selected_event_row: dict | None = None
        self._event_actions = EventActionsController(self, main_window)
        self._setup_ui()
        self._has_loaded = False
        if not lazy_load:
            self.refresh_data()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(ROOT_SECTION_SPACING)

        control_panel = QueryWorkflowShell()
        root.addWidget(control_panel)
        control_outer = QVBoxLayout(control_panel)
        control_outer.setContentsMargins(*SUBPANEL_TOOLBAR_MARGINS)
        control_outer.setSpacing(CONTROL_ROW_SPACING)

        # Row 1: scope chips. Scope is a view of the same event query page, not
        # a separate navigation route.
        if self.mode == "query":
            scope_row = QHBoxLayout()
            scope_row.setSpacing(INLINE_SPACING)
            scope_label = QLabel("案件視角")
            scope_label.setProperty("role", "helperText")
            scope_row.addWidget(scope_label)
            scope_group = QButtonGroup(self)
            scope_group.setExclusive(True)
            for label, scope, _event_type in EVENT_QUERY_SCOPE_TABS:
                chip = QPushButton(label)
                chip.setObjectName("EventScopeChip")
                chip.setProperty("role", "scopeChip")
                chip.setCheckable(True)
                chip.setToolTip(f"顯示{label}資料")
                chip.clicked.connect(
                    lambda _checked=False, selected_scope=scope: self.set_event_scope(
                        selected_scope
                    )
                )
                scope_group.addButton(chip)
                self.scope_chip_buttons[scope] = chip
                scope_row.addWidget(chip)
            scope_row.addStretch(1)
            control_outer.addLayout(scope_row)

        # Row 2: filters / helper + new-event actions (consistent across modes)
        actions_row = QHBoxLayout()
        actions_row.setSpacing(INLINE_SPACING)

        if self.mode == "query":
            lbl_supplier = QLabel("供應商")
            lbl_supplier.setProperty("role", "helperText")
            self.supplier_filter_input = QLineEdit()
            self.supplier_filter_input.setPlaceholderText("輸入供應商名稱")
            self.supplier_filter_input.setMinimumWidth(FILTER_SUPPLIER_MIN_WIDTH)
            self.supplier_filter_input.setClearButtonEnabled(True)
            self.supplier_filter_input.returnPressed.connect(self._apply_filters_from_ui)
            prefs = appearance_preferences_service.load_application_preferences()
            if prefs.search_mode == "live":
                self.supplier_filter_input.textEdited.connect(lambda _: self._apply_filters_from_ui())

            lbl_status = QLabel("狀態")
            lbl_status.setProperty("role", "helperText")
            self.status_combo = QComboBox()
            self.status_combo.setFixedWidth(FILTER_STATUS_COMBO_WIDTH)
            self.status_combo.addItem("全部", "ALL")
            self.status_combo.addItem("待處理", "待處理")

            btn_search = QPushButton("查詢")
            btn_search.setProperty("variant", "primary")
            apply_clickable_affordance(btn_search, tooltip="套用篩選條件")
            btn_search.clicked.connect(self._apply_filters_from_ui)
            btn_reset = QPushButton("清除")
            btn_reset.setProperty("variant", "secondary")
            apply_clickable_affordance(btn_reset, tooltip="清除目前篩選條件")
            btn_reset.clicked.connect(self._reset_filters_ui)

            actions_row.addWidget(lbl_supplier)
            actions_row.addWidget(self.supplier_filter_input, 1)

            if not self.fixed_status:
                actions_row.addWidget(lbl_status)
                actions_row.addWidget(self.status_combo)
            else:
                fixed_lbl = QLabel(f"狀態：{self.fixed_status}")
                fixed_lbl.setProperty("role", "helperText")
                fixed_lbl.setEnabled(False)
                actions_row.addWidget(fixed_lbl)

            lbl_month = QLabel("月份")
            lbl_month.setProperty("role", "helperText")
            self.all_months_checkbox = QCheckBox("全部")
            self.all_months_checkbox.setChecked(True)
            apply_clickable_affordance(self.all_months_checkbox, tooltip="勾選顯示所有月份")
            self.month_input = QDateEdit()
            self.month_input.setDisplayFormat("yyyy-MM")
            self.month_input.setDate(QDate.currentDate())
            self.month_input.setCalendarPopup(True)
            self.month_input.setEnabled(False)
            self.month_input.setFixedWidth(FILTER_MONTH_INPUT_WIDTH)
            self.all_months_checkbox.toggled.connect(
                lambda checked: self.month_input.setEnabled(not checked)
            )
            self.status_combo.currentIndexChanged.connect(self._apply_filters_from_ui)
            self.all_months_checkbox.toggled.connect(self._apply_filters_from_ui)
            self.month_input.dateChanged.connect(
                lambda _: self._apply_filters_from_ui()
                if self.all_months_checkbox is not None and not self.all_months_checkbox.isChecked()
                else None
            )
            actions_row.addWidget(lbl_month)
            actions_row.addWidget(self.month_input)
            actions_row.addWidget(self.all_months_checkbox)

            actions_row.addWidget(btn_search)
            actions_row.addWidget(btn_reset)
        control_outer.addLayout(actions_row)

        # Row 2 (action bar): export actions (right).
        self.pagination = PaginationBar(
            on_page_changed=self._on_page_changed,
            on_page_size_changed=self._on_page_size_changed,
            default_page_size=self._page_size,
        )

        toolbar_row = QHBoxLayout()
        toolbar_row.setSpacing(CONTROL_ROW_SPACING)

        self.column_profile_notice = QLabel("")
        self.column_profile_notice.setProperty("role", "helperText")
        self.column_profile_notice.setWordWrap(True)
        self.column_profile_notice.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        toolbar_row.addWidget(self.column_profile_notice, 1)

        self.column_profile_button = QPushButton()
        self.column_profile_button.setProperty("variant", "secondary")
        self.column_profile_button.clicked.connect(self._toggle_column_profile)
        toolbar_row.addWidget(self.column_profile_button)

        if self.mode == "query":
            self.export_pdf_button = QPushButton("輸出PDF")
            self.export_pdf_button.setProperty("variant", "secondary")
            apply_clickable_affordance(
                self.export_pdf_button,
                tooltip="輸出目前選取的單筆事件 PDF",
            )
            self.export_pdf_button.clicked.connect(self._export_selected_pdf)
            toolbar_row.addWidget(self.export_pdf_button)
            self._sync_export_pdf_state()

        control_outer.addLayout(toolbar_row)

        # Row 3 (dedicated pagination row): the shared PaginationBar needs ~584px for
        # its 共 N 筆 / 每頁 / 跳至 controls.
        pagination_row = QHBoxLayout()
        pagination_row.setSpacing(CONTROL_ROW_SPACING)
        pagination_row.addWidget(self.pagination, 1)
        control_outer.addLayout(pagination_row)

        root.addWidget(control_panel)

        result_panel = QFrame()
        result_panel.setProperty("role", "panel")
        result_layout = QVBoxLayout(result_panel)
        result_layout.setContentsMargins(*PANEL_MARGINS)
        result_layout.setSpacing(8)

        self.empty_state = EmptyStateWidget("", parent=self)
        self.empty_state.setVisible(False)
        result_layout.addWidget(self.empty_state)

        self.table = QTableWidget()
        self.table.setColumnCount(len(EVENT_LIST_HEADERS))
        self.table.setHorizontalHeaderLabels(EVENT_LIST_HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        style_table(self.table)
        apply_table_action_affordance(
            self.table,
            "點擊列選取；雙擊列以開啟編輯、刪除、結案或明細動作選單",
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for field in (
            "ref_no", "supplier_name", "product_code", "product_name",
            "product_stage", "category", "process_keywords", "responsible_person",
            "quality_report_required", "status", "closed_at",
        ):
            header.setSectionResizeMode(
                EVENT_LIST_FIELDS.index(field),
                QHeaderView.ResizeMode.ResizeToContents,
            )
        header.setSectionResizeMode(
            EVENT_LIST_FIELDS.index("content"), QHeaderView.ResizeMode.Stretch
        )
        header.setSectionResizeMode(
            EVENT_LIST_FIELDS.index("defect_notes"), QHeaderView.ResizeMode.Interactive
        )
        header.setSortIndicatorShown(True)
        header.sectionClicked.connect(self._on_header_clicked)
        header.setMinimumSectionSize(EVENT_LIST_NAME_COL_MIN_WIDTH)

        self.table.cellDoubleClicked.connect(self._on_table_row_clicked)
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        result_layout.addWidget(self.table, 1)
        if self.fixed_status:
            self.table.setColumnHidden(EVENT_LIST_FIELDS.index("status"), True)

        root.addWidget(result_panel, 1)

        if self.mode == "query":
            self._sync_filter_widgets_from_state()
        self._sync_table_column_profile()

    def _sync_scope_chip_labels(self) -> None:
        if self.mode != "query" or not self.scope_chip_buttons:
            return
        try:
            counts = _query_service.get_event_scope_counts()
        except Exception:
            logger.exception("讀取事件 scope 件數失敗")
            counts = {}
        for scope, button in self.scope_chip_buttons.items():
            label = self.scope_chip_labels.get(scope, scope)
            count = int(counts.get(scope, 0))
            button.setText(f"{label} ({count})")

    def refresh_data(self):
        self._has_loaded = True
        self._sync_category_column_visibility()
        filters = {
            "event_type": self._filter_event_type,
            "status": self._filter_status,
            "supplier": self._filter_supplier,
        }
        if self.mode == "query" and self._filter_event_scope:
            filters["event_scope"] = self._filter_event_scope
        if self._filter_yyyymm:
            filters["yyyymm"] = self._filter_yyyymm
        try:
            self._all_rows = _query_service.list_events(filters)
            self._set_load_failed(False)
        except Exception:
            logger.exception("事件清單載入失敗")
            self._all_rows = []
            self._set_load_failed(True)
        self._apply_sort()
        self._current_page = 1
        self._sync_scope_chip_labels()
        self._render_current_page()

    def _sync_category_column_visibility(self) -> None:
        """依當前 scope 同步表格欄位顯示。"""
        self._sync_table_column_profile()

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        if hasattr(self, "table"):
            self._sync_table_column_profile()

    def _compact_column_profile_active(self) -> bool:
        if self._compact_column_profile_override is not None:
            return self._compact_column_profile_override
        return self.width() < EVENT_LIST_FULL_COLUMNS_MIN_WIDTH

    def _toggle_column_profile(self) -> None:
        self._compact_column_profile_override = not self._compact_column_profile_active()
        self._sync_table_column_profile()

    def _sync_table_column_profile(self) -> None:
        """Keep the minimum-width event list scanable without discarding fields."""
        if not hasattr(self, "table"):
            return

        compact = self._compact_column_profile_active()
        for column in _EVENT_LIST_COMPACT_OPTIONAL_COLUMNS:
            self.table.setColumnHidden(column, compact)
        header = self.table.horizontalHeader()
        if compact:
            for field_name, width in _EVENT_LIST_CORE_WIDTHS.items():
                column_index = EVENT_LIST_FIELDS.index(field_name)
                header.setSectionResizeMode(column_index, QHeaderView.ResizeMode.Interactive)
                self.table.setColumnWidth(column_index, width)
            header.setSectionResizeMode(
                EVENT_LIST_FIELDS.index("content"), QHeaderView.ResizeMode.Stretch
            )
        else:
            header.setSectionResizeMode(
                EVENT_LIST_FIELDS.index("supplier_name"),
                QHeaderView.ResizeMode.ResizeToContents,
            )
            header.setSectionResizeMode(
                EVENT_LIST_FIELDS.index("content"), QHeaderView.ResizeMode.Stretch
            )
        if self.fixed_status:
            self.table.setColumnHidden(EVENT_LIST_FIELDS.index("status"), True)

        if self.column_profile_notice is not None:
            self.column_profile_notice.setVisible(compact)
            if compact:
                self.column_profile_notice.setText(
                    "目前為重點欄位檢視；可顯示完整欄位以查看類別、料號、階段、缺失紀錄與結案日期。"
                )
            else:
                self.column_profile_notice.setText("")
        if self.column_profile_button is not None:
            if compact:
                self.column_profile_button.setText("顯示完整欄位")
                tooltip = "顯示事件列表的全部欄位"
            else:
                self.column_profile_button.setText("使用重點欄位")
                tooltip = "只顯示事件列表的重點欄位"
            self.column_profile_button.setToolTip(tooltip)
            self.column_profile_button.setStatusTip(tooltip)
            apply_clickable_affordance(self.column_profile_button)

    def _apply_sort(self) -> None:
        # 使用者點擊表頭後以欄位排序(mixin 行為);否則套用偏好預設排序。
        if getattr(self, "_sort_col", None) is not None:
            return super()._apply_sort()
        prefs = appearance_preferences_service.load_application_preferences()
        sort_mode = getattr(self, "_sort_mode", None) or getattr(prefs, "default_list_sort_field", "none")
        if sort_mode == "date_desc":
            self._all_rows.sort(key=lambda r: str(r.get("event_date") or ""), reverse=True)
        elif sort_mode == "status_first":
            self._all_rows.sort(
                key=lambda r: (
                    0 if str(r.get("status") or "").strip() == "待處理" else 1,
                    str(r.get("ref_no") or r.get("event_date") or ""),
                ),
                reverse=False,
            )
        elif sort_mode == "anomaly_no_desc" and getattr(self, "_sort_mode", None) == "anomaly_no_desc":
            self._all_rows.sort(key=lambda r: str(r.get("ref_no") or r.get("event_date") or ""), reverse=True)

    def _on_header_clicked(self, logical_index: int) -> None:
        # 委派給 mixin 的欄位排序實作(表頭點擊排序)。
        super()._on_header_clicked(logical_index)

    def _render_current_page(self):
        self._selected_event_row = None
        total_pages = self._total_pages()
        self._current_page = min(max(1, self._current_page), total_pages)
        start = (self._current_page - 1) * self._page_size
        end = start + self._page_size
        page_rows = self._all_rows[start:end]

        prefs = appearance_preferences_service.load_application_preferences()
        date_slash = prefs.date_format_display == "YYYY/MM/DD"

        def _fmt_date(val: Any) -> str:
            s = str(val or "").strip()
            if date_slash and "-" in s:
                return s.replace("-", "/")
            return s

        with preserve_table_sorting(self.table):
            self.table.setRowCount(0)
            for idx, row in enumerate(page_rows):
                self.table.insertRow(idx)
                no_val = row.get("ref_no") or _fmt_date(row.get("event_date"))
                no_item = SortableTableWidgetItem(self._text_or_dash(no_val), sort_key=str(no_val or ""))

                no_item.setData(Qt.ItemDataRole.UserRole, dict(row))
                no_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                defect_summary = row.get("defect_note_summary") or row.get("pending_items")
                status_text = str(row.get("status") or "").strip() or "-"
                values = {
                    "ref_no": no_item,
                    "supplier_name": self._text_cell(row.get("supplier_name")),
                    "product_code": self._text_cell(row.get("product_code")),
                    "product_name": self._text_cell(row.get("product_name")),
                    "product_stage": self._text_cell(row.get("product_stage")),
                    "category": self._text_cell(row.get("category")),
                    "process_keywords": self._text_cell(
                        format_process_keywords_display(row.get("process_keywords"))
                    ),
                    "responsible_person": self._text_cell(row.get("responsible_person") or "未指定"),
                    "content": self._text_cell(row.get("content")),
                    "defect_notes": self._text_cell(defect_summary),
                    "quality_report_required": self._text_cell(
                        self._quality_report_required_text(row)
                    ),
                    "status": create_status_item(status_text, sort_key=status_text),
                    "closed_at": self._text_cell(_fmt_date(row.get("closed_at"))),
                }
                for column, field in enumerate(EVENT_LIST_FIELDS):
                    self.table.setItem(idx, column, values[field])

        self.table.clearSelection()
        self._sync_export_pdf_state()
        self.pagination.set_state(
            total_items=len(self._all_rows),
            current_page=self._current_page,
            page_size=self._page_size,
        )
        self._update_empty_state()


    def _text_or_dash(self, value) -> str:
        text = str(value or "").strip()
        return text or EMPTY_DISPLAY

    def _text_cell(self, value) -> QTableWidgetItem:
        """Long-text cell whose tooltip shows the full CJK text when elided (§6)."""
        return text_table_item(value)

    def _quality_report_required_text(self, row: dict) -> str:
        """Return the supplier-anomaly quality-report requirement display text."""
        event_type = str(row.get("event_type") or "").strip().upper()
        if event_type != "ANOMALY":
            return "不適用"

        value = row.get("quality_report_required")
        if value is None:
            return "未設定"
        if isinstance(value, str):
            normalized = value.strip().lower()
            if not normalized:
                return "未設定"
            if normalized in {"1", "true", "yes", "是"}:
                return "是"
            if normalized in {"0", "false", "no", "否"}:
                return "否"
        return "是" if bool(value) else "否"

    def _on_page_changed(self, page_no: int):
        self._current_page = page_no
        self._render_current_page()

    def _on_page_size_changed(self, page_size: int):
        if page_size <= 0:
            return
        self._page_size = page_size
        self._current_page = 1
        self._render_current_page()

    def _total_pages(self) -> int:
        return PaginationBar._total_pages(len(self._all_rows), self._page_size)

    def _row_data(self, row_idx: int) -> dict | None:
        if row_idx < 0:
            return None
        item = self.table.item(row_idx, 0)
        if item is None:
            return None
        payload = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(payload, dict):
            return None
        return payload

    def _on_table_selection_changed(self) -> None:
        if not self.table.selectedIndexes():
            self._selected_event_row = None
            self._sync_export_pdf_state()
            return
        row = self._row_data(self.table.currentRow())
        self._selected_event_row = dict(row) if row is not None else None
        self._sync_export_pdf_state()

    def _export_selected_pdf(self) -> None:
        row = self._selected_event_row
        if row is None:
            QMessageBox.information(self, "提示", "請先選取一筆資料")
            return

        from services.event import _export_service
        from ui.export_helpers import get_default_export_filepath, handle_export_completion

        try:
            default_name = _export_service.default_event_pdf_filename(row)
        except Exception:
            logger.exception("取得預設 PDF 檔名失敗")
            default_name = "SQE_事件單.pdf"
        target_default = get_default_export_filepath(default_name)
        target, _ = QFileDialog.getSaveFileName(
            self,
            "輸出PDF",
            target_default,
            "PDF Files (*.pdf)",
        )
        if not target:
            return
        if not target.lower().endswith(".pdf"):
            target = f"{target}.pdf"

        ok, msg = _export_service.export_event_pdf(target, row)
        if ok:
            handle_export_completion(target, msg, self)
        else:
            QMessageBox.critical(self, "失敗", localize_popup_message(msg))

    def _menu_pos(self, row_idx: int):
        index = self.table.model().index(row_idx, 0)
        rect = self.table.visualRect(index)
        if rect.isValid():
            return self.table.viewport().mapToGlobal(rect.center())
        return self.table.mapToGlobal(self.table.rect().center())

    def _on_table_row_clicked(self, row_idx: int, _column_idx: int):
        row = self._row_data(row_idx)
        if row is None:
            return
        self._selected_event_row = dict(row)
        self.table.selectRow(row_idx)
        self._sync_export_pdf_state()

        prefs = appearance_preferences_service.load_application_preferences()
        action = prefs.table_double_click_action
        if action == "preview":
            if row.get("id"):
                self.open_anomaly_details(str(row["id"]))
                return
        elif action == "edit":
            if row.get("id"):
                self.open_edit_anomaly_dialog(str(row["id"]))
                return

        menu, action_map = build_event_action_menu(self, row)
        if not action_map:
            return
        selected = menu.exec(self._menu_pos(row_idx))
        action_key = action_map.get(selected)
        if not action_key:
            return
        self._dispatch_event_action(action_key, row)

    def _dispatch_event_action(self, action_key: str, row: dict) -> None:
        dispatch_event_action(
            action_key,
            row,
            on_edit_anomaly=self.open_edit_anomaly_dialog,
            on_delete_anomaly=self.delete_anomaly,
            on_close_anomaly=self.open_close_dialog,
            on_view_anomaly_details=self.open_anomaly_details,
            on_reopen_anomaly=self.reopen_anomaly,
            on_update_closed_at=self.open_update_closed_at_dialog,
            on_send_line=self.send_line_brief_report,
        )

    def open_close_dialog(self, anomaly_id: str, problem_desc: str):
        self._event_actions.open_close_dialog(anomaly_id, problem_desc)

    def open_update_closed_at_dialog(self, anomaly_id: str, problem_desc: str):
        self._event_actions.open_update_closed_at_dialog(anomaly_id, problem_desc)

    def open_edit_anomaly_dialog(self, anomaly_id: str):
        self._event_actions.open_edit_anomaly_dialog(anomaly_id)

    def delete_anomaly(self, anomaly_id: str, ref_no: str):
        self._event_actions.delete_anomaly(anomaly_id, ref_no)

    def open_anomaly_details(self, anomaly_id: str):
        self._event_actions.open_anomaly_details(anomaly_id)

    def reopen_anomaly(self, anomaly_id: str, ref_no: str):
        self._event_actions.reopen_anomaly(anomaly_id, ref_no)

    def send_line_brief_report(self, row: dict):
        from services import line_service
        from services.event import _export_service

        image = _export_service.render_brief_event_image(row)
        if image is None:
            QMessageBox.critical(self, "失敗", "無法產生精簡報告圖片")
            return

        success, workflow_msg = line_service.send_brief_report_to_line(image)
        if success:
            QMessageBox.information(self, "傳送報告至 LINE", localize_popup_message(workflow_msg))
        else:
            QMessageBox.critical(self, "失敗", localize_popup_message(workflow_msg))
