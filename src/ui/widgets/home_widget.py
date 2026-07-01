from __future__ import annotations

import logging

from PySide6.QtCore import QDate, QEvent, QObject, Qt

logger = logging.getLogger(__name__)
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ncr.services import stats_service as warehouse_stats_service
from services import event_service
from ui.layout_constants import (
    BACKLOG_SUPPLIER_MAX_COL_WIDTH,
    GRID_GUTTER,
    PANEL_MARGINS,
    ROOT_SECTION_SPACING,
    ROW_GAP,
)
from ui.status_colors import get_status_palette
from ui.widgets.common_widgets import (
    BrandDivider,
    EmptyStateWidget,
    KpiCard,
    apply_table_action_affordance,
    create_status_item,
    style_table,
)


class _ClickFilter(QObject):
    def __init__(self, callback, parent=None):
        super().__init__(parent)
        self._callback = callback

    def eventFilter(self, watched, event):  # noqa: N802
        et = event.type()
        if et == QEvent.Type.MouseButtonPress:
            self._callback()
            return True
        if et == QEvent.Type.KeyPress and event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        ):
            self._callback()
            return True
        return False


class HomeWidget(QWidget):
    # Daily-cockpit backlog list size (read-only actionable to-do list).
    _BACKLOG_LIMIT = 8

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._kpi_cards: dict[str, KpiCard] = {}
        self._kpi_click_filters: dict[str, _ClickFilter] = {}
        self._backlog_rows: list[dict] = []
        self._setup_ui()
        self.refresh_data()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(ROOT_SECTION_SPACING)

        kpi_panel = QFrame()
        kpi_panel.setObjectName("HomeKpiPanel")
        kpi_panel.setProperty("role", "panel")
        kpi_outer = QVBoxLayout(kpi_panel)
        kpi_outer.setContentsMargins(*PANEL_MARGINS)
        kpi_outer.setSpacing(8)

        self._kpi_title = QLabel()
        self._kpi_title.setProperty("role", "sectionTitle")
        kpi_outer.addWidget(self._kpi_title)
        kpi_outer.addWidget(BrandDivider())

        kpi_grid = QGridLayout()
        kpi_grid.setHorizontalSpacing(GRID_GUTTER)
        kpi_grid.setVerticalSpacing(ROW_GAP)
        # 四象限 KPI（2×2）：逾期未結 / 單獨異常 / 訪廠發現異常 / 倉庫待處理不合格品。
        # 已移除「總異常件數」「已結案」兩卡——其導覽分別由「單獨異常」卡與事件頁「已結案」scope 涵蓋。
        row0_defs = [
            ("overdue_open_anomaly_count", "逾期未結", get_status_palette("逾期未結").chart, "danger"),
            ("standalone_open_anomaly_count", "單獨異常", get_status_palette("單獨異常").chart, "pending"),
        ]
        row1_defs = [
            ("visit_open_anomaly_count", "訪廠發現異常", get_status_palette("訪廠發現異常").chart, "info"),
            ("defect_open_count", "倉庫待處理不合格品", get_status_palette("異常").chart, "danger"),
        ]
        for col, (key, text, color, tone) in enumerate(row0_defs):
            card = KpiCard(text, color, tone=tone)
            self._kpi_cards[key] = card
            kpi_grid.addWidget(card, 0, col)
            kpi_grid.setColumnStretch(col, 1)
        for col, (key, text, color, tone) in enumerate(row1_defs):
            card = KpiCard(text, color, tone=tone)
            self._kpi_cards[key] = card
            kpi_grid.addWidget(card, 1, col)
            kpi_grid.setColumnStretch(col, 1)

        self._install_kpi_navigation()

        kpi_outer.addLayout(kpi_grid)
        root.addWidget(kpi_panel)

        # Daily-cockpit backlog: read-only actionable to-do list that fills the
        # first screen. Reads existing services only; rows route through existing
        # navigation (no new write paths).
        root.addWidget(self._build_backlog_panel(), 1)

    def _build_backlog_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("HomeBacklogPanel")
        panel.setProperty("role", "panel")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(*PANEL_MARGINS)
        outer.setSpacing(8)

        self._backlog_title = QLabel("待辦事項（待處理異常，逾期優先）")
        self._backlog_title.setProperty("role", "sectionTitle")
        outer.addWidget(self._backlog_title)
        outer.addWidget(BrandDivider())

        self._backlog_table = QTableWidget()
        self._backlog_table.setObjectName("HomeBacklogTable")
        self._backlog_table.setColumnCount(4)
        self._backlog_table.setHorizontalHeaderLabels(
            ["日期", "供應商", "問題/摘要", "狀態"]
        )
        style_table(self._backlog_table)
        apply_table_action_affordance(
            self._backlog_table,
            "點擊待辦列開啟事件管理頁，並帶入該供應商的待處理異常篩選",
        )
        header = self._backlog_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._backlog_table.cellClicked.connect(self._on_backlog_row_clicked)
        outer.addWidget(self._backlog_table, 1)

        self._backlog_empty = EmptyStateWidget(
            "目前沒有待處理異常",
            "本月供應商異常均已結案，或尚無待處理項目。",
            parent=self,
        )
        self._backlog_empty.setVisible(False)
        outer.addWidget(self._backlog_empty)

        # 倉庫待處理彙總列：唯讀導覽捷徑（點擊跳轉待處理不合格品頁，不新增寫入）。
        self._warehouse_summary_btn = QPushButton("倉庫待處理不合格品：— 件　→")
        self._warehouse_summary_btn.setObjectName("HomeBacklogWarehouseLink")
        self._warehouse_summary_btn.setProperty("variant", "secondary")
        self._warehouse_summary_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._warehouse_summary_btn.setToolTip("開啟同一視窗內的待處理不合格品")
        self._warehouse_summary_btn.clicked.connect(self._on_defect_kpi_clicked)
        outer.addWidget(self._warehouse_summary_btn)

        return panel

    def _month_key(self) -> str:
        return QDate.currentDate().toString("yyyyMM")

    def _install_kpi_navigation(self) -> None:
        self._set_kpi_action(
            "overdue_open_anomaly_count",
            "開啟本月逾期未結（待處理且逾期）清單",
            lambda: self._open_event_workbench(
                event_scope=event_service.EVENT_SCOPE_ANOMALY_ONLY,
                status="待處理",
                overdue=True,
            ),
        )
        self._set_kpi_action(
            "standalone_open_anomaly_count",
            "開啟本月單獨異常待處理清單",
            lambda: self._open_event_workbench(
                event_scope=event_service.EVENT_SCOPE_ANOMALY_ONLY,
                status="待處理",
            ),
        )
        self._set_kpi_action(
            "visit_open_anomaly_count",
            "開啟本月訪廠發現異常待處理清單",
            lambda: self._open_event_workbench(
                event_scope=event_service.EVENT_SCOPE_VISIT_WITH_ANOMALY,
                status="待處理",
            ),
        )
        self._set_kpi_action(
            "defect_open_count",
            "開啟同一主視窗內的待處理不合格品",
            self._on_defect_kpi_clicked,
        )

    def _set_kpi_action(self, key: str, tooltip: str, callback) -> None:
        card = self._kpi_cards.get(key)
        if card is None:
            return
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setToolTip(tooltip)
        card.setProperty("interactive", True)
        # Keyboard reachability + screen-reader label (a11y §5): the card is a
        # plain QFrame, so give it focus and announce its KPI title + action.
        card.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        card.setAccessibleName(card.title_label.text())
        card.setAccessibleDescription(tooltip)
        click_filter = _ClickFilter(callback, self)
        self._kpi_click_filters[key] = click_filter
        card.installEventFilter(click_filter)

    def _open_event_workbench(
        self, *, event_scope: str, status: str, overdue: bool = False
    ) -> None:
        open_filters = getattr(self.main_window, "open_event_query_with_filters", None)
        if not callable(open_filters):
            return
        open_filters(
            event_type="ANOMALY",
            yyyymm=self._month_key(),
            status=status,
            event_scope=event_scope,
            overdue_only=overdue,
        )

    def _on_defect_kpi_clicked(self):
        self.main_window.open_warehouse_nonconforming_tracker()

    def refresh_data(self):
        month_text = QDate.currentDate().toString("yyyy-MM")
        self._kpi_title.setText(f"本月品質工作台（{month_text}）")
        defect_count = 0
        try:
            summary = event_service.get_monthly_stats()

            from database.connection import get_connection

            try:
                with get_connection() as conn:
                    warehouse_summary = (
                        warehouse_stats_service.get_warehouse_nonconforming_summary(
                            conn
                        )
                    )
                    defect_count = int(warehouse_summary.get("open_count", 0))
            except Exception:
                logger.exception("讀取不合格品統計失敗")
                defect_count = 0

            summary = dict(summary)
            summary["defect_open_count"] = defect_count

            for key, card in self._kpi_cards.items():
                card.set_value(str(int(summary.get(key, 0))))
        except Exception:
            logger.exception("讀取儀表板摘要失敗")
            for card in self._kpi_cards.values():
                card.set_value("-")

        self._refresh_backlog(defect_count)

    def _refresh_backlog(self, defect_count: int) -> None:
        """Populate the read-only backlog list from existing services only."""
        try:
            overdue_rows = event_service.list_events(
                {"event_type": "ANOMALY", "status": "待處理", "overdue_only": True}
            )
        except Exception:
            logger.exception("讀取逾期待辦清單失敗")
            overdue_rows = []
        try:
            pending_rows = event_service.list_events(
                {"event_type": "ANOMALY", "status": "待處理"}
            )
        except Exception:
            logger.exception("讀取待辦清單失敗")
            pending_rows = []

        # 逾期優先，再補其餘待處理；以 event_id 去重。
        merged: list[dict] = []
        seen: set[str] = set()
        for row in [*overdue_rows, *pending_rows]:
            event_id = row.get("event_id") or row.get("anomaly_id")
            key = str(event_id or f"{row.get('supplier_name','')}_{row.get('event_date','')}_{row.get('content','')}")
            if key in seen:
                continue
            seen.add(key)
            merged.append(row)

        self._render_backlog_rows(merged[: self._BACKLOG_LIMIT])

        self._warehouse_summary_btn.setText(
            f"倉庫待處理不合格品：{defect_count} 件　→"
        )

    def _render_backlog_rows(self, rows: list[dict]) -> None:
        self._backlog_rows = list(rows)
        has_rows = bool(rows)
        self._backlog_table.setVisible(has_rows)
        self._backlog_empty.setVisible(not has_rows)

        self._backlog_table.setRowCount(0)
        for idx, row in enumerate(rows):
            self._backlog_table.insertRow(idx)
            date_item = QTableWidgetItem(str(row.get("event_date") or "—"))
            date_item.setData(Qt.ItemDataRole.UserRole, dict(row))
            self._backlog_table.setItem(idx, 0, date_item)
            full_name = str(row.get("supplier_name") or "—")
            name_item = QTableWidgetItem(full_name)
            name_item.setToolTip(full_name)
            self._backlog_table.setItem(idx, 1, name_item)
            self._backlog_table.setItem(
                idx, 2, QTableWidgetItem(str(row.get("content") or "—"))
            )
            self._backlog_table.setItem(
                idx, 3, create_status_item(str(row.get("status") or "待處理"))
            )

        # Cap supplier column so very long names don't crowd the problem/summary column.
        actual_w = self._backlog_table.horizontalHeader().sectionSize(1)
        if actual_w > BACKLOG_SUPPLIER_MAX_COL_WIDTH:
            self._backlog_table.setColumnWidth(1, BACKLOG_SUPPLIER_MAX_COL_WIDTH)

    def _on_backlog_row_clicked(self, row_idx: int, _column_idx: int) -> None:
        item = self._backlog_table.item(row_idx, 0)
        if item is None:
            return
        payload = item.data(Qt.ItemDataRole.UserRole)
        supplier = (
            str(payload.get("supplier_name") or "") if isinstance(payload, dict) else ""
        )
        open_filters = getattr(self.main_window, "open_event_query_with_filters", None)
        if not callable(open_filters):
            return
        open_filters(
            event_type="ANOMALY",
            supplier_keyword=supplier,
            yyyymm=self._month_key(),
            status="待處理",
            event_scope=event_service.EVENT_SCOPE_ANOMALY_ONLY,
        )
