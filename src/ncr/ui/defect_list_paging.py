"""Query-backed pagination and table rendering for the NCR defect list."""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget

from ncr.db import crud
from ncr.models.defect import (
    LIST_FIELD_ORDER,
    PROCESSING_LINE_UNCLASSIFIED,
)
from ncr.models.labels import (
    HINT_CLOSED_CASES_MONTH_SCOPE,
    HINT_CLOSED_CASES_SCOPE,
    HINT_EMPTY_RESULT,
    HINT_OPEN_CASES_SCOPE,
    HINT_PROCESSING_LINE_SCOPE,
    LABEL_CLOSED_COUNT,
    LABEL_DATA_COUNT,
    LABEL_OPEN_COUNT,
)
from ncr.services import stats_service
from ncr.ui.ui_style import (
    create_status_badge,
    create_table_item,
    display_text,
)
from ui.widgets.common_widgets import EMPTY_PLACEHOLDER, preserve_table_sorting


class _DefectListPagingMixin:
    """State and rendering shared by the combined/tracking/history NCR lists.

    The host supplies the widgets, filters, workflow mode, and CRUD connection.
    Rows are intentionally page-local; count and export calls use the same query
    specification so an interaction never targets a stale all-results cache.
    """

    def refresh_data(self) -> None:
        self._has_loaded = True
        self.current_page = 1
        self.refresh_filter_options()
        filters = self.build_filters()

        self._configure_result_scopes(filters)
        self._open_count = crud.count_defects(
            self.conn,
            self._open_filters,
            exclude_status=self._open_exclude_status,
        )
        self._closed_count = crud.count_defects(
            self.conn,
            self._closed_filters,
            exclude_status=self._closed_exclude_status,
        )

        self.update_display()

        total_count = self._open_count + self._closed_count
        self.total_count_label.setText(LABEL_DATA_COUNT.format(total_count))
        self.open_count_label.setText(LABEL_OPEN_COUNT.format(self._open_count))
        self.closed_count_label.setText(LABEL_CLOSED_COUNT.format(self._closed_count))

        active_count = self._active_count()
        self.export_button.setEnabled(active_count > 0)
        self._update_scope_notices(filters, active_count)
        self._update_unclassified_hint()

    def _configure_result_scopes(self, filters: dict[str, str]) -> None:
        self._open_filters = {}
        self._closed_filters = {}
        self._open_exclude_status = None
        self._closed_exclude_status = None

        if self.workflow == "tracking":
            self._open_filters = filters.copy()
            self._open_filters.pop("month", None)
            self._open_exclude_status = "已結案"
            return

        if self.workflow == "trace":
            self._closed_filters = filters.copy()
            self._closed_filters["status"] = "已結案"
            return

        self._open_filters = filters.copy()
        self._open_filters.pop("month", None)
        self._open_exclude_status = "已結案"
        self._closed_filters = filters.copy()
        self._closed_filters["status"] = "已結案"

    def _update_unclassified_hint(self) -> None:
        button = self.unclassified_link_button
        if button is None:
            return
        try:
            counts = stats_service.get_pending_counts_by_processing_line(self.conn)
            pending_unclassified = int(counts.get(PROCESSING_LINE_UNCLASSIFIED, 0))
        except sqlite3.Error:
            pending_unclassified = 0
        if pending_unclassified > 0:
            button.setText(f"另有 {pending_unclassified} 筆未分流待整理　→")
            button.setVisible(True)
        else:
            button.setVisible(False)

    def update_display(self) -> None:
        active_count = self._active_count()
        total_pages = max(1, (active_count + self._page_size - 1) // self._page_size)
        self.current_page = min(max(1, self.current_page), total_pages)
        self.pagination.set_state(
            total_items=active_count,
            current_page=self.current_page,
            page_size=self._page_size,
        )
        active_results = self._load_active_page()

        if self.workflow == "tracking":
            self.populate_table(self.open_table, active_results)
        elif self.workflow == "trace":
            self.populate_table(self.closed_table, active_results)
        else:
            self.populate_table(self._get_active_table(), active_results)

    def _on_page_changed(self, page: int) -> None:
        self.current_page = page
        self.update_display()

    def _on_page_size_changed(self, page_size: int) -> None:
        if page_size <= 0:
            return
        self._page_size = page_size
        self.current_page = 1
        self.update_display()

    def _on_tab_changed(self, index: int) -> None:
        self.current_page = 1
        filters = self.build_filters()
        active_count = self._active_count()
        self._update_scope_notices(filters, active_count)
        self.export_button.setEnabled(active_count > 0)
        self.update_display()

    def _active_count(self) -> int:
        if self.workflow == "tracking":
            return self._open_count
        if self.workflow == "trace":
            return self._closed_count
        assert self.tabs is not None
        return self._open_count if self.tabs.currentIndex() == 0 else self._closed_count

    def _active_query(self) -> tuple[dict[str, str], str | None]:
        if self.workflow == "tracking":
            return self._open_filters, self._open_exclude_status
        if self.workflow == "trace":
            return self._closed_filters, self._closed_exclude_status
        assert self.tabs is not None
        if self.tabs.currentIndex() == 0:
            return self._open_filters, self._open_exclude_status
        return self._closed_filters, self._closed_exclude_status

    def _load_active_page(self) -> list[sqlite3.Row]:
        filters, exclude_status = self._active_query()
        rows = crud.get_defects_page(
            self.conn,
            filters,
            exclude_status=exclude_status,
            page=self.current_page,
            page_size=self._page_size,
        )
        if self.workflow == "tracking":
            self.open_results = rows
        elif self.workflow == "trace":
            self.closed_results = rows
        elif self.tabs is not None and self.tabs.currentIndex() == 0:
            self.open_results = rows
        else:
            self.closed_results = rows
        return rows

    def _get_active_results(self) -> list[sqlite3.Row]:
        if self.workflow == "tracking":
            return self.open_results
        if self.workflow == "trace":
            return self.closed_results
        assert self.tabs is not None
        if self.tabs.currentIndex() == 0:
            return self.open_results
        return self.closed_results

    def _get_active_table(self) -> QTableWidget:
        if self.workflow == "tracking":
            return self.open_table
        if self.workflow == "trace":
            return self.closed_table
        assert self.tabs is not None
        if self.tabs.currentIndex() == 0:
            return self.open_table
        return self.closed_table

    def _update_scope_notices(self, filters: dict[str, str], result_count: int) -> None:
        if self.workflow == "tracking":
            if self.processing_line:
                self.month_scope_notice.setText(
                    f"{HINT_OPEN_CASES_SCOPE}；{HINT_PROCESSING_LINE_SCOPE.format(self.processing_line)}"
                )
            else:
                self.month_scope_notice.setText(HINT_OPEN_CASES_SCOPE)
        elif self.workflow == "trace":
            month_value = filters.get("month", self.month_edit.date().toString("yyyy-MM"))
            self.month_scope_notice.setText(
                HINT_CLOSED_CASES_MONTH_SCOPE.format(month_value)
                if self._uses_month_filter()
                else HINT_CLOSED_CASES_SCOPE
            )
        elif self.tabs is not None and self.tabs.currentIndex() == 0:
            self.month_scope_notice.setText(HINT_OPEN_CASES_SCOPE)
        else:
            month_value = filters.get("month", self.month_edit.date().toString("yyyy-MM"))
            self.month_scope_notice.setText(HINT_CLOSED_CASES_MONTH_SCOPE.format(month_value))

        self.month_scope_notice.show()
        if result_count == 0:
            self.empty_state.set_message(HINT_EMPTY_RESULT)
            self.empty_state.setVisible(True)
            self._get_active_table().setVisible(False)
        else:
            self.empty_state.setVisible(False)
            self._get_active_table().setVisible(True)

    def populate_table(self, table: QTableWidget, rows: list[sqlite3.Row]) -> None:
        with preserve_table_sorting(table):
            table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                row_data = dict(row)
                for column_index, field_name in enumerate(LIST_FIELD_ORDER):
                    value = row_data.get(field_name, "")
                    display_value = display_text(value)

                    if field_name == "status":
                        placeholder = create_table_item(
                            str(value or ""), sort_key=str(value or "")
                        )
                        placeholder.setTextAlignment(
                            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                        )
                        table.setItem(row_index, column_index, placeholder)
                        table.setCellWidget(
                            row_index, column_index, create_status_badge(display_value)
                        )
                        continue

                    raw_sort_key = value
                    if field_name in {"id", "qty"}:
                        try:
                            raw_sort_key = int(value)
                        except (ValueError, TypeError):
                            raw_sort_key = value

                    item = create_table_item(
                        display_value,
                        is_numeric=(field_name in {"id", "qty"}),
                        sort_key=raw_sort_key,
                    )
                    item.setToolTip("" if value is None else str(value))
                    if field_name == "defect_desc" and display_value != EMPTY_PLACEHOLDER:
                        item.setData(Qt.ItemDataRole.DisplayRole, display_value)
                    table.setItem(row_index, column_index, item)
