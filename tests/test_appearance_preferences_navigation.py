from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui.appearance_preferences import AppearancePreferences
from ui.main_window import (
    APPEARANCE_SETTINGS_PAGE_INDEX,
    EVENT_PAGE_INDEX,
    MainWindow,
)
from ui.sidebar_nav import (
    ACTION_OPEN_APPEARANCE_REDESIGN,
    PAGE_APPEARANCE_SETTINGS,
    PAGE_EVENT_QUERY,
    SidebarNav,
)
from ui.theme import apply_app_theme
from ui.widgets.appearance_preferences_dialog import AppearancePreferencesPage


class AppearancePreferencesNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        pass  # style initialized once in tests/__init__.py
        apply_app_theme(cls.app)

    def test_system_sidebar_has_the_only_global_appearance_entry(self) -> None:
        sidebar = SidebarNav()
        action = ("page", PAGE_APPEARANCE_SETTINGS)
        button = sidebar.button_for_action(action)

        self.assertIsNotNone(button)
        assert button is not None
        self.assertEqual("顯示設定", button.accessibleName())
        self.assertEqual(action, button.action)
        self.assertEqual(("page", PAGE_EVENT_QUERY), sidebar._active_action)

        emitted: list[object] = []
        sidebar.nav_activated.connect(emitted.append)
        button.click()
        self.assertEqual([action], emitted)
        self.assertEqual(("page", PAGE_EVENT_QUERY), sidebar._active_action)

    def test_legacy_appearance_command_keeps_compatibility_route(self) -> None:
        class _CommandHost:
            opened = False

            def open_appearance_preferences(self) -> None:
                self.opened = True

        host = _CommandHost()
        MainWindow._on_nav_activated(host, ("command", ACTION_OPEN_APPEARANCE_REDESIGN))
        self.assertTrue(host.opened)

    @patch(
        "ui.widgets.appearance_preferences_dialog.load_application_preferences",
        return_value=AppearancePreferences.default(),
    )
    @patch(
        "ui.main_window.load_application_preferences",
        return_value=AppearancePreferences.default(),
    )
    def test_appearance_navigation_opens_an_embedded_active_page(
        self,
        _load_main_preferences,
        _load_page_preferences,
    ) -> None:
        window = MainWindow()
        self.addCleanup(window.close)
        window.resize(1024, 680)
        window.show()
        self.app.processEvents()
        window.sidebar._nav_scroll.setFixedHeight(300)
        action = ("page", PAGE_APPEARANCE_SETTINGS)
        button = window.sidebar.button_for_action(action)
        self.assertIsNotNone(button)
        assert button is not None

        button.click()
        self.app.processEvents()

        self.assertEqual(APPEARANCE_SETTINGS_PAGE_INDEX, window.stack.currentIndex())
        self.assertEqual(action, window.sidebar._active_action)
        lazy_page = window.stack.currentWidget()
        page = lazy_page.ensure_widget()
        self.assertIsInstance(page, AppearancePreferencesPage)
        self.assertIs(page.window(), window)
        self.assertGreater(window.sidebar._nav_scroll.verticalScrollBar().value(), 0)
        self.assertTrue(button.isVisible())

    @patch(
        "ui.main_window.load_application_preferences",
        return_value=AppearancePreferences.default(),
    )
    def test_main_window_defaults_to_event_management_page(
        self,
        _load_preferences,
    ) -> None:
        window = MainWindow()
        self.addCleanup(window.close)
        self.assertEqual(EVENT_PAGE_INDEX, window.stack.currentIndex())


if __name__ == "__main__":
    unittest.main()
