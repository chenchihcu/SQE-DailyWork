import unittest
from pathlib import Path
from uuid import uuid4
from services import attachment_manager

class AttachmentDeletionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.anomaly_id = f"test-del-{uuid4().hex}"
        self.target_dir = attachment_manager.ANOMALY_ATTACHMENT_ROOT / self.anomaly_id
        self.scratch = Path("scratch") / f"src-{uuid4().hex}"
        self.scratch.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        if self.target_dir.exists():
            for p in self.target_dir.iterdir(): p.unlink()
            self.target_dir.rmdir()
        if self.scratch.exists():
            for p in self.scratch.iterdir(): p.unlink()
            self.scratch.rmdir()

    def _make_img(self, name: str) -> Path:
        p = self.scratch / name
        p.write_bytes(b"img-data")
        return p

    def test_delete_attachment_removes_file_and_caption(self) -> None:
        img = self._make_img("to_delete.png")
        attachment_manager.import_anomaly_attachments(self.anomaly_id, [img])
        attachment_manager.set_anomaly_captions(self.anomaly_id, {"to_delete.png": "Some caption"})
        
        self.assertTrue((self.target_dir / "to_delete.png").exists())
        self.assertEqual(attachment_manager.get_anomaly_captions(self.anomaly_id), {"to_delete.png": "Some caption"})
        
        # Act
        res = attachment_manager.delete_anomaly_attachment(self.anomaly_id, "to_delete.png")
        
        # Assert
        self.assertTrue(res)
        self.assertFalse((self.target_dir / "to_delete.png").exists())
        self.assertEqual(attachment_manager.get_anomaly_captions(self.anomaly_id), {})

    def test_delete_missing_returns_false(self) -> None:
        self.assertFalse(attachment_manager.delete_anomaly_attachment(self.anomaly_id, "no.png"))

if __name__ == "__main__":
    unittest.main()
