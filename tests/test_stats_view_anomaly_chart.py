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
        visit_trend_data: list[dict] | None = None,
        category_pareto_data: list[dict] | None = None,
        main_window: _DummyMainWindow | None = None,
    ) -> tuple[StatsViewWidget, _DummyMainWindow]:
        host = main_window or _DummyMainWindow()
        resp_stats = []
        if "top_suppliers_by_anomaly" in summary:
            for item in summary["top_suppliers_by_anomaly"]:
                resp_stats.append({
                    "responsible_person": item.get("supplier_name") or item.get("responsible_person"),
                    "total_count": item.get("anomaly_count", 0),
                    "closed_count": item.get("closed_anomaly_count", 0),
                    "open_count": item.get("open_anomaly_count", 0),
                    "min_open_date": "2026-02-01",
                    "max_open_date": "2026-05-01",
                })
        month_key = month.toString("yyyyMM")
        with patch("services.event_service.get_monthly_stats", return_value=summary), \
             patch("services.event_service.get_anomaly_trend_by_range", return_value=trend_data or []), \
             patch("services.event_service.get_visit_trend_by_range", return_value=visit_trend_data or []), \
             patch("services.event_service.get_responsible_person_stats_by_range", return_value=resp_stats), \
             patch("services.event_service.get_anomaly_category_pareto_by_range", return_value=category_pareto_data or []):
            widget = StatsViewWidget(main_window=host)
            widget.set_range(month_key, month_key)

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
        self.assertEqual(2, len(bar_sets))
        closed_set = bar_sets[0]
        open_set = bar_sets[1]
        
        self.assertEqual("已結案", closed_set.label())
        self.assertEqual("未結案", open_set.label())
        
        # In setup, B is last, so it's index 0 in reversed categories
        self.assertEqual(0, int(closed_set.at(0))) # B
        self.assertEqual(1, int(closed_set.at(1))) # A
        self.assertEqual(2, int(closed_set.at(2))) # C
        self.assertEqual(1, int(open_set.at(0))) # B
        self.assertEqual(2, int(open_set.at(1))) # A
        self.assertEqual(3, int(open_set.at(2))) # C
 
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
            QColor(get_status_palette("已結案").chart).name().lower(),
            closed_set.color().name().lower(),
        )
        self.assertEqual(
            QColor(get_status_palette("待處理").chart).name().lower(),
            open_set.color().name().lower(),
        )
        self.assertTrue(widget._chart.legend().isVisible())
 
        self.assertEqual([], widget.findChildren(QTabWidget))
        self.assertEqual("statsInfoBanner", widget.info_banner.property("role"))
        self.assertIsNotNone(widget.findChild(QFrame, "StatsFourPhaseChartPanel"))
        self.assertIsNone(widget.findChild(QFrame, "StatsCategoryParetoPanel"))
        self.assertIsNone(widget.findChild(QFrame, "StatsResponsiblePanel"))

    def test_stats_view_uses_ncr_style_two_by_two_four_phase_grid(self) -> None:
        summary = {
            "anomaly_count": 6,
            "visit_count": 2,
            "closed_anomaly_count": 2,
            "open_anomaly_count": 4,
            "top_suppliers_by_anomaly": [
                {
                    "supplier_name": "Supplier-A",
                    "anomaly_count": 6,
                    "closed_anomaly_count": 2,
                    "open_anomaly_count": 4,
                },
            ],
        }
        trend_data = [
            {"yyyymm": "2026-04", "total_count": 6, "closed_count": 2, "overdue_count": 0, "backlog_count": 4},
        ]
        visit_data = [
            {"yyyymm": "2026-04", "visit_count": 2, "visit_anomaly_count": 1},
        ]
        category_pareto = [
            {"rank": 1, "category": "製程參數失控", "count": 4, "percent": 66.7, "cumulative_percent": 66.7},
            {"rank": 2, "category": "規範文件缺漏", "count": 2, "percent": 33.3, "cumulative_percent": 100.0},
        ]
        widget, _host = self._build_widget(
            summary,
            month=QDate(2026, 4, 1),
            trend_data=trend_data,
            visit_trend_data=visit_data,
            category_pareto_data=category_pareto,
        )

        self.assertIsNotNone(widget.findChild(QFrame, "StatsFourPhaseChartPanel"))
        self.assertIsNone(widget.findChild(QFrame, "StatsCategoryParetoPanel"))
        self.assertIsNone(widget.findChild(QFrame, "StatsResponsiblePanel"))
        for row, col in ((0, 0), (0, 1), (1, 0), (1, 1)):
            item = widget.grid_layout.itemAtPosition(row, col)
            self.assertIsNotNone(item, f"missing phase at {row},{col}")
            assert item is not None
            self.assertIsInstance(item.widget(), QChartView)

        titles = {
            chart_view.chart().title()
            for chart_view in widget.findChildren(QChartView)
        }
        self.assertIn("供應商事件處理效率趨勢分析 (2026-04)", titles)
        self.assertIn("供應商訪廠與訪廠異常趨勢分析 (2026-04)", titles)
        self.assertIn("異常類別柏拉圖分析 (2026-04)", titles)
        self.assertIn("責任人事件統計 (已結案 vs 未結案)", titles)
        self.assertIsNotNone(widget.insight_label)
        assert widget.insight_label is not None
        self.assertIn("主要異常類別", widget.insight_label.text())

    def test_stats_view_renders_category_pareto_chart(self) -> None:
        summary = {
            "anomaly_count": 6,
            "visit_count": 0,
            "closed_anomaly_count": 0,
            "open_anomaly_count": 6,
            "top_suppliers_by_anomaly": [],
        }
        category_pareto = [
            {"rank": 1, "category": "製程條件/參數未受控", "count": 3, "percent": 50.0, "cumulative_percent": 50.0},
            {"rank": 2, "category": "標準作業不落實", "count": 2, "percent": 33.3, "cumulative_percent": 83.3},
            {"rank": 3, "category": "未分類", "count": 1, "percent": 16.7, "cumulative_percent": 100.0},
        ]
        widget, _host = self._build_widget(
            summary,
            month=QDate(2026, 4, 1),
            category_pareto_data=category_pareto,
        )

        pareto_chart = next(
            chart_view.chart()
            for chart_view in widget.findChildren(QChartView)
            if "異常類別柏拉圖分析" in chart_view.chart().title()
        )
        category_axis = next(
            axis
            for axis in pareto_chart.axes(Qt.Orientation.Vertical)
            if isinstance(axis, QBarCategoryAxis)
        )
        value_axes = [
            axis
            for axis in pareto_chart.axes(Qt.Orientation.Horizontal)
            if isinstance(axis, QValueAxis)
        ]
        line_series = [
            series for series in pareto_chart.series() if isinstance(series, QLineSeries)
        ]

        self.assertEqual(
            ["未分類", "標準作業不落實", "製程條件/參數未受控"],
            category_axis.categories(),
        )
        self.assertEqual(2, len(value_axes))
        self.assertEqual(1, len(line_series))
        self.assertEqual("累積佔比", line_series[0].name())
        self.assertEqual(3, line_series[0].count())
        self.assertEqual(100.0, line_series[0].at(0).x())
        self.assertTrue(line_series[0].pointsVisible())
        self.assertTrue(line_series[0].pointLabelsVisible())
        self.assertEqual("@xPoint%", line_series[0].pointLabelsFormat())
        self.assertFalse(line_series[0].pointLabelsClipping())

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
        self.assertEqual(9, category_axis.labelsFont().pointSize())
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

    def test_stats_view_chart_click_does_not_route_in_responsible_chart(self) -> None:
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
            ],
        }
        widget, host = self._build_widget(summary, month=QDate(2026, 11, 1))
        self.assertEqual([], host.quick_filter_calls)

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
                "closed_count": index % 4,
                "open_count": (index % 5) + 1,
                "avg_resolution_time": index / 2 + 1,
                "min_open_date": "2026-01-15",
                "max_open_date": "2026-12-15",
            }
            for index in range(25)
        ]
        with (
            patch("services.event_service.get_monthly_stats", return_value=summary),
            patch("services.event_service.get_anomaly_trend_by_range", return_value=trend_data),
            patch("services.event_service.get_visit_trend_by_range", return_value=[]),
            patch("services.event_service.get_responsible_person_stats_by_range", return_value=resp_stats),
            patch("services.event_service.get_anomaly_category_pareto_by_range", return_value=[
                {"rank": 1, "category": "超長異常類別名稱-01-ABCDEFGHIJKLMNOPQRSTUVWXYZ", "count": 10, "percent": 50.0, "cumulative_percent": 50.0},
                {"rank": 2, "category": "外觀不良", "count": 6, "percent": 30.0, "cumulative_percent": 80.0},
                {"rank": 3, "category": "未分類", "count": 4, "percent": 20.0, "cumulative_percent": 100.0},
            ]),
        ):
            widget = StatsViewWidget(main_window=_DummyMainWindow())
            widget.set_range("202601", "202606")
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

    def test_stats_view_trend_charts_follow_selected_range(self) -> None:
        """趨勢與彙總查詢必須跟隨起迄年月下拉（真實可見控件），
        而不是永遠以今天為錨點（圖表不同步 bug 的回歸測試）。"""
        summary = {
            "anomaly_count": 0,
            "visit_count": 0,
            "closed_anomaly_count": 0,
            "open_anomaly_count": 0,
            "top_suppliers_by_anomaly": [],
        }
        with patch("services.event_service.get_monthly_stats", return_value=summary), \
             patch("services.event_service.get_anomaly_trend_by_range", return_value=[]) as mock_trend, \
             patch("services.event_service.get_visit_trend_by_range", return_value=[]) as mock_visit, \
             patch("services.event_service.get_responsible_person_stats_by_range", return_value=[]) as mock_resp, \
             patch("services.event_service.get_anomaly_category_pareto_by_range", return_value=[]) as mock_category:
            widget = StatsViewWidget(main_window=_DummyMainWindow())
            self._widgets.append(widget)

            # 先設定迄月再設定起月，全程操作真實可見下拉
            widget.range_selectors.end_year.setCurrentText("2025")
            widget.range_selectors.end_month.setCurrentText("03")
            widget.range_selectors.start_year.setCurrentText("2025")
            widget.range_selectors.start_month.setCurrentText("01")
            self.app.processEvents()

        expected_window = ("2025-01-01", "2025-03-31")
        self.assertEqual(expected_window, tuple(mock_trend.call_args.args))
        self.assertEqual(expected_window, tuple(mock_visit.call_args.args))
        self.assertEqual(("2025-01-01", "2025-03-31"), tuple(mock_resp.call_args.args))
        self.assertEqual(("2025-01-01", "2025-03-31"), tuple(mock_category.call_args.args))
        self.assertEqual("2025-01 至 2025-03", widget._range_text())

    def test_stats_view_default_range_is_six_months_ending_current_month(self) -> None:
        summary = {
            "anomaly_count": 0,
            "visit_count": 0,
            "closed_anomaly_count": 0,
            "open_anomaly_count": 0,
            "top_suppliers_by_anomaly": [],
        }
        with patch("services.event_service.get_monthly_stats", return_value=summary), \
             patch("services.event_service.get_anomaly_trend_by_range", return_value=[]), \
             patch("services.event_service.get_visit_trend_by_range", return_value=[]), \
             patch("services.event_service.get_responsible_person_stats_by_range", return_value=[]), \
             patch("services.event_service.get_anomaly_category_pareto_by_range", return_value=[]):
            widget = StatsViewWidget(main_window=_DummyMainWindow())
            self._widgets.append(widget)

        from ui.widgets.stats_dashboard_helpers import default_range_keys

        self.assertEqual(default_range_keys(), widget._range_keys())

    def test_stats_view_range_clamp_touched_control_wins(self) -> None:
        """起 > 迄 時「碰到的控件優先」：改起始把迄拖到起始，改迄把起始拖到迄。"""
        summary = {
            "anomaly_count": 0,
            "visit_count": 0,
            "closed_anomaly_count": 0,
            "open_anomaly_count": 0,
            "top_suppliers_by_anomaly": [],
        }
        with patch("services.event_service.get_monthly_stats", return_value=summary), \
             patch("services.event_service.get_anomaly_trend_by_range", return_value=[]), \
             patch("services.event_service.get_visit_trend_by_range", return_value=[]), \
             patch("services.event_service.get_responsible_person_stats_by_range", return_value=[]), \
             patch("services.event_service.get_anomaly_category_pareto_by_range", return_value=[]):
            widget = StatsViewWidget(main_window=_DummyMainWindow())
            self._widgets.append(widget)
            widget.set_range("202601", "202603")

            with patch.object(widget, "refresh_data") as mock_refresh:
                # 把起始改到超過迄 → 迄被拖到起始
                widget.range_selectors.start_year.setCurrentText("2027")
                self.app.processEvents()
            self.assertEqual(("202701", "202701"), widget._range_keys())
            self.assertEqual(1, mock_refresh.call_count)

            with patch.object(widget, "refresh_data") as mock_refresh:
                # 把迄改到早於起始 → 起始被拖到迄
                widget.range_selectors.end_year.setCurrentText("2026")
                self.app.processEvents()
            self.assertEqual(("202601", "202601"), widget._range_keys())
            self.assertEqual(1, mock_refresh.call_count)

    def test_stats_view_long_range_keeps_range_state_without_external_title_labels(self) -> None:
        summary = {
            "anomaly_count": 0,
            "visit_count": 0,
            "closed_anomaly_count": 0,
            "open_anomaly_count": 0,
            "top_suppliers_by_anomaly": [],
        }
        with patch("services.event_service.get_monthly_stats", return_value=summary), \
             patch("services.event_service.get_anomaly_trend_by_range", return_value=[]), \
             patch("services.event_service.get_visit_trend_by_range", return_value=[]), \
             patch("services.event_service.get_responsible_person_stats_by_range", return_value=[]), \
             patch("services.event_service.get_anomaly_category_pareto_by_range", return_value=[]):
            widget = StatsViewWidget(main_window=_DummyMainWindow())
            self._widgets.append(widget)
            widget.set_range("202501", "202606")

        self.assertEqual("2025-01 至 2026-06", widget._range_text())
        self.assertFalse(hasattr(widget, "_trend_title_label"))
        self.assertFalse(hasattr(widget, "_visit_trend_title_label"))

    def test_stats_view_hover_uses_full_responsible_name_in_tooltip(self) -> None:
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
                },
            ],
        }
        widget, _host = self._build_widget(summary, month=QDate(2026, 9, 1))
        assert widget._chart_series is not None
        
        resp_data = [
            {
                "responsible_person": "NorthStarSupplierAlpha",
                "total_count": 4,
                "open_count": 3,
                "closed_count": 1,
                "min_open_date": "2026-02-01",
                "max_open_date": "2026-05-01",
            }
        ]

        with patch("ui.widgets.stats_chart_mixin.QToolTip.showText") as mock_show:
            widget._on_resp_stacked_hovered(True, 0, resp_data)
        mock_show.assert_called_once()
        tooltip_text = str(mock_show.call_args.args[1])
        self.assertIn("NorthStarSupplierAlpha", tooltip_text)
        self.assertIn("已結案：1 件", tooltip_text)
        self.assertIn("未結案：3 件", tooltip_text)
        self.assertIn("未結案累計月份：2026/02 ~ 2026/05", tooltip_text)

        with patch("ui.widgets.stats_chart_mixin.QToolTip.hideText") as mock_hide:
            widget._on_resp_stacked_hovered(False, 0, resp_data)
        mock_hide.assert_called_once()


if __name__ == "__main__":
    unittest.main()
