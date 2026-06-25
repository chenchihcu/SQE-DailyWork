"""Regression tests for writes through the ``product_records`` VIEW on a
canonical ``repository.create_schema`` database.

The unified ``sqe_v2.db`` (built by ``repository.create_schema``) exposes
``product_records`` as a VIEW over ``products`` with INSTEAD OF triggers. The
embedded NCR module obtains its connection from this same unified DB
(``ncr.db.database.initialize_database`` -> ``repository.create_schema``), so
every NCR product write goes through this view at runtime.

These tests pin three defects that were latent on the view path:

1. The INSTEAD OF INSERT trigger used ``ON CONFLICT(product_code) DO UPDATE``,
   but ``products.product_code`` has only PARTIAL unique indexes
   (``WHERE supplier_id IS NULL`` / ``IS NOT NULL``) — there is no full unique
   index on ``product_code`` alone. So ANY insert through the view raised
   ``OperationalError: ON CONFLICT clause does not match any PRIMARY KEY or
   UNIQUE constraint``. The trigger now uses a plain inner INSERT and inherits
   the caller's conflict resolution (``INSERT`` -> raise, ``INSERT OR IGNORE``
   -> skip) against ``idx_products_global_code``.
2. ``crud.update_product`` / ``crud.delete_product`` gated "not found" on
   ``cursor.rowcount``, which is always 0 through a view (``changes()`` excludes
   trigger actions) — so update spuriously raised and delete raised *and rolled
   back the real delete*. They now use an explicit existence check.
3. ``crud.insert_products_if_missing`` summed ``cursor.rowcount`` (0 through the
   view), so ``sync_product_from_defect``'s ``if inserted_count: commit`` never
   fired and ``bulk_sync_products_from_all_defects`` always reported 0. It now
   counts via the ``conn.total_changes`` delta.
"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from database.repository import create_schema
from ncr.db import crud
from ncr.services import defect_service, product_service


class ProductRecordsViewWritePathTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "sqe_v2.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        create_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self._tmpdir.cleanup()

    def _second_connection(self) -> sqlite3.Connection:
        """A separate connection — used to prove writes were actually committed."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # --- the object really is a view (otherwise these tests prove nothing) ---
    def test_product_records_is_a_view(self) -> None:
        row = self.conn.execute(
            "SELECT type FROM sqlite_master WHERE name = 'product_records'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(str(row["type"]), "view")

    # --- 1. plain INSERT through the view no longer raises OperationalError ---
    def test_plain_insert_through_view_reaches_products(self) -> None:
        self.conn.execute(
            "INSERT INTO product_records (item_no, product_name, created_at) "
            "VALUES (?, ?, ?)",
            ("P-001", "Widget", "2026-06-25T00:00:00"),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT product_name, supplier_id FROM products WHERE product_code = ?",
            ("P-001",),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(str(row["product_name"]), "Widget")
        # The view maps to the GLOBAL (shared) product master: supplier_id IS NULL,
        # so the conflict can only ever hit idx_products_global_code.
        self.assertIsNone(row["supplier_id"])

    def test_duplicate_plain_insert_raises_unique_constraint(self) -> None:
        self.conn.execute(
            "INSERT INTO product_records (item_no, product_name, created_at) "
            "VALUES (?, ?, ?)",
            ("P-001", "Widget", "2026-06-25T00:00:00"),
        )
        self.conn.commit()
        with self.assertRaises(sqlite3.IntegrityError) as ctx:
            self.conn.execute(
                "INSERT INTO product_records (item_no, product_name, created_at) "
                "VALUES (?, ?, ?)",
                ("P-001", "Widget v2", "2026-06-25T00:00:00"),
            )
        # create_product relies on this substring to surface "料號已存在".
        self.assertIn("UNIQUE constraint failed", str(ctx.exception))
        self.conn.rollback()

    def test_insert_or_ignore_skips_duplicate_without_overwriting(self) -> None:
        self.conn.execute(
            "INSERT INTO product_records (item_no, product_name, created_at) "
            "VALUES (?, ?, ?)",
            ("P-001", "Original", "2026-06-25T00:00:00"),
        )
        self.conn.commit()
        # Must NOT raise and must NOT overwrite the existing name.
        self.conn.execute(
            "INSERT OR IGNORE INTO product_records (item_no, product_name, created_at) "
            "VALUES (?, ?, ?)",
            ("P-001", "Should Be Ignored", "2026-06-25T00:00:00"),
        )
        self.conn.commit()
        names = [
            str(r["product_name"])
            for r in self.conn.execute(
                "SELECT product_name FROM products WHERE product_code = ?", ("P-001",)
            ).fetchall()
        ]
        self.assertEqual(names, ["Original"])

    # --- 2. UPDATE / DELETE crud round-trip (rowcount-through-view trap) ---
    def test_update_product_round_trip(self) -> None:
        product_service.create_product(
            self.conn, {"item_no": "P-010", "product_name": "Before"}
        )
        self.conn.commit()
        pid = self.conn.execute(
            "SELECT id FROM products WHERE product_code = 'P-010'"
        ).fetchone()["id"]

        # Must NOT raise "找不到要更新的產品 ID" even though rowcount is 0 via the view.
        product_service.update_product(
            self.conn, pid, {"item_no": "P-010", "product_name": "After"}
        )
        self.assertEqual(
            str(
                self.conn.execute(
                    "SELECT product_name FROM products WHERE id = ?", (pid,)
                ).fetchone()["product_name"]
            ),
            "After",
        )

    def test_update_missing_product_raises(self) -> None:
        with self.assertRaises(sqlite3.DatabaseError):
            product_service.update_product(
                self.conn, "no-such-id", {"item_no": "X", "product_name": "Y"}
            )

    def test_delete_product_round_trip(self) -> None:
        product_service.create_product(
            self.conn, {"item_no": "P-020", "product_name": "Doomed"}
        )
        self.conn.commit()
        pid = self.conn.execute(
            "SELECT id FROM products WHERE product_code = 'P-020'"
        ).fetchone()["id"]

        # Old bug: rowcount==0 -> raise -> rollback undid the real delete.
        product_service.delete_product(self.conn, pid)
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM products WHERE id = ?", (pid,)
            ).fetchone()[0],
            0,
        )

    def test_delete_missing_product_raises(self) -> None:
        with self.assertRaises(sqlite3.DatabaseError):
            product_service.delete_product(self.conn, "no-such-id")

    # --- 3. insert_products_if_missing count + self-commit ---
    def test_insert_products_if_missing_counts_through_view(self) -> None:
        first = crud.insert_products_if_missing(
            self.conn,
            [{"item_no": "P-030", "product_name": "New", "created_at": "2026-06-25"}],
        )
        # New row -> count 1 (rowcount would have wrongly reported 0 via the view).
        self.assertEqual(first, 1)
        again = crud.insert_products_if_missing(
            self.conn,
            [{"item_no": "P-030", "product_name": "Dup", "created_at": "2026-06-25"}],
        )
        self.assertEqual(again, 0)

    def test_create_product_duplicate_surfaces_value_error(self) -> None:
        product_service.create_product(
            self.conn, {"item_no": "P-040", "product_name": "Alpha"}
        )
        self.conn.commit()
        with self.assertRaises(ValueError):
            product_service.create_product(
                self.conn, {"item_no": "P-040", "product_name": "Alpha dup"}
            )
        self.conn.rollback()

    def test_sync_product_from_defect_self_commits(self) -> None:
        # No sibling commit available here; the product must persist on its own.
        product_service.sync_product_from_defect(
            self.conn, {"item_no": "P-050", "product_name": "Synced"}
        )
        other = self._second_connection()
        try:
            seen = other.execute(
                "SELECT 1 FROM products WHERE product_code = 'P-050'"
            ).fetchone()
        finally:
            other.close()
        self.assertIsNotNone(seen, "synced product was not committed")

    def test_create_defect_without_supplier_persists_product(self) -> None:
        defect_no = defect_service.create_defect(
            self.conn,
            {
                "event_date": "2026-06-25",
                "work_order_no": "WO-1",
                "internal_work_order_no": "",
                "transfer_slip_no": "TS-1",
                "item_no": "P-060",
                "product_name": "Gamma",
                "qty": 3,
                "category": "成品",
                "supplier_name": "",
                "outsource_supplier_name": "",
                "defect_desc": "凹痕",
                "return_slip_type": "廠內退料",
            },
        )
        self.assertTrue(defect_no)
        other = self._second_connection()
        try:
            seen = other.execute(
                "SELECT 1 FROM products WHERE product_code = 'P-060'"
            ).fetchone()
        finally:
            other.close()
        self.assertIsNotNone(
            seen, "product synced from a no-supplier defect was not committed"
        )


if __name__ == "__main__":
    unittest.main()
