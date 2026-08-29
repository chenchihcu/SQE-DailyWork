from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from database import repository
from services import attachment_manager
from services.event import _anomaly_workbench_service


def _seed_anomaly(conn: sqlite3.Connection, suffix: str = "") -> str:
    suffix_text = suffix or "primary"
    supplier_id = repository.create_supplier_record(
        conn, supplier_name=f"Phase2 Attachment Supplier {suffix_text}"
    )
    product_id = repository.create_product_record(
        conn,
        product_code=f"PH2-ATT-{suffix_text}",
        product_name="Phase 2 Attachment Product",
        supplier_id=supplier_id,
    )
    return repository.create_anomaly_with_visit_link(
        conn,
        anomaly_date="2026-08-24",
        supplier_id=supplier_id,
        product_id=product_id,
        problem_desc="attachment foundation fixture",
        sync_visit=False,
    )["anomaly_id"]


class Phase2AttachmentRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.anomaly_id = _seed_anomaly(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_fresh_schema_has_phase2_attachment_contract(self) -> None:
        preview = repository.preview_anomaly_attachments_contract_v1(self.conn)

        self.assertTrue(preview["ready"])
        self.assertEqual([], preview["missing_columns"])
        columns = set(preview["columns"])
        self.assertTrue(
            {
                "file_type",
                "uploaded_by",
                "related_note_id",
                "related_action_id",
            }.issubset(columns)
        )

    def test_legacy_schema_preview_is_read_only_then_upgrade_is_idempotent(self) -> None:
        self.conn.execute("PRAGMA foreign_keys=OFF")
        self.conn.execute("DROP TABLE anomaly_attachments")
        self.conn.execute(
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
        self.conn.execute(
            "DELETE FROM migration_meta WHERE key = ?",
            ("anomaly_attachments_contract_v1",),
        )
        self.conn.commit()
        self.conn.execute("PRAGMA foreign_keys=ON")

        preview = repository.preview_anomaly_attachments_contract_v1(self.conn)
        self.assertFalse(preview["ready"])
        self.assertEqual(
            sorted(
                ["file_type", "uploaded_by", "related_action_id", "related_note_id"]
            ),
            sorted(preview["missing_columns"]),
        )
        self.assertIsNone(
            self.conn.execute(
                "SELECT value FROM migration_meta "
                "WHERE key = 'anomaly_attachments_contract_v1'"
            ).fetchone()
        )

        applied = repository.migrate_anomaly_attachments_contract_v1(
            self.conn, apply=True
        )
        self.assertTrue(applied["applied"])
        self.assertTrue(
            repository.preview_anomaly_attachments_contract_v1(self.conn)["ready"]
        )
        repeated = repository.migrate_anomaly_attachments_contract_v1(
            self.conn, apply=True
        )
        self.assertTrue(repeated["skipped"])

    def test_attachment_can_link_same_anomaly_note_and_canonical_action(self) -> None:
        note_id = repository.create_anomaly_analysis_note(
            self.conn,
            anomaly_id=self.anomaly_id,
            content="現場量測結果",
            evidence_type="FACT",
        )
        action_id = repository.create_case_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            action_type="CORRECTIVE_ACTION",
            description="補做驗證",
        )
        attachment_id = repository.create_anomaly_attachment(
            self.conn,
            anomaly_id=self.anomaly_id,
            file_name="measurement.pdf",
            stored_name="measurement.pdf",
            category="Evidence",
            file_type="application/pdf",
            uploaded_by="local_user",
            related_note_id=note_id,
            related_action_id=action_id,
        )

        rows = repository.list_anomaly_attachments(self.conn, self.anomaly_id)
        self.assertEqual([attachment_id], [row["id"] for row in rows])
        self.assertEqual("證據", rows[0]["category_label"])
        self.assertEqual(note_id, rows[0]["related_note_id"])
        self.assertEqual(action_id, rows[0]["related_action_id"])
        self.assertEqual("application/pdf", rows[0]["file_type"])
        self.assertEqual("local_user", rows[0]["uploaded_by"])

    def test_attachment_relationship_cannot_cross_anomaly_boundary(self) -> None:
        other_anomaly_id = _seed_anomaly(self.conn, "other")
        note_id = repository.create_anomaly_analysis_note(
            self.conn,
            anomaly_id=other_anomaly_id,
            content="另一案件紀錄",
        )
        with self.assertRaisesRegex(ValueError, "Related analysis note"):
            repository.create_anomaly_attachment(
                self.conn,
                anomaly_id=self.anomaly_id,
                file_name="cross-case.txt",
                related_note_id=note_id,
            )

    def test_attachment_metadata_rejects_path_components(self) -> None:
        with self.assertRaisesRegex(ValueError, "file name"):
            repository.create_anomaly_attachment(
                self.conn,
                anomaly_id=self.anomaly_id,
                file_name="..\\escape.pdf",
                stored_name="escape.pdf",
            )
        with self.assertRaisesRegex(ValueError, "file name"):
            repository.create_anomaly_attachment(
                self.conn,
                anomaly_id=self.anomaly_id,
                file_name="safe.pdf",
                stored_name="C:\\outside.pdf",
            )

    def test_overview_counts_unregistered_legacy_physical_file_once(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "attachments" / "anomaly"
            with patch.object(attachment_manager, "ANOMALY_ATTACHMENT_ROOT", root):
                folder = root / self.anomaly_id
                folder.mkdir(parents=True)
                (folder / "legacy-photo.png").write_bytes(b"legacy")
                card = repository.get_anomaly_overview_card(
                    self.conn, self.anomaly_id
                )
                self.assertEqual(1, card["attachment_count"])

                repository.create_anomaly_attachment(
                    self.conn,
                    anomaly_id=self.anomaly_id,
                    file_name="legacy-photo.png",
                    stored_name="legacy-photo.png",
                )
                repository.create_anomaly_attachment(
                    self.conn,
                    anomaly_id=self.anomaly_id,
                    file_name="legacy-photo.png",
                    stored_name="legacy-photo.png",
                )
                card_with_metadata = repository.get_anomaly_overview_card(
                    self.conn, self.anomaly_id
                )
                self.assertEqual(1, card_with_metadata["attachment_count"])

    def test_workbench_service_projects_legacy_file_and_missing_metadata(self) -> None:
        repository.create_anomaly_attachment(
            self.conn,
            anomaly_id=self.anomaly_id,
            file_name="registered-but-missing.pdf",
            stored_name="registered-but-missing.pdf",
        )
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "attachments" / "anomaly"
            folder = root / self.anomaly_id
            folder.mkdir(parents=True)
            (folder / "legacy-only.pdf").write_bytes(b"legacy")
            with (
                patch.object(attachment_manager, "ANOMALY_ATTACHMENT_ROOT", root),
                patch.object(
                    _anomaly_workbench_service,
                    "_open_conn",
                    return_value=self.conn,
                ),
            ):
                rows = _anomaly_workbench_service.list_attachments(self.anomaly_id)

        by_name = {row["file_name"]: row for row in rows}
        self.assertEqual("missing", by_name["registered-but-missing.pdf"]["storage_state"])
        self.assertFalse(by_name["registered-but-missing.pdf"]["legacy_physical"])
        self.assertEqual("present", by_name["legacy-only.pdf"]["storage_state"])
        self.assertTrue(by_name["legacy-only.pdf"]["legacy_physical"])

    def test_service_file_import_registers_metadata_and_compensates_on_failure(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "attachments" / "anomaly"
            source = Path(temp_dir) / "evidence.pdf"
            source.write_bytes(b"pdf-data")
            with (
                patch.object(attachment_manager, "ANOMALY_ATTACHMENT_ROOT", root),
                patch.object(
                    attachment_manager, "_sync_anomaly_markdown", return_value=None
                ),
                patch.object(
                    _anomaly_workbench_service,
                    "_open_conn",
                    return_value=self.conn,
                ),
            ):
                attachment_id = _anomaly_workbench_service.import_attachment_from_file(
                    anomaly_id=self.anomaly_id,
                    source_path=source,
                    category="Evidence",
                    uploaded_by="local_user",
                )
                rows = repository.list_anomaly_attachments(
                    self.conn, self.anomaly_id
                )
                self.assertEqual(attachment_id, rows[0]["id"])
                self.assertEqual(8, rows[0]["file_size"])
                self.assertEqual("application/pdf", rows[0]["file_type"])

                with patch.object(
                    repository,
                    "create_anomaly_attachment",
                    side_effect=RuntimeError("metadata failure"),
                ):
                    with self.assertRaisesRegex(RuntimeError, "metadata failure"):
                        _anomaly_workbench_service.import_attachment_from_file(
                            anomaly_id=self.anomaly_id,
                            source_path=source,
                            target_name="failed.pdf",
                        )
                self.assertFalse((root / self.anomaly_id / "failed.pdf").exists())

    def test_service_metadata_update_delete_and_audit_are_transactional(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "attachments" / "anomaly"
            source = Path(temp_dir) / "evidence.pdf"
            source.write_bytes(b"pdf-data")
            with (
                patch.object(attachment_manager, "ANOMALY_ATTACHMENT_ROOT", root),
                patch.object(
                    attachment_manager, "_sync_anomaly_markdown", return_value=None
                ),
                patch.object(
                    _anomaly_workbench_service,
                    "_open_conn",
                    return_value=self.conn,
                ),
            ):
                attachment_id = _anomaly_workbench_service.import_attachment_from_file(
                    anomaly_id=self.anomaly_id,
                    source_path=source,
                    category="Evidence",
                    description="原始量測",
                )
                note_id = repository.create_anomaly_analysis_note(
                    self.conn,
                    anomaly_id=self.anomaly_id,
                    content="量測紀錄",
                    evidence_type="FACT",
                )
                updated = _anomaly_workbench_service.update_attachment(
                    anomaly_id=self.anomaly_id,
                    attachment_id=attachment_id,
                    category="FA Report",
                    description="更新後說明",
                    revision="Rev A",
                    related_note_id=note_id,
                    actor_name="tester",
                )
                self.assertEqual("FA Report", updated["category"])
                self.assertEqual("Rev A", updated["revision"])
                self.assertTrue((root / self.anomaly_id / "evidence.pdf").exists())

                result = _anomaly_workbench_service.delete_attachment(
                    anomaly_id=self.anomaly_id,
                    attachment_id=attachment_id,
                    actor_name="tester",
                )
                self.assertTrue(result["physical_deleted"])
                self.assertFalse((root / self.anomaly_id / "evidence.pdf").exists())
                self.assertEqual([], repository.list_anomaly_attachments(self.conn, self.anomaly_id))
                audit_actions = [
                    row["action"]
                    for row in repository.list_anomaly_audit_logs(self.conn, self.anomaly_id)
                ]
                self.assertEqual(
                    ["ATTACHMENT_CREATED", "ATTACHMENT_UPDATED", "ATTACHMENT_DELETED"],
                    audit_actions,
                )


class Phase2AttachmentStorageTests(unittest.TestCase):
    def test_general_evidence_storage_accepts_documents_and_rejects_traversal(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "attachments" / "anomaly"
            source = Path(temp_dir) / "evidence.pdf"
            source.write_bytes(b"pdf")
            with patch.object(attachment_manager, "ANOMALY_ATTACHMENT_ROOT", root):
                stored = attachment_manager.import_single_attachment(
                    "anomaly-1", source
                )
                assert stored is not None
                self.assertEqual("evidence.pdf", stored.name)
                self.assertEqual(
                    [stored],
                    attachment_manager.list_stored_attachment_files("anomaly-1"),
                )
                self.assertIsNone(
                    attachment_manager.import_single_attachment(
                        "anomaly-1", source, "..\\outside.pdf"
                    )
                )
                self.assertFalse(
                    attachment_manager.delete_anomaly_attachment(
                        "anomaly-1", "..\\outside.pdf"
                    )
                )


class Phase2ItemsMappingDocTests(unittest.TestCase):
    def test_phase2_items_14_19_mapping_doc_exists_and_lists_six_items(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        mapping_doc = (
            repo_root
            / "docs/exec-plans/completed/2026-08-26-phase2-items-14-19-mapping.md"
        )
        self.assertTrue(mapping_doc.is_file())
        text = mapping_doc.read_text(encoding="utf-8")
        self.assertIn("mapping_type`: **design-derived**", text)
        for item_id in ("14", "15", "16", "17", "18", "19"):
            self.assertIn(f"| {item_id} |", text)

        from importlib import util

        audit_script = repo_root / "scripts/audit_phase2r_attachments.py"
        spec = util.spec_from_file_location(
            "audit_phase2r_attachments_test", audit_script
        )
        assert spec and spec.loader
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)
        payload = module.PHASE2_ITEMS_14_19
        self.assertEqual("design-derived", payload["mapping_type"])
        self.assertEqual(6, len(payload["items"]))
        self.assertEqual(
            {"14", "15", "16", "17", "18", "19"},
            {item["id"] for item in payload["items"]},
        )


if __name__ == "__main__":
    unittest.main()
