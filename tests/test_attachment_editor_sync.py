import os
import unittest
from pathlib import Path
from uuid import uuid4
from PySide6.QtWidgets import QApplication, QListWidgetItem
from ui.widgets.defect_form_widget import AttachmentEditor
from services import attachment_manager

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

class AttachmentEditorSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])


    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            cls.app.quit()

    def setUp(self) -> None:
        self.anomaly_id = f"test-sync-{uuid4().hex}"
        self.target_dir = attachment_manager.ANOMALY_ATTACHMENT_ROOT / self.anomaly_id
        self.scratch = Path("scratch") / f"src-{uuid4().hex}"
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.editor = AttachmentEditor()

    def tearDown(self) -> None:
        self.editor.close()
        if self.target_dir.exists():
            for p in self.target_dir.iterdir(): p.unlink()
            self.target_dir.rmdir()
        if self.scratch.exists():
            for p in self.scratch.iterdir(): p.unlink()
            self.scratch.rmdir()

    def _make_img(self, name: str) -> Path:
        p = self.scratch / name
        p.write_bytes(b"data")
        return p

    def test_load_existing_attachments_populates_list(self) -> None:
        img = self._make_img("existing.png")
        attachment_manager.import_anomaly_attachments(self.anomaly_id, [img])
        attachment_manager.set_anomaly_captions(self.anomaly_id, {"existing.png": "Cap"})
        
        self.editor.load_existing_attachments(self.anomaly_id)
        
        self.assertEqual(self.editor.list_widget.count(), 1)
        item = self.editor.list_widget.item(0)
        self.assertEqual(item.text(), "existing.png — Cap")

    def test_sync_save_handles_deletions_and_updates(self) -> None:
        img1 = self._make_img("img1.png")
        img2 = self._make_img("img2.png")
        attachment_manager.import_anomaly_attachments(self.anomaly_id, [img1, img2])
        attachment_manager.set_anomaly_captions(self.anomaly_id, {"img1.png": "C1", "img2.png": "C2"})
        
        self.editor.load_existing_attachments(self.anomaly_id)
        
        # 1. Remove img1
        item1 = self.editor.list_widget.item(0)
        item1.setSelected(True)
        self.editor._remove_selected()
        
        # 2. Add img3
        img3 = self._make_img("img3.png")
        self.editor._pending_attachments.append(img3)
        item3 = QListWidgetItem("img3.png")
        item3.setData(0x0100, str(img3)) # Qt.UserRole
        item3.setData(0x0101, "img3.png") # UserRole + 1
        self.editor.list_widget.addItem(item3)
        self.editor._pending_captions[str(img3)] = "C3"
        
        # 3. Update img2 caption
        item2 = self.editor.list_widget.item(0) # img2 was the second item, now first
        item2.setText("img2.png — Updated")
        self.editor._on_item_changed(item2)
        
        # 4. Save
        self.editor.save_to_anomaly(self.anomaly_id)
        
        # 5. Verify Disk
        files = [p.name for p in attachment_manager.list_anomaly_attachments(self.anomaly_id)]
        self.assertNotIn("img1.png", files)
        self.assertIn("img2.png", files)
        self.assertIn("img3.png", files)
        
        caps = attachment_manager.get_anomaly_captions(self.anomaly_id)
        self.assertEqual(caps.get("img2.png"), "Updated")
        self.assertEqual(caps.get("img3.png"), "C3")

if __name__ == "__main__":
    unittest.main()
