from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from database import connection as _connection
from database import repository
from database.repo_helpers import CASE_ACTIONS_MIGRATION_META_KEY
from services.event import _case_action_service


def _seed_anomaly(conn: sqlite3.Connection, suffix: str = "1") -> str:
    supplier_id = repository.create_supplier_record(
        conn,
        supplier_name=f"Canonical Action Supplier {suffix}",
    )
    product_id = repository.create_product_record(
        conn,
        product_code=f"CA-{suffix}",
        product_name=f"Canonical Action Product {suffix}",
        supplier_id=supplier_id,
    )
    return repository.create_anomaly_with_visit_link(
        conn,
        anomaly_date="2026-08-01",
        supplier_id=supplier_id,
        product_id=product_id,
        problem_desc="Canonical Action test",
        sync_visit=False,
    )["anomaly_id"]


def _fresh_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    repository.create_schema(conn)
    return conn


def _drop_canonical_schema_for_legacy_fixture(conn: sqlite3.Connection) -> None:
    trigger_rows = conn.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type = 'trigger' AND name LIKE 'guard_%_case_actions_v1'
        """
    ).fetchall()
    for row in trigger_rows:
        conn.execute(f'DROP TRIGGER "{row[0]}"')
    conn.execute(
        "DELETE FROM migration_meta WHERE key = ?",
        (CASE_ACTIONS_MIGRATION_META_KEY,),
    )
    conn.commit()
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("DROP TABLE case_action_legacy_map")
    conn.execute("DROP TABLE action_verifications")
    conn.execute("DROP TABLE case_actions")
    # Recreate the attachment table exactly as it existed before Phase 1.
    # Keeping the fresh-schema related_action_id FK while dropping its parent
    # would not represent a real legacy database and would block fixture setup.
    conn.execute("DROP TABLE anomaly_attachments")
    conn.execute(
        """
        CREATE TABLE anomaly_attachments (
            id TEXT PRIMARY KEY,
            anomaly_id TEXT NOT NULL,
            file_name TEXT NOT NULL DEFAULT '',
            stored_name TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '其他',
            description TEXT NOT NULL DEFAULT '',
            file_size INTEGER NOT NULL DEFAULT 0,
            revision TEXT NOT NULL DEFAULT '',
            related_ca_id TEXT,
            uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (anomaly_id) REFERENCES anomalies(id) ON DELETE CASCADE,
            FOREIGN KEY (related_ca_id) REFERENCES corrective_actions(id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX idx_anomaly_attachments_anomaly "
        "ON anomaly_attachments(anomaly_id)"
    )
    conn.commit()
    conn.execute("PRAGMA foreign_keys=ON")


class CanonicalCaseActionRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = _fresh_conn()
        self.anomaly_id = _seed_anomaly(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_fresh_schema_is_ready_and_legacy_writes_are_guarded(self) -> None:
        self.assertTrue(repository.case_actions_schema_ready(self.conn))
        with self.assertRaisesRegex(sqlite3.IntegrityError, "read-only"):
            self.conn.execute(
                """
                INSERT INTO anomaly_actions(id, anomaly_id, description)
                VALUES ('legacy-new', ?, 'must fail')
                """,
                (self.anomaly_id,),
            )

    def test_non_improvement_action_cannot_require_verification(self) -> None:
        with self.assertRaisesRegex(ValueError, "Only improvement"):
            repository.create_case_action(
                self.conn,
                anomaly_id=self.anomaly_id,
                action_type="NEXT_ACTION",
                description="Request 8D",
                verification_required=True,
            )

    def test_improvement_defaults_to_verification_required(self) -> None:
        action_id = repository.create_case_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            action_type="CORRECTIVE_ACTION",
            description="Replace fixture",
        )
        action = repository.get_case_action(self.conn, action_id)
        self.assertTrue(action["verification_required"])
        self.assertEqual(action["verification_status"], "待驗證")

    def test_planned_start_complete_and_append_verification(self) -> None:
        action_id = repository.create_case_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            action_type="SYSTEMIC_IMPROVEMENT",
            description="Deploy SPC alarm",
        )
        with self.assertRaisesRegex(ValueError, "Only 執行中"):
            repository.complete_case_action(self.conn, action_id)
        repository.update_case_action(
            self.conn,
            action_id,
            execution_status="執行中",
        )
        repository.complete_case_action(
            self.conn,
            action_id,
            implementation_evidence="Alarm screenshot",
            completion_note="Enabled on all lines",
        )
        verification_id = repository.record_action_verification(
            self.conn,
            action_id=action_id,
            method="30-day monitor",
            result="無效",
            evidence="Two recurrences",
        )
        action = repository.get_case_action(self.conn, action_id)
        self.assertEqual(action["execution_status"], "已完成")
        self.assertEqual(action["verification_status"], "無效")
        self.assertEqual(action["latest_verification"]["id"], verification_id)

    def test_only_completed_required_improvement_can_be_verified(self) -> None:
        action_id = repository.create_case_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            action_type="CORRECTIVE_ACTION",
            description="Change stencil",
            execution_status="執行中",
        )
        with self.assertRaisesRegex(ValueError, "Only completed"):
            repository.record_action_verification(
                self.conn,
                action_id=action_id,
                method="Three lots",
                result="有效",
            )
        next_action_id = repository.create_case_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            action_type="NEXT_ACTION",
            description="Notify supplier",
            execution_status="執行中",
        )
        repository.complete_case_action(self.conn, next_action_id)
        with self.assertRaisesRegex(ValueError, "does not support"):
            repository.record_action_verification(
                self.conn,
                action_id=next_action_id,
                method="Not applicable",
                result="有效",
            )

    def test_cancel_requires_reason(self) -> None:
        action_id = repository.create_case_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            action_type="CONTAINMENT",
            description="Sort stock",
        )
        with self.assertRaisesRegex(ValueError, "Cancel reason"):
            repository.cancel_case_action(self.conn, action_id, cancel_note="")
        repository.cancel_case_action(
            self.conn,
            action_id,
            cancel_note="Duplicate Action",
        )
        self.assertEqual(
            repository.get_case_action(self.conn, action_id)["execution_status"],
            "已取消",
        )

    def test_overdue_and_current_action_use_canonical_rules(self) -> None:
        planned_id = repository.create_case_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            action_type="NEXT_ACTION",
            description="Planned and overdue",
            due_date="2020-01-01",
        )
        in_progress_id = repository.create_case_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            action_type="CONTAINMENT",
            description="In progress without due date",
            execution_status="執行中",
        )
        self.assertTrue(
            repository.is_case_action_overdue(
                self.conn,
                self.anomaly_id,
                today="2026-08-24",
            )
        )
        self.assertEqual(
            repository.get_current_case_action(self.conn, self.anomaly_id)["id"],
            in_progress_id,
        )
        repository.cancel_case_action(
            self.conn,
            planned_id,
            cancel_note="No longer needed",
        )
        self.assertFalse(
            repository.is_case_action_overdue(
                self.conn,
                self.anomaly_id,
                today="2026-08-24",
            )
        )


class CaseActionLegacyMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = _fresh_conn()
        _drop_canonical_schema_for_legacy_fixture(self.conn)
        self.anomaly_id = _seed_anomaly(self.conn, "legacy")

    def tearDown(self) -> None:
        self.conn.close()

    def _insert_legacy_collision_fixture(self) -> None:
        self.conn.execute(
            """
            INSERT INTO anomaly_actions(
                id, anomaly_id, description, owner, due_date, status,
                created_at, updated_at
            ) VALUES ('same-id', ?, 'Legacy next', 'Alice', '2026-09-01',
                      '進行中', '2026-08-01 08:00', '2026-08-01 08:00')
            """,
            (self.anomaly_id,),
        )
        self.conn.execute(
            """
            INSERT INTO corrective_actions(
                id, anomaly_id, description, responsible_party, target_date,
                status, effectiveness_verification_required, created_at, updated_at
            ) VALUES ('same-id', ?, 'Legacy CA', 'Bob', '2026-09-10',
                      '有效', 1, '2026-08-02 08:00', '2026-08-20 08:00')
            """,
            (self.anomaly_id,),
        )
        self.conn.execute(
            """
            INSERT INTO anomaly_attachments(
                id, anomaly_id, file_name, related_ca_id
            ) VALUES ('att-1', ?, 'legacy.png', 'same-id')
            """,
            (self.anomaly_id,),
        )
        self.conn.commit()

    def test_collision_mapping_attachment_and_synthetic_legacy_result(self) -> None:
        self._insert_legacy_collision_fixture()
        preview = repository.preview_case_actions_v1_migration(self.conn)
        self.assertEqual(preview["legacy_id_collisions"], 1)
        self.assertEqual(preview["legacy_status_verifications"], 1)

        report = repository.migrate_case_actions_v1(self.conn, apply=True)
        self.assertTrue(report["reconciled"])
        self.assertEqual(report["integrity_check"], "ok")
        self.assertEqual(report["foreign_key_violations"], [])

        mapping = {
            (row["legacy_source"], row["legacy_id"]): row["canonical_id"]
            for row in self.conn.execute(
                "SELECT legacy_source, legacy_id, canonical_id "
                "FROM case_action_legacy_map"
            ).fetchall()
        }
        self.assertEqual(mapping[("anomaly_actions", "same-id")], "same-id")
        corrective_id = mapping[("corrective_actions", "same-id")]
        self.assertNotEqual(corrective_id, "same-id")
        attachment = self.conn.execute(
            "SELECT related_action_id FROM anomaly_attachments WHERE id = 'att-1'"
        ).fetchone()
        self.assertEqual(attachment[0], corrective_id)
        synthetic = self.conn.execute(
            """
            SELECT method, result, evidence, conclusion
            FROM action_verifications WHERE action_id = ?
            """,
            (corrective_id,),
        ).fetchone()
        self.assertEqual(synthetic["method"], "LEGACY_STATUS")
        self.assertEqual(synthetic["result"], "有效")
        self.assertEqual(synthetic["evidence"], "")
        self.assertIn("legacy-incomplete", synthetic["conclusion"])

    def test_all_legacy_statuses_map_and_existing_verification_is_preserved(self) -> None:
        anomaly_statuses = ("進行中", "已完成", "已取消")
        for index, status in enumerate(anomaly_statuses):
            self.conn.execute(
                """
                INSERT INTO anomaly_actions(id, anomaly_id, description, status)
                VALUES (?, ?, ?, ?)
                """,
                (f"next-{index}", self.anomaly_id, status, status),
            )
        corrective_statuses = (
            "已規劃",
            "執行中",
            "已實施",
            "待有效性驗證",
            "有效",
            "無效",
            "已取消",
        )
        for index, status in enumerate(corrective_statuses):
            self.conn.execute(
                """
                INSERT INTO corrective_actions(
                    id, anomaly_id, description, status,
                    effectiveness_verification_required
                ) VALUES (?, ?, ?, ?, 1)
                """,
                (f"ca-{index}", self.anomaly_id, status, status),
            )
        self.conn.execute(
            """
            INSERT INTO effectiveness_verifications(
                id, corrective_action_id, method, result
            ) VALUES ('verify-existing', 'ca-5', 'Legacy monitor', '無效')
            """
        )
        self.conn.commit()

        repository.migrate_case_actions_v1(self.conn, apply=True)
        next_results = {
            row["legacy_id"]: row["execution_status"]
            for row in self.conn.execute(
                "SELECT legacy_id, execution_status FROM case_actions "
                "WHERE legacy_source = 'anomaly_actions'"
            ).fetchall()
        }
        self.assertEqual(
            next_results,
            {"next-0": "執行中", "next-1": "已完成", "next-2": "已取消"},
        )
        ca_results = {
            row["legacy_id"]: row["execution_status"]
            for row in self.conn.execute(
                "SELECT legacy_id, execution_status FROM case_actions "
                "WHERE legacy_source = 'corrective_actions'"
            ).fetchall()
        }
        self.assertEqual(ca_results["ca-0"], "已規劃")
        self.assertEqual(ca_results["ca-1"], "執行中")
        for index in (2, 3, 4, 5):
            self.assertEqual(ca_results[f"ca-{index}"], "已完成")
        self.assertEqual(ca_results["ca-6"], "已取消")
        preserved = self.conn.execute(
            "SELECT id, result FROM action_verifications WHERE id = 'verify-existing'"
        ).fetchone()
        self.assertEqual(tuple(preserved), ("verify-existing", "無效"))

    def test_migration_is_idempotent(self) -> None:
        self._insert_legacy_collision_fixture()
        repository.migrate_case_actions_v1(self.conn, apply=True)
        before = (
            self.conn.execute("SELECT COUNT(*) FROM case_actions").fetchone()[0],
            self.conn.execute("SELECT COUNT(*) FROM action_verifications").fetchone()[0],
            self.conn.execute("SELECT COUNT(*) FROM case_action_legacy_map").fetchone()[0],
        )
        report = repository.migrate_case_actions_v1(self.conn, apply=True)
        after = (
            self.conn.execute("SELECT COUNT(*) FROM case_actions").fetchone()[0],
            self.conn.execute("SELECT COUNT(*) FROM action_verifications").fetchone()[0],
            self.conn.execute("SELECT COUNT(*) FROM case_action_legacy_map").fetchone()[0],
        )
        self.assertTrue(report["skipped"])
        self.assertEqual(before, after)

    def test_failed_migration_rolls_back_schema_and_meta(self) -> None:
        self.conn.commit()
        self.conn.execute("PRAGMA foreign_keys=OFF")
        self.conn.execute(
            """
            INSERT INTO effectiveness_verifications(
                id, corrective_action_id, method, result
            ) VALUES ('orphan-v', 'missing-ca', 'legacy', '有效')
            """
        )
        self.conn.commit()
        self.conn.execute("PRAGMA foreign_keys=ON")
        with self.assertRaisesRegex(RuntimeError, "unmapped corrective action"):
            repository.migrate_case_actions_v1(self.conn, apply=True)
        table_names = {
            str(row[0])
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        self.assertNotIn("case_actions", table_names)
        self.assertIsNone(
            self.conn.execute(
                "SELECT value FROM migration_meta WHERE key = ?",
                (CASE_ACTIONS_MIGRATION_META_KEY,),
            ).fetchone()
        )

    def test_existing_formal_target_requires_both_promotion_markers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = os.path.join(temp_dir, "sqe_v2.db")
            conn = sqlite3.connect(target)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            repository.create_schema(conn)
            _drop_canonical_schema_for_legacy_fixture(conn)
            anomaly_id = _seed_anomaly(conn, "formal-guard")
            conn.execute(
                """
                INSERT INTO anomaly_actions(id, anomaly_id, description, status)
                VALUES ('formal-legacy', ?, 'must remain legacy', '進行中')
                """,
                (anomaly_id,),
            )
            conn.commit()

            marker_values = {
                "SQE_CASE_ACTIONS_PROMOTION_APPROVED": "",
                "SQE_DAILYWORK_CONFIRM_APPLY": "",
            }
            with (
                mock.patch(
                    "database.case_action_repository.formal_db_path",
                    return_value=Path(target),
                ),
                mock.patch.dict(os.environ, marker_values),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "Formal case_actions_v1 migration refused",
                ):
                    repository.migrate_case_actions_v1(
                        conn,
                        apply=True,
                        formal_promotion=True,
                    )
                with mock.patch.dict(
                    os.environ,
                    {
                        "SQE_CASE_ACTIONS_PROMOTION_APPROVED": "1",
                        "SQE_DAILYWORK_CONFIRM_APPLY": "1",
                    },
                ):
                    report = repository.migrate_case_actions_v1(
                        conn,
                        apply=True,
                        formal_promotion=True,
                    )
            self.assertTrue(report["applied"])
            self.assertEqual(
                1,
                conn.execute("SELECT COUNT(*) FROM case_actions").fetchone()[0],
            )
            conn.close()

    def test_create_schema_disposable_flag_cannot_upgrade_formal_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = os.path.join(temp_dir, "sqe_v2.db")
            conn = sqlite3.connect(target)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            repository.create_schema(conn)
            _drop_canonical_schema_for_legacy_fixture(conn)
            with (
                mock.patch(
                    "database.case_action_repository.formal_db_path",
                    return_value=Path(target),
                ),
                mock.patch.dict(
                    os.environ,
                    {
                        "SQE_REQUIRE_DISPOSABLE_DB": "1",
                        "SQE_CASE_ACTIONS_PROMOTION_APPROVED": "",
                        "SQE_DAILYWORK_CONFIRM_APPLY": "",
                    },
                ),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "Formal case_actions_v1 migration refused",
                ):
                    repository.create_schema(conn)
            self.assertNotIn(
                "case_actions",
                {
                    str(row[0])
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                },
            )
            conn.close()


class CaseActionServiceTransactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="case-action-service-")
        self.db_path = os.path.join(self.temp_dir.name, "case-actions.db")
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(conn)
        self.anomaly_id = _seed_anomaly(conn, "service")
        conn.close()

        def _factory(*_args, **_kwargs):
            connection = sqlite3.connect(
                self.db_path,
                factory=_connection.ClosingConnection,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            return connection

        self.connection_patch = mock.patch.object(
            _connection,
            "get_connection",
            side_effect=_factory,
        )
        self.connection_patch.start()

    def tearDown(self) -> None:
        self.connection_patch.stop()
        self.temp_dir.cleanup()

    def test_create_and_audit_commit_together(self) -> None:
        action_id = _case_action_service.create_case_action(
            anomaly_id=self.anomaly_id,
            action_type="NEXT_ACTION",
            description="Request 8D",
            execution_status="執行中",
            actor_name="SQE",
        )
        conn = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM case_actions WHERE id = ?",
                    (action_id,),
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM anomaly_audit_logs "
                    "WHERE action = 'CASE_ACTION_CREATED'"
                ).fetchone()[0],
                1,
            )
        finally:
            conn.close()

    def test_audit_failure_rolls_back_action_write(self) -> None:
        with mock.patch.object(
            repository,
            "append_anomaly_audit_log",
            side_effect=RuntimeError("audit failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "audit failed"):
                _case_action_service.create_case_action(
                    anomaly_id=self.anomaly_id,
                    action_type="NEXT_ACTION",
                    description="Must roll back",
                    execution_status="執行中",
                )
        conn = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM case_actions "
                    "WHERE description = 'Must roll back'"
                ).fetchone()[0],
                0,
            )
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
