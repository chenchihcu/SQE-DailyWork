from __future__ import annotations

import logging

from PySide6.QtCore import QDate, Qt

from database import repository

logger = logging.getLogger(__name__)


class _EventListFilterMixin:
    """Filter, scope, and query state management for EventListWidget.

    Expects the host (self) to provide:
      - Instance attributes: self.mode | self.fixed_scope | self.fixed_status
      - Filter attributes: self._filter_event_scope | self._filter_event_type |
        self._filter_status | self._filter_supplier | self._filter_yyyymm |
        self._filter_overdue_only | self._sort_col | self._sort_asc |
        self._all_rows
      - UI widget attributes: self.source_tag_label | self.status_combo |
        self.event_scope_tab_bar | self.supplier_filter_input |
        self.all_months_checkbox | self.month_input | self.export_pdf_button |
        self.empty_state | self.table | self.pagination
      - Host methods: self.refresh_data() | self._render_current_page()
    """

    # -- Scope / source helpers -----------------------------------------------

    def _source_tag_text(self) -> str:
        scope = self.fixed_scope or self._filter_event_scope
        if scope == repository.EVENT_SCOPE_VISIT_ONLY:
            base = "供應商事件 / 訪廠紀錄"
        elif scope == repository.EVENT_SCOPE_VISIT_WITH_ANOMALY:
            base = "供應商事件 / 訪廠發現異常"
        elif scope == repository.EVENT_SCOPE_CLOSED_ONLY:
            base = "供應商事件 / 已結案"
        elif scope == repository.EVENT_SCOPE_ANOMALY_ONLY:
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

    # -- Scope / filter state helpers -----------------------------------------

    def _combo_set_current_data(self, combo, value: str) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            combo.setCurrentIndex(0)

    def _normalize_event_scope(self, event_scope: str | None) -> str | None:
        from ui.widgets.defect_list_widget import EVENT_QUERY_SCOPE_TABS

        scope_key = str(event_scope or "").strip().upper()
        if scope_key == repository.EVENT_SCOPE_CLOSED_ONLY:
            return scope_key
        known_scopes = {scope for _label, scope, _event_type in EVENT_QUERY_SCOPE_TABS}
        if scope_key in known_scopes:
            return scope_key
        return None

    def _event_type_for_scope(self, event_scope: str | None) -> str:
        from ui.widgets.defect_list_widget import EVENT_QUERY_SCOPE_TABS

        for _label, scope, event_type in EVENT_QUERY_SCOPE_TABS:
            if scope == event_scope:
                return event_type
        return self._filter_event_type

    def _scope_tab_index(self, event_scope: str | None) -> int:
        from ui.widgets.defect_list_widget import EVENT_QUERY_SCOPE_TABS

        for index, (_label, scope, _event_type) in enumerate(EVENT_QUERY_SCOPE_TABS):
            if scope == event_scope:
                return index
        return 0

    # -- Filter UI sync --------------------------------------------------------

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
                self._filter_event_scope == repository.EVENT_SCOPE_CLOSED_ONLY
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

    # -- Event handlers (called from signals) ---------------------------------

    def set_event_scope(self, event_scope: str | None) -> None:
        """切換事件 scope（取代原頁內 scope 分頁；保留 supplier / 月份篩選）。

        由側欄 scope 導覽列觸發。KPI / 統計下鑽請改用 apply_quick_filters（會一併設定
        supplier / 月份 / 狀態）。再次選取同一 scope 仍會刷新（導覽語意）。
        """
        if self.mode != "query" or self.fixed_scope:
            return
        scope = self._normalize_event_scope(event_scope)
        if scope is None:
            return
        # 切換 scope 會離開 KPI 逾期下鑽 lens。
        self._filter_overdue_only = False
        self._filter_event_scope = scope
        self._filter_event_type = self._event_type_for_scope(scope)
        if scope == repository.EVENT_SCOPE_CLOSED_ONLY:
            # 已結案：狀態固定為已結案、停用狀態下拉。
            self._filter_status = "已結案"
        elif self._filter_status == "已結案":
            # 離開已結案時，已結案狀態不再適用於進行中 scope。
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
        if self.fixed_scope == repository.EVENT_SCOPE_VISIT_ONLY:
            return "目前沒有訪廠紀錄，請先新增訪廠。"
        if self.fixed_scope == repository.EVENT_SCOPE_ANOMALY_ONLY:
            return "目前沒有異常事件，請先新增異常。"
        if self.fixed_scope == repository.EVENT_SCOPE_CLOSED_ONLY:
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

    # -- Sorting ---------------------------------------------------------------

    def _on_header_clicked(self, col_idx: int) -> None:
        from ui.widgets.defect_list_widget import _SORTABLE_COLS

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
        from ui.widgets.defect_list_widget import _SORTABLE_COLS

        if self._sort_col is None or self._sort_col not in _SORTABLE_COLS:
            return
        key = _SORTABLE_COLS[self._sort_col]
        self._all_rows.sort(
            key=lambda r: (str(r.get(key) or "") or str(r.get("event_date") or "")).lower(),
            reverse=not self._sort_asc,
        )

    # -- Public quick-filter API -----------------------------------------------

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
                self._filter_event_scope = repository.EVENT_SCOPE_ANOMALY_ONLY
                self._filter_event_type = "ANOMALY"
            elif event_type_key == "VISIT":
                self._filter_event_scope = repository.EVENT_SCOPE_VISIT_ONLY
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
        if self.mode == "query" and self._filter_status not in ("ALL", "待處理", "已結案"):
            self._filter_status = "ALL"
        self._filter_supplier = str(supplier_keyword or "").strip()
        self._filter_overdue_only = bool(overdue_only)
        self._filter_yyyymm = self._normalize_month_filter(yyyymm)

        self._sync_filter_widgets_from_state()
        self.refresh_data()
