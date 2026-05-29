from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from services import event_service
from ui.widgets.defect_list_widget import EventListWidget

class _DummyMainWindow:
    def refresh_all_views(self) -> None:
        return
    def open_new_visit_dialog(self) -> None:
        return
    def open_new_anomaly_dialog(self) -> None:
        return

class ClosedTabCategoriesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._list_events_patch = patch(
            "ui.widgets.defect_list_widget.event_service.list_events",
            return_value=[],
        )
        self._list_events = self._list_events_patch.start()

    def tearDown(self) -> None:
        self._list_events_patch.stop()

    def test_closed_tab_has_no_subtabs(self) -> None:
        # Initialize with fixed_status="已結案"
        widget = EventListWidget(
            _DummyMainWindow(), 
            mode="query", 
            fixed_scope=event_service.EVENT_SCOPE_CLOSED_ONLY,
            fixed_status="已結案"
        )
        
        # Verify sub-tabs are removed for unified "Closed" view
        self.assertIsNone(widget.event_scope_tab_bar)
        
        # Verify scope is fixed to CLOSED_ONLY
        self.assertEqual(event_service.EVENT_SCOPE_CLOSED_ONLY, widget._filter_event_scope)
        
        widget.close()

    def test_normal_tab_has_all_subtabs(self) -> None:
        # Initialize normally
        widget = EventListWidget(
            _DummyMainWindow(), 
            mode="query"
        )
        
        self.assertIsNotNone(widget.event_scope_tab_bar)
        assert widget.event_scope_tab_bar is not None
        
        labels = [
            widget.event_scope_tab_bar.tabText(i)
            for i in range(widget.event_scope_tab_bar.count())
        ]
        
        self.assertIn("訪廠紀錄", labels)
        self.assertIn("訪廠發現異常", labels)
        self.assertIn("單獨異常", labels)
        self.assertEqual(3, len(labels))
        
        # Verify default selected scope is VISIT_ONLY
        self.assertEqual(event_service.EVENT_SCOPE_VISIT_ONLY, widget._filter_event_scope)
        
        widget.close()

if __name__ == "__main__":
    unittest.main()
