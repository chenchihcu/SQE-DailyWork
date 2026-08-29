from __future__ import annotations

import os
import sqlite3
import unittest
from contextlib import contextmanager
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from database import repository
from services import repeat_issue_service
from services.event import _anomaly_service
from services.repeat_issue_scoring import REPEAT_MIN_SCORE, compute_repeat_similarity
from services import supplier_360_service


def _seed_supplier_product(conn: sqlite3.Connection, *, suffix: str) -> tuple[str, str]:
    supplier_id = repository.create_supplier_record(
        conn, supplier_name=f"Phase5 Repeat Supplier {suffix}"
    )
    product_id = repository.create_product_record(
        conn,
        product_code=f"PH5-REP-{suffix}",
        product_name="Phase 5 Repeat Product",
        supplier_id=supplier_id,
    )
    return supplier_id, product_id


def _create_anomaly(
    conn: sqlite3.Connection,
    *,
    supplier_id: str,
    product_id: str,
    category: str,
    problem_desc: str,
    anomaly_no: str,
) -> str:
    return repository.create_anomaly_with_visit_link(
        conn,
        anomaly_date="2026-08-20",
        supplier_id=supplier_id,
        product_id=product_id,
        problem_desc=problem_desc,
        category=category,
        sync_visit=False,
        anomaly_no=anomaly_no,
    )["anomaly_id"]


class RepeatIssuePhase5RepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.supplier_id, self.product_id = _seed_supplier_product(
            self.conn, suffix="A"
        )
        self.anomaly_a = _create_anomaly(
            self.conn,
            supplier_id=self.supplier_id,
            product_id=self.product_id,
            category="外觀",
            problem_desc="外觀刮傷導致功能異常",
            anomaly_no="20260820001",
        )
        self.anomaly_b = _create_anomaly(
            self.conn,
            supplier_id=self.supplier_id,
            product_id=self.product_id,
            category="外觀",
            problem_desc="外觀刮傷再次發生",
            anomaly_no="20260820002",
        )
        repository.refresh_supplier_repeat_links(self.conn, self.supplier_id)
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_fresh_schema_has_repeat_links_contract(self) -> None:
        preview = repository.preview_anomaly_repeat_links_v1(self.conn)
        self.assertTrue(preview["ready"])
        self.assertEqual([], preview["missing_table_columns"])

    def test_legacy_preview_then_apply_is_idempotent(self) -> None:
        self.conn.execute("DROP TABLE IF EXISTS anomaly_repeat_links")
        self.conn.execute(
            "DELETE FROM migration_meta WHERE key = 'anomaly_repeat_links_v1'"
        )
        self.conn.commit()
        preview = repository.preview_anomaly_repeat_links_v1(self.conn)
        self.assertFalse(preview["ready"])
        applied = repository.migrate_anomaly_repeat_links_v1(self.conn, apply=True)
        self.conn.commit()
        self.assertTrue(applied["applied"])
        self.assertTrue(repository.preview_anomaly_repeat_links_v1(self.conn)["ready"])
        repeated = repository.migrate_anomaly_repeat_links_v1(self.conn, apply=True)
        self.assertTrue(repeated["skipped"])

    def test_refresh_repeat_links_requires_schema(self) -> None:
        self.conn.execute("DROP TABLE IF EXISTS anomaly_repeat_links")
        self.conn.execute(
            "DELETE FROM migration_meta WHERE key = 'anomaly_repeat_links_v1'"
        )
        self.conn.commit()
        with self.assertRaises(RuntimeError):
            repeat_issue_service.refresh_repeat_links_for_suppliers(
                self.conn,
                self.supplier_id,
            )

    def test_same_supplier_category_product_creates_repeat_link(self) -> None:
        rows = repository.list_repeat_links_for_anomaly(self.conn, self.anomaly_a)
        peer_ids = {row["peer_anomaly_id"] for row in rows}
        self.assertIn(self.anomaly_b, peer_ids)
        self.assertGreaterEqual(int(rows[0]["similarity_score"]), REPEAT_MIN_SCORE)

    def test_different_supplier_does_not_link(self) -> None:
        other_supplier, other_product = _seed_supplier_product(self.conn, suffix="B")
        other_id = _create_anomaly(
            self.conn,
            supplier_id=other_supplier,
            product_id=other_product,
            category="外觀",
            problem_desc="外觀刮傷導致功能異常",
            anomaly_no="20260820003",
        )
        rows = repository.list_repeat_links_for_anomaly(self.conn, other_id)
        self.assertEqual([], rows)

    def test_refresh_repeat_links_ignores_defect_records(self) -> None:
        """Repeat scoring must index supplier anomalies only, never defect_records."""
        before = self.conn.execute(
            "SELECT COUNT(*) FROM anomaly_repeat_links"
        ).fetchone()[0]
        self.conn.execute(
            """
            INSERT INTO defect_records(
                defect_no, event_date, processing_line, item_no, qty,
                defect_desc, status, created_at, supplier_id, category
            ) VALUES (
                'NCR-PH5-001', '2026-08-20', '委外加工', 'PH5-REP-A', 1,
                '外觀刮傷導致功能異常', '待處理', '2026-08-20 09:00', ?, '外觀'
            )
            """,
            (self.supplier_id,),
        )
        self.conn.commit()
        repository.refresh_supplier_repeat_links(self.conn, self.supplier_id)
        self.conn.commit()

        rows = self.conn.execute(
            "SELECT anomaly_id, peer_anomaly_id FROM anomaly_repeat_links"
        ).fetchall()
        anomaly_ids = {self.anomaly_a, self.anomaly_b}
        for row in rows:
            self.assertIn(row["anomaly_id"], anomaly_ids)
            self.assertIn(row["peer_anomaly_id"], anomaly_ids)
        self.assertEqual(before, len(rows))
        self.assertGreaterEqual(len(rows), 1)

    def test_supplier_summary_counts_repeat_flagged_anomalies(self) -> None:
        @contextmanager
        def _fake_connection():
            yield self.conn

        with mock.patch(
            "services.supplier_360_service._connection.get_connection",
            side_effect=_fake_connection,
        ):
            summary = supplier_360_service.get_supplier_summary(self.supplier_id)
        self.assertGreaterEqual(summary.get("repeat_flagged_anomaly_count", 0), 2)


