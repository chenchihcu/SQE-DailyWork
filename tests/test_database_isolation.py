from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import connection
from database.backup import sqlite_state_fingerprint


class DatabaseIsolationTests(unittest.TestCase):
    def test_disposable_guard_rejects_formal_database(self) -> None:
        with patch.dict(os.environ, {"SQE_REQUIRE_DISPOSABLE_DB": "1"}):
            with self.assertRaisesRegex(RuntimeError, "formal SQE database"):
                connection.get_connection(connection.DEFAULT_DB_PATH)

    def test_disposable_guard_allows_non_formal_database(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "sqe_v2.db"
            with patch.dict(os.environ, {"SQE_REQUIRE_DISPOSABLE_DB": "1"}):
                with connection.get_connection(target) as conn:
                    self.assertEqual(1, conn.execute("SELECT 1").fetchone()[0])

    def test_unpromoted_formal_database_fails_before_writable_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "sqe_v2.db"
            db = sqlite3.connect(target)
            db.execute("CREATE TABLE anomalies(id TEXT PRIMARY KEY)")
            db.execute(
                "CREATE TABLE migration_meta("
                "key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT)"
            )
            db.commit()
            db.close()
            before = sqlite_state_fingerprint(target)["state_sha256"]

            with (
                patch.object(connection, "DB_PATH", target),
                patch.object(connection, "DEFAULT_DB_PATH", target),
                patch.dict(
                    os.environ,
                    {
                        "SQE_REQUIRE_DISPOSABLE_DB": "",
                        "SQE_DB_PATH": "",
                    },
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "需要完成資料升級"):
                    connection.initialize_database()

            after = sqlite_state_fingerprint(target)["state_sha256"]
            self.assertEqual(before, after)

    def test_phase1_verifiers_initialize_disposable_schema_before_tests(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        full_script = (repo_root / "scripts" / "verify.ps1").read_text(
            encoding="utf-8-sig"
        )
        focused_script = (
            repo_root / "scripts" / "verify_case_actions_phase1.ps1"
        ).read_text(encoding="utf-8-sig")
        preflight_marker = "[preflight] initialize disposable case_actions_v1"

        self.assertIn(preflight_marker, full_script)
        self.assertLess(
            full_script.index(preflight_marker),
            full_script.index("[2/6] python -m unittest discover -s tests"),
        )
        regression_reset_marker = (
            "[preflight] reset disposable database before visual regression"
        )
        regression_start = full_script.index("[5/6] native visual regression")
        regression_reset = full_script.index(regression_reset_marker)
        regression_call = full_script.index("& $resolvedPython @regressArgs")
        self.assertLess(regression_start, regression_reset)
        self.assertLess(regression_reset, regression_call)
        self.assertIn(preflight_marker, focused_script)
        self.assertLess(
            focused_script.index(preflight_marker),
            focused_script.index("& $phase1Ruff check"),
        )


if __name__ == "__main__":
    unittest.main()
