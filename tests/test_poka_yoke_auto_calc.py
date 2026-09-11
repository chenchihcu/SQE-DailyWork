from __future__ import annotations

import importlib
import sqlite3
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication

from database.repository import (
    create_anomaly_with_visit_link,
    create_schema,
    find_anomaly_trace_duplicate,
    get_anomaly_detail,
)
from services.anomaly_trace_contract import ANOMALY_SOURCE_OUTSOURCE_PROCESSING
from services.anomaly_trace_validator import validate_trace_duplicates
from services.event import _anomaly_service


class TraceDuplicateValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        create_schema(self.conn)
        self.conn.execute(
            """
            INSERT INTO suppliers(
                id, supplier_name, category, is_active, created_at, updated_at
            ) VALUES ('sup-1', '供應商A', '原物料供應商', 1, '', '')
            """
        )
        self.conn.execute(
            """
            INSERT INTO products(
                id, supplier_id, product_code, product_name, product_stage,
                is_active, created_at, updated_at
            ) VALUES ('prod-1', 'sup-1', 'PN-001', '測試產品', '量產', 1, '', '')
            """
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_validate_trace_duplicates_blocks_new_value(self) -> None:
        create_anomaly_with_visit_link(
            self.conn,
            anomaly_date="2026-05-12",
            supplier_id="sup-1",
            product_id="prod-1",
            problem_desc="第一筆",
            anomaly_source=ANOMALY_SOURCE_OUTSOURCE_PROCESSING,
            outsource_work_order="OWO-9001",
            sync_visit=False,
            anomaly_no="20260512001",
        )
        with self.assertRaisesRegex(ValueError, "委外製令單號與異常單號 20260512001 重複"):
            validate_trace_duplicates(
                self.conn,
                supplier_id="sup-1",
                trace_fields={"outsource_work_order": "OWO-9001"},
            )

    def test_validate_trace_duplicates_grandfathers_unchanged_value(self) -> None:
        create_anomaly_with_visit_link(
            self.conn,
            anomaly_date="2026-05-12",
            supplier_id="sup-1",
            product_id="prod-1",
            problem_desc="第一筆",
            anomaly_source=ANOMALY_SOURCE_OUTSOURCE_PROCESSING,
            outsource_work_order="OWO-9001",
            sync_visit=False,
            anomaly_no="20260512001",
        )
        validate_trace_duplicates(
            self.conn,
            supplier_id="sup-1",
            trace_fields={"outsource_work_order": "OWO-9001"},
            exclude_anomaly_id="ignored",
            existing_trace_fields={"outsource_work_order": "OWO-9001"},
        )


class TraceDuplicateServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        create_schema(self.conn)
        self.conn.execute(
            """
            INSERT INTO suppliers(
                id, supplier_name, category, is_active, created_at, updated_at
            ) VALUES ('sup-1', '供應商A', '原物料供應商', 1, '', '')
            """
        )
        self.conn.execute(
            """
            INSERT INTO products(
                id, supplier_id, product_code, product_name, product_stage,
                is_active, created_at, updated_at
            ) VALUES ('prod-1', 'sup-1', 'PN-001', '測試產品', '量產', 1, '', '')
            """
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    @patch("services.event._anomaly_service.load_application_preferences")
    @patch("services.event._anomaly_service._connection.get_connection")
    def test_create_anomaly_blocks_duplicate_trace(
        self,
        mock_get_connection,
        mock_load_preferences,
    ) -> None:
        mock_get_connection.return_value.__enter__.return_value = self.conn
        mock_get_connection.return_value.__exit__.return_value = False
        mock_load_preferences.return_value = SimpleNamespace(
            erp_material_receipt_no_pattern="",
            erp_internal_work_order_no_pattern="",
            erp_outsource_work_order_pattern="^OWO-\\d+$",
            erp_outsource_receipt_no_pattern="",
        )
        _anomaly_service.create_anomaly_with_visit_link(
            {
                "anomaly_date": "2026-05-12",
                "supplier_id": "sup-1",
                "product_id": "prod-1",
                "problem_desc": "第一筆",
                "anomaly_source": ANOMALY_SOURCE_OUTSOURCE_PROCESSING,
                "outsource_work_order": "OWO-9001",
                "anomaly_no": "20260512001",
            }
        )
        with self.assertRaisesRegex(ValueError, "委外製令單號與異常單號 20260512001 重複"):
            _anomaly_service.create_anomaly_with_visit_link(
                {
                    "anomaly_date": "2026-05-13",
                    "supplier_id": "sup-1",
                    "product_id": "prod-1",
                    "problem_desc": "第二筆",
                    "anomaly_source": ANOMALY_SOURCE_OUTSOURCE_PROCESSING,
                    "outsource_work_order": "OWO-9001",
                    "anomaly_no": "20260513001",
                }
            )

    def test_repository_still_finds_duplicate_for_legacy_rows(self) -> None:
        create_anomaly_with_visit_link(
            self.conn,
            anomaly_date="2026-05-12",
            supplier_id="sup-1",
            product_id="prod-1",
            problem_desc="第一筆",
            anomaly_source=ANOMALY_SOURCE_OUTSOURCE_PROCESSING,
            outsource_work_order="OWO-9001",
            sync_visit=False,
            anomaly_no="20260512001",
        )
        second = create_anomaly_with_visit_link(
            self.conn,
            anomaly_date="2026-05-13",
            supplier_id="sup-1",
            product_id="prod-1",
            problem_desc="第二筆",
            anomaly_source=ANOMALY_SOURCE_OUTSOURCE_PROCESSING,
            outsource_work_order="OWO-9001",
            sync_visit=False,
            anomaly_no="20260513001",
        )
        duplicate = find_anomaly_trace_duplicate(
            self.conn,
            supplier_id="sup-1",
            field_name="outsource_work_order",
            field_value="OWO-9001",
        )
        self.assertIsNotNone(duplicate)
        second_detail = get_anomaly_detail(self.conn, str(second["anomaly_id"]))
        assert second_detail is not None
        self.assertEqual("OWO-9001", second_detail["outsource_work_order"])


class NewAnomalyDialogPokaYokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._pandas_patch = patch.dict(sys.modules, {"pandas": ModuleType("pandas")})
        self._pandas_patch.start()
        self.addCleanup(self._pandas_patch.stop)
        sys.modules.pop("ui.widgets.defect_form_shim", None)
        self.widget_module = importlib.import_module("ui.widgets.defect_form_shim")
        self.addCleanup(lambda: sys.modules.pop("ui.widgets.defect_form_shim", None))
        import services.event_service as canonical_event_service

        self.widget_module.event_service = canonical_event_service
        self.NewAnomalyDialog = self.widget_module.NewAnomalyDialog
        self._suppliers = [{"id": "sup-1", "supplier_name": "供應商A", "is_active": True}]
        self._products = [
            {
                "id": "prd-1",
                "product_code": "PN-001",
                "product_name": "產品一號",
                "product_stage": "量產",
            }
        ]
        self._patches = [
            patch.object(
                self.widget_module.event_service,
                "preview_anomaly_no",
                side_effect=lambda d: d.replace("-", "") + "001" if d else "20260702001",
            ),
            patch.object(
                _anomaly_service,
                "preview_anomaly_no",
                side_effect=lambda d: d.replace("-", "") + "001" if d else "20260702001",
            ),
            patch.object(
                self.widget_module.event_service,
                "list_active_suppliers",
                return_value=self._suppliers,
            ),
            patch.object(
                self.widget_module.event_service,
                "list_active_products_for_supplier",
                return_value=self._products,
            ),
        ]
        for item in self._patches:
            item.start()
            self.addCleanup(item.stop)

    def test_date_edit_cannot_select_future(self) -> None:
        dialog = self.NewAnomalyDialog()
        self.addCleanup(dialog.close)
        self.assertEqual(QDate.currentDate(), dialog.date_edit.maximumDate())

    @patch("ui.widgets.new_anomaly_dialog.load_application_preferences")
    def test_date_change_respects_auto_fill_preference(self, mock_prefs) -> None:
        mock_prefs.return_value = SimpleNamespace(
            auto_fill_anomaly_no_on_date_change=False,
            default_anomaly_source="",
            default_responsible_person="",
            default_anomaly_category="",
            default_due_days=7,
            auto_uppercase_part_no=False,
        )
        dialog = self.NewAnomalyDialog()
        self.addCleanup(dialog.close)
        dialog.anomaly_no_preview_input.setText("20260101099")
        dialog.date_edit.setDate(QDate(2026, 1, 2))
        self.assertEqual("20260101099", dialog.anomaly_no_preview_input.text())
        dialog._dirty = False


if __name__ == "__main__":
    unittest.main()
