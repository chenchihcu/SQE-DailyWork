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


    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            cls.app.quit()

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

    def test_normal_query_has_no_visible_scope_tabbar(self) -> None:
        # Stage 2：scope 已升級為側欄一等導覽列，事件頁不再渲染頁內 scope 分頁列。
        widget = EventListWidget(
            _DummyMainWindow(),
            mode="query"
        )

        self.assertIsNone(widget.event_scope_tab_bar)

        # EVENT_QUERY_SCOPE_TABS 仍是 scope metadata 單一真相（4 個 scope）。
        from ui.widgets.defect_list_widget import EVENT_QUERY_SCOPE_TABS
        scopes = [scope for _label, scope, _t in EVENT_QUERY_SCOPE_TABS]
        self.assertEqual(
            [
                event_service.EVENT_SCOPE_ANOMALY_ONLY,
                event_service.EVENT_SCOPE_VISIT_WITH_ANOMALY,
                event_service.EVENT_SCOPE_VISIT_ONLY,
                event_service.EVENT_SCOPE_CLOSED_ONLY,
            ],
            scopes,
        )

        # 預設 scope 為 ANOMALY_ONLY（對應 anomaly 側欄 badge / 單獨異常 列）。
        self.assertEqual(event_service.EVENT_SCOPE_ANOMALY_ONLY, widget._filter_event_scope)

        # set_event_scope 可切到任一 scope（保留既有 supplier / 月份篩選）。
        widget.set_event_scope(event_service.EVENT_SCOPE_VISIT_ONLY)
        self.assertEqual(event_service.EVENT_SCOPE_VISIT_ONLY, widget._filter_event_scope)
        widget.set_event_scope(event_service.EVENT_SCOPE_CLOSED_ONLY)
        self.assertEqual(event_service.EVENT_SCOPE_CLOSED_ONLY, widget._filter_event_scope)
        self.assertEqual("已結案", widget._filter_status)

        widget.close()

if __name__ == "__main__":
    unittest.main()
