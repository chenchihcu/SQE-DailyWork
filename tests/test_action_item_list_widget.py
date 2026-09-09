from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from ui import layout_constants as lc
from ui.widgets.action_item_list_widget import ActionItemListWidget


class ActionItemListWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_add_rows_and_collect_items(self) -> None:
        widget = ActionItemListWidget()
        widget.set_items(
            [
                {
                    "description": "評估修改鋼板開孔",
                    "owner": "Alice",
                    "due_date": "2026-09-16",
                },
                {
                    "description": "觀察 SPI 錫量",
                    "owner": "Bob",
                    "due_date": "2026-09-20",
                },
            ]
        )
        items = widget.get_items()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["owner"], "Alice")
        self.assertEqual(items[1]["due_date"], "2026-09-20")

    def test_legacy_numbered_description_expands_rows(self) -> None:
        widget = ActionItemListWidget()
        widget.set_from_legacy_description(
            "1. 第一項\n2. 第二項\n3. 第三項",
            default_owner="振順豐",
            default_due="2026-09-16",
        )
        items = widget.get_items()
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["description"], "第一項")
        self.assertEqual(items[1]["owner"], "振順豐")
        self.assertEqual(items[2]["due_date"], "2026-09-16")

    def test_single_legacy_line_keeps_one_row(self) -> None:
        widget = ActionItemListWidget()
        widget.set_from_legacy_description(
            "1. 要求 8D",
            default_owner="Alice",
            default_due="2026-09-16",
        )
        items = widget.get_items()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["description"], "要求 8D")

    def test_column_header_labels_and_date_field_width(self) -> None:
        widget = ActionItemListWidget()
        header_labels = [
            label.text()
            for label in widget._column_header.findChildren(QLabel)
            if label.text()
        ]
        self.assertEqual(header_labels, ["處置內容", "責任人", "預定日期"])

        row = widget._rows[0]
        self.assertEqual(row.due_date_edit.minimumWidth(), lc.ACTION_ITEM_DUE_DATE_WIDTH)
        self.assertEqual(row.owner_input.minimumWidth(), lc.ACTION_ITEM_OWNER_WIDTH)
        widget.set_items([{"description": "測試", "owner": "", "due_date": "2026-09-01"}])
        self.assertEqual(
            widget._rows[0].due_date_edit.date().toString("yyyy-MM-dd"),
            "2026-09-01",
        )

    def test_read_only_hides_column_header(self) -> None:
        widget = ActionItemListWidget()
        self.assertFalse(widget._column_header.isHidden())
        widget.setReadOnly(True)
        self.assertTrue(widget._column_header.isHidden())


if __name__ == "__main__":
    unittest.main()
