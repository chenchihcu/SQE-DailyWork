from __future__ import annotations

import sqlite3
import unittest
from unittest.mock import patch

from database.repository import (
    ANOMALY_TRACE_UNIQUE_INDEX_REMOVAL_META_KEY,
    create_schema,
    create_anomaly_with_visit_link,
    find_anomaly_trace_duplicate,
    get_anomaly_detail,
    get_migration_meta,
)
from services.anomaly_trace_contract import (
    ANOMALY_SOURCE_MATERIAL_INCOMING,
    ANOMALY_SOURCE_OTHER,
    ANOMALY_SOURCE_OUTSOURCE_PROCESSING,
    ANOMALY_SOURCE_VISIT_AUDIT,
    normalize_anomaly_source,
    required_trace_fields_for_source,
    visible_trace_fields_for_source,
)
from services.anomaly_trace_validator import validate_anomaly_trace_payload
from ui.appearance_preferences import AppearancePreferences


class AnomalyTraceContractTests(unittest.TestCase):
    def test_legacy_source_normalization(self) -> None:
        self.assertEqual(
            ANOMALY_SOURCE_MATERIAL_INCOMING,
            normalize_anomaly_source("進料檢驗 (IQC)"),
        )
        self.assertEqual(
            ANOMALY_SOURCE_VISIT_AUDIT,
            normalize_anomaly_source("訪廠發現"),
        )

    def test_source_field_matrix(self) -> None:
        self.assertEqual(
            {"material_receipt_no"},
            set(visible_trace_fields_for_source(ANOMALY_SOURCE_MATERIAL_INCOMING)),
        )
        self.assertEqual(
            {"outsource_work_order"},
            set(required_trace_fields_for_source(ANOMALY_SOURCE_OUTSOURCE_PROCESSING)),
        )
        self.assertEqual(
            set(),
            set(required_trace_fields_for_source(ANOMALY_SOURCE_OTHER)),
        )
        self.assertEqual(
            set(),
            set(visible_trace_fields_for_source(ANOMALY_SOURCE_VISIT_AUDIT)),
        )


class AnomalyTraceValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.patterns = {
            "material_receipt_no": "^MR-\\d+$",
            "internal_work_order_no": "^IWO-\\d+$",
            "outsource_work_order": "^OWO-\\d+$",
            "outsource_receipt_no": "^OR-\\d+$",
        }

    def test_required_field_missing_pattern_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "ERP 格式規則"):
            validate_anomaly_trace_payload(
                anomaly_source=ANOMALY_SOURCE_MATERIAL_INCOMING,
                supplier_id="sup-1",
                payload={"material_receipt_no": "MR-1001"},
                patterns={"material_receipt_no": ""},
            )

    def test_hidden_field_rejected_for_visit_source(self) -> None:
        with self.assertRaisesRegex(ValueError, "不可填寫"):
            validate_anomaly_trace_payload(
                anomaly_source=ANOMALY_SOURCE_VISIT_AUDIT,
                supplier_id="sup-1",
                payload={"material_receipt_no": "MR-1001"},
                patterns=self.patterns,
            )


class AnomalyTraceRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        create_schema(self.conn)
        self.conn.execute(
            """
            INSERT INTO suppliers(
                id, supplier_name, contact_name, department, phone,
                contact_email, category, is_active, created_at, updated_at
            ) VALUES ('sup-1', '測試供應商', '', '', '', '', '', 1, '', '')
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

    def test_create_and_read_trace_fields(self) -> None:
        result = create_anomaly_with_visit_link(
            self.conn,
            anomaly_date="2026-05-12",
            supplier_id="sup-1",
            product_id="prod-1",
            problem_desc="測試不良",
            anomaly_source=ANOMALY_SOURCE_OUTSOURCE_PROCESSING,
            outsource_work_order="OWO-9001",
            sync_visit=False,
            anomaly_no="20260512001",
        )
        detail = get_anomaly_detail(self.conn, str(result["anomaly_id"]))
        assert detail is not None
        self.assertEqual(ANOMALY_SOURCE_OUTSOURCE_PROCESSING, detail["anomaly_source"])
        self.assertEqual("OWO-9001", detail["outsource_work_order"])

    def test_same_supplier_trace_number_allows_multiple_anomalies(self) -> None:
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
        self.assertIn(
            duplicate["anomaly_no"],
            {"20260512001", "20260513001"},
        )
        second_detail = get_anomaly_detail(self.conn, str(second["anomaly_id"]))
        assert second_detail is not None
        self.assertEqual("OWO-9001", second_detail["outsource_work_order"])


class AnomalyTraceMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(
            """
            CREATE TABLE suppliers (
                id TEXT PRIMARY KEY,
                supplier_name TEXT NOT NULL UNIQUE,
                contact_name TEXT NOT NULL DEFAULT '',
                department TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                contact_email TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE products (
                id TEXT PRIMARY KEY,
                product_code TEXT NOT NULL,
                product_name TEXT NOT NULL,
                product_stage TEXT NOT NULL DEFAULT '量產',
                supplier_id TEXT,
                secondary_supplier_id TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
            );
            CREATE TABLE anomalies (
                id TEXT PRIMARY KEY,
                anomaly_no TEXT NOT NULL UNIQUE,
                anomaly_date TEXT NOT NULL,
                supplier_id TEXT NOT NULL,
                visit_id TEXT,
                product_id TEXT,
                problem_desc TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                product_lot_no TEXT NOT NULL DEFAULT '',
                product_name TEXT NOT NULL DEFAULT '',
                product_stage TEXT NOT NULL DEFAULT '量產',
                outsource_work_order TEXT NOT NULL DEFAULT '',
                batch_qty INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT '待處理',
                improvement_desc TEXT NOT NULL DEFAULT '',
                closed_by TEXT NOT NULL DEFAULT '',
                closed_at TEXT,
                pending_items TEXT NOT NULL DEFAULT '',
                responsible_person TEXT NOT NULL DEFAULT '',
                due_date TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
            );
            """
        )
        self.conn.execute(
            "INSERT INTO suppliers(id, supplier_name) VALUES ('sup-1', 'Legacy Supplier')"
        )
        self.conn.execute(
            """
            INSERT INTO products(id, product_code, product_name, supplier_id)
            VALUES ('prod-1', 'PN-001', 'Legacy Product', 'sup-1')
            """
        )
        self.conn.executemany(
            """
            INSERT INTO anomalies(
                id, anomaly_no, anomaly_date, supplier_id, product_id, problem_desc,
                outsource_work_order, status
            ) VALUES (?, ?, ?, 'sup-1', 'prod-1', ?, ?, '待處理')
            """,
            [
                ("anom-1", "20260507001", "2026-05-07", "第一筆", "5102-260401002"),
                ("anom-2", "20260511003", "2026-05-11", "第二筆", "5102-260401002"),
            ],
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_legacy_duplicate_trace_values_migrate_without_blocking(self) -> None:
        create_schema(self.conn)

        index_names = {
            str(row["name"])
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='anomalies'"
            ).fetchall()
        }
        for column in (
            "material_receipt_no",
            "internal_work_order_no",
            "outsource_work_order",
            "outsource_receipt_no",
        ):
            self.assertNotIn(f"uniq_anomalies_{column}_supplier", index_names)
        self.assertEqual(
            "1",
            get_migration_meta(self.conn, ANOMALY_TRACE_UNIQUE_INDEX_REMOVAL_META_KEY),
        )
        duplicate_count = self.conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM anomalies
            WHERE supplier_id = 'sup-1'
              AND outsource_work_order = '5102-260401002'
            """
        ).fetchone()["cnt"]
        self.assertEqual(2, duplicate_count)

    def test_retired_trace_unique_indexes_are_dropped(self) -> None:
        create_schema(self.conn)
        self.conn.execute(
            "UPDATE anomalies SET outsource_work_order = '5102-260401002-1' WHERE id = 'anom-1'"
        )
        self.conn.execute(
            "UPDATE anomalies SET outsource_work_order = '5102-260401002-2' WHERE id = 'anom-2'"
        )
        self.conn.execute(
            """
            CREATE UNIQUE INDEX uniq_anomalies_outsource_work_order_supplier
            ON anomalies(supplier_id, outsource_work_order)
            WHERE TRIM(COALESCE(outsource_work_order, '')) <> ''
            """
        )
        self.conn.execute(
            "DELETE FROM migration_meta WHERE key = ?",
            (ANOMALY_TRACE_UNIQUE_INDEX_REMOVAL_META_KEY,),
        )
        self.conn.commit()

        create_schema(self.conn)

        index_names = {
            str(row["name"])
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='anomalies'"
            ).fetchall()
        }
        self.assertNotIn("uniq_anomalies_outsource_work_order_supplier", index_names)


class NcrToAnomalyHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        create_schema(self.conn)
        self.conn.execute(
            """
            INSERT INTO suppliers(
                id, supplier_name, contact_name, department, phone,
                contact_email, category, is_active, created_at, updated_at
            ) VALUES ('sup-1', '供應商A', '', '', '', '', '', 1, '', '')
            """
        )
        self.conn.execute(
            """
            INSERT INTO products(
                id, supplier_id, product_code, product_name, product_stage,
                is_active, created_at, updated_at
            ) VALUES ('prod-1', 'sup-1', 'PN-001', '產品A', '量產', 1, '', '')
            """
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    @patch("ncr.ui.defect_form.crud.get_defect_by_id")
    def test_convert_payload_includes_work_orders_not_transfer_slip(self, get_defect) -> None:
        from ncr.ui.defect_form import DefectEditDialog

        captured: dict = {}

        class _MainWindow:
            def open_new_anomaly_create_page(self, initial_data=None):
                captured.update(dict(initial_data or {}))

        get_defect.return_value = {
            "supplier_id": "sup-1",
            "supplier_name": "供應商A",
            "item_no": "PN-001",
            "product_name": "產品A",
            "defect_desc": "不良",
            "event_date": "2026-05-12",
            "defect_no": "NCR-001",
            "work_order_no": "OWO-100",
            "internal_work_order_no": "IWO-200",
            "transfer_slip_no": "TS-999",
            "processing_line": "委外加工",
            "qty": 12,
        }
        dialog = DefectEditDialog.__new__(DefectEditDialog)
        dialog.conn = self.conn
        dialog.defect_id = 1
        dialog.window = lambda: _MainWindow()
        dialog.accept = lambda: None
        DefectEditDialog.convert_to_supplier_anomaly(dialog)
        self.assertEqual("OWO-100", captured["outsource_work_order"])
        self.assertEqual("IWO-200", captured["internal_work_order_no"])
        self.assertEqual("NCR-001", captured["source_defect_no"])
        self.assertEqual("委外加工", captured["anomaly_source_hint"])
        self.assertNotIn("transfer_slip_no", captured)
        self.assertNotIn("outsource_receipt_no", captured)

    @patch("ncr.ui.defect_form.crud.get_defect_by_id")
    def test_convert_payload_maps_shared_category(self, get_defect) -> None:
        from ncr.ui.defect_form import DefectEditDialog
        from ui.widgets.new_anomaly_dialog import ANOMALY_CATEGORY_OPTIONS

        captured: dict = {}

        class _MainWindow:
            def open_new_anomaly_create_page(self, initial_data=None):
                captured.update(dict(initial_data or {}))

        category = "其他"
        self.assertIn(category, ANOMALY_CATEGORY_OPTIONS)
        get_defect.return_value = {
            "supplier_id": "sup-1",
            "supplier_name": "供應商A",
            "item_no": "PN-001",
            "product_name": "產品A",
            "defect_desc": "不良",
            "event_date": "2026-05-12",
            "defect_no": "NCR-002",
            "category": category,
            "processing_line": "原物料",
            "qty": 1,
        }
        dialog = DefectEditDialog.__new__(DefectEditDialog)
        dialog.conn = self.conn
        dialog.defect_id = 2
        dialog.window = lambda: _MainWindow()
        dialog.accept = lambda: None
        DefectEditDialog.convert_to_supplier_anomaly(dialog)
        self.assertEqual(category, captured.get("category"))


class AppearancePreferencesV9Tests(unittest.TestCase):
    def test_v9_mapping_round_trip(self) -> None:
        prefs = AppearancePreferences.default()
        prefs = AppearancePreferences(
            **{
                **prefs.to_mapping(),
                "erp_material_receipt_no_pattern": "^MR-\\d+$",
                "erp_internal_work_order_no_pattern": "^IWO-\\d+$",
                "erp_outsource_work_order_pattern": "^OWO-\\d+$",
                "erp_outsource_receipt_no_pattern": "^OR-\\d+$",
            }
        )
        restored = AppearancePreferences.from_mapping(prefs.to_mapping())
        self.assertEqual("^MR-\\d+$", restored.erp_material_receipt_no_pattern)


if __name__ == "__main__":
    unittest.main()
