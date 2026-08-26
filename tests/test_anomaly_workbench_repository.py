from __future__ import annotations

import sqlite3
import unittest

from database import repository


def _make_anom(conn: sqlite3.Connection) -> str:
    supplier = repository.create_supplier_record(conn, supplier_name="WS")
    product = repository.create_product_record(
        conn,
        product_code="WS-001",
        product_name="WS Product",
        supplier_id=supplier,
    )
    return repository.create_anomaly_with_visit_link(
        conn,
        anomaly_date="2026-06-01",
        supplier_id=supplier,
        product_id=product,
        problem_desc="workbench problem",
        sync_visit=False,
    )["anomaly_id"]


class AnomalyWorkbenchRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.anomaly_id = _make_anom(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    # ---- analysis notes ------------------------------------------------
    def test_create_and_list_analysis_note_with_label(self) -> None:
        repository.create_anomaly_analysis_note(
            self.conn,
            anomaly_id=self.anomaly_id,
            content="確認烘烤溫度超標",
            evidence_type="FACT",
            author_name="張三",
        )
        notes = repository.list_anomaly_analysis_notes(self.conn, self.anomaly_id)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["content"], "確認烘烤溫度超標")
        self.assertEqual(notes[0]["evidence_type"], "FACT")
        self.assertEqual(notes[0]["evidence_label"], "已確認事實")
        self.assertEqual(notes[0]["author_name"], "張三")

    def test_analysis_note_rejects_invalid_evidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "Evidence type"):
            repository.create_anomaly_analysis_note(
                self.conn,
                anomaly_id=self.anomaly_id,
                content="x",
                evidence_type="OPINION",
            )

    def test_analysis_note_rejects_empty_content(self) -> None:
        with self.assertRaisesRegex(ValueError, "content is required"):
            repository.create_anomaly_analysis_note(
                self.conn,
                anomaly_id=self.anomaly_id,
                content="   ",
            )

    # ---- root cause ----------------------------------------------------
    def test_upsert_root_cause_creates_then_updates(self) -> None:
        rc_id = repository.upsert_anomaly_root_cause(
            self.conn,
            anomaly_id=self.anomaly_id,
            statement="製程參數失控",
            status="調查中",
        )
        rc = repository.get_anomaly_root_cause(self.conn, self.anomaly_id)
        assert rc is not None
        self.assertEqual(rc["id"], rc_id)
        self.assertEqual(rc["status"], "調查中")

        repository.upsert_anomaly_root_cause(
            self.conn,
            anomaly_id=self.anomaly_id,
            statement="治具磨損",
            status="已驗證",
            validation_method="5-Why",
            not_established_reason="",
        )
        rc2 = repository.get_anomaly_root_cause(self.conn, self.anomaly_id)
        assert rc2 is not None
        self.assertEqual(rc2["id"], rc_id)
        self.assertEqual(rc2["statement"], "治具磨損")
        self.assertEqual(rc2["status"], "已驗證")
        self.assertEqual(rc2["validation_method"], "5-Why")

    def test_root_cause_requires_statement_for_verified(self) -> None:
        with self.assertRaisesRegex(ValueError, "statement is required"):
            repository.upsert_anomaly_root_cause(
                self.conn,
                anomaly_id=self.anomaly_id,
                statement="",
                status="已驗證",
            )

    def test_root_cause_requires_not_established_reason(self) -> None:
        with self.assertRaisesRegex(ValueError, "Not established reason is required"):
            repository.upsert_anomaly_root_cause(
                self.conn,
                anomaly_id=self.anomaly_id,
                statement="治具磨損",
                status="無法確認",
                not_established_reason="",
            )

    # ---- corrective actions --------------------------------------------
    def test_ca_requires_implementation_for_verification_flow(self) -> None:
        action_id = repository.create_case_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            action_type="CORRECTIVE_ACTION",
            description="更換治具",
            owner="製程組",
            due_date="2026/07/30",
            verification_required=True,
        )
        action = repository.get_case_action(self.conn, action_id)
        assert action is not None
        self.assertEqual(action["execution_status"], "已規劃")
        self.assertEqual(action["due_date"], "2026-07-30")
        self.assertTrue(action["verification_required"])

        repository.update_case_action(
            self.conn, action_id, execution_status="執行中"
        )
        repository.complete_case_action(
            self.conn, action_id, implementation_evidence="更換完成照片"
        )
        action2 = repository.get_case_action(self.conn, action_id)
        assert action2 is not None
        self.assertEqual(action2["execution_status"], "已完成")
        self.assertEqual(action2["verification_status"], "待驗證")
        self.assertEqual(action2["implementation_evidence"], "更換完成照片")

    def test_ca_without_verification_goes_straight_to_implemented(self) -> None:
        action_id = repository.create_case_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            action_type="CORRECTIVE_ACTION",
            description="補文件",
            execution_status="執行中",
            verification_required=False,
        )
        repository.complete_case_action(self.conn, action_id)
        action = repository.get_case_action(self.conn, action_id)
        assert action is not None
        self.assertEqual(action["execution_status"], "已完成")
        self.assertEqual(action["verification_status"], "不需要")

    def test_verification_result_updates_ca_status(self) -> None:
        action_id = repository.create_case_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            action_type="CORRECTIVE_ACTION",
            description="製程改善",
            execution_status="執行中",
            verification_required=True,
        )
        repository.complete_case_action(self.conn, action_id)
        repository.record_action_verification(
            self.conn,
            action_id=action_id,
            method="30天監控",
            acceptance_criteria="NG率<0.5%",
            period_sample="3批",
            result="有效",
            verified_by="王五",
        )
        action = repository.get_case_action(self.conn, action_id)
        assert action is not None
        self.assertEqual(action["execution_status"], "已完成")
        self.assertEqual(action["verification_status"], "有效")
        verifications = repository.list_action_verifications(
            self.conn, action_id
        )
        self.assertEqual(len(verifications), 1)
        self.assertEqual(verifications[0]["result"], "有效")

    # ---- attachments / 8D / audit / timeline ---------------------------
    def test_attachment_linked_to_ca(self) -> None:
        action_id = repository.create_case_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            action_type="CORRECTIVE_ACTION",
            description="對策",
        )
        att_id = repository.create_anomaly_attachment(
            self.conn,
            anomaly_id=self.anomaly_id,
            file_name="evidence.png",
            category="矯正措施證據",
            related_action_id=action_id,
        )
        atts = repository.list_anomaly_attachments(self.conn, self.anomaly_id)
        self.assertEqual(len(atts), 1)
        self.assertEqual(atts[0]["related_action_id"], action_id)
        self.assertEqual(atts[0]["id"], att_id)

    def test_8d_review_append_only(self) -> None:
        r1 = repository.create_anomaly_eight_d_review(
            self.conn,
            anomaly_id=self.anomaly_id,
            revision="Rev A",
            review_status="退回修正",
            review_comment="缺 D4",
        )
        r2 = repository.create_anomaly_eight_d_review(
            self.conn,
            anomaly_id=self.anomaly_id,
            revision="Rev B",
            review_status="接受",
            review_comment="已補齊",
        )
        reviews = repository.list_anomaly_eight_d_reviews(
            self.conn, self.anomaly_id
        )
        self.assertEqual(len(reviews), 2)
        self.assertEqual([v["id"] for v in reviews], [r1, r2])
        # Neither, later revision overwrites the earlier one.
        self.assertTrue(all(v["revision"] in ("Rev A", "Rev B") for v in reviews))

    def test_audit_log_append_only_and_readable(self) -> None:
        repository.append_anomaly_audit_log(
            self.conn,
            anomaly_id=self.anomaly_id,
            action="STATUS_CHANGED",
            before_value="待處理",
            after_value="調查中",
            actor_name="李四",
        )
        repository.append_anomaly_audit_log(
            self.conn,
            anomaly_id=self.anomaly_id,
            action="ACTION_CREATED",
            after_value="要求 FA",
        )
        logs = repository.list_anomaly_audit_logs(self.conn, self.anomaly_id)
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0]["action"], "STATUS_CHANGED")

    def test_timeline_merges_audit_without_duplicate(self) -> None:
        repository.append_anomaly_audit_log(
            self.conn,
            anomaly_id=self.anomaly_id,
            action="ROOT_CAUSE_UPDATED",
            after_value="根因更新",
        )
        repository.upsert_anomaly_root_cause(
            self.conn,
            anomaly_id=self.anomaly_id,
            statement="根因",
            status="已驗證",
        )
        timeline = repository.list_anomaly_timeline(self.conn, self.anomaly_id)
        kinds = [e["kind"] for e in timeline]
        # ROOT_CAUSE_UPDATED only appears once (audit authoritative, not duplicated).
        self.assertEqual(kinds.count("ROOT_CAUSE_UPDATED"), 1)

    def test_overview_card_aggregates(self) -> None:
        repository.create_case_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            action_type="NEXT_ACTION",
            description="下一步",
            due_date="2026-01-01",
            execution_status="執行中",
        )
        repository.create_anomaly_analysis_note(
            self.conn,
            anomaly_id=self.anomaly_id,
            content="分析一",
            evidence_type="INFERENCE",
        )
        action_id = repository.create_case_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            action_type="CORRECTIVE_ACTION",
            description="對策",
            execution_status="執行中",
            verification_required=True,
        )
        repository.complete_case_action(self.conn, action_id)
        repository.record_action_verification(
            self.conn,
            action_id=action_id,
            method="監控",
            result="無效",
        )
        card = repository.get_anomaly_overview_card(self.conn, self.anomaly_id)
        self.assertEqual(card["status"], "待處理")
        self.assertTrue(card["overdue"])
        self.assertEqual(card["open_action_count"], 1)
        self.assertEqual(card["root_cause_status"], "尚未開始")
        self.assertEqual(card["corrective_action_status"], "已完成")
        self.assertEqual(card["verification_result"], "無效")
        self.assertTrue(card["has_analysis_notes"])


class AnomalyEvidenceTablesMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")

    def tearDown(self) -> None:
        self.conn.close()

    def test_all_phase_tables_created(self) -> None:
        repository.create_schema(self.conn)
        tables = {
            r["name"]
            for r in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for expected in (
            "anomaly_analysis_notes",
            "anomaly_root_causes",
            "corrective_actions",
            "effectiveness_verifications",
            "anomaly_attachments",
            "anomaly_eight_d_reviews",
            "anomaly_audit_logs",
            "case_actions",
            "action_verifications",
            "case_action_legacy_map",
        ):
            self.assertIn(expected, tables)


if __name__ == "__main__":
    unittest.main()
