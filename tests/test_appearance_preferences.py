from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import repository
from services.appearance_preferences_service import (
    APPEARANCE_PREFERENCES_KEY,
    APPEARANCE_PREFERENCES_V1_KEY,
    APPEARANCE_PREFERENCES_V2_KEY,
    APPEARANCE_PREFERENCES_V3_KEY,
    APPEARANCE_PREFERENCES_V4_KEY,
    APPEARANCE_PREFERENCES_V5_KEY,
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

    def test_save_and_reload_v5_round_trip_without_touching_ncr_key(self) -> None:
        self.conn.execute(
            "INSERT INTO ui_settings (setting_key, setting_value) VALUES (?, ?)",
            ("defect_list_columns", '["defect_no", "status"]'),
        )
        self.conn.commit()
        expected = AppearancePreferences(
            density="comfortable",
            text_scale="large",
            sidebar_density="compact",
            table_density="comfortable",
            contrast_mode="high",
            accent_color="emerald",
            alternating_row_colors=False,
            table_grid_lines=True,
            enable_animations=True,
            table_double_click_action="preview",
            search_mode="manual",
            stats_default_span_months=12,
            pareto_show_cutoff_line=False,
            default_startup_page="events",
            table_page_limit=100,
            auto_backup_prompt=False,
            default_responsible_person="王小明",
            default_anomaly_category="零件缺件",
            default_sync_visit=False,
            default_due_days=14,
            default_visit_time_slot="上午",
            default_export_dir="C:/Reports",
            export_completion_action="open_folder",
            report_organization_header="品質部",
            export_include_charts=False,
            backup_retention_count=20,
            confirm_on_delete=False,
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

        self.assertEqual(AppearancePreferences.default(), load_preferences(self.conn))
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
                self.assertEqual(AppearancePreferences.default(), load_preferences(self.conn))

    def test_v1_v2_v3_and_v4_payloads_are_upgraded_in_memory(self) -> None:
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

        legacy_v3 = (
            '{"density":"compact","text_scale":"standard","sidebar_density":"standard","table_density":"standard",'
            '"contrast_mode":"standard","accent_color":"emerald","alternating_row_colors":false,'
            '"table_grid_lines":false,"enable_animations":false,"default_startup_page":"stats",'
            '"table_page_limit":25,"auto_backup_prompt":false}'
        )
        self.conn.execute(
            "INSERT INTO ui_settings (setting_key, setting_value) VALUES (?, ?)",
            (APPEARANCE_PREFERENCES_V3_KEY, legacy_v3),
        )
        self.conn.commit()
        self.assertEqual(
            AppearancePreferences(
                density="compact",
                accent_color="emerald",
                alternating_row_colors=False,
                table_grid_lines=False,
                enable_animations=False,
                default_startup_page="stats",
                table_page_limit=25,
                auto_backup_prompt=False,
            ),
            load_preferences(self.conn),
        )

        legacy_v4 = (
            '{"density":"standard","text_scale":"standard","sidebar_density":"standard","table_density":"standard",'
            '"contrast_mode":"standard","accent_color":"electric_blue","alternating_row_colors":true,'
            '"table_grid_lines":true,"table_page_limit":50,"enable_animations":false,'
            '"default_responsible_person":"SQE01","default_anomaly_category":"尺寸超差",'
            '"default_sync_visit":true,"default_due_days":7,"default_visit_time_slot":"下午",'
            '"default_export_dir":"","export_completion_action":"open_file",'
            '"report_organization_header":"SQE 供應商品質工程部","export_include_charts":true,'
            '"default_startup_page":"events","auto_backup_prompt":true,"backup_retention_count":10,'
            '"confirm_on_delete":true}'
        )
        self.conn.execute(
            "INSERT INTO ui_settings (setting_key, setting_value) VALUES (?, ?)",
            (APPEARANCE_PREFERENCES_V4_KEY, legacy_v4),
        )
        self.conn.commit()
        self.assertEqual(
            AppearancePreferences(
                enable_animations=False,
                default_startup_page="events",
                default_responsible_person="SQE01",
                default_anomaly_category="尺寸超差",
                table_double_click_action="menu",
                search_mode="live",
                stats_default_span_months=6,
                pareto_show_cutoff_line=True,
            ),
            load_preferences(self.conn),
        )

    def test_save_rejects_an_invalid_in_memory_preference(self) -> None:
        invalid = AppearancePreferences(density="invalid", text_scale="standard")
        with self.assertRaises(ValueError):
            save_preferences(self.conn, invalid)


class AppearanceThemeTests(unittest.TestCase):
    def test_density_and_accent_color_are_applied(self) -> None:
        qss = get_theme_qss(
            AppearancePreferences(density="comfortable", text_scale="large", accent_color="amber")
        )
        self.assertIn("min-height: 40px;", qss)
        self.assertIn("font-size: 15px;", qss)

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
        self.assertEqual(34, sidebar.button_for_action(("page", "HOME")).height())
        table = QTableWidget(2, 2)
        table.setParent(sidebar)
        style_table(table)
        self.assertEqual(36, table.verticalHeader().defaultSectionSize())
        self.assertEqual(40, table.horizontalHeader().minimumHeight())

        apply_app_theme(app, AppearancePreferences(table_density="compact"))
        self.assertEqual(26, table.verticalHeader().defaultSectionSize())
        self.assertEqual(30, table.horizontalHeader().minimumHeight())
        apply_app_theme(app)


if __name__ == "__main__":
    unittest.main()


