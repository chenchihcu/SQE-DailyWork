from __future__ import annotations

import json
import sqlite3
import unittest
from pathlib import Path
from uuid import uuid4

from database import repository
from services.process_keyword_preset_service import (
    SMT_PROCESS_KEYWORDS_SETTINGS_KEY,
    all_suggestion_keywords,
    default_presets,
    load_presets,
    save_presets,
)


class ProcessKeywordPresetServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        base_tmp_dir = Path("scratch")
        base_tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = base_tmp_dir / f"sqe_process_keyword_presets_{uuid4().hex}.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        repository.create_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def test_default_presets_include_smt_groups(self) -> None:
        presets = default_presets()
        labels = [group.label for group in presets.groups]
        self.assertIn("製程站別", labels)
        self.assertIn("現象關鍵詞", labels)
        self.assertIn("SPI", all_suggestion_keywords(presets))

    def test_save_and_load_round_trip(self) -> None:
        presets = default_presets()
        presets.groups[0].keywords.append("自訂站別")
        save_presets(presets, self.conn)
        loaded = load_presets(self.conn)
        self.assertIn("自訂站別", loaded.groups[0].keywords)

    def test_invalid_json_falls_back_to_default(self) -> None:
        self.conn.execute(
            "INSERT INTO ui_settings (setting_key, setting_value) VALUES (?, ?)",
            (SMT_PROCESS_KEYWORDS_SETTINGS_KEY, "{bad json"),
        )
        self.conn.commit()
        loaded = load_presets(self.conn)
        self.assertEqual(
            [group.label for group in default_presets().groups],
            [group.label for group in loaded.groups],
        )


if __name__ == "__main__":
    unittest.main()
