from __future__ import annotations

import sqlite3
import unittest
from unittest import mock

from database import repository
from database.repo_helpers import (
    ANOMALY_AUDIT_HYPOTHESIS_CREATED,
    ANOMALY_AUDIT_HYPOTHESIS_PROMOTED,
    ANOMALY_AUDIT_HYPOTHESIS_UPDATED,
    ANOMALY_HYPOTHESIS_ADOPTED,
    ANOMALY_ROOT_CAUSE_PROPOSED,
    ANOMALY_ROOT_CAUSE_VERIFIED,
)
from services.event import _anomaly_workbench_service


def _seed_anomaly(conn: sqlite3.Connection, suffix: str = "") -> str:
    suffix_text = suffix or "primary"
    supplier_id = repository.create_supplier_record(
        conn, supplier_name=f"Phase3 Hypothesis Supplier {suffix_text}"
    )
    product_id = repository.create_product_record(
        conn,
        product_code=f"PH3-HYP-{suffix_text}",
        product_name="Phase 3 Hypothesis Product",
        supplier_id=supplier_id,
    )
    return repository.create_anomaly_with_visit_link(
        conn,
        anomaly_date="2026-08-26",
        supplier_id=supplier_id,
        product_id=product_id,
        problem_desc="hypothesis foundation fixture",
        sync_visit=False,
    )["anomaly_id"]


