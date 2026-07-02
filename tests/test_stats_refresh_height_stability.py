from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QCoreApplication
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCharts import QChartView

from services import event_service
from ui.theme import apply_app_theme
from ui.widgets.stats_view_widget import StatsViewWidget
from ui.widgets.chart_style import StableChartView


class DummyMainWindow:
    def open_event_query_with_filters(self, **kwargs) -> None:
        pass
    def open_warehouse_nonconforming_tracker(self) -> None:
        pass


class StatsRefreshHeightStabilityTests(unittest.TestCase):
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
        self.widgets: list[QWidget] = []

    def tearDown(self) -> None:
        for w in self.widgets:
            w.close()
        self.app.processEvents()

    def test_stats_view_widget_height_stability_on_multiple_refreshes(self) -> None:
        # Mock 必要的 Service 資料，避免空的 state 或 None 異常
        summary = {
            "anomaly_count": 5,
            "visit_count": 3,
            "closed_anomaly_count": 2,
            "open_anomaly_count": 3,
            "top_suppliers_by_anomaly": [
                {
                    "supplier_name": "Supplier A",
                    "anomaly_count": 3,
                    "open_anomaly_count": 2,
                    "closed_anomaly_count": 1,
                }
            ],
        }
        trend_data = [
            {"yyyymm": "2026-01", "total_count": 1, "closed_count": 1, "backlog_count": 0},
            {"yyyymm": "2026-02", "total_count": 2, "closed_count": 1, "backlog_count": 1},
        ]
        visit_trend_data = [
            {"yyyymm": "2026-01", "visit_count": 1, "visit_anomaly_count": 0},
            {"yyyymm": "2026-02", "visit_count": 2, "visit_anomaly_count": 1},
        ]
        resp_data = [
            {
                "responsible_person": "SQE_Alpha",
                "total_count": 3,
                "open_count": 2,
                "closed_count": 1,
                "min_open_date": "2026-01-01",
                "max_open_date": "2026-02-01",
            }
        ]
        category_pareto_data = [
            {"category": "零件不良", "count": 3, "cumulative_percent": 100.0, "percent": 100.0}
        ]

        with (
            patch("services.event_service.get_monthly_stats", return_value=summary),
            patch("services.event_service.get_anomaly_trend_by_range", return_value=trend_data),
            patch("services.event_service.get_visit_trend_by_range", return_value=visit_trend_data),
            patch("services.event_service.get_responsible_person_stats_by_range", return_value=resp_data),
            patch("services.event_service.get_anomaly_category_pareto_by_range", return_value=category_pareto_data),
        ):
            widget = StatsViewWidget(main_window=DummyMainWindow(), lazy_load=True)
            self.widgets.append(widget)
            
            widget.resize(1280, 800)
            widget.show()
            self.app.processEvents()

            # 找到 StatsScrollContent
            scroll_content = widget.findChild(QWidget, "StatsScrollContent")
            self.assertIsNotNone(scroll_content)
            
            # 獲取初始高度
            initial_height = scroll_content.height()
            initial_size_hint = scroll_content.sizeHint().height()

            heights = [initial_height]
            size_hints = [initial_size_hint]

            # 連續重新整理 5 次
            for i in range(5):
                widget.refresh_data()
                self.app.processEvents()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                self.app.processEvents()

                heights.append(scroll_content.height())
                size_hints.append(scroll_content.sizeHint().height())

            # 斷言在第一次 refresh 之後，高度與 sizeHint 維持不變
            for h in heights[1:]:
                self.assertEqual(heights[1], h, f"ScrollContent height changed during refresh loop: {heights}")

            for sh in size_hints[1:]:
                self.assertEqual(size_hints[1], sh, f"ScrollContent sizeHint height changed during refresh loop: {size_hints}")

            # 檢查產生的圖表元件是否皆為 StableChartView
            chart_views = widget.findChildren(QChartView)
            self.assertEqual(4, len(chart_views))
            for view in chart_views:
                self.assertIsInstance(view, StableChartView)


if __name__ == "__main__":
    unittest.main()
