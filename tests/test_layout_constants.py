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

    def test_appearance_settings_page_contract(self) -> None:
        self.assertEqual(160, lc.APPEARANCE_CATEGORY_RAIL_WIDTH)
        self.assertEqual(760, lc.APPEARANCE_TWO_COLUMN_MIN_WIDTH)

    def test_flat_page_command_row_rhythm(self) -> None:
        self.assertEqual(6, lc.COMPACT_PAGE_SPACING)
        self.assertEqual((12, 6, 12, 6), lc.COMPACT_COMMAND_ROW_MARGINS)

    def test_workbench_action_table_column_widths(self) -> None:
        self.assertEqual(112, lc.WORKBENCH_ACTION_DUE_DATE_WIDTH)
        self.assertEqual(96, lc.WORKBENCH_ACTION_OWNER_WIDTH)
        self.assertEqual(88, lc.WORKBENCH_ACTION_STATUS_WIDTH)
        self.assertEqual(120, lc.WORKBENCH_ACTION_TYPE_WIDTH)
        self.assertEqual(56, lc.WORKBENCH_ACTION_EDIT_WIDTH)
        self.assertEqual(168, lc.WORKBENCH_ACTION_FLOW_WIDTH)
        self.assertEqual(4, lc.TABLE_CELL_WIDGET_V_MARGIN)
        self.assertEqual(40, lc.TABLE_CELL_ACTION_MIN_HEIGHT)
        self.assertEqual(44, lc.WORKBENCH_ACTION_ROW_HEIGHT)

    def test_action_item_list_layout_constants(self) -> None:
        self.assertEqual(28, lc.ACTION_ITEM_INDEX_WIDTH)
        self.assertEqual(52, lc.ACTION_ITEM_DELETE_WIDTH)
        self.assertEqual(112, lc.ACTION_ITEM_OWNER_WIDTH)
        self.assertEqual(128, lc.ACTION_ITEM_DUE_DATE_WIDTH)
        self.assertGreater(lc.ACTION_ITEM_OWNER_WIDTH, lc.WORKBENCH_ACTION_OWNER_WIDTH)
        self.assertGreater(
            lc.ACTION_ITEM_DUE_DATE_WIDTH, lc.WORKBENCH_ACTION_DUE_DATE_WIDTH
        )

    def test_workbench_root_cause_dialog_constants(self) -> None:
        self.assertEqual(820, lc.WORKBENCH_ROOT_CAUSE_DIALOG_PREFERRED_WIDTH)
        self.assertEqual(640, lc.WORKBENCH_ROOT_CAUSE_DIALOG_PREFERRED_HEIGHT)
        self.assertEqual(28, lc.WORKBENCH_ROOT_CAUSE_COMPACT_ADD_HEIGHT)

    def test_event_list_column_profile_breakpoint(self) -> None:
        self.assertEqual(1024, lc.EVENT_LIST_FULL_COLUMNS_MIN_WIDTH)
        self.assertEqual(106, lc.EVENT_LIST_CORE_ANOMALY_NO_WIDTH)
        self.assertEqual(110, lc.EVENT_LIST_CORE_SUPPLIER_WIDTH)
        self.assertEqual(140, lc.EVENT_LIST_CORE_PRODUCT_WIDTH)
        self.assertEqual(130, lc.EVENT_LIST_CORE_QUALITY_REQUIREMENT_WIDTH)
        self.assertEqual(78, lc.EVENT_LIST_CORE_STATUS_WIDTH)
        self.assertEqual(360, lc.EVENT_LIST_QUICK_REVIEW_MIN_WIDTH)
        self.assertEqual(58, lc.EVENT_LIST_SPLITTER_LIST_STRETCH)
        self.assertEqual(42, lc.EVENT_LIST_SPLITTER_PREVIEW_STRETCH)
        self.assertEqual(1200, lc.EVENT_LIST_PREVIEW_COLLAPSE_WIDTH)
        self.assertEqual(62, lc.EVENT_LIST_PREVIEW_THUMB_SIZE)

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
        self.assertEqual(4, lc.SIDEBAR_MASTER_SUBGROUP_TOP_SPACING)
        self.assertEqual(2, lc.SIDEBAR_MASTER_SUBGROUP_LABEL_BOTTOM_SPACING)
        self.assertEqual(6, lc.SIDEBAR_MASTER_SUBGROUP_GAP)

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
        self.assertEqual(320, lc.CLOSE_DIALOG_ATTACHMENT_SCROLL_MAX_HEIGHT)

    def test_global_search_dialog_constants(self) -> None:
        self.assertEqual(620, lc.GLOBAL_SEARCH_DIALOG_MIN_WIDTH)
        self.assertEqual((18, 16, 18, 14), lc.GLOBAL_SEARCH_DIALOG_MARGINS)
        self.assertEqual(8, lc.GLOBAL_SEARCH_DIALOG_SPACING)

    def test_query_workflow_page_spacing(self) -> None:
        self.assertEqual(10, lc.QUERY_WORKFLOW_PAGE_SPACING)

    def test_ncr_list_preferred_column_widths(self) -> None:
        self.assertEqual(140, lc.NCR_LIST_PREFERRED_DEFECT_NO_WIDTH)
        self.assertEqual(100, lc.NCR_LIST_PREFERRED_EVENT_DATE_WIDTH)
        self.assertEqual(110, lc.NCR_LIST_PREFERRED_PROCESSING_LINE_WIDTH)
        self.assertEqual(120, lc.NCR_LIST_PREFERRED_RETURN_SLIP_TYPE_WIDTH)
        self.assertEqual(140, lc.NCR_LIST_PREFERRED_WORK_ORDER_WIDTH)
        self.assertEqual(140, lc.NCR_LIST_PREFERRED_INTERNAL_WORK_ORDER_WIDTH)
        self.assertEqual(140, lc.NCR_LIST_PREFERRED_TRANSFER_SLIP_WIDTH)
        self.assertEqual(120, lc.NCR_LIST_PREFERRED_ITEM_NO_WIDTH)
        self.assertEqual(200, lc.NCR_LIST_PREFERRED_PRODUCT_NAME_WIDTH)
        self.assertEqual(320, lc.NCR_LIST_PREFERRED_DESCRIPTION_WIDTH)

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

    def test_anomaly_problem_photo_dual_column_contract(self) -> None:
        self.assertEqual(3, lc.ANOMALY_PROBLEM_PHOTO_LEFT_STRETCH)
        self.assertEqual(2, lc.ANOMALY_PROBLEM_PHOTO_RIGHT_STRETCH)
        self.assertEqual(72, lc.WORKBENCH_OVERVIEW_THUMB_SIZE)
        self.assertEqual(6, lc.WORKBENCH_OVERVIEW_MAX_THUMBNAILS)

if __name__ == "__main__":
    unittest.main()
