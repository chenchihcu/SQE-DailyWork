from __future__ import annotations

import unittest

from ui.widgets.defect_list_widget import EVENT_QUERY_SCOPE_TABS


class SupplierOrientedUiContractTests(unittest.TestCase):
    def test_event_scope_contract_has_four_page_local_views(self) -> None:
        self.assertEqual(
            ["單獨異常", "訪廠發現異常", "訪廠紀錄", "已結案"],
            [label for label, _scope, _event_type in EVENT_QUERY_SCOPE_TABS],
        )

    def test_source_scopes_are_not_navigation_labels(self) -> None:
        from ui.sidebar_nav import _NAV_GROUPS

        labels = [
            label
            for _group, entries in _NAV_GROUPS
            for label, _action, _badge, _icon in entries
        ]
        self.assertNotIn("單獨異常", labels)
        self.assertNotIn("訪廠發現異常", labels)
        self.assertIn("事件管理", labels)
        self.assertIn("供應商總覽", labels)


if __name__ == "__main__":
    unittest.main()
