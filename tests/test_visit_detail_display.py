from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtWidgets import QApplication, QFrame, QLabel

from services.event import _query_service as _query_service_mod, _visit_service as _visit_service_mod
from ui.theme import apply_app_theme
from ui.widgets import event_actions
from ui.widgets.defect_list_widget import EventListWidget


class _DummyMainWindow:
    def refresh_all_views(self) -> None:
        return

    def open_new_visit_dialog(self) -> None:
        return

    def open_new_anomaly_dialog(self) -> None:
        return


class VisitDetailDisplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        apply_app_theme(cls.app)


    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            cls.app.quit()

    def setUp(self) -> None:
        self._original_list_events = _query_service_mod.list_events
        _query_service_mod.list_events = lambda _filters=None: []
        try:
            self.widget = EventListWidget(_DummyMainWindow(), mode="query")
            self.widget.show()
            self.app.processEvents()
        except Exception:
            _query_service_mod.list_events = self._original_list_events
            raise

    def tearDown(self) -> None:
        self.widget.close()
        self.app.processEvents()
        _query_service_mod.list_events = self._original_list_events

    def _visit_detail_item_values(self, dialog: event_actions.VisitDetailDialog) -> dict[str, str]:
        item_values: dict[str, str] = {}
        for row in dialog.findChildren(QFrame, "vdItemRow"):
            texts = [label.text().strip() for label in row.findChildren(QLabel)]
            if len(texts) >= 3:
                item_values[texts[1]] = texts[2]
        return item_values

    def test_visit_detail_stylesheets_do_not_emit_parse_warnings(self) -> None:
        messages: list[str] = []

        def capture_qt_message(_mode, _context, message) -> None:
            messages.append(str(message))

        previous_handler = qInstallMessageHandler(capture_qt_message)
        dialog = None
        try:
            dialog = event_actions.VisitDetailDialog(
                {
                    "visit_date": "2026-04-18",
                    "supplier_name": "供應商-A",
                    "work_order_no": "WO-001",
                    "production_qty": 120,
                    "tech_transfer": True,
                    "tech_transfer_doc": True,
                    "carrier_requirement": False,
                    "dispensing_process": True,
                    "functional_test": False,
                    "packaging_requirement": True,
                    "summary": "摘要內容",
                }
            )
            self.app.processEvents()
        finally:
            qInstallMessageHandler(previous_handler)
            if dialog is not None:
                dialog.close()
                dialog.deleteLater()
                self.app.processEvents()

        stylesheet_warnings = [
            message for message in messages if "Could not parse stylesheet" in message
        ]
        self.assertEqual([], stylesheet_warnings, "\n".join(messages))

    def test_open_visit_detail_shows_all_transfer_items(self) -> None:
        visit_detail = {
            "visit_date": "2026-04-18",
            "supplier_name": "供應商-A",
            "work_order_no": "WO-001",
            "production_qty": 120,
            "tech_transfer": True,
            "tech_transfer_doc": True,
            "carrier_requirement": False,
            "dispensing_process": True,
            "functional_test": False,
            "packaging_requirement": True,
            "summary": "摘要內容",
        }

        requested_visit_ids: list[str] = []
        captured_dialogs: list[event_actions.VisitDetailDialog] = []
        original_get_visit_detail = _visit_service_mod.get_visit_detail
        original_exec = event_actions.VisitDetailDialog.exec

        def fake_get_visit_detail(visit_id: str) -> dict:
            requested_visit_ids.append(visit_id)
            return visit_detail

        def fake_exec(dialog: event_actions.VisitDetailDialog) -> int:
            captured_dialogs.append(dialog)
            return 0

        _visit_service_mod.get_visit_detail = fake_get_visit_detail
        event_actions.VisitDetailDialog.exec = fake_exec
        try:
            self.widget.open_visit_detail("visit-001")
        finally:
            _visit_service_mod.get_visit_detail = original_get_visit_detail
            event_actions.VisitDetailDialog.exec = original_exec

        self.assertEqual(["visit-001"], requested_visit_ids)
        self.assertEqual(1, len(captured_dialogs))
        dialog = captured_dialogs[0]
        dialog_texts = [label.text().strip() for label in dialog.findChildren(QLabel)]
        self.assertIn("已技轉", dialog_texts)
        self.assertEqual(
            {
                "作業標準書": "有",
                "載具要求": "沒有",
                "Underfill 要求": "有",
                "電訊測試": "沒有",
                "包裝規範": "有",
            },
            self._visit_detail_item_values(dialog),
        )


if __name__ == "__main__":
    unittest.main()
