"""Regression tests for the legacy-DB migration rewrite in ``repository``.

These cover the failure modes that the status/spec_desc migration rewrite
re-introduced and that ``test_product_spec_removal`` does not exercise:

* The ``product_records`` view's INSTEAD OF triggers must survive the
  ``spec_desc`` removal even when the view already exists in the legacy DB
  (a real prior-version database has it). Dropping the view silently drops the
  triggers, breaking the NCR product write path that goes through the view.
* The rebuilt ``products`` table must match the canonical schema
  (``product_stage`` DEFAULT '量產', no table-level ``UNIQUE``, no
  ``ON DELETE RESTRICT``), not a divergent one.
* The status normalization must preserve every non-status column — including
  the closure-tracking fields and the per-item tech-transfer ``*_state``
  columns — and keep ``visit_defect_notes`` rows that reference an anomaly via
  a foreign key intact across the table rebuild.
"""

from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from uuid import uuid4

from database import repository


_LEGACY_PRODUCT_RECORDS_VIEW = """
CREATE VIEW product_records AS
SELECT id, product_code AS item_no, product_name, created_at
FROM products;

CREATE TRIGGER trg_product_records_insert
INSTEAD OF INSERT ON product_records
BEGIN
    INSERT INTO products (id, product_code, product_name, created_at, updated_at, is_active)
    VALUES (
        COALESCE(NEW.id, hex(randomblob(16))),
        NEW.item_no,
        NEW.product_name,
        COALESCE(NEW.created_at, datetime('now', 'localtime')),
        datetime('now', 'localtime'),
        1
    )
    ON CONFLICT(product_code) DO UPDATE SET
        product_name = NEW.product_name,
        updated_at = datetime('now', 'localtime');
END;

CREATE TRIGGER trg_product_records_update
INSTEAD OF UPDATE ON product_records
BEGIN
    UPDATE products
    SET product_code = NEW.item_no,
        product_name = NEW.product_name,
        updated_at = datetime('now', 'localtime')
    WHERE id = OLD.id;
END;

CREATE TRIGGER trg_product_records_delete
INSTEAD OF DELETE ON product_records
BEGIN
    DELETE FROM products WHERE id = OLD.id;
END;
"""


class MigrationViewTriggerRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        base_tmp_dir = Path("scratch")
        base_tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = base_tmp_dir / f"sqe_migration_regression_{uuid4().hex}.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")

    def tearDown(self) -> None:
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def _schema_objects(self) -> dict[str, str]:
        rows = self.conn.execute(
            "SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
        ).fetchall()
        return {f"{r['type']}:{r['name']}" for r in rows}

    def _create_legacy_db(self) -> dict[str, str]:
        """Build a legacy DB that mirrors a real prior-version schema.

        It has the ``product_records`` view + INSTEAD OF triggers, a
        ``spec_desc`` column, legacy OPEN/CLOSED/COMPLETED statuses, populated
        closure-tracking + ``*_state`` columns, and a ``visit_defect_notes`` row
        whose foreign key references an anomaly.
        """
        ids = {
            "supplier": uuid4().hex,
            "product": uuid4().hex,
            "visit": uuid4().hex,
            "anomaly_open": uuid4().hex,
            "anomaly_closed": uuid4().hex,
            "note": uuid4().hex,
        }
        self.conn.executescript(
            """
            CREATE TABLE suppliers (
                id TEXT PRIMARY KEY,
                supplier_name TEXT NOT NULL UNIQUE,
                contact_name TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE products (
                id TEXT PRIMARY KEY,
                product_code TEXT NOT NULL,
                product_name TEXT NOT NULL,
                spec_desc TEXT NOT NULL DEFAULT '',
                product_stage TEXT NOT NULL DEFAULT '量產',
                supplier_id TEXT,
                secondary_supplier_id TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
            );

            CREATE TABLE visits (
                id TEXT PRIMARY KEY,
                visit_date TEXT NOT NULL,
                supplier_id TEXT NOT NULL,
                product_id TEXT,
                product_name TEXT NOT NULL DEFAULT '',
                product_stage TEXT NOT NULL DEFAULT '量產',
                visitor_name TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                work_order_no TEXT NOT NULL DEFAULT '',
                production_qty INTEGER NOT NULL DEFAULT 0,
                tech_transfer INTEGER NOT NULL DEFAULT 0,
                tech_transfer_doc INTEGER NOT NULL DEFAULT 0,
                carrier_requirement INTEGER NOT NULL DEFAULT 0,
                dispensing_process INTEGER NOT NULL DEFAULT 0,
                functional_test INTEGER NOT NULL DEFAULT 0,
                packaging_requirement INTEGER NOT NULL DEFAULT 0,
                tech_transfer_doc_state TEXT NOT NULL DEFAULT 'no',
                carrier_requirement_state TEXT NOT NULL DEFAULT 'no',
                dispensing_process_state TEXT NOT NULL DEFAULT 'no',
                functional_test_state TEXT NOT NULL DEFAULT 'no',
                packaging_requirement_state TEXT NOT NULL DEFAULT 'no',
                status TEXT NOT NULL DEFAULT 'COMPLETED' CHECK (status='COMPLETED'),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
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
                product_stage TEXT NOT NULL DEFAULT '試產',
                outsource_work_order TEXT NOT NULL DEFAULT '',
                batch_qty INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CLOSED')),
                improvement_desc TEXT NOT NULL DEFAULT '',
                closed_by TEXT NOT NULL DEFAULT '',
                closed_at TEXT,
                pending_items TEXT NOT NULL DEFAULT '',
                responsible_person TEXT NOT NULL DEFAULT '',
                due_date TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
                FOREIGN KEY (visit_id) REFERENCES visits(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );

            CREATE TABLE visit_defect_notes (
                id TEXT PRIMARY KEY,
                visit_id TEXT NOT NULL,
                visit_product_section_id TEXT,
                defect_desc TEXT NOT NULL,
                improvement_desc TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '',
                confirmed_anomaly_id TEXT,
                confirmed_at TEXT,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (visit_id) REFERENCES visits(id),
                FOREIGN KEY (confirmed_anomaly_id) REFERENCES anomalies(id)
            );
            """
            + _LEGACY_PRODUCT_RECORDS_VIEW
        )

        self.conn.execute(
            "INSERT INTO suppliers(id, supplier_name) VALUES (?, 'Legacy Supplier')",
            (ids["supplier"],),
        )
        self.conn.execute(
            """
            INSERT INTO products(id, product_code, product_name, spec_desc, product_stage, supplier_id)
            VALUES (?, 'LEG-001', 'Legacy Product', 'old spec', '試產', ?)
            """,
            (ids["product"], ids["supplier"]),
        )
        self.conn.execute(
            """
            INSERT INTO visits(
                id, visit_date, supplier_id, product_id, product_name, product_stage,
                visitor_name, summary, status, packaging_requirement,
                packaging_requirement_state
            )
            VALUES (?, '2026-04-16', ?, ?, 'Legacy Product', '試產', '訪客甲',
                    'legacy visit', 'COMPLETED', 1, 'yes')
            """,
            (ids["visit"], ids["supplier"], ids["product"]),
        )
        self.conn.execute(
            """
            INSERT INTO anomalies(
                id, anomaly_no, anomaly_date, supplier_id, visit_id, product_id,
                problem_desc, product_stage, status, improvement_desc, closed_by,
                closed_at, pending_items, responsible_person, due_date
            )
            VALUES (?, 'ANM-OPEN', '2026-04-16', ?, ?, ?, 'open problem', '試產', 'OPEN',
                    '', '', NULL, '追蹤項目A', '負責人甲', '2026-05-01')
            """,
            (ids["anomaly_open"], ids["supplier"], ids["visit"], ids["product"]),
        )
        self.conn.execute(
            """
            INSERT INTO anomalies(
                id, anomaly_no, anomaly_date, supplier_id, visit_id, product_id,
                problem_desc, product_stage, status, improvement_desc, closed_by,
                closed_at, pending_items, responsible_person, due_date
            )
            VALUES (?, 'ANM-CLOSED', '2026-04-16', ?, ?, ?, 'closed problem', '試產', 'CLOSED',
                    '已修正', '結案人乙', '2026-04-18', '', '負責人乙', '2026-04-20')
            """,
            (ids["anomaly_closed"], ids["supplier"], ids["visit"], ids["product"]),
        )
        self.conn.execute(
            """
            INSERT INTO visit_defect_notes(id, visit_id, defect_desc, confirmed_anomaly_id)
            VALUES (?, ?, '缺失內容', ?)
            """,
            (ids["note"], ids["visit"], ids["anomaly_closed"]),
        )
        self.conn.commit()
        return ids

    def test_product_records_triggers_survive_spec_desc_migration(self) -> None:
        ids = self._create_legacy_db()

        repository.create_schema(self.conn)

        objects = self._schema_objects()
        self.assertIn("view:product_records", objects)
        self.assertIn("trigger:trg_product_records_insert", objects)
        self.assertIn("trigger:trg_product_records_update", objects)
        self.assertIn("trigger:trg_product_records_delete", objects)

        # spec_desc gone, original product preserved.
        product_columns = {
            str(r["name"])
            for r in self.conn.execute("PRAGMA table_info(products)").fetchall()
        }
        self.assertNotIn("spec_desc", product_columns)
        original = self.conn.execute(
            "SELECT product_code, product_stage FROM products WHERE id = ?",
            (ids["product"],),
        ).fetchone()
        self.assertIsNotNone(original)
        self.assertEqual(str(original["product_code"]), "LEG-001")
        # product_stage value is preserved as-is (試產 not coerced to 量產).
        self.assertEqual(str(original["product_stage"]), "試產")

        # The INSTEAD OF triggers must still FIRE (not just exist): writes
        # through the view must reach the products table. create_schema replaces
        # the legacy view (DROP VIEW cascades its triggers away), so the broken
        # legacy insert trigger (ON CONFLICT(product_code) against a
        # non-existent full unique index) is swapped for the corrected one.
        # INSERT through the view must now succeed (it previously raised
        # OperationalError: ON CONFLICT clause does not match...).
        self.conn.execute(
            "INSERT INTO product_records (item_no, product_name, created_at) "
            "VALUES ('NEW-VIEW-1', 'Inserted Through View', '2026-06-25')"
        )
        inserted = self.conn.execute(
            "SELECT supplier_id FROM products WHERE product_code = 'NEW-VIEW-1'"
        ).fetchone()
        self.assertIsNotNone(
            inserted, "INSTEAD OF insert trigger did not fire / still broken"
        )
        self.assertIsNone(inserted["supplier_id"])

        # UPDATE through the view on the existing (FK-referenced) product.
        self.conn.execute(
            "UPDATE product_records SET product_name = 'Renamed Through View' "
            "WHERE id = ?",
            (ids["product"],),
        )
        renamed = self.conn.execute(
            "SELECT product_name FROM products WHERE id = ?",
            (ids["product"],),
        ).fetchone()
        self.assertEqual(
            str(renamed["product_name"]),
            "Renamed Through View",
            "INSTEAD OF update trigger did not fire — view triggers were lost",
        )

        # DELETE through the view on an unreferenced product.
        free_id = uuid4().hex
        self.conn.execute(
            "INSERT INTO products(id, product_code, product_name, is_active, "
            "created_at, updated_at) VALUES (?, 'FREE-1', 'Free', 1, "
            "'2026-06-25', '2026-06-25')",
            (free_id,),
        )
        self.conn.execute(
            "DELETE FROM product_records WHERE id = ?", (free_id,)
        )
        gone = self.conn.execute(
            "SELECT 1 FROM products WHERE id = ?", (free_id,)
        ).fetchone()
        self.assertIsNone(
            gone, "INSTEAD OF delete trigger did not fire — view triggers were lost"
        )

    def test_products_table_matches_canonical_schema(self) -> None:
        self._create_legacy_db()
        repository.create_schema(self.conn)

        products_sql = str(
            self.conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='products'"
            ).fetchone()["sql"]
        )
        # Canonical default is 量產, not the divergent 試產.
        self.assertIn("product_stage TEXT NOT NULL DEFAULT '量產'", products_sql)
        self.assertNotIn("'試產'", products_sql)
        # Uniqueness is enforced by partial indexes, not a table-level UNIQUE.
        self.assertNotIn("UNIQUE(", products_sql.replace(" ", ""))
        # Canonical FKs have no ON DELETE RESTRICT.
        self.assertNotIn("ON DELETE RESTRICT", products_sql)

        index_names = {
            str(r["name"])
            for r in self.conn.execute("PRAGMA index_list(products)").fetchall()
        }
        for expected in (
            "idx_products_global_code",
            "idx_products_supplier_code",
            "idx_products_supplier",
            "idx_products_secondary_supplier",
            "idx_products_active",
        ):
            self.assertIn(expected, index_names)

    def test_status_rebuild_preserves_all_non_status_columns(self) -> None:
        ids = self._create_legacy_db()
        repository.create_schema(self.conn)

        anomaly_columns = {
            str(r["name"])
            for r in self.conn.execute("PRAGMA table_info(anomalies)").fetchall()
        }
        self.assertNotIn("closed_by", anomaly_columns)

        # Status mapped; active closure-tracking fields preserved verbatim.
        closed = self.conn.execute(
            """
            SELECT status, improvement_desc,
                   closed_at, responsible_person, due_date, product_stage
            FROM anomalies WHERE anomaly_no = 'ANM-CLOSED'
            """
        ).fetchone()
        self.assertEqual(str(closed["status"]), "已結案")
        self.assertEqual(str(closed["improvement_desc"]), "已修正")
        self.assertEqual(str(closed["closed_at"]), "2026-04-18")
        self.assertEqual(str(closed["responsible_person"]), "負責人乙")
        self.assertEqual(str(closed["due_date"]), "2026-04-20")
        # product_stage is preserved as-is (試產), not coerced.
        self.assertEqual(str(closed["product_stage"]), "試產")

        opened = self.conn.execute(
            "SELECT status, pending_items, responsible_person, closed_at "
            "FROM anomalies WHERE anomaly_no = 'ANM-OPEN'"
        ).fetchone()
        self.assertEqual(str(opened["status"]), "待處理")
        self.assertEqual(str(opened["pending_items"]), "追蹤項目A")
        self.assertEqual(str(opened["responsible_person"]), "負責人甲")
        # closed_at is cleared for non-closed rows.
        self.assertIsNone(opened["closed_at"])

        # Visit *_state columns and visitor_name preserved; status normalized.
        visit = self.conn.execute(
            "SELECT status, visitor_name, packaging_requirement, "
            "packaging_requirement_state FROM visits"
        ).fetchone()
        self.assertEqual(str(visit["status"]), "已完成")
        self.assertEqual(str(visit["visitor_name"]), "訪客甲")
        self.assertEqual(int(visit["packaging_requirement"]), 1)
        self.assertEqual(str(visit["packaging_requirement_state"]), "yes")

        # The FK from visit_defect_notes to the (rebuilt) anomaly survives.
        note = self.conn.execute(
            "SELECT confirmed_anomaly_id FROM visit_defect_notes"
        ).fetchone()
        self.assertEqual(str(note["confirmed_anomaly_id"]), ids["anomaly_closed"])
        # FK integrity holds after the rebuild.
        fk_violations = self.conn.execute("PRAGMA foreign_key_check").fetchall()
        self.assertEqual(fk_violations, [])

    def test_migration_is_idempotent_across_reopen(self) -> None:
        self._create_legacy_db()
        repository.create_schema(self.conn)
        objects_first = self._schema_objects()

        # A second create_schema (next app start) must be a no-op for the
        # one-time migrations and must not error or drop triggers.
        repository.create_schema(self.conn)
        objects_second = self._schema_objects()

        self.assertIn("view:product_records", objects_second)
        self.assertIn("trigger:trg_product_records_insert", objects_second)
        self.assertEqual(objects_first, objects_second)
        # No leftover temp tables from the rebuilds.
        for leftover in (
            "anomalies__new",
            "visits__new",
            "products__new",
            "anomalies_old",
            "anomalies_new",
            "visits_old",
            "visits_new",
            "products_new",
        ):
            self.assertNotIn(f"table:{leftover}", objects_second)


if __name__ == "__main__":
    unittest.main()
