from __future__ import annotations

import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui.widgets.anomaly_evidence_thumbnail_strip import (
    AnomalyEvidenceThumbnailStrip,
    _image_attachments,
    _is_field_photo_attachment,
)


class AnomalyEvidenceThumbnailStripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_field_photo_filter_includes_legacy_and_ng_photo(self) -> None:
        self.assertTrue(
            _is_field_photo_attachment(
                {"legacy_physical": True, "category": "Other"}
            )
        )
        self.assertTrue(
            _is_field_photo_attachment({"category": "NG Photo"})
        )
        self.assertFalse(
            _is_field_photo_attachment(
                {"category": "Corrective Action Evidence"}
            )
        )

    def test_image_attachments_skips_non_images(self) -> None:
        rows = [
            {
                "storage_state": "present",
                "legacy_physical": True,
                "category": "Other",
                "stored_name": "notes.txt",
            },
            {
                "storage_state": "present",
                "legacy_physical": True,
                "category": "Other",
                "stored_name": "photo.png",
            },
        ]
        with mock.patch(
            "ui.widgets.anomaly_evidence_thumbnail_strip._anomaly_workbench_service.list_attachments",
            return_value=rows,
        ), mock.patch(
            "ui.widgets.anomaly_evidence_thumbnail_strip.attachment_manager.stored_attachment_path",
            side_effect=lambda _aid, name: mock.Mock(is_file=lambda: name.endswith(".png")),
        ):
            images = _image_attachments("anomaly-1")
        self.assertEqual(1, len(images))
        self.assertEqual("photo.png", images[0]["stored_name"])

    def test_strip_shows_empty_state_without_anomaly(self) -> None:
        strip = AnomalyEvidenceThumbnailStrip()
        strip.set_anomaly("")
        self.assertEqual("現場照片", strip.title_label.text())
        self.assertFalse(strip.grid_host.isVisibleTo(strip))
        self.assertTrue(strip.empty_label.isVisibleTo(strip))
        strip.close()


if __name__ == "__main__":
    unittest.main()
