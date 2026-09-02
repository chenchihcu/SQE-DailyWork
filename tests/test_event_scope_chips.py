from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from database import repository
from ui.widgets.defect_list_widget import EVENT_QUERY_SCOPE_TABS, EventListWidget


class EventScopeChipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_scope_chips_exist_and_are_exclusive(self) -> None:
        widget = EventListWidget(main_window=None, mode="query", fixed_scope=None)
        self.assertEqual(len(EVENT_QUERY_SCOPE_TABS), len(widget.scope_chip_buttons))
        checked = [
            scope
            for scope, button in widget.scope_chip_buttons.items()
            if button.isChecked()
        ]
        self.assertEqual(1, len(checked))
        self.assertEqual(repository.EVENT_SCOPE_ANOMALY_ONLY, checked[0])

    def test_set_event_scope_updates_checked_chip(self) -> None:
        widget = EventListWidget(main_window=None, mode="query", fixed_scope=None)
        with patch.object(widget, "refresh_data"):
            widget.set_event_scope(repository.EVENT_SCOPE_CLOSED_ONLY)
        self.assertEqual(
            repository.EVENT_SCOPE_CLOSED_ONLY,
            widget._filter_event_scope,
        )
        self.assertTrue(
            widget.scope_chip_buttons[repository.EVENT_SCOPE_CLOSED_ONLY].isChecked()
        )

    @patch("services.event._query_service.get_event_scope_counts", return_value={
        repository.EVENT_SCOPE_ANOMALY_ONLY: 3,
        repository.EVENT_SCOPE_CLOSED_ONLY: 9,
    })
    def test_chip_labels_include_scope_counts(self, _mock_counts) -> None:
        widget = EventListWidget(main_window=None, mode="query", fixed_scope=None)
        widget._sync_scope_chip_labels()
        self.assertEqual(
            "單獨異常 (3)",
            widget.scope_chip_buttons[repository.EVENT_SCOPE_ANOMALY_ONLY].text(),
        )
        self.assertEqual(
            "已結案 (9)",
            widget.scope_chip_buttons[repository.EVENT_SCOPE_CLOSED_ONLY].text(),
        )


if __name__ == "__main__":
    unittest.main()
