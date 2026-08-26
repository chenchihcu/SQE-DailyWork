"""Tests for shared overview/export display helpers."""

from __future__ import annotations

import unittest

from services.event._overview_format_helpers import (
    format_current_action_text,
    format_quality_report_required_for_export,
)


class OverviewFormatHelpersTests(unittest.TestCase):
    def test_format_current_action_text_with_due_date(self) -> None:
        text = format_current_action_text(
            {
                "description": "追蹤 8D",
                "owner": "王小明",
                "due_date": "2026-07-15",
            }
        )
        self.assertEqual("追蹤 8D（王小明 / 2026-07-15）", text)

    def test_format_current_action_text_without_due_date(self) -> None:
        text = format_current_action_text(
            {"description": "追蹤 8D", "owner": "", "due_date": ""}
        )
        self.assertEqual("追蹤 8D（—）", text)

    def test_format_current_action_text_empty(self) -> None:
        self.assertEqual("", format_current_action_text(None))

    def test_format_quality_report_required_for_export(self) -> None:
        self.assertEqual("未設定", format_quality_report_required_for_export(None))
        self.assertEqual("是", format_quality_report_required_for_export(True))
        self.assertEqual("否", format_quality_report_required_for_export(False))
        self.assertEqual("是", format_quality_report_required_for_export("yes"))


if __name__ == "__main__":
    unittest.main()
