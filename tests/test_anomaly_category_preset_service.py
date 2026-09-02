from __future__ import annotations

import json
import sqlite3
import unittest

from services.anomaly_category_preset_service import (
    ANOMALY_CATEGORIES_SETTINGS_KEY,
    AnomalyCategoryPresets,
    count_anomalies_using_category,
    default_categories,
    invalidate_cache,
    is_valid_category,
    load_categories,
    save_categories,
    validate_categories,
)


class AnomalyCategoryPresetServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        invalidate_cache()
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute(
            """
            CREATE TABLE ui_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE anomalies (
                id TEXT PRIMARY KEY,
                category TEXT NOT NULL DEFAULT ''
            )
            """
        )

    def tearDown(self) -> None:
        invalidate_cache()
        self.conn.close()

    def test_default_categories_exclude_blank_option(self) -> None:
        presets = default_categories()
        self.assertEqual(10, len(presets.categories))
        self.assertIn("製程參數失控", presets.categories)
        self.assertNotIn("", presets.categories)

    def test_save_and_load_round_trip(self) -> None:
        presets = AnomalyCategoryPresets(version=1, categories=["外觀不良", "尺寸異常"])
        save_categories(presets, self.conn)
        loaded = load_categories(self.conn)
        self.assertEqual(["外觀不良", "尺寸異常"], loaded.categories)

    def test_duplicate_labels_rejected(self) -> None:
        presets = AnomalyCategoryPresets(version=1, categories=["A", "a"])
        self.assertIn("重複", validate_categories(presets))

    def test_is_valid_category_allows_blank(self) -> None:
        self.assertTrue(is_valid_category(""))
        self.assertTrue(is_valid_category("製程參數失控"))
        self.assertFalse(is_valid_category("客製分類"))

    def test_count_anomalies_using_category(self) -> None:
        self.conn.execute(
            "INSERT INTO anomalies (id, category) VALUES ('a1', '外觀不良')"
        )
        self.conn.commit()
        self.assertEqual(1, count_anomalies_using_category("外觀不良", self.conn))

    def test_malformed_settings_fall_back_to_defaults(self) -> None:
        self.conn.execute(
            "INSERT INTO ui_settings (setting_key, setting_value) VALUES (?, ?)",
            (ANOMALY_CATEGORIES_SETTINGS_KEY, json.dumps({"version": 2})),
        )
        loaded = load_categories(self.conn)
        self.assertEqual(default_categories().categories, loaded.categories)


if __name__ == "__main__":
    unittest.main()
