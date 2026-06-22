from __future__ import annotations

import logging

from PySide6.QtCore import QDate, Qt

logger = logging.getLogger(__name__)
from PySide6.QtWidgets import (
    QAbstractItemView,
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
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services import event_service
from ui.event_display import event_type_display
from ui.popup_i18n import localize_popup_message
from ui.layout_constants import (
    EVENT_LIST_NAME_COL_MIN_WIDTH,
    INLINE_SPACING,
    PANEL_MARGINS,
    ROOT_SECTION_SPACING,
    SUBPANEL_TOOLBAR_MARGINS,
)

from ui.widgets.common_widgets import (
    EMPTY_DISPLAY,
    EmptyStateWidget,
    apply_clickable_affordance,
    apply_table_action_affordance,
    create_status_item,
    style_table,
)
from ui.widgets.event_actions import (
    EventActionsController,
    build_event_action_menu,
    dispatch_event_action,
)
from ui.widgets.pagination_bar import PaginationBar

# Consolidated event-management page: one widget, scope tabs cover every supplier
# event view (including 已結案查詢). Order = most-used first; default = 單獨異常.
EVENT_QUERY_SCOPE_TABS = (
    ("單獨異常", event_service.EVENT_SCOPE_ANOMALY_ONLY, "ANOMALY"),
    ("訪廠發現異常", event_service.EVENT_SCOPE_VISIT_WITH_ANOMALY, "ANOMALY"),
    ("訪廠紀錄", event_service.EVENT_SCOPE_VISIT_ONLY, "VISIT"),
    ("已結案", event_service.EVENT_SCOPE_CLOSED_ONLY, "ANOMALY"),
)

_SORTABLE_COLS: dict[int, str] = {
    0: "event_date",
    2: "supplier_name",
    3: "product_name",
    5: "product_stage",
    10: "status",
}


class EventListWidget(QWidget):
    def __init__(self, main_window, *, mode: str = "query", fixed_scope: str | None = None, fixed_status: str | None = None, lazy_load: bool = False):
        super().__init__()
        self.main_window = main_window
        self.mode = "entry" if mode == "entry" else "query"
        self.fixed_scope = self._normalize_event_scope(fixed_scope) if fixed_scope else None
        self.fixed_status = fixed_status
        self._all_rows: list[dict] = []
        self._current_page = 1
        self._page_size = 12
        self._filter_event_type = "ALL"
        self._sort_col: int | None = None
        self._sort_asc: bool = True
        if self.fixed_scope:
            self._filter_event_scope = self.fixed_scope
            if self.fixed_scope == event_service.EVENT_SCOPE_CLOSED_ONLY:
                self._filter_event_type = "ANOMALY"
            else:
                self._filter_event_type = self._event_type_for_scope(self.fixed_scope)
        else:
            if self.mode == "query":
                # Consolidated event page defaults to the first scope tab (單獨異常),
                # matching the anomaly sidebar badge count.
                self._filter_event_scope = EVENT_QUERY_SCOPE_TABS[0][1]
                self._filter_event_type = self._event_type_for_scope(
                    self._filter_event_scope
                )
            else:
                self._filter_event_scope = None
                self._filter_event_type = "ALL"
        self._filter_status = fixed_status if fixed_status else "ALL"
        self._filter_supplier = ""
        self._filter_yyyymm: str | None = None
        self._filter_overdue_only = False
        self.event_type_combo: QComboBox | None = None
        self.event_scope_tab_bar: QTabBar | None = None
        self.status_combo: QComboBox | None = None
        self.supplier_filter_input: QLineEdit | None = None
        self.month_input: QDateEdit | None = None
        self.all_months_checkbox: QCheckBox | None = None
        self.export_pdf_button: QPushButton | None = None
        self.source_tag_label: QLabel | None = None
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

        control_panel = QFrame()
        control_panel.setProperty("role", "subpanel")
        control_outer = QVBoxLayout(control_panel)
        control_outer.setContentsMargins(*SUBPANEL_TOOLBAR_MARGINS)
        control_outer.setSpacing(8)

        # Row 1: filters / helper + new-event actions (consistent across modes)
        actions_row = QHBoxLayout()
        actions_row.setSpacing(INLINE_SPACING)

        if self.mode == "query":
            if not self.fixed_scope:
                self.event_scope_tab_bar = QTabBar()
                self.event_scope_tab_bar.setObjectName("EventQueryScopeTabs")
                for label, scope, _event_type in EVENT_QUERY_SCOPE_TABS:
                    if self.fixed_status == "已結案" and scope == event_service.EVENT_SCOPE_VISIT_ONLY:
                        # Visit records don't have 'closed' status.
                        continue
                    index = self.event_scope_tab_bar.addTab(label)
                    self.event_scope_tab_bar.setTabData(index, scope)
                apply_clickable_affordance(
                    self.event_scope_tab_bar,
                    tooltip="切換事件管理分類",
                )
                self.event_scope_tab_bar.currentChanged.connect(self._on_event_scope_tab_changed)
                control_outer.addWidget(self.event_scope_tab_bar)

            lbl_supplier = QLabel("供應商")
            lbl_supplier.setProperty("role", "helperText")
            self.supplier_filter_input = QLineEdit()
            self.supplier_filter_input.setPlaceholderText("輸入供應商名稱")
            self.supplier_filter_input.setMinimumWidth(170)
            self.supplier_filter_input.setClearButtonEnabled(True)
            self.supplier_filter_input.returnPressed.connect(self._apply_filters_from_ui)

            lbl_status = QLabel("狀態")
            lbl_status.setProperty("role", "helperText")
            self.status_combo = QComboBox()
            self.status_combo.setFixedWidth(112)
            self.status_combo.addItem("全部", "ALL")
            self.status_combo.addItem("待處理", "待處理")
            self.status_combo.addItem("已結案", "已結案")

            btn_search = QPushButton("查詢")
            btn_search.setProperty("variant", "primary")
            apply_clickable_affordance(btn_search, tooltip="套用篩選條件")
            btn_search.clicked.connect(self._apply_filters_from_ui)
            btn_reset = QPushButton("清除條件")
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
            self.month_input.setFixedWidth(104)
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
        else:
            helper = QLabel("點擊列可編輯、刪除或查看明細")
            helper.setProperty("role", "helperText")
            actions_row.addWidget(helper)
            actions_row.addStretch(1)

        control_outer.addLayout(actions_row)

        # Row 2: pagination + new-event actions + secondary actions (export).
        # The consolidated event page carries both 新增訪廠 and 新增異常; placing
        # them on the toolbar row (not the filter row) keeps the filter row within
        # the 1024-wide minimum without overlapping controls.
        toolbar_row = QHBoxLayout()
        toolbar_row.setSpacing(8)

        if self.mode == "query":
            self.source_tag_label = QLabel(self._source_tag_text())
            self.source_tag_label.setProperty("role", "sourceTag")
            self.source_tag_label.setToolTip("目前列表的資料流程來源")
            toolbar_row.addWidget(self.source_tag_label)

        self.pagination = PaginationBar(
            on_page_changed=self._on_page_changed,
            on_page_size_changed=self._on_page_size_changed,
            default_page_size=self._page_size,
        )
        toolbar_row.addWidget(self.pagination, 1)

        # Shared new-event actions (deduplicated across modes).
        btn_new_visit, btn_new_anomaly = self._build_new_event_buttons()
        if btn_new_visit:
            toolbar_row.addWidget(btn_new_visit)
        if btn_new_anomaly:
            toolbar_row.addWidget(btn_new_anomaly)

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
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels(
            ["日期", "類型", "供應商", "品名", "料號", "階段", "工單", "數量", "問題/摘要", "缺失紀錄", "狀態"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        style_table(self.table)
        apply_table_action_affordance(
            self.table,
            "點擊列選取；雙擊列以開啟編輯、刪除、結案或明細動作選單",
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # 日期
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # 類型
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # 供應商
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # 品名
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # 料號
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # 階段
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)       # 工單（限寬）
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)           # 問題/摘要
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Interactive)       # 缺失紀錄
        header.setSectionResizeMode(10, QHeaderView.ResizeMode.ResizeToContents) # 狀態
        header.setSortIndicatorShown(True)
        header.sectionClicked.connect(self._on_header_clicked)
        # 初始工單欄寬度 — 防止超長工單號擠壓 Stretch 欄；使用者仍可手動拖寬
        self.table.setColumnWidth(6, 140)
        header.setMinimumSectionSize(EVENT_LIST_NAME_COL_MIN_WIDTH)

        self.table.cellDoubleClicked.connect(self._on_table_row_clicked)
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        result_layout.addWidget(self.table, 1)
        if self.fixed_status:
            self.table.setColumnHidden(10, True)

        root.addWidget(result_panel, 1)

        if self.mode == "query":
            self._sync_filter_widgets_from_state()

    def _source_tag_text(self) -> str:
        scope = self.fixed_scope or self._filter_event_scope
        if scope == event_service.EVENT_SCOPE_VISIT_ONLY:
            base = "供應商事件 / 訪廠紀錄"
        elif scope == event_service.EVENT_SCOPE_VISIT_WITH_ANOMALY:
            base = "供應商事件 / 訪廠發現異常"
        elif scope == event_service.EVENT_SCOPE_CLOSED_ONLY:
            base = "供應商事件 / 已結案"
        elif scope == event_service.EVENT_SCOPE_ANOMALY_ONLY:
            base = "供應商事件 / 單獨異常"
        else:
            base = "供應商事件"
        if self._filter_overdue_only:
            return f"{base} / 逾期未結"
        return base

    def _sync_source_tag(self) -> None:
        if self.source_tag_label is None:
            return
        self.source_tag_label.setText(self._source_tag_text())

    def _sync_export_pdf_state(self) -> None:
        if self.export_pdf_button is None:
            return
        has_selection = self._selected_event_row is not None
        self.export_pdf_button.setEnabled(has_selection)
        if has_selection:
            self.export_pdf_button.setToolTip("輸出目前選取的單筆事件 PDF")
            self.export_pdf_button.setStatusTip("輸出目前選取的單筆事件 PDF")
        else:
            self.export_pdf_button.setToolTip("請先選取一筆事件以輸出 PDF")
            self.export_pdf_button.setStatusTip("請先選取一筆事件以輸出 PDF")

    def _build_new_event_buttons(self) -> tuple[QPushButton | None, QPushButton | None]:
        """Create the standard 「新增訪廠」/「新增異常」 button pair shared by query and entry modes."""
        btn_new_visit = None
        btn_new_anomaly = None

        if not self.fixed_scope or self.fixed_scope == event_service.EVENT_SCOPE_VISIT_ONLY:
            btn_new_visit = QPushButton("新增訪廠")
            btn_new_visit.setProperty("variant", "secondary")
            apply_clickable_affordance(btn_new_visit, tooltip="建立新的訪廠紀錄")
            btn_new_visit.clicked.connect(self.main_window.open_new_visit_dialog)

        if not self.fixed_scope or self.fixed_scope in (event_service.EVENT_SCOPE_ANOMALY_ONLY, event_service.EVENT_SCOPE_VISIT_WITH_ANOMALY):
            btn_new_anomaly = QPushButton("新增異常")
            btn_new_anomaly.setProperty("variant", "primary")
            apply_clickable_affordance(btn_new_anomaly, tooltip="建立新的異常單")
            btn_new_anomaly.clicked.connect(self.main_window.open_new_anomaly_dialog)

        return btn_new_visit, btn_new_anomaly

    def _combo_set_current_data(self, combo: QComboBox, value: str) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            combo.setCurrentIndex(0)

    def _normalize_event_scope(self, event_scope: str | None) -> str | None:
        scope_key = str(event_scope or "").strip().upper()
        if scope_key == event_service.EVENT_SCOPE_CLOSED_ONLY:
            return scope_key
        known_scopes = {scope for _label, scope, _event_type in EVENT_QUERY_SCOPE_TABS}
        if scope_key in known_scopes:
            return scope_key
        return None

    def _event_type_for_scope(self, event_scope: str | None) -> str:
        for _label, scope, event_type in EVENT_QUERY_SCOPE_TABS:
            if scope == event_scope:
                return event_type
        return self._filter_event_type

    def _scope_tab_index(self, event_scope: str | None) -> int:
        for index, (_label, scope, _event_type) in enumerate(EVENT_QUERY_SCOPE_TABS):
            if scope == event_scope:
                return index
        return 0

    def _sync_filter_widgets_from_state(self) -> None:
        if self.mode != "query" or self.status_combo is None:
            return
        self._sync_source_tag()
        if self.event_scope_tab_bar is not None:
            index = self._scope_tab_index(self._filter_event_scope)
            self.event_scope_tab_bar.blockSignals(True)
            try:
                self.event_scope_tab_bar.setCurrentIndex(index)
            finally:
                self.event_scope_tab_bar.blockSignals(False)
        self.status_combo.blockSignals(True)
        try:
            self._combo_set_current_data(self.status_combo, self._filter_status)
        finally:
            self.status_combo.blockSignals(False)
        # 已結案分頁固定狀態為已結案：鎖定狀態下拉，避免相互矛盾的篩選。
        if not self.fixed_status:
            is_closed_scope = (
                self._filter_event_scope == event_service.EVENT_SCOPE_CLOSED_ONLY
            )
            self.status_combo.setEnabled(not is_closed_scope)
        if self.supplier_filter_input is not None:
            self.supplier_filter_input.setText(self._filter_supplier)
        if self.all_months_checkbox is not None and self.month_input is not None:
            self.all_months_checkbox.blockSignals(True)
            self.month_input.blockSignals(True)
            if self._filter_yyyymm:
                try:
                    self.all_months_checkbox.setChecked(False)
                    y, m = int(self._filter_yyyymm[:4]), int(self._filter_yyyymm[4:])
                    self.month_input.setDate(QDate(y, m, 1))
                finally:
                    self.month_input.blockSignals(False)
                    self.all_months_checkbox.blockSignals(False)
                self.month_input.setEnabled(True)
            else:
                try:
                    self.all_months_checkbox.setChecked(True)
                finally:
                    self.month_input.blockSignals(False)
                    self.all_months_checkbox.blockSignals(False)
                self.month_input.setEnabled(False)

    def _on_event_scope_tab_changed(self, index: int) -> None:
        if self.mode != "query" or self.event_scope_tab_bar is None:
            return
        scope = self._normalize_event_scope(self.event_scope_tab_bar.tabData(index))
        if scope is None or scope == self._filter_event_scope:
            return
        # Switching scope tabs exits the KPI overdue drill-down lens.
        self._filter_overdue_only = False
        self._filter_event_scope = scope
        self._filter_event_type = self._event_type_for_scope(scope)
        if scope == event_service.EVENT_SCOPE_CLOSED_ONLY:
            # 已結案分頁：狀態固定為已結案、停用狀態下拉。
            self._filter_status = "已結案"
        elif self._filter_status == "已結案":
            # 離開已結案分頁時，已結案狀態不再適用於進行中分頁。
            self._filter_status = "ALL"
        self._sync_filter_widgets_from_state()
        self._sync_source_tag()
        self.refresh_data()

    def _apply_filters_from_ui(self) -> None:
        if self.mode != "query" or self.status_combo is None:
            return
        # Manual filter interaction exits the KPI overdue drill-down lens.
        self._filter_overdue_only = False
        self._filter_status = str(self.status_combo.currentData() or "ALL")
        self._filter_supplier = (
            self.supplier_filter_input.text().strip() if self.supplier_filter_input else ""
        )
        if self.all_months_checkbox is not None and not self.all_months_checkbox.isChecked() and self.month_input is not None:
            self._filter_yyyymm = self.month_input.date().toString("yyyyMM")
        else:
            self._filter_yyyymm = None
        # Drop the "逾期未結" source tag now that the overdue lens is cleared.
        self._sync_source_tag()
        self.refresh_data()

    def _reset_filters_ui(self) -> None:
        if self.mode != "query":
            return
        self._filter_overdue_only = False
        self._filter_status = "ALL"
        self._filter_supplier = ""
        self._filter_yyyymm = None
        self._sync_filter_widgets_from_state()
        self.refresh_data()

    def _has_active_filters(self) -> bool:
        return (
            self._filter_status != "ALL"
            or bool(str(self._filter_supplier or "").strip())
            or self._filter_yyyymm is not None
            or self._filter_overdue_only
        )

    def _default_empty_message(self) -> str:
        if self.fixed_scope == event_service.EVENT_SCOPE_VISIT_ONLY:
            return "目前沒有訪廠紀錄，請先新增訪廠。"
        if self.fixed_scope == event_service.EVENT_SCOPE_ANOMALY_ONLY:
            return "目前沒有異常事件，請先新增異常。"
        if self.fixed_scope == event_service.EVENT_SCOPE_CLOSED_ONLY:
            return "目前沒有已結案紀錄。"
        return "目前沒有事件資料，請先新增訪廠或異常。"

    def _update_empty_state(self) -> None:
        has_rows = len(self._all_rows) > 0
        self.empty_state.setVisible(not has_rows)
        self.table.setVisible(has_rows)
        if not has_rows:
            if self._has_active_filters():
                self.empty_state.set_message("找不到符合條件的事件，請調整篩選條件。")
            else:
                self.empty_state.set_message(self._default_empty_message())

    def _normalize_month_filter(self, yyyymm: str | None) -> str | None:
        text = str(yyyymm or "").strip().replace("-", "")
        if len(text) == 6 and text.isdigit():
            return text
        return None

    def _on_header_clicked(self, col_idx: int) -> None:
        if col_idx not in _SORTABLE_COLS:
            return
        if self._sort_col == col_idx:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col_idx
            self._sort_asc = True
        order = Qt.SortOrder.AscendingOrder if self._sort_asc else Qt.SortOrder.DescendingOrder
        self.table.horizontalHeader().setSortIndicator(col_idx, order)
        self._apply_sort()
        self._current_page = 1
        self._render_current_page()

    def _apply_sort(self) -> None:
        if self._sort_col is None or self._sort_col not in _SORTABLE_COLS:
            return
        key = _SORTABLE_COLS[self._sort_col]
        self._all_rows.sort(
            key=lambda r: str(r.get(key) or "").lower(),
            reverse=not self._sort_asc,
        )

    def apply_quick_filters(
        self,
        *,
        event_type: str = "ANOMALY",
        supplier_keyword: str = "",
        yyyymm: str | None = None,
        status: str = "ALL",
        event_scope: str | None = None,
        overdue_only: bool = False,
    ):
        event_type_key = str(event_type or "").strip().upper()
        scope_key = self._normalize_event_scope(event_scope)
        if self.mode == "query":
            if self.fixed_scope:
                pass
            elif scope_key is not None:
                self._filter_event_scope = scope_key
                self._filter_event_type = self._event_type_for_scope(scope_key)
            elif event_type_key == "ANOMALY":
                self._filter_event_scope = event_service.EVENT_SCOPE_ANOMALY_ONLY
                self._filter_event_type = "ANOMALY"
            elif event_type_key == "VISIT":
                self._filter_event_scope = event_service.EVENT_SCOPE_VISIT_ONLY
                self._filter_event_type = "VISIT"
            else:
                self._filter_event_type = "ALL"
        else:
            if event_type_key == "ANOMALY":
                self._filter_event_type = "ANOMALY"
            elif event_type_key == "VISIT":
                self._filter_event_type = "VISIT"
            else:
                self._filter_event_type = "ALL"

        status_key = str(status or "").strip()
        status_map = {
            "ALL": "ALL",
            "全部": "ALL",
            "待處理": "待處理",
            "已結案": "已結案",
        }
        self._filter_status = status_map.get(status_key.upper(), status_map.get(status_key, "ALL"))
        # Allow '已結案' even in query mode if it's explicitly requested or fixed.
        if self.mode == "query" and self._filter_status not in ("ALL", "待處理", "已結案"):
            self._filter_status = "ALL"
        self._filter_supplier = str(supplier_keyword or "").strip()
        self._filter_overdue_only = bool(overdue_only)

        # Make the drill-down month an explicit, visible filter (control bar
        # reflects it) rather than a one-time hidden condition.
        self._filter_yyyymm = self._normalize_month_filter(yyyymm)

        self._sync_filter_widgets_from_state()
        self.refresh_data()

    def refresh_data(self):
        self._has_loaded = True
        filters = {
            "event_type": self._filter_event_type,
            "status": self._filter_status,
            "supplier": self._filter_supplier,
        }
        if self.mode == "query" and self._filter_event_scope:
            filters["event_scope"] = self._filter_event_scope
        if self._filter_yyyymm:
            filters["yyyymm"] = self._filter_yyyymm
        if self._filter_overdue_only:
            filters["overdue_only"] = True
        self._all_rows = event_service.list_events(filters)
        self._apply_sort()
        self._current_page = 1
        self._render_current_page()

    def _render_current_page(self):
        self._selected_event_row = None
        total_pages = self._total_pages()
        self._current_page = min(max(1, self._current_page), total_pages)
        start = (self._current_page - 1) * self._page_size
        end = start + self._page_size
        page_rows = self._all_rows[start:end]

        self.table.setRowCount(0)
        for idx, row in enumerate(page_rows):
            self.table.insertRow(idx)
            event_type = event_type_display(str(row.get("event_type") or ""))
            date_item = QTableWidgetItem(self._text_or_dash(row.get("event_date")))
            date_item.setData(Qt.ItemDataRole.UserRole, dict(row))
            self.table.setItem(idx, 0, date_item)
            self.table.setItem(idx, 1, QTableWidgetItem(event_type))
            self.table.setItem(idx, 2, QTableWidgetItem(self._text_or_dash(row.get("supplier_name"))))
            self.table.setItem(idx, 3, QTableWidgetItem(self._text_or_dash(row.get("product_name"))))
            self.table.setItem(idx, 4, QTableWidgetItem(self._text_or_dash(row.get("product_code"))))
            self.table.setItem(idx, 5, QTableWidgetItem(self._text_or_dash(row.get("product_stage"))))
            self.table.setItem(idx, 6, QTableWidgetItem(self._text_or_dash(row.get("work_order_no"))))
            self.table.setItem(idx, 7, QTableWidgetItem(self._format_positive_qty(row.get("production_qty"))))
            self.table.setItem(idx, 8, QTableWidgetItem(self._text_or_dash(row.get("content"))))
            defect_summary = row.get("defect_note_summary") or row.get("pending_items")
            self.table.setItem(idx, 9, QTableWidgetItem(self._text_or_dash(defect_summary)))

            status_text = str(row.get("status") or "").strip() or "-"
            self.table.setItem(idx, 10, create_status_item(status_text))

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

    def _format_positive_qty(self, value) -> str:
        if value is None:
            return "-"
        text = str(value).strip()
        if not text:
            return "-"
        try:
            qty = int(text)
        except (TypeError, ValueError):
            return "-"
        if qty <= 0:
            return "-"
        return str(qty)

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

        try:
            default_name = event_service.default_event_pdf_filename(row)
        except Exception:
            logger.exception("取得預設 PDF 檔名失敗")
            default_name = "SQE_事件單.pdf"
        target, _ = QFileDialog.getSaveFileName(
            self,
            "輸出PDF",
            default_name,
            "PDF Files (*.pdf)",
        )
        if not target:
            return
        if not target.lower().endswith(".pdf"):
            target = f"{target}.pdf"

        ok, msg = event_service.export_event_pdf(target, row)
        if ok:
            QMessageBox.information(self, "成功", localize_popup_message(msg))
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
            on_edit_visit=self.open_edit_visit_dialog,
            on_delete_visit=self.delete_visit,
            on_open_visit_detail=self.open_visit_detail,
            on_preview_anomaly=self.open_preview_anomaly_dialog,
            on_preview_visit=self.open_preview_visit_dialog,
            on_reopen_anomaly=self.reopen_anomaly,
            on_send_line=self.send_line_brief_report,
        )

    def open_close_dialog(self, anomaly_id: str, problem_desc: str):
        self._event_actions.open_close_dialog(anomaly_id, problem_desc)

    def open_edit_anomaly_dialog(self, anomaly_id: str):
        self._event_actions.open_edit_anomaly_dialog(anomaly_id)

    def delete_anomaly(self, anomaly_id: str, ref_no: str):
        self._event_actions.delete_anomaly(anomaly_id, ref_no)

    def open_edit_visit_dialog(self, visit_id: str):
        self._event_actions.open_edit_visit_dialog(visit_id)

    def delete_visit(self, visit_id: str, visit_date: str):
        self._event_actions.delete_visit(visit_id, visit_date)

    def open_visit_detail(self, visit_id: str):
        self._event_actions.open_visit_detail(visit_id)

    def open_preview_anomaly_dialog(self, anomaly_id: str):
        self._event_actions.open_preview_anomaly_dialog(anomaly_id)

    def open_preview_visit_dialog(self, visit_id: str):
        self._event_actions.open_preview_visit_dialog(visit_id)

    def reopen_anomaly(self, anomaly_id: str, ref_no: str):
        self._event_actions.reopen_anomaly(anomaly_id, ref_no)

    def send_line_brief_report(self, row: dict):
        from services import line_service

        image = event_service.render_brief_event_image(row)
        if image is None:
            QMessageBox.critical(self, "失敗", "無法產生精簡報告圖片")
            return

        success, workflow_msg = line_service.send_brief_report_to_line(image)
        if success:
            QMessageBox.information(self, "傳送報告至 LINE", localize_popup_message(workflow_msg))
        else:
            QMessageBox.critical(self, "失敗", localize_popup_message(workflow_msg))
