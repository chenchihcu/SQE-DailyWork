from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui.widgets.evidence_bullet_list_widget import EvidenceBulletListWidget, _RowPhoto


class EvidenceBulletListWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_delete_row_removes_photos(self) -> None:
        widget = EvidenceBulletListWidget()
        widget.set_anomaly_context("anomaly-test")
        row = widget.add_item("第一條")
        row._photos.append(
            _RowPhoto(path=Path("x.png"), stored_name="x.png", pending=False)
        )
        with mock.patch.object(
            row,
            "delete_all_photos",
            wraps=row.delete_all_photos,
        ) as delete_mock:
            widget.add_item("第二條")
            widget._remove_row(row)
            delete_mock.assert_called()
        widget.close()

    def test_save_photos_writes_links(self) -> None:
        widget = EvidenceBulletListWidget()
        row = widget._rows[0]
        row.set_text("爆板")
        scratch = Path("scratch") / f"evidence-{uuid4().hex}.png"
        scratch.write_bytes(b"png")
        row._photos.append(_RowPhoto(path=scratch, pending=True))
        anomaly_id = f"anomaly-{uuid4().hex}"
        stored = Path("scratch") / f"stored-{uuid4().hex}.png"
        with mock.patch(
            "ui.widgets.evidence_bullet_list_widget.attachment_manager.import_single_anomaly_attachment",
            return_value=stored,
        ), mock.patch(
            "ui.widgets.evidence_bullet_list_widget.set_problem_photo_links"
        ) as set_links:
            widget.save_photos_to_anomaly(anomaly_id)
            set_links.assert_called_once()
            links = set_links.call_args[0][1]
            self.assertEqual(1, links[stored.name])
        widget.close()
        if scratch.exists():
            scratch.unlink()


if __name__ == "__main__":
    unittest.main()
