from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox, QScrollArea

from ui.appearance_preferences import AppearancePreferences
from ui.theme import apply_app_theme
from ui.widgets.appearance_preferences_dialog import AppearancePreferencesPage
from ui.widgets.appearance_preferences_dialog import _ResponsivePreferenceColumns


class AppearancePreferencesPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        # style initialized once in tests/__init__.py
        apply_app_theme(cls.app)

    @property
    def current_app(self) -> QApplication:
        return getattr(self, "app", None) or QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        apply_app_theme(self.current_app)

    @patch("ui.widgets.appearance_preferences_dialog.load_application_preferences")
    def test_cancel_restores_opening_preferences_after_live_preview(self, load_preferences) -> None:
        opening = AppearancePreferences(density="compact", text_scale="standard", sidebar_density="compact")
        load_preferences.return_value = opening
        page = AppearancePreferencesPage()
        page._density_buttons["comfortable"].click()
        page._text_scale_buttons["large"].click()
        page._table_density_buttons["comfortable"].click()
        page._contrast_mode_buttons["high"].click()
        self.current_app.processEvents()

        self.assertIn("min-height: 40px;", self.current_app.styleSheet())
        self.assertTrue(page.has_unsaved_changes())

        page._discard_changes()

        self.assertIn("min-height: 34px;", self.current_app.styleSheet())
        self.assertNotIn("background: #000000", self.current_app.styleSheet())
        self.assertNotIn("font-size: 17px;", self.current_app.styleSheet())
        self.assertFalse(page.has_unsaved_changes())
        self.assertFalse(page.feedback_label.isHidden())

    @patch("ui.widgets.appearance_preferences_dialog.is_automated_runtime", return_value=False)
    @patch("ui.widgets.appearance_preferences_dialog.QMessageBox.question")
    @patch("ui.widgets.appearance_preferences_dialog.load_application_preferences")
    def test_can_leave_blocks_or_discards_unsaved_preview(
        self,
        load_preferences,
        question,
        _automated_runtime,
    ) -> None:
        opening = AppearancePreferences(density="compact")
        load_preferences.return_value = opening
        page = AppearancePreferencesPage()
        page._density_buttons["comfortable"].click()

        question.return_value = QMessageBox.StandardButton.No
        self.assertFalse(page.can_leave())
        self.assertTrue(page.has_unsaved_changes())

        question.return_value = QMessageBox.StandardButton.Yes
        self.assertTrue(page.can_leave())
        self.assertFalse(page.has_unsaved_changes())

    @patch("ui.widgets.appearance_preferences_dialog.save_application_preferences")
    @patch("ui.widgets.appearance_preferences_dialog.load_application_preferences")
    def test_reset_only_previews_and_save_persists_selected_values(self, load_preferences, save_preferences) -> None:
        load_preferences.return_value = AppearancePreferences(
            density="comfortable",
            text_scale="large",
            sidebar_density="compact",
            table_density="comfortable",
            contrast_mode="high",
            accent_color="rose",
            theme_mode="dark_slate",
            cjk_font_family_preference="noto_sans",
            window_geometry_mode="maximized",
            status_bar_detail_level="detailed",
            highlight_overdue_rows=False,
            date_format_display="YYYY/MM/DD",
            table_auto_scroll_to_top=False,
            table_hover_highlight=False,
            table_text_wrapping="wrap",
            default_list_sort_field="date_desc",
            default_responsible_person="測試者",
            default_closer_name="陳主管",
            default_anomaly_category="零件缺件",
            default_due_days=14,
            default_anomaly_source="進料檢驗 (IQC)",
            default_severity_level="重大",
            default_defect_disposition="特採",
            auto_fill_anomaly_no_on_date_change=False,
            auto_uppercase_part_no=False,
            default_export_dir="D:/Reports",
            export_completion_action="open_folder",
            report_organization_header="品保部",
            export_include_charts=False,
            export_file_naming_rule="detailed",
            pdf_page_orientation="landscape",
            pdf_watermark_text="機密文件",
            excel_autofit_columns=False,
            excel_theme_style="forest_green",
            pdf_font_density="compact",
            export_include_disclaimer=False,
            backup_retention_count=20,
            confirm_on_delete=False,
            overdue_reminder_days=3,
            auto_check_unresolved_on_startup=False,
            clean_temp_files_on_exit=False,
            log_level="DEBUG",
            auto_save_drafts=False,
            import_conflict_strategy="overwrite",
        )
        dialog = AppearancePreferencesPage()

        dialog.reset_button.click()
        self.assertFalse(save_preferences.called)
        self.assertTrue(dialog._density_buttons["standard"].isChecked())
        self.assertTrue(dialog._text_scale_buttons["standard"].isChecked())
        self.assertTrue(dialog._sidebar_density_buttons["standard"].isChecked())
        self.assertTrue(dialog._sidebar_icon_buttons["both"].isChecked())
        self.assertTrue(dialog._theme_mode_buttons["light"].isChecked())
        self.assertTrue(dialog._cjk_font_buttons["default"].isChecked())
        self.assertTrue(dialog._window_geometry_buttons["remember"].isChecked())
        self.assertTrue(dialog._status_bar_detail_buttons["standard"].isChecked())

        self.assertTrue(dialog._table_density_buttons["standard"].isChecked())
        self.assertTrue(dialog._date_format_buttons["YYYY-MM-DD"].isChecked())
        self.assertTrue(dialog._double_click_buttons["menu"].isChecked())
        self.assertTrue(dialog._search_mode_buttons["live"].isChecked())
        self.assertTrue(dialog._stats_span_buttons[6].isChecked())
        self.assertTrue(dialog._pareto_cutoff_checkbox.isChecked())
        self.assertTrue(dialog._auto_scroll_top_checkbox.isChecked())
        self.assertTrue(dialog._hover_highlight_checkbox.isChecked())
        self.assertTrue(dialog._text_wrapping_buttons["elide"].isChecked())
        self.assertTrue(dialog._list_sort_buttons["anomaly_no_desc"].isChecked())
        self.assertFalse(dialog._table_show_row_numbers_checkbox.isChecked())
        self.assertFalse(dialog._quick_filter_case_checkbox.isChecked())

        self.assertEqual("", dialog._responsible_person_input.text())
        self.assertEqual("", dialog._closer_name_input.text())
        self.assertEqual("", dialog._anomaly_category_combo.currentText())
        self.assertEqual("", dialog._anomaly_source_combo.currentText())
        self.assertTrue(dialog._severity_level_buttons["一般"].isChecked())
        self.assertTrue(dialog._auto_anomaly_no_checkbox.isChecked())
        self.assertTrue(dialog._auto_uppercase_checkbox.isChecked())
        self.assertFalse(dialog._require_defect_photos_checkbox.isChecked())
        self.assertTrue(dialog._due_days_buttons[7].isChecked())
        self.assertFalse(hasattr(dialog, "_sync_visit_checkbox"))
        self.assertFalse(hasattr(dialog, "_visit_type_combo"))
        self.assertFalse(hasattr(dialog, "_visit_time_slot_combo"))
        self.assertEqual("", dialog._defect_disposition_combo.currentText())
        self.assertTrue(dialog._defect_sample_size_buttons[0].isChecked())

        self.assertEqual("", dialog._export_dir_input.text())
        self.assertTrue(dialog._export_action_buttons["open_file"].isChecked())
        self.assertTrue(dialog._export_naming_buttons["standard"].isChecked())
        self.assertEqual("SQE 供應商品質工程部", dialog._report_header_input.text())
        self.assertTrue(dialog._pdf_orientation_buttons["portrait"].isChecked())
        self.assertEqual("", dialog._pdf_watermark_input.text())
        self.assertTrue(dialog._export_charts_checkbox.isChecked())
        self.assertTrue(dialog._excel_autofit_checkbox.isChecked())
        self.assertTrue(dialog._excel_theme_buttons["classic_navy"].isChecked())
        self.assertTrue(dialog._pdf_density_buttons["standard"].isChecked())
        self.assertTrue(dialog._export_disclaimer_checkbox.isChecked())
        self.assertTrue(dialog._export_summary_sheet_checkbox.isChecked())
        self.assertTrue(dialog._pdf_header_logo_checkbox.isChecked())

        self.assertTrue(dialog._startup_page_buttons["events"].isChecked())
        self.assertTrue(dialog._retention_count_buttons[10].isChecked())
        self.assertTrue(dialog._confirm_delete_checkbox.isChecked())
        self.assertTrue(dialog._auto_check_unresolved_checkbox.isChecked())
        self.assertTrue(dialog._auto_save_drafts_checkbox.isChecked())
        self.assertTrue(dialog._clean_temp_checkbox.isChecked())
        self.assertTrue(dialog._session_restore_filters_checkbox.isChecked())
        self.assertFalse(dialog._auto_compact_db_checkbox.isChecked())
        self.assertTrue(dialog._log_level_buttons["INFO"].isChecked())
        self.assertTrue(dialog._import_conflict_buttons["prompt"].isChecked())

        dialog.save_button.click()
        save_preferences.assert_called_once_with(AppearancePreferences.default())
        self.assertFalse(dialog.has_unsaved_changes())
        self.assertEqual("設定已儲存並套用", dialog.feedback_label.text())

    @patch("ui.widgets.appearance_preferences_dialog.load_application_preferences")
    def test_controls_have_explicit_accessibility_and_fixed_action_order(self, load_preferences) -> None:
        load_preferences.return_value = AppearancePreferences.default()
        dialog = AppearancePreferencesPage()
        self.assertEqual("AppearancePreferencesPage", dialog.objectName())
        self.assertTrue(dialog._density_buttons["standard"].accessibleName())
        self.assertTrue(dialog._density_buttons["standard"].accessibleDescription())
        self.assertTrue(dialog._text_scale_buttons["large"].accessibleName())
        self.assertTrue(dialog._text_scale_buttons["large"].accessibleDescription())
        self.assertTrue(dialog._sidebar_density_buttons["compact"].accessibleName())
        self.assertTrue(dialog._sidebar_icon_buttons["both"].accessibleName())
        self.assertTrue(dialog._table_density_buttons["comfortable"].accessibleName())
        self.assertTrue(dialog._contrast_mode_buttons["high"].accessibleName())
        self.assertTrue(dialog._theme_mode_buttons["light"].accessibleName())
        self.assertTrue(dialog._cjk_font_buttons["default"].accessibleName())
        self.assertTrue(dialog._window_geometry_buttons["remember"].accessibleName())
        self.assertTrue(dialog._status_bar_detail_buttons["standard"].accessibleName())
        self.assertTrue(dialog._date_format_buttons["YYYY-MM-DD"].accessibleName())
        self.assertTrue(dialog._table_show_row_numbers_checkbox.accessibleName())
        self.assertTrue(dialog._double_click_buttons["menu"].accessibleName())
        self.assertTrue(dialog._search_mode_buttons["live"].accessibleName())
        self.assertTrue(dialog._quick_filter_case_checkbox.accessibleName())
        self.assertTrue(dialog._stats_span_buttons[6].accessibleName())
        self.assertTrue(dialog._pareto_cutoff_checkbox.accessibleName())
        self.assertTrue(dialog._auto_scroll_top_checkbox.accessibleName())
        self.assertTrue(dialog._hover_highlight_checkbox.accessibleName())
        self.assertTrue(dialog._text_wrapping_buttons["elide"].accessibleName())
        self.assertTrue(dialog._list_sort_buttons["anomaly_no_desc"].accessibleName())
        self.assertTrue(dialog._responsible_person_input.accessibleName())
        self.assertTrue(dialog._closer_name_input.accessibleName())
        self.assertTrue(dialog._anomaly_category_combo.accessibleName())
        self.assertTrue(dialog._anomaly_source_combo.accessibleName())
        self.assertTrue(dialog._anomaly_category_presets_button.accessibleName())
        self.assertTrue(dialog._anomaly_source_presets_button.accessibleName())
        self.assertTrue(dialog._severity_level_buttons["一般"].accessibleName())
        self.assertTrue(dialog._auto_anomaly_no_checkbox.accessibleName())
        self.assertTrue(dialog._auto_uppercase_checkbox.accessibleName())
        self.assertTrue(dialog._require_defect_photos_checkbox.accessibleName())
        self.assertTrue(dialog._due_days_buttons[7].accessibleName())
        self.assertTrue(dialog._defect_disposition_combo.accessibleName())
        self.assertTrue(dialog._defect_sample_size_buttons[0].accessibleName())
        self.assertTrue(dialog._export_dir_input.accessibleName())
        self.assertTrue(dialog._browse_dir_button.accessibleName())
        self.assertTrue(dialog._export_naming_buttons["standard"].accessibleName())
        self.assertTrue(dialog._report_header_input.accessibleName())
        self.assertTrue(dialog._pdf_orientation_buttons["portrait"].accessibleName())
        self.assertTrue(dialog._excel_theme_buttons["classic_navy"].accessibleName())
        self.assertTrue(dialog._pdf_density_buttons["standard"].accessibleName())
        self.assertTrue(dialog._pdf_watermark_input.accessibleName())
        self.assertTrue(dialog._export_charts_checkbox.accessibleName())
        self.assertTrue(dialog._excel_autofit_checkbox.accessibleName())
        self.assertTrue(dialog._export_disclaimer_checkbox.accessibleName())
        self.assertTrue(dialog._export_summary_sheet_checkbox.accessibleName())
        self.assertTrue(dialog._pdf_header_logo_checkbox.accessibleName())
        self.assertTrue(dialog._confirm_delete_checkbox.accessibleName())
        self.assertTrue(dialog._auto_check_unresolved_checkbox.accessibleName())
        self.assertTrue(dialog._auto_save_drafts_checkbox.accessibleName())
        self.assertTrue(dialog._clean_temp_checkbox.accessibleName())
        self.assertTrue(dialog._session_restore_filters_checkbox.accessibleName())
        self.assertTrue(dialog._auto_compact_db_checkbox.accessibleName())
        self.assertTrue(dialog._log_level_buttons["INFO"].accessibleName())
        self.assertTrue(dialog._import_conflict_buttons["prompt"].accessibleName())
        self.assertTrue(dialog.save_button.accessibleName())
        self.assertTrue(dialog.cancel_button.accessibleName())

    @patch("ui.widgets.appearance_preferences_dialog.AnomalyCategoryPresetsDialog")
    @patch("ui.widgets.appearance_preferences_dialog.AnomalySourcePresetsDialog")
    @patch("ui.widgets.appearance_preferences_dialog.load_application_preferences")
    def test_lexicon_preset_dialogs_open_from_forms_tab(
        self,
        load_preferences,
        source_dialog_cls,
        category_dialog_cls,
    ) -> None:
        load_preferences.return_value = AppearancePreferences.default()
        source_dialog = source_dialog_cls.return_value
        category_dialog = category_dialog_cls.return_value
        source_dialog.exec.return_value = 0
        category_dialog.exec.return_value = 0

        dialog = AppearancePreferencesPage()
        dialog._anomaly_source_presets_button.click()
        source_dialog_cls.assert_called_once()
        source_dialog.exec.assert_called_once()

        dialog._anomaly_category_presets_button.click()
        category_dialog_cls.assert_called_once()
        category_dialog.exec.assert_called_once()

    @patch("ui.widgets.appearance_preferences_dialog.load_application_preferences")
    def test_uses_five_preference_tabs_with_per_tab_scroll_protection(self, load_preferences) -> None:
        load_preferences.return_value = AppearancePreferences.default()
        dialog = AppearancePreferencesPage()

        scroll_areas = dialog.findChildren(QScrollArea)
        self.assertEqual(5, len(scroll_areas))
        self.assertEqual(5, dialog._category_list.count())
        self.assertEqual(
            ["外觀主題", "視覺表格", "表單業務預設", "匯出與報告", "系統與備份"],
            [dialog.preference_tabs.tabText(index) for index in range(dialog.preference_tabs.count())],
        )
        self.assertEqual(5, dialog.preference_tabs.count())

    @patch("ui.widgets.appearance_preferences_dialog.load_application_preferences")
    def test_minimum_shell_content_width_reflows_without_horizontal_overflow(
        self,
        load_preferences,
    ) -> None:
        load_preferences.return_value = AppearancePreferences.default()
        page = AppearancePreferencesPage()
        page.resize(804, 600)
        page.show()
        self.current_app.processEvents()

        columns = page.findChildren(_ResponsivePreferenceColumns)
        self.assertEqual(5, len(columns))
        self.assertTrue(all(column._is_stacked for column in columns))
        for scroll_area in page.findChildren(QScrollArea):
            self.assertEqual(0, scroll_area.horizontalScrollBar().maximum())

        page.close()


if __name__ == "__main__":
    unittest.main()
