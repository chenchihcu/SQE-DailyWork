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
            density="comfortable",
            text_scale="large",
            sidebar_density="compact",
            table_density="comfortable",
            contrast_mode="high",
            default_responsible_person="測試者",
            default_anomaly_category="零件缺件",
            default_sync_visit=False,
            default_due_days=14,
            default_visit_time_slot="上午",
            default_export_dir="D:/Reports",
            export_completion_action="open_folder",
            report_organization_header="品保部",
            export_include_charts=False,
            backup_retention_count=20,
            confirm_on_delete=False,
        )
        dialog = AppearancePreferencesDialog()

        dialog.reset_button.click()
        self.assertFalse(save_preferences.called)
        self.assertTrue(dialog._density_buttons["standard"].isChecked())
        self.assertTrue(dialog._text_scale_buttons["standard"].isChecked())
        self.assertTrue(dialog._sidebar_density_buttons["standard"].isChecked())
        self.assertTrue(dialog._table_density_buttons["standard"].isChecked())
        self.assertTrue(dialog._double_click_buttons["menu"].isChecked())
        self.assertTrue(dialog._search_mode_buttons["live"].isChecked())
        self.assertTrue(dialog._stats_span_buttons[6].isChecked())
        self.assertTrue(dialog._pareto_cutoff_checkbox.isChecked())
        self.assertEqual("", dialog._responsible_person_input.text())
        self.assertEqual("", dialog._anomaly_category_combo.currentText())
        self.assertTrue(dialog._sync_visit_checkbox.isChecked())
        self.assertTrue(dialog._due_days_buttons[7].isChecked())
        self.assertTrue(dialog._visit_time_slot_buttons["下午"].isChecked())
        self.assertEqual("", dialog._export_dir_input.text())
        self.assertTrue(dialog._export_action_buttons["open_file"].isChecked())
        self.assertEqual("SQE 供應商品質工程部", dialog._report_header_input.text())
        self.assertTrue(dialog._export_charts_checkbox.isChecked())
        self.assertTrue(dialog._retention_count_buttons[10].isChecked())
        self.assertTrue(dialog._confirm_delete_checkbox.isChecked())

        dialog.save_button.click()
        save_preferences.assert_called_once_with(AppearancePreferences.default())

    @patch("ui.widgets.appearance_preferences_dialog.load_application_preferences")
    def test_controls_have_explicit_accessibility_and_fixed_action_order(self, load_preferences) -> None:
        load_preferences.return_value = AppearancePreferences.default()
        dialog = AppearancePreferencesDialog()
        self.assertEqual("系統與顯示設定", dialog.windowTitle())
        self.assertTrue(dialog._density_buttons["standard"].accessibleName())
        self.assertTrue(dialog._density_buttons["standard"].accessibleDescription())
        self.assertTrue(dialog._text_scale_buttons["large"].accessibleName())
        self.assertTrue(dialog._text_scale_buttons["large"].accessibleDescription())
        self.assertTrue(dialog._sidebar_density_buttons["compact"].accessibleName())
        self.assertTrue(dialog._table_density_buttons["comfortable"].accessibleName())
        self.assertTrue(dialog._contrast_mode_buttons["high"].accessibleName())
        self.assertTrue(dialog._double_click_buttons["menu"].accessibleName())
        self.assertTrue(dialog._search_mode_buttons["live"].accessibleName())
        self.assertTrue(dialog._stats_span_buttons[6].accessibleName())
        self.assertTrue(dialog._pareto_cutoff_checkbox.accessibleName())
        self.assertTrue(dialog._responsible_person_input.accessibleName())
        self.assertTrue(dialog._anomaly_category_combo.accessibleName())
        self.assertTrue(dialog._sync_visit_checkbox.accessibleName())
        self.assertTrue(dialog._export_dir_input.accessibleName())
        self.assertTrue(dialog._browse_dir_button.accessibleName())
        self.assertTrue(dialog._report_header_input.accessibleName())
        self.assertTrue(dialog._export_charts_checkbox.accessibleName())
        self.assertTrue(dialog._confirm_delete_checkbox.accessibleName())
        self.assertTrue(dialog.save_button.accessibleName())
        self.assertTrue(dialog.cancel_button.accessibleName())

    @patch("ui.widgets.appearance_preferences_dialog.load_application_preferences")
    def test_uses_five_preference_tabs_without_a_whole_dialog_scroll_body(self, load_preferences) -> None:
        load_preferences.return_value = AppearancePreferences.default()
        dialog = AppearancePreferencesDialog()

        self.assertEqual([], dialog.findChildren(QScrollArea))
        self.assertIsInstance(dialog.preference_tabs, QTabWidget)
        self.assertEqual(
            ["外觀主題", "視覺表格", "表單業務預設", "匯出與報告", "系統與備份"],
            [dialog.preference_tabs.tabText(index) for index in range(dialog.preference_tabs.count())],
        )
        self.assertEqual(5, dialog.preference_tabs.count())


if __name__ == "__main__":
    unittest.main()

