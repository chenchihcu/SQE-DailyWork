from __future__ import annotations

import json
import sqlite3
import unittest
from unittest import mock

from services.anomaly_source_preset_service import (
    ANOMALY_SOURCES_SETTINGS_KEY,
    AnomalySourceEntry,
    AnomalySourcePresets,
    clone_sources,
    default_sources,
    invalidate_cache,
    load_sources,
    save_sources,
    validate_sources,
)
from services.anomaly_trace_contract import (
    ANOMALY_SOURCE_MATERIAL_INCOMING,
    normalize_anomaly_source,
    processing_line_source_hint,
    required_trace_fields_for_source,
    visible_trace_fields_for_source,
)


class AnomalySourcePresetServiceTests(unittest.TestCase):
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
                anomaly_source TEXT NOT NULL DEFAULT ''
            )
            """
        )

    def tearDown(self) -> None:
        invalidate_cache()
        self.conn.close()

    def test_default_sources_match_builtin_matrix(self) -> None:
        presets = default_sources()
        self.assertEqual(6, len(presets.sources))
        material = next(item for item in presets.sources if item.id == "material_incoming")
        self.assertEqual(ANOMALY_SOURCE_MATERIAL_INCOMING, material.label)
        self.assertEqual(["material_receipt_no"], material.visible_trace_fields)
        self.assertEqual(["material_receipt_no"], material.required_trace_fields)

    def test_save_and_load_round_trip(self) -> None:
        presets = default_sources()
        custom = AnomalySourceEntry(
            id="custom_ab12cd34",
            label="客製來源",
            visible_trace_fields=["internal_work_order_no"],
            required_trace_fields=[],
        )
        presets.sources.append(custom)
        save_sources(presets, self.conn)
        loaded = load_sources(self.conn)
        self.assertEqual("客製來源", loaded.sources[-1].label)

    def test_invalid_required_not_subset_of_visible_rejected(self) -> None:
        presets = AnomalySourcePresets(
            version=1,
            sources=[
                AnomalySourceEntry(
                    id="bad",
                    label="錯誤來源",
                    visible_trace_fields=[],
                    required_trace_fields=["material_receipt_no"],
                )
            ],
        )
        self.assertIn("必填追溯欄位", validate_sources(presets))

    def test_trace_contract_uses_saved_presets(self) -> None:
        presets = default_sources()
        custom = AnomalySourceEntry(
            id="custom_trace",
            label="追溯測試來源",
            visible_trace_fields=["outsource_receipt_no"],
            required_trace_fields=["outsource_receipt_no"],
        )
        presets.sources.append(custom)
        saved = clone_sources(presets)
        with mock.patch(
            "services.anomaly_source_preset_service.load_sources",
            return_value=saved,
        ):
            invalidate_cache()
            self.assertEqual("追溯測試來源", normalize_anomaly_source("追溯測試來源"))
            self.assertEqual(
                frozenset({"outsource_receipt_no"}),
                visible_trace_fields_for_source("追溯測試來源"),
            )
            self.assertEqual(
                frozenset({"outsource_receipt_no"}),
                required_trace_fields_for_source("追溯測試來源"),
            )

    def test_processing_line_source_hint_resolves_renamed_builtin_label(self) -> None:
        presets = clone_sources(default_sources())
        material = next(item for item in presets.sources if item.id == "material_incoming")
        material.label = "IQC 進料"
        saved = clone_sources(presets)
        with mock.patch(
            "services.anomaly_source_preset_service.load_sources",
            return_value=saved,
        ):
            invalidate_cache()
            self.assertEqual("IQC 進料", processing_line_source_hint("原物料"))

    def test_malformed_settings_fall_back_to_defaults(self) -> None:
        self.conn.execute(
            "INSERT INTO ui_settings (setting_key, setting_value) VALUES (?, ?)",
            (ANOMALY_SOURCES_SETTINGS_KEY, json.dumps({"version": 9})),
        )
        loaded = load_sources(self.conn)
        self.assertEqual(
            [entry.label for entry in default_sources().sources],
            [entry.label for entry in loaded.sources],
        )


if __name__ == "__main__":
    unittest.main()
