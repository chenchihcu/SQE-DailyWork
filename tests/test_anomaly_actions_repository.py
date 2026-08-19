from __future__ import annotations

import sqlite3
import unittest

from database import repository


class AnomalyActionsRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.supplier = repository.create_supplier_record(
            self.conn, supplier_name="Supplier AA"
        )
        self.product = repository.create_product_record(
            self.conn,
            product_code="AA-001",
            product_name="Product AA",
            supplier_id=self.supplier,
        )
        self.anomaly_id = repository.create_anomaly_with_visit_link(
            self.conn,
            anomaly_date="2026-06-01",
            supplier_id=self.supplier,
            product_id=self.product,
            problem_desc="unit test problem",
            sync_visit=False,
        )["anomaly_id"]

    def tearDown(self) -> None:
        self.conn.close()

    # --- create / list -------------------------------------------------

    def test_create_action_requires_description_and_anomaly(self) -> None:
        with self.assertRaisesRegex(ValueError, "Action description is required"):
            repository.create_anomaly_action(
                self.conn,
                anomaly_id=self.anomaly_id,
                description="   ",
            )
        with self.assertRaisesRegex(ValueError, "Anomaly not found"):
            repository.create_anomaly_action(
                self.conn,
                anomaly_id="nope",
                description="desc",
            )

    def test_create_action_normalizes_due_date_to_iso(self) -> None:
        action_id = repository.create_anomaly_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            description="聯絡供應商",
            owner="Alice",
            due_date="2026/07/01",
        )
        row = repository.get_anomaly_action(self.conn, action_id)
        assert row is not None
        self.assertEqual(row["due_date"], "2026-07-01")
        self.assertEqual(row["status"], "進行中")
        self.assertEqual(row["owner"], "Alice")

    def test_create_action_rejects_invalid_status(self) -> None:
        with self.assertRaisesRegex(ValueError, "Action status must be"):
            repository.create_anomaly_action(
                self.conn,
                anomaly_id=self.anomaly_id,
                description="desc",
                status="UNKNOWN",
            )

    def test_create_action_rejects_invalid_due_date(self) -> None:
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            repository.create_anomaly_action(
                self.conn,
                anomaly_id=self.anomaly_id,
                description="desc",
                due_date="bad-date",
            )

    def test_list_orders_open_first_then_by_due_date(self) -> None:
        repository.create_anomaly_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            description="late",
            due_date="2026-07-15",
        )
        repository.create_anomaly_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            description="early",
            due_date="2026-07-01",
        )
        no_date_id = repository.create_anomaly_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            description="nodate",
        )
        rows = repository.list_anomaly_actions(self.conn, self.anomaly_id)
        self.assertEqual(
            [r["description"] for r in rows],
            ["early", "late", "nodate"],
        )
        # Also validates that the no-date row keeps no due_date
        self.assertEqual(rows[-1]["id"], no_date_id)
        self.assertEqual(rows[-1]["due_date"], "")

    # --- update / complete / cancel ------------------------------------

    def test_update_only_open_actions(self) -> None:
        action_id = repository.create_anomaly_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            description="desc",
        )
        repository.complete_anomaly_action(
            self.conn, action_id, completion_note="OK"
        )
        with self.assertRaisesRegex(ValueError, "Only 進行中"):
            repository.update_anomaly_action(
                self.conn, action_id, description="new"
            )

    def test_complete_sets_status_and_timestamp(self) -> None:
        action_id = repository.create_anomaly_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            description="send FA",
            due_date="2026-07-01",
        )
        repository.complete_anomaly_action(
            self.conn,
            action_id,
            completion_note="FA submitted",
            completed_at="2026-07-02",
        )
        row = repository.get_anomaly_action(self.conn, action_id)
        assert row is not None
        self.assertEqual(row["status"], "已完成")
        self.assertEqual(row["completed_at"], "2026-07-02")
        self.assertEqual(row["completed_note"], "FA submitted")

    def test_cancel_sets_status_and_timestamp(self) -> None:
        action_id = repository.create_anomaly_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            description="reschedule",
            due_date="2026-07-01",
        )
        repository.cancel_anomaly_action(
            self.conn,
            action_id,
            cancel_note="supplier delayed",
            cancelled_at="2026-07-01",
        )
        row = repository.get_anomaly_action(self.conn, action_id)
        assert row is not None
        self.assertEqual(row["status"], "已取消")
        self.assertEqual(row["cancelled_at"], "2026-07-01")
        self.assertEqual(row["cancelled_note"], "supplier delayed")

    def test_complete_rejects_future_date(self) -> None:
        action_id = repository.create_anomaly_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            description="desc",
        )
        with self.assertRaisesRegex(ValueError, "cannot be in the future"):
            repository.complete_anomaly_action(
                self.conn,
                action_id,
                completed_at="2999-01-01",
            )

    # --- overdue / current action --------------------------------------

    def test_overdue_for_open_anomaly_with_past_due(self) -> None:
        repository.create_anomaly_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            description="late",
            due_date="2026-01-01",
        )
        self.assertTrue(
            repository.is_anomaly_overdue(
                self.conn, self.anomaly_id, today="2026-08-01"
            )
        )

    def test_overdue_false_when_due_date_in_future(self) -> None:
        repository.create_anomaly_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            description="future",
            due_date="2999-01-01",
        )
        self.assertFalse(
            repository.is_anomaly_overdue(
                self.conn, self.anomaly_id, today="2026-08-01"
            )
        )

    def test_overdue_false_when_no_due_date(self) -> None:
        repository.create_anomaly_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            description="nodate",
        )
        self.assertFalse(
            repository.is_anomaly_overdue(
                self.conn, self.anomaly_id, today="2026-08-01"
            )
        )

    def test_overdue_false_when_anomaly_closed(self) -> None:
        repository.create_anomaly_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            description="late",
            due_date="2026-05-01",
        )
        repository.close_anomaly(
            self.conn,
            self.anomaly_id,
            "改善完成",
            closed_at="2026-06-15",
        )
        self.assertFalse(
            repository.is_anomaly_overdue(
                self.conn, self.anomaly_id, today="2026-08-01"
            )
        )

    def test_overdue_ignores_cancelled_actions(self) -> None:
        action_id = repository.create_anomaly_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            description="late",
            due_date="2026-01-01",
        )
        repository.cancel_anomaly_action(self.conn, action_id, cancel_note="x")
        self.assertFalse(
            repository.is_anomaly_overdue(
                self.conn, self.anomaly_id, today="2026-08-01"
            )
        )

    def test_current_action_picks_earliest_due(self) -> None:
        repository.create_anomaly_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            description="late",
            due_date="2026-12-01",
        )
        early_id = repository.create_anomaly_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            description="early",
            due_date="2026-07-01",
        )
        current = repository.get_current_anomaly_action(
            self.conn, self.anomaly_id
        )
        assert current is not None
        self.assertEqual(current["id"], early_id)

    def test_current_action_picks_open_over_completed(self) -> None:
        completed_id = repository.create_anomaly_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            description="done",
        )
        repository.complete_anomaly_action(self.conn, completed_id)
        open_id = repository.create_anomaly_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            description="open",
        )
        current = repository.get_current_anomaly_action(
            self.conn, self.anomaly_id
        )
        assert current is not None
        self.assertEqual(current["id"], open_id)


class AnomalyActionsMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")

    def tearDown(self) -> None:
        self.conn.close()

    def _create_supplier_and_product(self) -> tuple[str, str]:
        supplier = repository.create_supplier_record(
            self.conn, supplier_name="M-1"
        )
        product = repository.create_product_record(
            self.conn,
            product_code="M-001",
            product_name="Product M",
            supplier_id=supplier,
        )
        return supplier, product

    def test_schema_creates_anomaly_actions_table(self) -> None:
        repository.create_schema(self.conn)
        cur = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='anomaly_actions'"
        )
        self.assertIsNotNone(cur.fetchone())

    def test_backfill_writes_one_action_for_open_anomaly(self) -> None:
        # First create the schema without an anomaly
        repository.create_schema(self.conn)
        supplier, product = self._create_supplier_and_product()
        # Insert an anomaly directly via SQL with rich pending data
        self.conn.execute(
            """
            INSERT INTO anomalies(
                id, anomaly_no, anomaly_date, supplier_id, product_id,
                product_lot_no, product_name, product_stage, status,
                problem_desc, pending_items, responsible_person, due_date
            ) VALUES (
                ?, '20260601001', '2026-06-01', ?, ?, '', '', '量產', '待處理',
                'real problem', '追蹤量產良率', 'Alice', '2026-07-01'
            )
            """,
            ("anc-1", supplier, product),
        )
        self.conn.commit()
        # Reset meta so the helper treats this as an upgrade scenario.
        self.conn.execute(
            "DELETE FROM migration_meta WHERE key IN (?, ?)",
            (
                repository.ANOMALY_ACTIONS_MIGRATION_META_KEY,
                repository.ANOMALY_ACTIONS_BACKFILL_META_KEY,
            ),
        )
        self.conn.commit()
        # Manually re-run the migration helper to simulate upgrading an old DB.
        repository._ensure_anomaly_actions_v1(self.conn)
        rows = self.conn.execute(
            "SELECT description, owner, due_date, status FROM anomaly_actions"
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["description"], "追蹤量產良率")
        self.assertEqual(rows[0]["owner"], "Alice")
        self.assertEqual(rows[0]["due_date"], "2026-07-01")
        self.assertEqual(rows[0]["status"], "進行中")

    def test_backfill_idempotent(self) -> None:
        repository.create_schema(self.conn)
        supplier, product = self._create_supplier_and_product()
        self.conn.execute(
            """
            INSERT INTO anomalies(
                id, anomaly_no, anomaly_date, supplier_id, product_id,
                problem_desc, pending_items, responsible_person, due_date
            ) VALUES (
                'anc-2', '20260601002', '2026-06-02', ?, ?,
                'p', '待確認', 'Bob', '2026-07-15'
            )
            """,
            (supplier, product),
        )
        self.conn.commit()
        self.conn.execute(
            "DELETE FROM migration_meta WHERE key IN (?, ?)",
            (
                repository.ANOMALY_ACTIONS_MIGRATION_META_KEY,
                repository.ANOMALY_ACTIONS_BACKFILL_META_KEY,
            ),
        )
        self.conn.commit()
        repository._ensure_anomaly_actions_v1(self.conn)
        repository._ensure_anomaly_actions_v1(self.conn)
        count = self.conn.execute(
            "SELECT COUNT(*) FROM anomaly_actions"
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_backfill_skips_anomalies_without_actionable_data(self) -> None:
        repository.create_schema(self.conn)
        supplier, product = self._create_supplier_and_product()
        self.conn.execute(
            """
            INSERT INTO anomalies(
                id, anomaly_no, anomaly_date, supplier_id, product_id,
                problem_desc, pending_items, responsible_person, due_date
            ) VALUES (
                'anc-3', '20260601003', '2026-06-03', ?, ?, 'p', '', '', ''
            )
            """,
            (supplier, product),
        )
        self.conn.commit()
        self.conn.execute(
            "DELETE FROM migration_meta WHERE key IN (?, ?)",
            (
                repository.ANOMALY_ACTIONS_MIGRATION_META_KEY,
                repository.ANOMALY_ACTIONS_BACKFILL_META_KEY,
            ),
        )
        self.conn.commit()
        repository._ensure_anomaly_actions_v1(self.conn)
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM anomaly_actions"
            ).fetchone()[0],
            0,
        )

    def test_backfill_skips_closed_anomalies(self) -> None:
        repository.create_schema(self.conn)
        supplier, product = self._create_supplier_and_product()
        self.conn.execute(
            """
            INSERT INTO anomalies(
                id, anomaly_no, anomaly_date, supplier_id, product_id,
                status, problem_desc, pending_items, responsible_person, due_date
            ) VALUES (
                'anc-4', '20260601004', '2026-06-04', ?, ?, '已結案',
                'p', 'history', 'Carol', '2026-07-01'
            )
            """,
            (supplier, product),
        )
        self.conn.commit()
        self.conn.execute(
            "DELETE FROM migration_meta WHERE key IN (?, ?)",
            (
                repository.ANOMALY_ACTIONS_MIGRATION_META_KEY,
                repository.ANOMALY_ACTIONS_BACKFILL_META_KEY,
            ),
        )
        self.conn.commit()
        repository._ensure_anomaly_actions_v1(self.conn)
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM anomaly_actions"
            ).fetchone()[0],
            0,
        )


if __name__ == "__main__":
    unittest.main()
