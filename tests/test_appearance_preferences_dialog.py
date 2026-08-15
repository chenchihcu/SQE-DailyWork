from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QScrollArea, QTabWidget

from ui.appearance_preferences import AppearancePreferences
from ui.theme import apply_app_theme
from ui.widgets.appearance_preferences_dialog import AppearancePreferencesDialog


class AppearancePreferencesDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        apply_app_theme(cls.app)

    def tearDown(self) -> None:
        apply_app_theme(self.app)

    @patch("ui.widgets.appearance_preferences_dialog.load_application_preferences")
    def test_cancel_restores_opening_preferences_after_live_preview(self, load_preferences) -> None:
        opening = AppearancePreferences(density="compact", text_scale="standard", sidebar_density="compact")
        load_preferences.return_value = opening
        dialog = AppearancePreferencesDialog()
        dialog._density_buttons["comfortable"].click()
        dialog._text_scale_buttons["large"].click()
        dialog._table_density_buttons["comfortable"].click()
        dialog._contrast_mode_buttons["high"].click()
        self.app.processEvents()
        # High-contrast mode owns the final control-height override; comfortable
        # density remains readable without reintroducing the old 44px chrome.
        self.assertIn("min-height: 40px;", self.app.styleSheet())

        dialog.reject()

        self.assertIn("min-height: 34px;", self.app.styleSheet())
        self.assertNotIn("background: #000000", self.app.styleSheet())
        self.assertNotIn("font-size: 17px;", self.app.styleSheet())

    @patch("ui.widgets.appearance_preferences_dialog.save_application_preferences")
    @patch("ui.widgets.appearance_preferences_dialog.load_application_preferences")
    def test_reset_only_previews_and_save_persists_selected_values(self, load_preferences, save_preferences) -> None:
        load_preferences.return_value = AppearancePreferences(
            density="comfortable", text_scale="large", sidebar_density="compact", table_density="comfortable", contrast_mode="high"
        )
        dialog = AppearancePreferencesDialog()

        dialog.reset_button.click()
        self.assertFalse(save_preferences.called)
        self.assertTrue(dialog._density_buttons["standard"].isChecked())
        self.assertTrue(dialog._text_scale_buttons["standard"].isChecked())
        self.assertTrue(dialog._sidebar_density_buttons["standard"].isChecked())
        self.assertTrue(dialog._table_density_buttons["standard"].isChecked())
        self.assertTrue(dialog._contrast_mode_buttons["standard"].isChecked())

        dialog.save_button.click()
        save_preferences.assert_called_once_with(AppearancePreferences.default())

    @patch("ui.widgets.appearance_preferences_dialog.load_application_preferences")
    def test_controls_have_explicit_accessibility_and_fixed_action_order(self, load_preferences) -> None:
        load_preferences.return_value = AppearancePreferences.default()
        dialog = AppearancePreferencesDialog()
        self.assertEqual("顯示設定", dialog.windowTitle())
        self.assertTrue(dialog._density_buttons["standard"].accessibleName())
        self.assertTrue(dialog._density_buttons["standard"].accessibleDescription())
        self.assertTrue(dialog._text_scale_buttons["large"].accessibleName())
        self.assertTrue(dialog._text_scale_buttons["large"].accessibleDescription())
        self.assertTrue(dialog._sidebar_density_buttons["compact"].accessibleName())
        self.assertTrue(dialog._table_density_buttons["comfortable"].accessibleName())
        self.assertTrue(dialog._contrast_mode_buttons["high"].accessibleName())
        self.assertTrue(dialog.save_button.accessibleName())
        self.assertTrue(dialog.cancel_button.accessibleName())

    @patch("ui.widgets.appearance_preferences_dialog.load_application_preferences")
    def test_uses_finite_preference_tabs_without_a_whole_dialog_scroll_body(self, load_preferences) -> None:
        load_preferences.return_value = AppearancePreferences.default()
        dialog = AppearancePreferencesDialog()

        self.assertEqual([], dialog.findChildren(QScrollArea))
        self.assertIsInstance(dialog.preference_tabs, QTabWidget)
        self.assertEqual(
            ["外觀與密度", "視覺與色彩", "系統與預設"],
            [dialog.preference_tabs.tabText(index) for index in range(dialog.preference_tabs.count())],
        )
        self.assertEqual(3, dialog.preference_tabs.count())



if __name__ == "__main__":
    unittest.main()
