from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

from database import repository


class ArchitectureWorkflowContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_contract_doc_names_separate_data_lines_and_import_audit(self) -> None:
        doc = Path("docs/architecture-workflow-contract.md").read_text(
            encoding="utf-8"
        )
        required_terms = [
            "Supplier event management",
            "Warehouse physical nonconforming-product management",
            "`visit_defect_notes`",
            "`defect_records`",
            "`import_batches`",
            "must never be inserted into `defect_records`",
        ]
        for term in required_terms:
            with self.subTest(term=term):
                self.assertIn(term, doc)

    def test_schema_keeps_event_warehouse_master_and_import_tables_distinct(self) -> None:
        tables = {
            row["name"]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            ).fetchall()
        }
        event_tables = {
            "visits",
            "visit_product_sections",
            "visit_defect_notes",
            "anomalies",
        }
        warehouse_tables = {"defect_records"}
        master_tables = {"suppliers", "products"}
        audit_tables = {"import_batches", "import_batch_rows"}

        self.assertTrue(event_tables.issubset(tables))
        self.assertTrue(warehouse_tables.issubset(tables))
        self.assertTrue(master_tables.issubset(tables))
        self.assertTrue(audit_tables.issubset(tables))
        self.assertTrue(event_tables.isdisjoint(warehouse_tables))
        self.assertTrue(master_tables.isdisjoint(warehouse_tables))
        self.assertTrue(audit_tables.isdisjoint(event_tables | warehouse_tables))

    def test_import_batches_have_no_workflow_foreign_keys(self) -> None:
        foreign_keys = self.conn.execute(
            "PRAGMA foreign_key_list(import_batch_rows)"
        ).fetchall()
        referenced_tables = {row["table"] for row in foreign_keys}
        self.assertEqual({"import_batches"}, referenced_tables)


if __name__ == "__main__":
    unittest.main()
