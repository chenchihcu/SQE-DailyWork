from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SQE_TESTING", "1")

from PySide6.QtWidgets import QApplication, QPushButton

from services.event import _anomaly_workbench_service
from ui.widgets.anomaly_attachment_panel import EvidenceAttachmentPanel


class EvidenceAttachmentPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_upload_form_uses_evidence_contract_and_calls_service(self) -> None:
        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "measurement.pdf"
            source.write_bytes(b"evidence")
            with (
                patch.object(_anomaly_workbench_service, "list_attachment_notes", return_value=[]),
                patch.object(_anomaly_workbench_service, "list_attachment_actions", return_value=[]),
                patch.object(_anomaly_workbench_service, "list_attachments", return_value=[]),
                patch.object(
                    _anomaly_workbench_service,
                    "import_attachment_from_file",
                    return_value="attachment-1",
                ) as import_mock,
                patch(
                    "ui.widgets.anomaly_attachment_panel.QFileDialog.getOpenFileName",
                    return_value=(str(source), ""),
                ),
            ):
                panel = EvidenceAttachmentPanel()
                panel.set_anomaly("anomaly-1")
                panel._choose_file()
                self.assertTrue(panel.upload_button.isEnabled())
                panel._upload()
                import_mock.assert_called_once()
                self.assertEqual("Evidence", import_mock.call_args.kwargs["category"])
                self.assertEqual("anomaly-1", import_mock.call_args.kwargs["anomaly_id"])
                panel.close()

    def test_registered_rows_have_edit_and_delete_but_legacy_rows_are_read_only(self) -> None:
        rows = [
            {
                "id": "att-1",
                "file_name": "registered.pdf",
                "category": "Evidence",
                "category_label": "證據",
                "storage_state": "present",
                "legacy_physical": False,
                "file_size": 10,
            },
            {
                "id": "",
                "file_name": "legacy.pdf",
                "category": "Other",
                "category_label": "其他",
                "storage_state": "present",
                "legacy_physical": True,
                "file_size": 11,
            },
        ]
        with (
            patch.object(_anomaly_workbench_service, "list_attachment_notes", return_value=[]),
            patch.object(_anomaly_workbench_service, "list_attachment_actions", return_value=[]),
            patch.object(_anomaly_workbench_service, "list_attachments", return_value=rows),
        ):
            panel = EvidenceAttachmentPanel()
            panel.set_anomaly("anomaly-1")
            self.assertEqual(2, panel.list_layout.count() - 1)  # trailing stretch
            registered = panel._build_row(rows[0])
            legacy = panel._build_row(rows[1])
            self.assertEqual(2, len(registered.findChildren(QPushButton)))
            self.assertEqual([], legacy.findChildren(QPushButton))
            panel.close()


if __name__ == "__main__":
    unittest.main()
