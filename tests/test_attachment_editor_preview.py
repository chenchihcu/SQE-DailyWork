from __future__ import annotations

import os
import unittest
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication, QListView

from ui.theme import apply_app_theme
from ui.widgets import defect_form_widget
from ui.widgets.defect_form_widget import (
    ATTACHMENT_ITEM_SIZE,
    AttachmentEditor,
)


class AttachmentEditorPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        apply_app_theme(cls.app)


    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            cls.app.quit()

    def setUp(self) -> None:
        self.scratch = Path("scratch") / f"attach_preview_{uuid4().hex}"
        self.scratch.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        if self.scratch.exists():
            for child in self.scratch.iterdir():
                if child.is_file():
                    child.unlink()
            self.scratch.rmdir()

    def test_pick_adds_thumbnail_preview_item(self) -> None:
        source = self.scratch / "現場照片.png"
        pixmap = QPixmap(12, 8)
        pixmap.fill(QColor("#0274BE"))
        self.assertTrue(pixmap.save(str(source), "PNG"))
        editor = AttachmentEditor()
        original_get_open_file_names = defect_form_widget.QFileDialog.getOpenFileNames

        def fake_get_open_file_names(*_args: object) -> tuple[list[str], str]:
            return [str(source)], "Images (*.png)"

        try:
            defect_form_widget.QFileDialog.getOpenFileNames = fake_get_open_file_names
            editor._pick()

            self.assertEqual(QListView.ViewMode.IconMode, editor.list_widget.viewMode())
            self.assertEqual(1, editor.list_widget.count())
            item = editor.list_widget.item(0)
            self.assertEqual("現場照片.png", item.text())
            self.assertEqual(ATTACHMENT_ITEM_SIZE, item.sizeHint())
            preview = item.icon().pixmap(editor.list_widget.iconSize())
            self.assertFalse(preview.isNull())
        finally:
            defect_form_widget.QFileDialog.getOpenFileNames = original_get_open_file_names
            editor.close()


if __name__ == "__main__":
    unittest.main()
