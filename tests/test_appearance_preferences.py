from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import repository
from services.appearance_preferences_service import (
    APPEARANCE_PREFERENCES_KEY,
    APPEARANCE_PREFERENCES_V1_KEY,
    APPEARANCE_PREFERENCES_V2_KEY,
    APPEARANCE_PREFERENCES_V7_KEY,
    load_preferences,
    save_preferences,
)
from ui.appearance_preferences import AppearancePreferences
from ui.theme import get_theme_qss


class AppearancePreferencesServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "appearance.db"
        self.conn = sqlite3.connect(self._db_path)
        self.conn.row_factory = sqlite3.Row
        repository.create_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self._temp_dir.cleanup()

    def test_missing_setting_uses_standard_defaults(self) -> None:
        self.assertEqual(AppearancePreferences.default(), load_preferences(self.conn))

    def test_save_and_reload_v8_round_trip_without_touching_ncr_key(self) -> None:
        self.conn.execute(
            "INSERT INTO ui_settings (setting_key, setting_value) VALUES (?, ?)",
            ("defect_list_columns", '["defect_no", "status"]'),
        )
        self.conn.commit()
        expected = AppearancePreferences(
            density="comfortable",
            text_scale="large",
            sidebar_density="compact",
            sidebar_icon_mode="compact_icon",
            table_density="comfortable",
            contrast_mode="high",
            accent_color="violet",
            theme_mode="dark_slate",
            cjk_font_family_preference="noto_sans",
            window_geometry_mode="maximized",
            status_bar_detail_level="detailed",
            alternating_row_colors=False,
            table_grid_lines=True,
            enable_animations=True,
            table_double_click_action="preview",
            search_mode="manual",
            stats_default_span_months=12,
            pareto_show_cutoff_line=False,
            highlight_overdue_rows=False,
            date_format_display="YYYY/MM/DD",
            table_auto_scroll_to_top=False,
            table_hover_highlight=False,
            table_text_wrapping="wrap",
            default_list_sort_field="date_desc",
            table_show_row_numbers=True,
            quick_filter_case_sensitive=True,
            default_startup_page="events",
            table_page_limit=100,
            auto_backup_prompt=False,
            default_responsible_person="王小明",
            default_anomaly_category="零件缺件",
            default_due_days=14,
            default_anomaly_source="進料檢驗 (IQC)",
            default_severity_level="重大",
            auto_fill_anomaly_no_on_date_change=False,
            default_closer_name="陳主管",
            default_defect_disposition="特採",
            auto_uppercase_part_no=False,
            default_defect_sample_size=100,
            require_defect_photos=True,
            default_export_dir="C:/Reports",
            export_completion_action="open_folder",
            report_organization_header="品質部",
            export_include_charts=False,
            export_file_naming_rule="detailed",
            pdf_page_orientation="landscape",
            pdf_watermark_text="機密文件",
            excel_autofit_columns=False,
            excel_theme_style="forest_green",
            pdf_font_density="compact",
            export_include_disclaimer=False,
            export_include_summary_sheet=False,
            pdf_header_logo_visible=False,
            backup_retention_count=20,
            confirm_on_delete=False,
            overdue_reminder_days=3,
            auto_check_unresolved_on_startup=False,
            clean_temp_files_on_exit=False,
            log_level="DEBUG",
            auto_save_drafts=False,
            import_conflict_strategy="overwrite",
            session_restore_last_filters=False,
            auto_compact_db_on_exit=True,
        )

        save_preferences(self.conn, expected)

        self.assertEqual(expected, load_preferences(self.conn))
        ncr_value = self.conn.execute(
            "SELECT setting_value FROM ui_settings WHERE setting_key = ?",
            ("defect_list_columns",),
        ).fetchone()[0]
        self.assertEqual('["defect_no", "status"]', ncr_value)

    def test_invalid_or_unknown_payload_falls_back_without_rewriting_data(self) -> None:
        invalid_payload = '{"density":"future", "text_scale":"large"}'
        self.conn.execute(
            "INSERT INTO ui_settings (setting_key, setting_value) VALUES (?, ?)",
            (APPEARANCE_PREFERENCES_KEY, invalid_payload),
        )
        self.conn.commit()

        with self.assertLogs("services.appearance_preferences_service", level="WARNING") as logs:
            self.assertEqual(AppearancePreferences.default(), load_preferences(self.conn))
        self.assertTrue(
            any("忽略格式無效的介面與系統 v10 偏好" in message for message in logs.output)
        )
        persisted = self.conn.execute(
            "SELECT setting_value FROM ui_settings WHERE setting_key = ?",
            (APPEARANCE_PREFERENCES_KEY,),
        ).fetchone()[0]
        self.assertEqual(invalid_payload, persisted)

    def test_unknown_keys_and_malformed_json_use_defaults(self) -> None:
        for payload in (
            '{"density":"standard","text_scale":"standard","future":true}',
            "not-json",
        ):
            with self.subTest(payload=payload):
                self.conn.execute("DELETE FROM ui_settings WHERE setting_key = ?", (APPEARANCE_PREFERENCES_KEY,))
                self.conn.execute(
                    "INSERT INTO ui_settings (setting_key, setting_value) VALUES (?, ?)",
                    (APPEARANCE_PREFERENCES_KEY, payload),
                )
                self.conn.commit()
                with self.assertLogs("services.appearance_preferences_service", level="WARNING") as logs:
                    self.assertEqual(AppearancePreferences.default(), load_preferences(self.conn))
                self.assertTrue(
                    any("忽略格式無效的介面與系統 v10 偏好" in message for message in logs.output)
                )

    def test_v1_to_v7_payloads_are_upgraded_in_memory(self) -> None:
        legacy_v1 = '{"density":"compact","text_scale":"large"}'
        self.conn.execute(
            "INSERT INTO ui_settings (setting_key, setting_value) VALUES (?, ?)",
            (APPEARANCE_PREFERENCES_V1_KEY, legacy_v1),
        )
        self.conn.commit()
        self.assertEqual(
            AppearancePreferences(density="compact", text_scale="large"),
            load_preferences(self.conn),
        )

        legacy_v2 = '{"density":"standard","text_scale":"standard","sidebar_density":"compact","table_density":"comfortable","contrast_mode":"high"}'
        self.conn.execute(
            "INSERT INTO ui_settings (setting_key, setting_value) VALUES (?, ?)",
            (APPEARANCE_PREFERENCES_V2_KEY, legacy_v2),
        )
        self.conn.commit()
        self.assertEqual(
            AppearancePreferences(sidebar_density="compact", table_density="comfortable", contrast_mode="high"),
            load_preferences(self.conn),
        )

        legacy_v7 = (
            '{"density":"comfortable","text_scale":"large","sidebar_density":"compact","table_density":"comfortable",'
            '"contrast_mode":"high","accent_color":"emerald","theme_mode":"dark_slate","cjk_font_family_preference":"noto_sans",'
            '"window_geometry_mode":"maximized","status_bar_detail_level":"detailed",'
            '"alternating_row_colors":false,"table_grid_lines":true,"enable_animations":true,"table_page_limit":100,'
            '"table_double_click_action":"preview","search_mode":"manual","stats_default_span_months":12,'
            '"pareto_show_cutoff_line":false,"highlight_overdue_rows":false,"date_format_display":"YYYY/MM/DD",'
            '"table_auto_scroll_to_top":false,"table_hover_highlight":false,"table_text_wrapping":"wrap",'
            '"default_list_sort_field":"date_desc","default_responsible_person":"王大明","default_anomaly_category":"零件缺件",'
            '"default_due_days":14,"default_anomaly_source":"進料檢驗 (IQC)",'
            '"default_severity_level":"重大","auto_fill_anomaly_no_on_date_change":false,'
            '"default_closer_name":"陳主管","default_defect_disposition":"特採","auto_uppercase_part_no":false,'
            '"default_export_dir":"D:/Reports","export_completion_action":"open_folder","report_organization_header":"品保部",'
            '"export_include_charts":false,"export_file_naming_rule":"detailed","pdf_page_orientation":"landscape",'
            '"pdf_watermark_text":"機密文件","excel_autofit_columns":false,"excel_theme_style":"forest_green",'
            '"pdf_font_density":"compact","export_include_disclaimer":false,"default_startup_page":"events",'
            '"auto_backup_prompt":false,"backup_retention_count":20,"confirm_on_delete":false,"overdue_reminder_days":3,'
            '"auto_check_unresolved_on_startup":false,"clean_temp_files_on_exit":false,"log_level":"DEBUG",'
            '"auto_save_drafts":false,"import_conflict_strategy":"overwrite"}'
        )
        self.conn.execute("DELETE FROM ui_settings")
        self.conn.execute(
            "INSERT INTO ui_settings (setting_key, setting_value) VALUES (?, ?)",
            (APPEARANCE_PREFERENCES_V7_KEY, legacy_v7),
        )
        self.conn.commit()
        self.assertEqual(
            AppearancePreferences(
                density="comfortable",
                text_scale="large",
                sidebar_density="compact",
                table_density="comfortable",
                contrast_mode="high",
                accent_color="emerald",
                theme_mode="dark_slate",
                cjk_font_family_preference="noto_sans",
                window_geometry_mode="maximized",
                status_bar_detail_level="detailed",
                alternating_row_colors=False,
                table_grid_lines=True,
                enable_animations=True,
                table_page_limit=100,
                table_double_click_action="preview",
                search_mode="manual",
                stats_default_span_months=12,
                pareto_show_cutoff_line=False,
                highlight_overdue_rows=False,
                date_format_display="YYYY/MM/DD",
                table_auto_scroll_to_top=False,
                table_hover_highlight=False,
                table_text_wrapping="wrap",
                default_list_sort_field="date_desc",
                default_responsible_person="王大明",
                default_anomaly_category="零件缺件",
                default_due_days=14,
                default_anomaly_source="進料檢驗 (IQC)",
                default_severity_level="重大",
                auto_fill_anomaly_no_on_date_change=False,
                default_closer_name="陳主管",
                default_defect_disposition="特採",
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
                default_startup_page="events",
                auto_backup_prompt=False,
                backup_retention_count=20,
                confirm_on_delete=False,
                overdue_reminder_days=3,
                auto_check_unresolved_on_startup=False,
                clean_temp_files_on_exit=False,
                log_level="DEBUG",
                auto_save_drafts=False,
                import_conflict_strategy="overwrite",
            ),
            load_preferences(self.conn),
        )

    def test_legacy_home_startup_page_migrates_to_events(self) -> None:
        mapping = AppearancePreferences.default().to_mapping()
        mapping["default_startup_page"] = "home"
        mapping["density"] = "compact"
        mapping["enable_animations"] = False
        prefs = AppearancePreferences.from_mapping(mapping)
        self.assertEqual("events", prefs.default_startup_page)
        self.assertEqual("compact", prefs.density)
        self.assertFalse(prefs.enable_animations)

    def _legacy_home_v9_mapping(self) -> dict[str, object]:
        mapping = AppearancePreferences.default().to_mapping()
        mapping["default_startup_page"] = "home"
        mapping["density"] = "compact"
        mapping["enable_animations"] = False
        return mapping

    def test_legacy_home_v9_payload_loads_without_invalid_warning(self) -> None:
        mapping = self._legacy_home_v9_mapping()
        payload = json.dumps(mapping, ensure_ascii=False, separators=(",", ":"))
        self.conn.execute(
            "INSERT INTO ui_settings (setting_key, setting_value) VALUES (?, ?)",
            (APPEARANCE_PREFERENCES_KEY, payload),
        )
        self.conn.commit()

        with self.assertNoLogs("services.appearance_preferences_service", level="WARNING"):
            loaded = load_preferences(self.conn)

        self.assertEqual(
            AppearancePreferences(
                density="compact",
                enable_animations=False,
            ),
            loaded,
        )
        persisted = self.conn.execute(
            "SELECT setting_value FROM ui_settings WHERE setting_key = ?",
            (APPEARANCE_PREFERENCES_KEY,),
        ).fetchone()[0]
        self.assertIn('"home"', persisted)

    def test_legacy_home_only_default_v9_payload_loads_without_invalid_warning(self) -> None:
        mapping = AppearancePreferences.default().to_mapping()
        mapping["default_startup_page"] = "home"
        payload = json.dumps(mapping, ensure_ascii=False, separators=(",", ":"))
        self.conn.execute(
            "INSERT INTO ui_settings (setting_key, setting_value) VALUES (?, ?)",
            (APPEARANCE_PREFERENCES_KEY, payload),
        )
        self.conn.commit()

        with self.assertNoLogs("services.appearance_preferences_service", level="WARNING"):
            loaded = load_preferences(self.conn)

        self.assertEqual(AppearancePreferences.default(), loaded)
        persisted = self.conn.execute(
            "SELECT setting_value FROM ui_settings WHERE setting_key = ?",
            (APPEARANCE_PREFERENCES_KEY,),
        ).fetchone()[0]
        self.assertIn('"home"', persisted)

    def test_save_rejects_an_invalid_in_memory_preference(self) -> None:
        invalid = AppearancePreferences(density="invalid", text_scale="standard")
        with self.assertRaises(ValueError):
            save_preferences(self.conn, invalid)


