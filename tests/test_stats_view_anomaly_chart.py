from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QChartView,
    QHorizontalStackedBarSeries,
    QLineSeries,
    QScatterSeries,
    QValueAxis,
)
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
)

from services import event_service
from ui.layout_constants import SCROLLBAR_WIDTH
from ui.status_colors import get_status_palette
from ui.theme import TOKENS, apply_app_theme
from ui.widgets.stats_view_widget import StatsViewWidget


class _DummyMainWindow:
    def __init__(self) -> None:
        self.quick_filter_calls: list[dict[str, str | None]] = []
        self.warehouse_tracker_calls = 0

    def open_event_query_with_filters(
        self,
        *,
        event_type: str = "ANOMALY",
        supplier_keyword: str = "",
        yyyymm: str | None = None,
        status: str = "ALL",
        event_scope: str | None = None,
        overdue_only: bool = False,
    ) -> None:
        self.quick_filter_calls.append(
            {
                "event_type": event_type,
                "supplier_keyword": supplier_keyword,
                "yyyymm": yyyymm,
                "status": status,
                "event_scope": event_scope,
                "overdue_only": overdue_only,
            }
        )

    def open_warehouse_nonconforming_tracker(self) -> None:
        self.warehouse_tracker_calls += 1


class StatsViewAnomalyChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        apply_app_theme(cls.app)


    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            cls.app.quit()

    def setUp(self) -> None:
        self._widgets: list[StatsViewWidget] = []

    def tearDown(self) -> None:
        for widget in self._widgets:
            widget.close()
        self.app.processEvents()

    def _build_widget(
        self,
        summary: dict,
        *,
        month: QDate,
        trend_data: list[dict] | None = None,
        main_window: _DummyMainWindow | None = None,
    ) -> tuple[StatsViewWidget, _DummyMainWindow]:
        host = main_window or _DummyMainWindow()
        with patch("services.event_service.get_monthly_stats", return_value=summary), \
             patch("services.event_service.get_anomaly_trend", return_value=trend_data or []), \
             patch("services.event_service.get_responsible_person_stats", return_value=[]):
            widget = StatsViewWidget(main_window=host)
            widget.month_input.setDate(month)
            widget.refresh_data()

        widget.show()
        self.app.processEvents()
        self._widgets.append(widget)
        return widget, host

    def test_stats_view_renders_stacked_chart_in_desc_order_with_status_colors(self) -> None:
        summary = {
            "anomaly_count": 9,
            "visit_count": 4,
            "closed_anomaly_count": 2,
            "open_anomaly_count": 7,
            "top_suppliers_by_anomaly": [
                {
                    "supplier_name": "Supplier-C",
                    "anomaly_count": 5,
                    "open_anomaly_count": 3,
                    "overdue_open_anomaly_count": 1,
                    "closed_anomaly_count": 2,
                    "avg_resolution_time": 4.5,
                },
                {
                    "supplier_name": "Supplier-A",
                    "anomaly_count": 3,
                    "open_anomaly_count": 2,
                    "overdue_open_anomaly_count": 0,
                    "closed_anomaly_count": 1,
                    "avg_resolution_time": 2.1,
                },
                {
                    "supplier_name": "Supplier-B",
                    "anomaly_count": 1,
                    "open_anomaly_count": 1,
                    "overdue_open_anomaly_count": 0,
                    "closed_anomaly_count": 0,
                    "avg_resolution_time": 0.0,
                },
            ],
        }
        widget, _host = self._build_widget(summary, month=QDate(2026, 4, 1))

        series = widget._chart_series
        self.assertIsNotNone(series)
        assert series is not None
        self.assertIsInstance(series, QHorizontalStackedBarSeries)

        bar_sets = series.barSets()
        self.assertEqual(3, len(bar_sets))
        overdue_set = bar_sets[0]
        ongoing_set = bar_sets[1]
        closed_set = bar_sets[2]
        
        self.assertEqual("逾期未結", overdue_set.label())
        self.assertEqual("進行中", ongoing_set.label())
        self.assertEqual("已結案", closed_set.label())
        
        # In setup, B is last, so it's index 0 in reversed categories
        self.assertEqual(0, int(overdue_set.at(0))) # B
        self.assertEqual(0, int(overdue_set.at(1))) # A
        self.assertEqual(1, int(overdue_set.at(2))) # C

        category_axis = next(
            axis
            for axis in widget._chart.axes(Qt.Orientation.Vertical)
            if isinstance(axis, QBarCategoryAxis)
        )
        self.assertEqual(
            ["Supplier-B", "Supplier-A", "Supplier-C"],
            category_axis.categories(),
        )

        self.assertEqual(
            QColor(get_status_palette("逾期未結").chart).name().lower(),
            overdue_set.color().name().lower(),
        )
        self.assertEqual(
            QColor(get_status_palette("已結案").chart).name().lower(),
            closed_set.color().name().lower(),
        )
        assert widget._rank_month_label is not None
        self.assertEqual("月份：2026-04", widget._rank_month_label.text())
        self.assertTrue(widget._chart.legend().isVisible())

        self.assertFalse(
            any(isinstance(series, QLineSeries) for series in widget._chart.series())
        )
        self.assertTrue(
            any(
                isinstance(series, QScatterSeries)
                and series.name() == "平均處理時效 (天)"
                for series in widget._chart.series()
            )
        )
        labels = [label.text() for label in widget.findChildren(QLabel)]
        self.assertIn("供應商事件趨勢分析 (過去 6 個月)", labels)
        self.assertIn("供應商事件責任人績效 (總件數 vs 平均處理時效)", labels)
        self.assertIn("供應商事件風險堆疊圖", labels)
        self.assertEqual([], widget.findChildren(QTabWidget))
        self.assertEqual("statsInfoBanner", widget.info_banner.property("role"))

    def test_stats_view_shortens_long_supplier_labels_and_disables_axis_truncation(self) -> None:
        summary = {
            "anomaly_count": 7,
            "visit_count": 0,
            "closed_anomaly_count": 0,
            "open_anomaly_count": 7,
            "top_suppliers_by_anomaly": [
                {"supplier_name": "NorthStarSupplierAlpha", "anomaly_count": 4, "avg_resolution_time": 5.0},
                {"supplier_name": "VeryLongSupplierBeta", "anomaly_count": 3, "avg_resolution_time": 1.0},
            ],
        }
        widget, _host = self._build_widget(summary, month=QDate(2026, 9, 1))

        category_axis = next(
            axis
            for axis in widget._chart.axes(Qt.Orientation.Vertical)
            if isinstance(axis, QBarCategoryAxis)
        )
        categories = category_axis.categories()
        self.assertEqual(["VeryLo…rBeta", "NorthS…Alpha"], categories)
        self.assertTrue(all(len(label) <= 13 for label in categories))
        self.assertTrue(all(label != "..." for label in categories))
        self.assertFalse(category_axis.truncateLabels())
        self.assertEqual(0, category_axis.labelsAngle())
        self.assertEqual("", category_axis.titleText())
        self.assertFalse(category_axis.isTitleVisible())

    def test_stats_view_chart_uses_enlarged_axis_fonts_and_shows_legend(self) -> None:
        summary = {
            "anomaly_count": 5,
            "visit_count": 1,
            "closed_anomaly_count": 1,
            "open_anomaly_count": 4,
            "top_suppliers_by_anomaly": [
                {
                    "supplier_name": "Supplier-A",
                    "anomaly_count": 3,
                    "open_anomaly_count": 2,
                    "closed_anomaly_count": 1,
                },
                {
                    "supplier_name": "Supplier-B",
                    "anomaly_count": 2,
                    "open_anomaly_count": 2,
                    "closed_anomaly_count": 0,
                },
            ],
        }
        widget, _host = self._build_widget(summary, month=QDate(2026, 10, 1))

        value_axis = next(
            axis
            for axis in widget._chart.axes(Qt.Orientation.Horizontal)
            if isinstance(axis, QValueAxis)
        )
        category_axis = next(
            axis
            for axis in widget._chart.axes(Qt.Orientation.Vertical)
            if isinstance(axis, QBarCategoryAxis)
        )

        self.assertEqual(11, value_axis.labelsFont().pointSize())
        self.assertEqual(11, value_axis.titleFont().pointSize())
        self.assertEqual(11, category_axis.labelsFont().pointSize())
        self.assertEqual(11, category_axis.titleFont().pointSize())
        self.assertTrue(widget._chart.legend().isVisible())

    def test_stats_view_chart_uses_dashed_gridline_and_clean_layout(self) -> None:
        rows = [
            {"supplier_name": f"Supplier-{idx:02d}", "anomaly_count": 1}
            for idx in range(1, 17)
        ]
        summary = {
            "anomaly_count": 16,
            "visit_count": 0,
            "closed_anomaly_count": 0,
            "open_anomaly_count": 16,
            "top_suppliers_by_anomaly": rows,
        }
        widget, _host = self._build_widget(summary, month=QDate(2026, 8, 1))

        self.assertEqual(
            {"StatsTrendScrollArea"},
            {scroll.objectName() for scroll in widget.findChildren(QScrollArea)},
        )
        self.assertEqual([], widget.findChildren(QTabWidget))

        value_axis = next(
            axis
            for axis in widget._chart.axes(Qt.Orientation.Horizontal)
            if isinstance(axis, QValueAxis)
        )
        self.assertEqual(Qt.PenStyle.DashLine, value_axis.gridLinePen().style())
        self.assertEqual(
            QColor(TOKENS["chart_grid"]).name().lower(),
            value_axis.gridLinePen().color().name().lower(),
        )

        self.assertIsNotNone(widget._chart_view)
        assert widget._chart_view is not None
        self.assertGreaterEqual(widget._chart_view.minimumHeight(), 400)
        self.assertEqual(
            QSizePolicy.Policy.Expanding,
            widget._chart_view.sizePolicy().horizontalPolicy(),
        )

    def test_stats_view_chart_click_routes_to_event_query_with_month_filter(self) -> None:
        summary = {
            "anomaly_count": 6,
            "visit_count": 2,
            "closed_anomaly_count": 3,
            "open_anomaly_count": 3,
            "top_suppliers_by_anomaly": [
                {
                    "supplier_name": "Supplier-A",
                    "anomaly_count": 4,
                    "open_anomaly_count": 3,
                    "closed_anomaly_count": 1,
                },
                {
                    "supplier_name": "Supplier-B",
                    "anomaly_count": 2,
                    "open_anomaly_count": 1,
                    "closed_anomaly_count": 1,
                },
            ],
        }
        widget, host = self._build_widget(summary, month=QDate(2026, 11, 1))
        assert widget._chart_series is not None
        bar_set = widget._chart_series.barSets()[0]

        widget._on_chart_bar_clicked(1, bar_set)

        self.assertEqual(
            [
                {
                    "event_type": "ANOMALY",
                    "supplier_keyword": "Supplier-A", # index 1 is now A after reverse
                    "yyyymm": "202611",
                    "status": "待處理",
                    "event_scope": event_service.EVENT_SCOPE_ANOMALY_ONLY,
                    "overdue_only": False,
                }
            ],
            host.quick_filter_calls,
        )

    def test_stats_view_does_not_render_decision_summary_cards(self) -> None:
        summary = {
            "anomaly_count": 6,
            "visit_count": 2,
            "closed_anomaly_count": 3,
            "open_anomaly_count": 3,
            "overdue_open_anomaly_count": 1,
            "top_suppliers_by_anomaly": [
                {
                    "supplier_name": "Supplier-Risk",
                    "anomaly_count": 4,
                    "open_anomaly_count": 3,
                    "overdue_open_anomaly_count": 1,
                    "closed_anomaly_count": 1,
                },
            ],
        }
        trend_data = [
            {"yyyymm": "2026-10", "total_count": 2, "closed_count": 1, "overdue_count": 0, "backlog_count": 2},
            {"yyyymm": "2026-11", "total_count": 4, "closed_count": 3, "overdue_count": 1, "backlog_count": 3},
        ]
        widget, host = self._build_widget(
            summary,
            month=QDate(2026, 11, 1),
            trend_data=trend_data,
        )

        buttons = widget.findChildren(QPushButton)
        self.assertFalse(hasattr(widget, "_summary_buttons"))
        self.assertFalse(hasattr(widget, "decision_summary"))
        self.assertIsNone(widget.findChild(QFrame, "StatsDecisionSummary"))
        self.assertFalse(any(button.property("role") == "decisionSummary" for button in buttons))
        self.assertEqual([], host.quick_filter_calls)

    def test_stats_view_visual_stress_keeps_scroll_guards_and_compact_width(self) -> None:
        long_supplier = "超長供應商名稱-01-ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        summary = {
            "anomaly_count": 200,
            "visit_count": 20,
            "closed_anomaly_count": 40,
            "open_anomaly_count": 160,
            "overdue_open_anomaly_count": 15,
            "top_suppliers_by_anomaly": [
                {
                    "supplier_name": (
                        long_supplier
                        if index == 1
                        else f"超長供應商名稱-{index:02d}-ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                    ),
                    "anomaly_count": index + 1,
                    "open_anomaly_count": index % 5,
                    "overdue_open_anomaly_count": index % 3,
                    "closed_anomaly_count": index % 4,
                    "avg_resolution_time": 1.5 + index,
                }
                for index in range(30)
            ],
        }
        trend_data = [
            {
                "yyyymm": f"2026-{month:02d}",
                "total_count": month * 2,
                "closed_count": month,
                "overdue_count": month % 3,
                "backlog_count": month * 4,
            }
            for month in range(1, 13)
        ]
        resp_stats = [
            {
                "responsible_person": f"責任人員-{index:02d}-VeryLongName",
                "total_count": index + 2,
                "avg_resolution_time": index / 2 + 1,
            }
            for index in range(25)
        ]
        with (
            patch("services.event_service.get_monthly_stats", return_value=summary),
            patch("services.event_service.get_anomaly_trend", return_value=trend_data),
            patch("services.event_service.get_responsible_person_stats", return_value=resp_stats),
        ):
            widget = StatsViewWidget(main_window=_DummyMainWindow())
            widget.month_input.setDate(QDate(2026, 6, 1))
            widget.resize(1024, 560)
            widget.show()
            self.app.processEvents()
        self._widgets.append(widget)

        self.assertLessEqual(widget.minimumSizeHint().width(), 1024)
        self.assertLessEqual(widget.minimumSizeHint().height(), 680)
        self.assertFalse(hasattr(widget, "defect_container"))
        self.assertFalse(hasattr(widget, "tabs"))
        self.assertEqual("StatsView", widget.objectName())
        self.assertEqual([], widget.findChildren(QTabWidget))
        self.assertIsNone(widget.findChild(QFrame, "StatsDecisionSummary"))
        self.assertGreaterEqual(SCROLLBAR_WIDTH, 8)

        scrolls = {scroll.objectName(): scroll for scroll in widget.findChildren(QScrollArea)}
        self.assertEqual(
            {"StatsTrendScrollArea"},
            set(scrolls),
        )
        for scroll in scrolls.values():
            self.assertEqual(Qt.ScrollBarPolicy.ScrollBarAsNeeded, scroll.verticalScrollBarPolicy())
            self.assertEqual(Qt.ScrollBarPolicy.ScrollBarAlwaysOff, scroll.horizontalScrollBarPolicy())

        for chart_view in widget.findChildren(QChartView):
            for axis in chart_view.chart().axes():
                if isinstance(axis, QBarCategoryAxis):
                    categories = axis.categories()
                    self.assertEqual(len(categories), len(set(categories)))

    def test_stats_view_hover_uses_full_supplier_name_in_tooltip(self) -> None:
        summary = {
            "anomaly_count": 4,
            "visit_count": 0,
            "closed_anomaly_count": 0,
            "open_anomaly_count": 4,
            "top_suppliers_by_anomaly": [
                {
                    "supplier_name": "NorthStarSupplierAlpha",
                    "anomaly_count": 4,
                    "open_anomaly_count": 3,
                    "closed_anomaly_count": 1,
                    "avg_resolution_time": 3.2,
                },
            ],
        }
        widget, _host = self._build_widget(summary, month=QDate(2026, 9, 1))
        assert widget._chart_series is not None
        bar_set = widget._chart_series.barSets()[0]

        with patch("ui.widgets.stats_chart_mixin.QToolTip.showText") as mock_show:
            widget._on_chart_bar_hovered(True, 0, bar_set)
        mock_show.assert_called_once()
        tooltip_text = str(mock_show.call_args.args[1])
        self.assertIn("NorthStarSupplierAlpha", tooltip_text)
        self.assertIn("逾期未結：0", tooltip_text)
        self.assertIn("進行中：3", tooltip_text)
        self.assertIn("已結案：1", tooltip_text)
        self.assertIn("總異常件數：4", tooltip_text)
        self.assertIn("平均處理時效：3.2 天", tooltip_text)
        self.assertIn("月份：2026-09", tooltip_text)

        with patch("ui.widgets.stats_chart_mixin.QToolTip.hideText") as mock_hide:
            widget._on_chart_bar_hovered(False, 0, bar_set)
        mock_hide.assert_called_once()


if __name__ == "__main__":
    unittest.main()
