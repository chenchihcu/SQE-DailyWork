"""版面常數與 .cursorrules 預設對齊（回歸時可及早發現誤改）。"""

from __future__ import annotations

import unittest

from ui import layout_constants as lc


class LayoutConstantsTests(unittest.TestCase):
    def test_form_max_width_and_panel_padding(self) -> None:
        self.assertEqual(960, lc.FORM_MAX_WIDTH)
        self.assertEqual((12, 10, 12, 10), lc.PANEL_MARGINS)
        self.assertEqual((16, 14, 16, 14), lc.DIALOG_OUTER_MARGINS)

    def test_window_sizing_contract(self) -> None:
        self.assertEqual(1024, lc.MAIN_WINDOW_MIN_WIDTH)
        self.assertEqual(680, lc.MAIN_WINDOW_MIN_HEIGHT)
        self.assertEqual(1360, lc.MAIN_WINDOW_DEFAULT_WIDTH)
        self.assertEqual(860, lc.MAIN_WINDOW_DEFAULT_HEIGHT)
        self.assertEqual(0.95, lc.WINDOW_SCREEN_FRACTION)

    def test_grid_rhythm(self) -> None:
        self.assertEqual(12, lc.GRID_GUTTER)
        self.assertEqual(8, lc.ROW_GAP)


if __name__ == "__main__":
    unittest.main()
