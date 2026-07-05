import os
import unittest
from pathlib import Path
from uuid import uuid4
from PySide6.QtWidgets import QApplication, QListWidgetItem
from ui.widgets.defect_form_shim import AttachmentEditor
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

    def test_save_to_anomaly_records_rename_failures(self) -> None:
        """Regression test for audit finding A12: a failed on-disk rename
        must be surfaced via _last_rename_failures instead of failing
        silently, and the list must reset on each save_to_anomaly call."""
        img1 = self._make_img("img1.png")
        attachment_manager.import_anomaly_attachments(self.anomaly_id, [img1])
        self.editor.load_existing_attachments(self.anomaly_id)

        # Force a stored-path/display-name mismatch directly (mirrors how
        # this test file already manipulates item data for the "pending add"
        # case above), since save_to_anomaly's rename branch triggers on
        # exactly this divergence. Block signals so this raw setData() call
        # doesn't route through _on_item_changed, which would re-derive the
        # filename from item.text() and undo the forced mismatch.
        item1 = self.editor.list_widget.item(0)
        self.editor.list_widget.blockSignals(True)
        try:
            item1.setData(0x0101, "renamed.png")  # Qt.UserRole + 1
        finally:
            self.editor.list_widget.blockSignals(False)

        original_rename = attachment_manager.rename_anomaly_attachment
        self.assertEqual(self.editor._last_rename_failures, [])
        try:
            attachment_manager.rename_anomaly_attachment = lambda *a, **k: False
            self.editor.save_to_anomaly(self.anomaly_id)
            self.assertIn("renamed.png", self.editor._last_rename_failures)
        finally:
            attachment_manager.rename_anomaly_attachment = original_rename

        # A subsequent successful save must clear the stale failure list.
        self.editor.load_existing_attachments(self.anomaly_id)
        self.editor.save_to_anomaly(self.anomaly_id)
        self.assertEqual(self.editor._last_rename_failures, [])

    def test_rename_collision_within_session_gets_numeric_suffix(self) -> None:
        """Regression test for audit finding A13: renaming one attachment to
        another item's display name within the same editing session must
        auto-dedupe with a numeric suffix instead of silently letting two
        items share one display name (which corrupts the caption map and the
        eventual on-disk rename)."""
        img1 = self._make_img("first.png")
        img2 = self._make_img("second.png")
        attachment_manager.import_anomaly_attachments(self.anomaly_id, [img1, img2])
        self.editor.load_existing_attachments(self.anomaly_id)

        names = {
            self.editor.list_widget.item(i).data(0x0101)
            for i in range(self.editor.list_widget.count())
        }
        self.assertEqual({"first.png", "second.png"}, names)

        # Rename "second.png" to collide with "first.png".
        target = next(
            self.editor.list_widget.item(i)
            for i in range(self.editor.list_widget.count())
            if self.editor.list_widget.item(i).data(0x0101) == "second.png"
        )
        target.setText("first.png")
        self.editor._on_item_changed(target)

        final_names = [
            self.editor.list_widget.item(i).data(0x0101)
            for i in range(self.editor.list_widget.count())
        ]
        self.assertEqual(len(final_names), len(set(final_names)))
        self.assertIn("first.png", final_names)
        self.assertIn("first_2.png", final_names)

if __name__ == "__main__":
    unittest.main()
