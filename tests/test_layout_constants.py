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
        self.assertEqual(120, lc.NCR_LIST_CORE_DEFECT_NO_WIDTH)
        self.assertEqual(96, lc.NCR_LIST_CORE_EVENT_DATE_WIDTH)
        self.assertEqual(88, lc.NCR_LIST_CORE_PROCESSING_LINE_WIDTH)
        self.assertEqual(120, lc.NCR_LIST_CORE_ITEM_NO_WIDTH)
        self.assertEqual(180, lc.NCR_LIST_CORE_PRODUCT_WIDTH)
        self.assertEqual(78, lc.NCR_LIST_CORE_STATUS_WIDTH)

    def test_sidebar_compact_create_navigation_rhythm(self) -> None:
        self.assertEqual(38, lc.SIDEBAR_NAV_ITEM_HEIGHT)
        self.assertEqual(10, lc.SIDEBAR_NAV_GROUP_GAP)
        self.assertEqual(4, lc.SIDEBAR_NAV_TOP_SPACING)
        self.assertEqual(6, lc.SIDEBAR_LOGO_TO_NAV_SPACING)

    # -- 新增常數回歸測試 -------------------------------------------------

    def test_control_row_spacing(self) -> None:
        self.assertEqual(8, lc.CONTROL_ROW_SPACING)

    def test_dialog_header_footer_constants(self) -> None:
        self.assertEqual(44, lc.DIALOG_HEADER_HEIGHT)
        self.assertEqual(88, lc.DIALOG_FOOTER_CLOSE_MIN_WIDTH)
        self.assertEqual(16, lc.DIALOG_HEADER_FOOTER_H_MARGIN)

    def test_dialog_body_and_card_margins(self) -> None:
        self.assertEqual((16, 14, 16, 10), lc.DIALOG_BODY_MARGINS)
        self.assertEqual((16, 12, 16, 12), lc.DIALOG_CARD_MARGINS)

    def test_close_dialog_constants(self) -> None:
        self.assertEqual((12, 8, 12, 8), lc.CLOSE_DIALOG_REF_MARGINS)
        self.assertEqual(120, lc.CLOSE_DIALOG_PROBLEM_MIN_HEIGHT)

    def test_empty_state_margins(self) -> None:
        self.assertEqual((24, 32, 24, 32), lc.EMPTY_STATE_MARGINS)

    def test_brand_divider_constants(self) -> None:
        self.assertEqual((0, 6, 0, 4), lc.BRAND_DIVIDER_MARGINS)
        self.assertEqual(5, lc.BRAND_DIVIDER_SPACING)

    def test_text_edit_fallback_constants(self) -> None:
        self.assertEqual(22, lc.TEXT_EDIT_FALLBACK_LINE_HEIGHT)
        self.assertEqual(20, lc.TEXT_EDIT_FALLBACK_PADDING)

    def test_filter_width_constants(self) -> None:
        self.assertEqual(112, lc.FILTER_STATUS_COMBO_WIDTH)
        self.assertEqual(104, lc.FILTER_MONTH_INPUT_WIDTH)
        self.assertEqual(170, lc.FILTER_SUPPLIER_MIN_WIDTH)

    def test_master_search_width_constants(self) -> None:
        self.assertEqual(220, lc.MASTER_SEARCH_MIN_WIDTH)
        self.assertEqual(340, lc.MASTER_SEARCH_MAX_WIDTH)

    def test_home_backlog_column_widths(self) -> None:
        self.assertEqual(120, lc.HOME_BACKLOG_ANOMALY_NO_WIDTH)
        self.assertEqual(110, lc.HOME_BACKLOG_SUPPLIER_WIDTH)
        self.assertEqual(130, lc.HOME_BACKLOG_ITEM_NO_WIDTH)
        self.assertEqual(130, lc.HOME_BACKLOG_PRODUCT_WIDTH)
        self.assertEqual(150, lc.HOME_BACKLOG_NEXT_ACTION_WIDTH)
        self.assertEqual(104, lc.HOME_BACKLOG_DUE_DATE_WIDTH)
        self.assertEqual(115, lc.HOME_BACKLOG_RESPONSIBLE_WIDTH)
        self.assertEqual(70, lc.HOME_BACKLOG_STATUS_WIDTH)


if __name__ == "__main__":
    unittest.main()
