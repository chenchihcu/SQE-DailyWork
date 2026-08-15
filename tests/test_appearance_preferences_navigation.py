from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.sidebar_nav import ACTION_OPEN_APPEARANCE_REDESIGN, PAGE_HOME, SidebarNav
from ui.theme import apply_app_theme


class AppearancePreferencesNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        apply_app_theme(cls.app)

    def test_system_sidebar_has_the_only_global_appearance_entry(self) -> None:
        sidebar = SidebarNav()
        action = ("command", ACTION_OPEN_APPEARANCE_REDESIGN)
        button = sidebar.button_for_action(action)

        self.assertIsNotNone(button)
        assert button is not None
        self.assertEqual("顯示設定", button.accessibleName())
        self.assertEqual(action, button.action)
        self.assertEqual(("page", PAGE_HOME), sidebar._active_action)

        emitted: list[object] = []
        sidebar.nav_activated.connect(emitted.append)
        button.click()
        self.assertEqual([action], emitted)
        self.assertEqual(("page", PAGE_HOME), sidebar._active_action)

    def test_appearance_command_does_not_use_page_leave_guard(self) -> None:
        class _CommandHost:
            opened = False

            def open_appearance_preferences(self) -> None:
                self.opened = True

        host = _CommandHost()
        MainWindow._on_nav_activated(host, ("command", ACTION_OPEN_APPEARANCE_REDESIGN))
        self.assertTrue(host.opened)


if __name__ == "__main__":
    unittest.main()
