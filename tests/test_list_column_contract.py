from __future__ import annotations

import unittest

from ncr.models.defect import DETAIL_EXPORT_COLUMNS, LIST_FIELD_ORDER
from ui.list_column_contract import (
    CASE_QUEUE_COLUMNS,
    EVENT_LIST_COMPACT_FIELDS,
    EVENT_LIST_FIELDS,
    SUPPLIER_360_ANOMALY_COLUMNS,
    SUPPLIER_OVERVIEW_COLUMNS,
)


class ListColumnContractTests(unittest.TestCase):
    def test_supplier_event_compact_view_keeps_category_visible(self) -> None:
        self.assertIn("category", EVENT_LIST_COMPACT_FIELDS)
        self.assertNotEqual("category", EVENT_LIST_FIELDS[-1])

    def test_supplier_event_product_and_content_order(self) -> None:
        self.assertLess(EVENT_LIST_FIELDS.index("product_code"), EVENT_LIST_FIELDS.index("product_name"))
        self.assertLess(EVENT_LIST_FIELDS.index("product_name"), EVENT_LIST_FIELDS.index("category"))
        self.assertLess(EVENT_LIST_FIELDS.index("category"), EVENT_LIST_FIELDS.index("process_keywords"))
        self.assertLess(EVENT_LIST_FIELDS.index("process_keywords"), EVENT_LIST_FIELDS.index("content"))

    def test_process_keywords_hidden_in_compact_view(self) -> None:
        self.assertNotIn("process_keywords", EVENT_LIST_COMPACT_FIELDS)

    def test_case_queue_columns_end_with_responsible_person(self) -> None:
        self.assertEqual("responsible_person", CASE_QUEUE_COLUMNS[-1].field)
        self.assertEqual("is_active", SUPPLIER_OVERVIEW_COLUMNS[-1].field)
        self.assertLess(
            SUPPLIER_OVERVIEW_COLUMNS.index(next(c for c in SUPPLIER_OVERVIEW_COLUMNS if c.field == "latest_anomaly_category")),
            SUPPLIER_OVERVIEW_COLUMNS.index(next(c for c in SUPPLIER_OVERVIEW_COLUMNS if c.field == "latest_anomaly_desc")),
        )

    def test_supplier_360_anomaly_includes_category_before_summary(self) -> None:
        fields = tuple(column.field for column in SUPPLIER_360_ANOMALY_COLUMNS)
        self.assertLess(fields.index("category"), fields.index("problem_desc"))
        self.assertEqual("status", fields[-1])

    def test_ncr_list_and_export_share_the_same_field_order(self) -> None:
        self.assertEqual(
            LIST_FIELD_ORDER,
            [field_name for field_name, _label in DETAIL_EXPORT_COLUMNS],
        )
        self.assertLess(LIST_FIELD_ORDER.index("item_no"), LIST_FIELD_ORDER.index("return_slip_type"))
        self.assertEqual("status", LIST_FIELD_ORDER[-1])
        self.assertNotEqual("category", LIST_FIELD_ORDER[-1])


if __name__ == "__main__":
    unittest.main()
