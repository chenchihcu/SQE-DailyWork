"""版面常數回歸測試：釘住 src/ui/layout_constants.py 的數值，回歸時可及早發現誤改。"""

from __future__ import annotations

import unittest

from ui import layout_constants as lc


class LayoutConstantsTests(unittest.TestCase):
    def test_form_max_width_and_panel_padding(self) -> None:
        self.assertEqual(960, lc.FORM_MAX_WIDTH)
        self.assertEqual((12, 10, 12, 10), lc.PANEL_MARGINS)
        self.assertEqual((16, 14, 16, 14), lc.DIALOG_OUTER_MARGINS)
        self.assertEqual((0, 0, 0, 0), lc.WORKFLOW_SHELL_EMBEDDED_MARGINS)

    def test_window_sizing_contract(self) -> None:
        self.assertEqual(1024, lc.MAIN_WINDOW_MIN_WIDTH)
        self.assertEqual(680, lc.MAIN_WINDOW_MIN_HEIGHT)
        self.assertEqual(1360, lc.MAIN_WINDOW_DEFAULT_WIDTH)
        self.assertEqual(860, lc.MAIN_WINDOW_DEFAULT_HEIGHT)
        self.assertEqual(0.95, lc.WINDOW_SCREEN_FRACTION)

    def test_grid_rhythm(self) -> None:
        self.assertEqual(12, lc.GRID_GUTTER)
        self.assertEqual(8, lc.ROW_GAP)

    def test_flat_page_command_row_rhythm(self) -> None:
        self.assertEqual(6, lc.COMPACT_PAGE_SPACING)
        self.assertEqual((12, 6, 12, 6), lc.COMPACT_COMMAND_ROW_MARGINS)

    def test_event_list_column_profile_breakpoint(self) -> None:
        self.assertEqual(1024, lc.EVENT_LIST_FULL_COLUMNS_MIN_WIDTH)
        self.assertEqual(106, lc.EVENT_LIST_CORE_ANOMALY_NO_WIDTH)
        self.assertEqual(110, lc.EVENT_LIST_CORE_SUPPLIER_WIDTH)
        self.assertEqual(140, lc.EVENT_LIST_CORE_PRODUCT_WIDTH)
        self.assertEqual(130, lc.EVENT_LIST_CORE_QUALITY_REQUIREMENT_WIDTH)
        self.assertEqual(78, lc.EVENT_LIST_CORE_STATUS_WIDTH)

    def test_ncr_list_column_profile_breakpoint(self) -> None:
        self.assertEqual(1024, lc.NCR_LIST_FULL_COLUMNS_MIN_WIDTH)
        self.assertEqual(118, lc.NCR_LIST_CORE_DEFECT_NO_WIDTH)
        self.assertEqual(96, lc.NCR_LIST_CORE_EVENT_DATE_WIDTH)
        self.assertEqual(88, lc.NCR_LIST_CORE_PROCESSING_LINE_WIDTH)
        self.assertEqual(108, lc.NCR_LIST_CORE_ITEM_NO_WIDTH)
        self.assertEqual(136, lc.NCR_LIST_CORE_PRODUCT_WIDTH)
        self.assertEqual(78, lc.NCR_LIST_CORE_STATUS_WIDTH)

    def test_sidebar_compact_create_navigation_rhythm(self) -> None:
        self.assertEqual(38, lc.SIDEBAR_NAV_ITEM_HEIGHT)
        self.assertEqual(10, lc.SIDEBAR_NAV_GROUP_GAP)
        self.assertEqual(4, lc.SIDEBAR_NAV_TOP_SPACING)
        self.assertEqual(6, lc.SIDEBAR_LOGO_TO_NAV_SPACING)


if __name__ == "__main__":
    unittest.main()
