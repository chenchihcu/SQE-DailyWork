from __future__ import annotations

from PySide6.QtCore import QDate, QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ncr.services import stats_service as warehouse_stats_service
from services import event_service
from ui.layout_constants import (
    GRID_GUTTER,
    PANEL_MARGINS,
    ROOT_SECTION_SPACING,
    ROW_GAP,
)
from ui.status_colors import get_status_palette
from ui.widgets.common_widgets import BrandDivider, KpiCard


class _ClickFilter(QObject):
    def __init__(self, callback, parent=None):
        super().__init__(parent)
        self._callback = callback

    def eventFilter(self, watched, event):  # noqa: N802
        if event.type() == QEvent.Type.MouseButtonPress:
            self._callback()
            return True
        return False


class HomeWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._kpi_cards: dict[str, KpiCard] = {}
        self._kpi_click_filters: dict[str, _ClickFilter] = {}
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
        row0_defs = [
            ("anomaly_count", "總異常件數", get_status_palette("異常").chart, "danger"),
            ("closed_anomaly_count", "已結案", get_status_palette("已結案").chart, "success"),
            ("overdue_open_anomaly_count", "逾期未結", get_status_palette("逾期未結").chart, "danger"),
        ]
        row1_defs = [
            ("standalone_open_anomaly_count", "單獨異常", get_status_palette("單獨異常").chart, "pending"),
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
        root.addStretch(1)

    def _month_key(self) -> str:
        return QDate.currentDate().toString("yyyyMM")

    def _install_kpi_navigation(self) -> None:
        self._set_kpi_action(
            "anomaly_count",
            "開啟本月供應商異常清單",
            lambda: self._open_event_workbench(
                event_scope=event_service.EVENT_SCOPE_ANOMALY_ONLY,
                status="ALL",
            ),
        )
        self._set_kpi_action(
            "closed_anomaly_count",
            "開啟本月已結案供應商異常",
            lambda: self._open_event_workbench(
                event_scope=event_service.EVENT_SCOPE_CLOSED_ONLY,
                status="已結案",
            ),
        )
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
            "開啟同一主視窗內的倉庫不合格品追蹤",
            self._on_defect_kpi_clicked,
        )

    def _set_kpi_action(self, key: str, tooltip: str, callback) -> None:
        card = self._kpi_cards.get(key)
        if card is None:
            return
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setToolTip(tooltip)
        card.setProperty("interactive", True)
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
                defect_count = 0

            summary = dict(summary)
            summary["defect_open_count"] = defect_count

            for key, card in self._kpi_cards.items():
                card.set_value(str(int(summary.get(key, 0))))
        except Exception:
            for card in self._kpi_cards.values():
                card.set_value("-")
