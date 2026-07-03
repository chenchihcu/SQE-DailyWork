"""迴歸測試:統計圖表「件數」軸的格線必須落在整數值上。

Bug 重現(修復前):QValueAxis 預設 tickCount=5(4 段),range 0..max+padding
多半不是 4 的倍數(例:訪廠趨勢 max=4 → 0..6),格線落在 0/1.5/3/4.5/6,
再被 %d、%i 標籤格式四捨五入成 0,1,3,4,6 的不等距標籤,
整數件數的長條就對不上任何標示格線(1 件的長條只到第一條格線的 2/3 高)。

修復:chart_style.apply_integer_count_axis 以 TicksDynamic + 1/2/5×10^n
整數間隔設定刻度,並把上限進位到間隔的倍數。
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCharts import QChartView, QValueAxis
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication

from ui.theme import apply_app_theme
from ui.widgets.chart_style import apply_integer_count_axis
from ui.widgets.stats_view_widget import StatsViewWidget

COUNT_LABEL_FORMATS = ("%d", "%i")


class _DummyMainWindow:
    def open_event_query_with_filters(self, **kwargs) -> None:
        pass

    def open_warehouse_nonconforming_tracker(self) -> None:
        pass


class IntegerCountAxisHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _configured_axis(self, max_value: int, padding: int) -> QValueAxis:
        axis = QValueAxis()
        apply_integer_count_axis(axis, max_value, padding=padding)
        return axis

    def test_screenshot_repro_max4_pad2_gets_even_integer_ticks(self) -> None:
        # 訪廠趨勢 max=4、padding=2:修復前 0..6 配 5 個刻度 → 0/1.5/3/4.5/6
        axis = self._configured_axis(4, 2)
        self.assertEqual(0.0, axis.min())
        self.assertEqual(6.0, axis.max())
        self.assertEqual(QValueAxis.TickType.TicksDynamic, axis.tickType())
        self.assertEqual(0.0, axis.tickAnchor())
        self.assertEqual(2.0, axis.tickInterval())

    def test_larger_range_snaps_to_nice_interval(self) -> None:
        axis = self._configured_axis(18, 2)
        self.assertEqual(20.0, axis.max())
        self.assertEqual(5.0, axis.tickInterval())

    def test_upper_bound_rounds_up_to_interval_multiple(self) -> None:
        axis = self._configured_axis(23, 1)
        self.assertEqual(25.0, axis.max())
        self.assertEqual(5.0, axis.tickInterval())

    def test_zero_max_still_yields_valid_integer_axis(self) -> None:
        axis = self._configured_axis(0, 2)
        self.assertEqual(3.0, axis.max())
        self.assertEqual(1.0, axis.tickInterval())


class StatsViewCountAxisIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        apply_app_theme(cls.app)

    def setUp(self) -> None:
        self._widgets: list[StatsViewWidget] = []

    def tearDown(self) -> None:
        for widget in self._widgets:
            widget.close()
        self.app.processEvents()

    def test_all_count_axes_have_integer_aligned_gridlines(self) -> None:
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
                    "closed_anomaly_count": 2,
                },
                {
                    "supplier_name": "Supplier-A",
                    "anomaly_count": 3,
                    "open_anomaly_count": 2,
                    "closed_anomaly_count": 1,
                },
            ],
        }
        resp_stats = [
            {
                "responsible_person": item["supplier_name"],
                "total_count": item["anomaly_count"],
                "closed_count": item["closed_anomaly_count"],
                "open_count": item["open_anomaly_count"],
                "min_open_date": "2026-02-01",
                "max_open_date": "2026-05-01",
            }
            for item in summary["top_suppliers_by_anomaly"]
        ]
        trend_data = [
            {"yyyymm": "2026-04", "total_count": 13, "closed_count": 8, "overdue_count": 0, "backlog_count": 18},
        ]
        # max=4:修復前會產生 0,1,3,4,6 的不等距標籤(截圖重現資料)
        visit_data = [
            {"yyyymm": "2026-03", "visit_count": 2, "visit_anomaly_count": 2},
            {"yyyymm": "2026-04", "visit_count": 4, "visit_anomaly_count": 1},
        ]
        category_pareto = [
            {"rank": 1, "category": "製程參數失控", "count": 5, "percent": 45.5, "cumulative_percent": 45.5},
            {"rank": 2, "category": "規範文件缺漏", "count": 4, "percent": 36.4, "cumulative_percent": 81.9},
            {"rank": 3, "category": "其他", "count": 2, "percent": 18.1, "cumulative_percent": 100.0},
        ]
        month_key = QDate(2026, 4, 1).toString("yyyyMM")
        host = _DummyMainWindow()
        with patch("services.event_service.get_monthly_stats", return_value=summary), \
             patch("services.event_service.get_anomaly_trend_by_range", return_value=trend_data), \
             patch("services.event_service.get_visit_trend_by_range", return_value=visit_data), \
             patch("services.event_service.get_responsible_person_stats_by_range", return_value=resp_stats), \
             patch("services.event_service.get_anomaly_category_pareto_by_range", return_value=category_pareto):
            widget = StatsViewWidget(main_window=host)
            widget.set_range(month_key, month_key)
        widget.show()
        self.app.processEvents()
        self._widgets.append(widget)

        count_axes: list[QValueAxis] = []
        for chart_view in widget.findChildren(QChartView):
            chart = chart_view.chart()
            if chart is None:
                continue
            for axis in chart.axes():
                if isinstance(axis, QValueAxis) and axis.labelFormat() in COUNT_LABEL_FORMATS:
                    count_axes.append(axis)

        # 四張圖各一條件數軸(責任人/柏拉圖/事件趨勢/訪廠趨勢);柏拉圖的
        # 累積佔比軸(%.0f%%)不在此列。
        self.assertGreaterEqual(len(count_axes), 4)
        for axis in count_axes:
            with self.subTest(axis=axis.titleText() or axis.labelFormat()):
                self.assertEqual(QValueAxis.TickType.TicksDynamic, axis.tickType())
                self.assertEqual(0.0, axis.tickAnchor())
                interval = axis.tickInterval()
                self.assertEqual(interval, int(interval))
                self.assertGreaterEqual(interval, 1.0)
                self.assertEqual(0.0, axis.min())
                self.assertEqual(axis.max(), int(axis.max()))
                self.assertEqual(0.0, axis.max() % interval)


if __name__ == "__main__":
    unittest.main()
