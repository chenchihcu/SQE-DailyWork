from __future__ import annotations

import sqlite3
import unittest

from ncr.db.database import apply_schema
from ncr.services import stats_service as ncr_stats_service
from services.event import _query_service
from ui.widgets.stats_dashboard_helpers import missing_chart_labels, render_chart_to_png


class DateRangeAndExportWarningTests(unittest.TestCase):
    def test_event_range_queries_reject_reverse_range(self) -> None:
        functions = (
            _query_service.list_events_by_range,
            _query_service.get_anomaly_category_pareto_by_range,
            _query_service.get_responsible_person_stats_by_range,
            _query_service.get_visit_trend_by_range,
            _query_service.get_anomaly_trend_by_range,
            _query_service.get_anomaly_closure_activity_by_range,
        )
        for function in functions:
            with self.subTest(function=function.__name__):
                with self.assertRaisesRegex(ValueError, "Start date"):
                    function("2026-06-30", "2026-06-01")

    def test_ncr_range_queries_reject_reverse_range(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        apply_schema(conn)
        try:
            functions = (
                ncr_stats_service.get_top_suppliers_stats_by_range,
                ncr_stats_service.get_top_products_stats_by_range,
                ncr_stats_service.get_scrap_rework_ratio_by_range,
                ncr_stats_service.get_return_slip_ratio_by_range,
                ncr_stats_service.get_defects_detail_by_range,
            )
            for function in functions:
                with self.subTest(function=function.__name__):
                    with self.assertRaisesRegex(ValueError, "Start date"):
                        function(conn, "2026-06-30", "2026-06-01")
        finally:
            conn.close()

    def test_missing_chart_labels_preserve_requested_order(self) -> None:
        self.assertEqual(
            ["異常趨勢圖", "柏拉圖"],
            missing_chart_labels(
                ["trend", "responsible", "pareto"],
                {"responsible": "responsible.png"},
                {"trend": "異常趨勢圖", "pareto": "柏拉圖"},
            ),
        )

    def test_chart_renderer_failure_is_reportable_without_aborting_export_data(self) -> None:
        def fail_factory():
            raise RuntimeError("injected renderer failure")

        with self.assertLogs(
            "ui.widgets.stats_dashboard_helpers", level="ERROR"
        ) as captured:
            rendered = render_chart_to_png(fail_factory, "never-created.png")
        self.assertFalse(rendered)
        self.assertIn("injected renderer failure", "\n".join(captured.output))
        self.assertEqual(
            ["趨勢圖"],
            missing_chart_labels(["trend"], {}, {"trend": "趨勢圖"}),
        )


if __name__ == "__main__":
    unittest.main()