class AppearanceThemeTests(unittest.TestCase):
    def test_density_and_accent_color_are_applied(self) -> None:
        qss = get_theme_qss(
            AppearancePreferences(density="comfortable", text_scale="large", accent_color="violet")
        )
        self.assertIn("min-height: 40px;", qss)
        self.assertIn("font-size: 15px;", qss)
        self.assertIn("#7C3AED", qss)

    def test_high_contrast_qss_and_runtime_table_sidebar_metrics(self) -> None:
        from PySide6.QtWidgets import QApplication, QTableWidget

        from ui.sidebar_nav import SidebarNav
        from ui.theme import apply_app_theme
        from ui.widgets.common_widgets import style_table

        app = QApplication.instance() or QApplication([])
        profile = AppearancePreferences(
            density="compact", sidebar_density="compact", table_density="comfortable", contrast_mode="high"
        )
        apply_app_theme(app, profile)
        self.assertIn("background: #000000", app.styleSheet())

        sidebar = SidebarNav()
        self.assertEqual(34, sidebar.button_for_action(("page", "EVENT_QUERY")).height())
        table = QTableWidget(2, 2)
        table.setParent(sidebar)
        style_table(table)
        self.assertEqual(36, table.verticalHeader().defaultSectionSize())
        self.assertEqual(40, table.horizontalHeader().minimumHeight())

        apply_app_theme(app, AppearancePreferences(table_density="compact"))
        style_table(table)
        self.assertEqual(26, table.verticalHeader().defaultSectionSize())
        self.assertEqual(30, table.horizontalHeader().minimumHeight())
        apply_app_theme(app)


if __name__ == "__main__":
    unittest.main()
