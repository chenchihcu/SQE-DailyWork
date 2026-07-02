from __future__ import annotations

import os
import unittest
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.widgets.stats_dashboard_helpers import (
    default_range_keys,
    normalize_range_keys,
    range_display_text,
    range_iso_dates,
    range_month_span,
    range_month_window,
)


class NormalizeRangeKeysTests(unittest.TestCase):
    """起迄 yyyyMM 鍵正規化：start > end 時交換。"""

    def test_ordered_keys_pass_through(self) -> None:
        self.assertEqual(("202602", "202607"), normalize_range_keys("202602", "202607"))

    def test_reversed_keys_are_swapped(self) -> None:
        self.assertEqual(("202602", "202607"), normalize_range_keys("202607", "202602"))

    def test_equal_keys_stay_equal(self) -> None:
        self.assertEqual(("202607", "202607"), normalize_range_keys("202607", "202607"))

    def test_cross_year_swap(self) -> None:
        self.assertEqual(("202511", "202603"), normalize_range_keys("202603", "202511"))

    def test_non_yyyymm_key_falls_back_to_current_month(self) -> None:
        today = date.today()
        current = f"{today.year:04d}{today.month:02d}"
        for key in ("ALL", "", None, "2026-07", "202699"):
            start, end = normalize_range_keys(key, key)  # type: ignore[arg-type]
            self.assertEqual(current, start, msg=f"key={key!r}")
            self.assertEqual(current, end, msg=f"key={key!r}")


class RangeMonthWindowTests(unittest.TestCase):
    """趨勢查詢窗口：兩端取當月 1 日 ISO 日期。"""

    def test_mid_year_range(self) -> None:
        self.assertEqual(
            ("2026-02-01", "2026-07-01"),
            range_month_window("202602", "202607"),
        )

    def test_range_crosses_year_boundary(self) -> None:
        self.assertEqual(
            ("2024-10-01", "2025-03-01"),
            range_month_window("202410", "202503"),
        )

    def test_single_month_range(self) -> None:
        self.assertEqual(
            ("2026-06-01", "2026-06-01"),
            range_month_window("202606", "202606"),
        )

    def test_reversed_keys_are_normalized(self) -> None:
        self.assertEqual(
            ("2026-02-01", "2026-07-01"),
            range_month_window("202607", "202602"),
        )


class RangeIsoDatesTests(unittest.TestCase):
    """ISO 日期範圍：起月 1 日到迄月最後一天。"""

    def test_end_of_31_day_month(self) -> None:
        self.assertEqual(
            ("2026-02-01", "2026-07-31"),
            range_iso_dates("202602", "202607"),
        )

    def test_end_of_30_day_month(self) -> None:
        self.assertEqual(
            ("2026-04-01", "2026-06-30"),
            range_iso_dates("202604", "202606"),
        )

    def test_leap_year_february_end(self) -> None:
        self.assertEqual(
            ("2028-01-01", "2028-02-29"),
            range_iso_dates("202801", "202802"),
        )

    def test_non_leap_year_february_end(self) -> None:
        self.assertEqual(
            ("2026-02-01", "2026-02-28"),
            range_iso_dates("202602", "202602"),
        )


class RangeDisplayTextTests(unittest.TestCase):
    def test_distinct_months(self) -> None:
        self.assertEqual("2026-02 至 2026-07", range_display_text("202602", "202607"))

    def test_degenerate_range_shows_single_month(self) -> None:
        self.assertEqual("2026-07", range_display_text("202607", "202607"))

    def test_reversed_keys_are_normalized(self) -> None:
        self.assertEqual("2026-02 至 2026-07", range_display_text("202607", "202602"))


class RangeMonthSpanTests(unittest.TestCase):
    def test_six_month_span(self) -> None:
        self.assertEqual(6, range_month_span("202602", "202607"))

    def test_single_month_span(self) -> None:
        self.assertEqual(1, range_month_span("202607", "202607"))

    def test_cross_year_span(self) -> None:
        self.assertEqual(13, range_month_span("202501", "202601"))


class DefaultRangeKeysTests(unittest.TestCase):
    """預設區間：迄 = 今年今月（夾限 2025–2030），起 = 迄往前 span-1 個月。"""

    def test_default_span_is_six_months_inclusive(self) -> None:
        start, end = default_range_keys()
        self.assertEqual(6, range_month_span(start, end))

    def test_end_anchors_to_current_month_when_in_option_range(self) -> None:
        today = date.today()
        if 2025 <= today.year <= 2030:
            _, end = default_range_keys()
            self.assertEqual(f"{today.year:04d}{today.month:02d}", end)

    def test_start_never_precedes_earliest_option_year(self) -> None:
        start, _ = default_range_keys(span_months=120)
        self.assertGreaterEqual(start, "202501")


if __name__ == "__main__":
    unittest.main()
