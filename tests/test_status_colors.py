from __future__ import annotations

import unittest

from ui.status_colors import (
    DEFAULT_STATUS_COLOR_HEX,
    get_status_color_hex,
    get_status_palette,
    get_status_tone,
)
from ui.theme import TOKENS


class StatusColorsTests(unittest.TestCase):
    def test_active_inactive_status_colors(self) -> None:
        self.assertEqual(get_status_color_hex("啟用"), TOKENS["status_success_fg"])
        self.assertEqual(get_status_color_hex("停用"), TOKENS["status_danger_fg"])
        self.assertEqual(get_status_color_hex("ACTIVE"), TOKENS["status_success_fg"])
        self.assertEqual(get_status_color_hex("INACTIVE"), TOKENS["status_danger_fg"])

    def test_event_status_colors(self) -> None:
        self.assertEqual(get_status_color_hex("待處理"), TOKENS["status_pending_fg"])
        self.assertEqual(get_status_color_hex("已結案"), TOKENS["status_success_fg"])
        self.assertEqual(get_status_color_hex("已完成"), TOKENS["status_success_fg"])
        self.assertEqual(get_status_color_hex("OPEN"), TOKENS["status_pending_fg"])
        self.assertEqual(get_status_color_hex("CLOSED"), TOKENS["status_success_fg"])
        self.assertEqual(get_status_color_hex("COMPLETED"), TOKENS["status_success_fg"])
        self.assertEqual(get_status_color_hex("訪廠"), TOKENS["status_info_fg"])
        self.assertEqual(get_status_color_hex("異常"), TOKENS["status_danger_fg"])
        self.assertEqual(get_status_color_hex("不適用"), TOKENS["status_na_fg"])

    def test_status_color_normalization(self) -> None:
        self.assertEqual(get_status_color_hex(" open "), TOKENS["status_pending_fg"])
        self.assertEqual(get_status_color_hex("closed"), TOKENS["status_success_fg"])
        self.assertEqual(get_status_color_hex("  啟用  "), TOKENS["status_success_fg"])
        self.assertEqual(get_status_tone(" n/a "), "na")

    def test_status_palette_returns_accessible_ui_triplet(self) -> None:
        pending = get_status_palette("待處理")
        self.assertEqual(TOKENS["status_pending_fg"], pending.foreground)
        self.assertEqual(TOKENS["status_pending_bg"], pending.background)
        self.assertEqual(TOKENS["status_pending_border"], pending.border)
        self.assertEqual(TOKENS["status_pending_chart"], pending.chart)

        na = get_status_palette("不適用")
        self.assertEqual(TOKENS["status_na_fg"], na.foreground)
        self.assertEqual(TOKENS["status_na_bg"], na.background)
        self.assertEqual(TOKENS["status_na_border"], na.border)
        self.assertEqual(TOKENS["status_na_chart"], na.chart)

    def test_unknown_status_uses_default_color(self) -> None:
        self.assertEqual(get_status_color_hex("UNKNOWN"), DEFAULT_STATUS_COLOR_HEX)
        self.assertEqual(get_status_color_hex(""), DEFAULT_STATUS_COLOR_HEX)
        self.assertEqual(get_status_color_hex(None), DEFAULT_STATUS_COLOR_HEX)


if __name__ == "__main__":
    unittest.main()
