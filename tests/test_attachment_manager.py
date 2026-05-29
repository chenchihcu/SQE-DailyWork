from __future__ import annotations

import unittest
from pathlib import Path
from uuid import uuid4

from database.connection import DATA_DIR, PROJECT_ROOT
from services import attachment_manager


class AttachmentManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = Path("scratch") / f"attach_src_{uuid4().hex}"
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.anomaly_id = f"anomaly-{uuid4().hex}"
        self.target_dir = (
            attachment_manager.ANOMALY_ATTACHMENT_ROOT / self.anomaly_id
        )
        self._created: list[Path] = []

    def tearDown(self) -> None:
        for path in self._created:
            if path.exists():
                path.unlink()
        if self.target_dir.exists():
            for child in self.target_dir.iterdir():
                child.unlink()
            self.target_dir.rmdir()
        if self.scratch.exists():
            for child in self.scratch.iterdir():
                if child.is_file():
                    child.unlink()
            self.scratch.rmdir()

    def _make_source(self, name: str, payload: bytes = b"x") -> Path:
        path = self.scratch / name
        path.write_bytes(payload)
        self._created.append(path)
        return path

    def test_attachment_root_is_fixed_under_project_data_dir(self) -> None:
        self.assertTrue(DATA_DIR.is_absolute())
        self.assertEqual(PROJECT_ROOT / "data", DATA_DIR)
        self.assertEqual(
            DATA_DIR / "attachments" / "anomaly",
            attachment_manager.ANOMALY_ATTACHMENT_ROOT,
        )

    def test_import_filters_disallowed_suffixes(self) -> None:
        keep = self._make_source("photo.jpg")
        skip = self._make_source("notes.txt")

        stored = attachment_manager.import_anomaly_attachments(
            self.anomaly_id, [keep, skip]
        )

        self.assertEqual(1, len(stored))
        self.assertEqual("photo.jpg", stored[0].name)
        listed = attachment_manager.list_anomaly_attachments(self.anomaly_id)
        self.assertEqual([stored[0]], listed)

    def test_import_handles_duplicate_names(self) -> None:
        first = self._make_source("photo.jpg", b"a")
        attachment_manager.import_anomaly_attachments(self.anomaly_id, [first])
        # Import the same source again — destination "photo.jpg" already exists,
        # so the manager should pick a non-clashing name.
        attachment_manager.import_anomaly_attachments(self.anomaly_id, [first])

        listed = attachment_manager.list_anomaly_attachments(self.anomaly_id)
        names = sorted(p.name for p in listed)
        self.assertEqual(["photo (1).jpg", "photo.jpg"], names)

    def test_list_returns_empty_for_unknown_anomaly(self) -> None:
        self.assertEqual(
            [],
            attachment_manager.list_anomaly_attachments(f"missing-{uuid4().hex}"),
        )

    def test_list_skips_disallowed_suffixes_in_directory(self) -> None:
        self.target_dir.mkdir(parents=True, exist_ok=True)
        (self.target_dir / "photo.png").write_bytes(b"p")
        (self.target_dir / "stray.txt").write_bytes(b"t")

        listed = attachment_manager.list_anomaly_attachments(self.anomaly_id)
        names = [p.name for p in listed]
        self.assertEqual(["photo.png"], names)


if __name__ == "__main__":
    unittest.main()