class RepeatIssuePhase5ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.supplier_id, self.product_id = _seed_supplier_product(
            self.conn, suffix="svc"
        )
        self.anomaly_id = _create_anomaly(
            self.conn,
            supplier_id=self.supplier_id,
            product_id=self.product_id,
            category="尺寸",
            problem_desc="尺寸超差",
            anomaly_no="20260820001",
        )

        @contextmanager
        def _fake_connection():
            yield self.conn

        self._conn_patcher = mock.patch(
            "services.repeat_issue_service._connection.get_connection",
            side_effect=_fake_connection,
        )
        self._conn_patcher.start()
        self._anomaly_conn_patcher = mock.patch(
            "services.event._anomaly_service._connection.get_connection",
            side_effect=_fake_connection,
        )
        self._anomaly_conn_patcher.start()
        self._snapshot_patcher = mock.patch(
            "services.event._anomaly_service._write_snapshot_with_warning",
            return_value=[],
        )
        self._snapshot_patcher.start()

    def tearDown(self) -> None:
        self._snapshot_patcher.stop()
        self._anomaly_conn_patcher.stop()
        self._conn_patcher.stop()
        self.conn.close()

    def test_compute_repeat_similarity_requires_category_match_minimum(self) -> None:
        score, reasons = compute_repeat_similarity(
            {"category": "外觀", "product_id": "p1"},
            {"category": "外觀", "product_id": "p2"},
        )
        self.assertGreaterEqual(score, REPEAT_MIN_SCORE)
        self.assertIn("相同異常類別", reasons)

    def test_create_anomaly_refreshes_repeat_links(self) -> None:
        peer_id = _create_anomaly(
            self.conn,
            supplier_id=self.supplier_id,
            product_id=self.product_id,
            category="尺寸",
            problem_desc="尺寸超差再發",
            anomaly_no="20260820002",
        )
        _anomaly_service.create_anomaly(
            {
                "supplier_id": self.supplier_id,
                "product_id": self.product_id,
                "category": "尺寸",
                "problem_desc": "尺寸超差第三件",
                "anomaly_date": "2026-08-26",
                "anomaly_no": "20260826001",
                "anomaly_source": "進料",
            }
        )
        rows = repeat_issue_service.list_repeat_issues(peer_id)
        peer_ids = {row["peer_anomaly_id"] for row in rows}
        self.assertTrue(peer_ids)
