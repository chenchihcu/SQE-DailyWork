from __future__ import annotations

import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QFrame, QListWidget

from ui.main_window import MainWindow
from ui.sidebar_nav import SidebarNav
from ui.theme import apply_app_theme
from ui.widgets.defect_form_widget import (
    AttachmentEditor,
    TECH_TRANSFER_STATE_NA,
    TECH_TRANSFER_STATE_YES,
    TechTransferCard,
)
from ncr.ui.ui_style import create_status_badge as create_ncr_status_badge


class ColorPolishUiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        apply_app_theme(cls.app)


    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            cls.app.quit()

    def test_main_window_exposes_color_polish_surfaces(self) -> None:
        window = MainWindow()
        try:
            # Sidebar navigation replaces old QTabWidget
            self.assertIsNotNone(window.sidebar)
            self.assertIsInstance(window.sidebar, SidebarNav)
            self.assertEqual(12, len(window.sidebar._buttons))
            self.assertIsNone(window.findChild(QFrame, "HomeKpiPanel"))
            self.assertIsNone(window.findChild(QFrame, "HomeQuickActionPanel"))
            self.assertIsNotNone(window.findChild(QFrame, "MasterInlineToolbar"))
            kpi_cards = [
                frame
                for frame in window.findChildren(QFrame)
                if frame.property("role") == "kpiCard"
            ]
            self.assertEqual(0, len(kpi_cards))
        finally:
            window.close()

    def test_mitcorp_app_icon_asset_loads_in_qt(self) -> None:
        logo_path = Path("src/ui/assets/mitcorp_logo.png")

        self.assertTrue(logo_path.is_file())
        self.assertFalse(QPixmap(str(logo_path)).isNull())

    def test_attachment_editor_uses_preview_list_surface(self) -> None:
        editor = AttachmentEditor()
        try:
            preview_list = editor.findChild(QListWidget, "AttachmentPreviewList")
            self.assertIsNotNone(preview_list)
        finally:
            editor.deleteLater()

    def test_tech_transfer_card_sets_tri_state_property(self) -> None:
        card = TechTransferCard("tech_transfer_doc", "作業標準書")
        try:
            card.set_state(TECH_TRANSFER_STATE_YES)
            self.assertEqual(card.property("state"), "selected")
            card.set_state(TECH_TRANSFER_STATE_NA)
            self.assertEqual(card.property("state"), "na")
        finally:
            card.deleteLater()

    def test_ncr_status_badge_uses_shared_role_and_tone(self) -> None:
        badge = create_ncr_status_badge("處理中")
        try:
            self.assertEqual(badge.property("role"), "statusBadge")
            self.assertEqual(badge.property("tone"), "pending")
        finally:
            badge.deleteLater()


if __name__ == "__main__":
    unittest.main()