class Phase3HypothesisRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.anomaly_id = _seed_anomaly(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_fresh_schema_has_hypothesis_contract(self) -> None:
        preview = repository.preview_anomaly_hypotheses_v1(self.conn)
        self.assertTrue(preview["ready"])
        self.assertEqual([], preview["missing_table_columns"])
        self.assertEqual([], preview["missing_extension_columns"])

    def test_legacy_preview_then_apply_is_idempotent(self) -> None:
        self.conn.execute("DROP TABLE IF EXISTS anomaly_hypotheses")
        self.conn.execute(
            "DELETE FROM migration_meta WHERE key = 'anomaly_hypotheses_v1'"
        )
        self.conn.commit()
        preview = repository.preview_anomaly_hypotheses_v1(self.conn)
        self.assertFalse(preview["ready"])
        applied = repository.migrate_anomaly_hypotheses_v1(self.conn, apply=True)
        self.conn.commit()
        self.assertTrue(applied["applied"])
        self.assertTrue(repository.preview_anomaly_hypotheses_v1(self.conn)["ready"])
        repeated = repository.migrate_anomaly_hypotheses_v1(self.conn, apply=True)
        self.assertTrue(repeated["skipped"])

    def test_tree_parent_child_same_anomaly_and_depth_limit(self) -> None:
        parent_id = repository.create_anomaly_hypothesis(
            self.conn,
            anomaly_id=self.anomaly_id,
            statement="L1 root cause candidate",
        )
        child_id = repository.create_anomaly_hypothesis(
            self.conn,
            anomaly_id=self.anomaly_id,
            statement="L2 child",
            parent_hypothesis_id=parent_id,
        )
        parent = repository.get_anomaly_hypothesis(self.conn, parent_id)
        child = repository.get_anomaly_hypothesis(self.conn, child_id)
        self.assertEqual(1, parent["level"])
        self.assertEqual(2, child["level"])
        other_anomaly = _seed_anomaly(self.conn, "other")
        with self.assertRaises(ValueError):
            repository.create_anomaly_hypothesis(
                self.conn,
                anomaly_id=other_anomaly,
                statement="cross case",
                parent_hypothesis_id=parent_id,
            )
        current = parent_id
        for index in range(2, 6):
            current = repository.create_anomaly_hypothesis(
                self.conn,
                anomaly_id=self.anomaly_id,
                statement=f"L{index}",
                parent_hypothesis_id=current,
            )
        with self.assertRaises(ValueError):
            repository.create_anomaly_hypothesis(
                self.conn,
                anomaly_id=self.anomaly_id,
                statement="too deep",
                parent_hypothesis_id=current,
            )

    def test_cycle_rejected_on_update(self) -> None:
        parent_id = repository.create_anomaly_hypothesis(
            self.conn,
            anomaly_id=self.anomaly_id,
            statement="parent",
        )
        child_id = repository.create_anomaly_hypothesis(
            self.conn,
            anomaly_id=self.anomaly_id,
            statement="child",
            parent_hypothesis_id=parent_id,
        )
        with self.assertRaises(ValueError):
            repository.update_anomaly_hypothesis(
                self.conn,
                hypothesis_id=parent_id,
                anomaly_id=self.anomaly_id,
                parent_hypothesis_id=child_id,
            )

    def test_reparent_cascades_child_levels(self) -> None:
        root_a = repository.create_anomaly_hypothesis(
            self.conn,
            anomaly_id=self.anomaly_id,
            statement="root A",
        )
        root_b = repository.create_anomaly_hypothesis(
            self.conn,
            anomaly_id=self.anomaly_id,
            statement="root B",
        )
        child_id = repository.create_anomaly_hypothesis(
            self.conn,
            anomaly_id=self.anomaly_id,
            statement="child under A",
            parent_hypothesis_id=root_a,
        )
        grandchild_id = repository.create_anomaly_hypothesis(
            self.conn,
            anomaly_id=self.anomaly_id,
            statement="grandchild",
            parent_hypothesis_id=child_id,
        )
        repository.update_anomaly_hypothesis(
            self.conn,
            hypothesis_id=child_id,
            anomaly_id=self.anomaly_id,
            parent_hypothesis_id=root_b,
        )
        child = repository.get_anomaly_hypothesis(self.conn, child_id)
        grandchild = repository.get_anomaly_hypothesis(self.conn, grandchild_id)
        self.assertEqual(2, child["level"])
        self.assertEqual(3, grandchild["level"])

    def test_attachment_hypothesis_link_and_note_xor(self) -> None:
        hypothesis_id = repository.create_anomaly_hypothesis(
            self.conn,
            anomaly_id=self.anomaly_id,
            statement="linked hypothesis",
        )
        note_id = repository.create_anomaly_analysis_note(
            self.conn,
            anomaly_id=self.anomaly_id,
            content="linked note",
        )
        attachment_id = repository.create_anomaly_attachment(
            self.conn,
            anomaly_id=self.anomaly_id,
            file_name="hypothesis.pdf",
            related_hypothesis_id=hypothesis_id,
        )
        rows = repository.list_anomaly_attachments(self.conn, self.anomaly_id)
        self.assertEqual(hypothesis_id, rows[0]["related_hypothesis_id"])
        self.assertIsNone(rows[0]["related_note_id"])
        with self.assertRaises(ValueError):
            repository.create_anomaly_attachment(
                self.conn,
                anomaly_id=self.anomaly_id,
                file_name="both.pdf",
                related_note_id=note_id,
                related_hypothesis_id=hypothesis_id,
            )
        self.assertEqual(attachment_id, rows[0]["id"])

    def test_promotion_copies_statement_without_auto_verified(self) -> None:
        hypothesis_id = repository.create_anomaly_hypothesis(
            self.conn,
            anomaly_id=self.anomaly_id,
            statement="Reflow profile drift",
            evidence_type="INFERENCE",
        )
        result = repository.promote_hypothesis_to_root_cause(
            self.conn,
            hypothesis_id=hypothesis_id,
            anomaly_id=self.anomaly_id,
        )
        root = result["root_cause"]
        self.assertEqual("Reflow profile drift", root["statement"])
        self.assertEqual(ANOMALY_ROOT_CAUSE_PROPOSED, root["status"])
        self.assertNotEqual(ANOMALY_ROOT_CAUSE_VERIFIED, root["status"])
        self.assertEqual(hypothesis_id, root["promoted_from_hypothesis_id"])
        hypothesis = repository.get_anomaly_hypothesis(self.conn, hypothesis_id)
        self.assertEqual(ANOMALY_HYPOTHESIS_ADOPTED, hypothesis["status"])

    def test_evidence_chain_and_overview_metrics(self) -> None:
        note_id = repository.create_anomaly_analysis_note(
            self.conn,
            anomaly_id=self.anomaly_id,
            content="measured peak",
            evidence_type="FACT",
        )
        hypothesis_id = repository.create_anomaly_hypothesis(
            self.conn,
            anomaly_id=self.anomaly_id,
            statement="profile drift",
        )
        repository.create_anomaly_attachment(
            self.conn,
            anomaly_id=self.anomaly_id,
            file_name="chart.png",
            related_hypothesis_id=hypothesis_id,
        )
        chain = repository.list_anomaly_evidence_chain(self.conn, self.anomaly_id)
        node_types = {row["node_type"] for row in chain}
        self.assertTrue({"analysis_note", "hypothesis", "attachment"}.issubset(node_types))
        hypothesis_node = next(
            row for row in chain if row["node_type"] == "hypothesis"
        )
        self.assertEqual(1, hypothesis_node["attachment_count"])
        overview = repository.get_anomaly_overview_card(self.conn, self.anomaly_id)
        self.assertEqual(1, overview["hypothesis_count"])
        self.assertEqual(1, overview["hypothesis_deepest_level"])
        self.assertFalse(overview["hypothesis_adopted"])
        self.assertIn(note_id, {row["node_id"] for row in chain})

    def test_analysis_note_attachment_count_uses_live_manifest(self) -> None:
        note_id = repository.create_anomaly_analysis_note(
            self.conn,
            anomaly_id=self.anomaly_id,
            content="note with attachment",
            attachment_count=0,
        )
        notes = repository.list_anomaly_analysis_notes(self.conn, self.anomaly_id)
        self.assertEqual(0, notes[0]["attachment_count"])
        repository.create_anomaly_attachment(
            self.conn,
            anomaly_id=self.anomaly_id,
            file_name="note-evidence.pdf",
            related_note_id=note_id,
        )
        notes = repository.list_anomaly_analysis_notes(self.conn, self.anomaly_id)
        self.assertEqual(1, notes[0]["attachment_count"])
        chain = repository.list_anomaly_evidence_chain(self.conn, self.anomaly_id)
        note_node = next(row for row in chain if row["node_type"] == "analysis_note")
        self.assertEqual(1, note_node["attachment_count"])


class Phase3HypothesisServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.anomaly_id = _seed_anomaly(self.conn)
        self.conn_patcher = mock.patch.object(
            _anomaly_workbench_service,
            "_open_conn",
            return_value=self.conn,
        )
        self.conn_patcher.start()

    def tearDown(self) -> None:
        self.conn_patcher.stop()
        self.conn.close()

    def test_create_hypothesis_writes_audit_log(self) -> None:
        hypothesis_id = _anomaly_workbench_service.create_hypothesis(
            anomaly_id=self.anomaly_id,
            statement="service path",
            evidence_type="FACT",
        )
        logs = repository.list_anomaly_audit_logs(self.conn, self.anomaly_id)
        self.assertTrue(any(log["action"] == ANOMALY_AUDIT_HYPOTHESIS_CREATED for log in logs))
        row = repository.get_anomaly_hypothesis(self.conn, hypothesis_id)
        self.assertEqual("service path", row["statement"])

    def test_promote_hypothesis_writes_audit_log(self) -> None:
        hypothesis_id = repository.create_anomaly_hypothesis(
            self.conn,
            anomaly_id=self.anomaly_id,
            statement="promote me",
            status="支持",
        )
        _anomaly_workbench_service.promote_hypothesis_to_root_cause(
            anomaly_id=self.anomaly_id,
            hypothesis_id=hypothesis_id,
        )
        logs = repository.list_anomaly_audit_logs(self.conn, self.anomaly_id)
        self.assertTrue(any(log["action"] == ANOMALY_AUDIT_HYPOTHESIS_PROMOTED for log in logs))

    def test_update_hypothesis_non_status_writes_audit_log(self) -> None:
        hypothesis_id = repository.create_anomaly_hypothesis(
            self.conn,
            anomaly_id=self.anomaly_id,
            statement="before edit",
        )
        _anomaly_workbench_service.update_hypothesis(
            anomaly_id=self.anomaly_id,
            hypothesis_id=hypothesis_id,
            statement="after edit",
            evidence_type="FACT",
        )
        logs = repository.list_anomaly_audit_logs(self.conn, self.anomaly_id)
        self.assertTrue(
            any(log["action"] == ANOMALY_AUDIT_HYPOTHESIS_UPDATED for log in logs)
        )


if __name__ == "__main__":
    unittest.main()
