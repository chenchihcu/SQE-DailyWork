from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app_paths import formal_db_path
from database.verify_prepare import SCHEMA_SOURCE_NAME, prepare_verify_database


_REPO_ROOT = Path(__file__).resolve().parents[1]
_PREPARE_CLI = _REPO_ROOT / "scripts" / "prepare_verify_database.py"


def _run_prepare_cli(*cli_args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_PREPARE_CLI), *[str(arg) for arg in cli_args]],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class PrepareVerifyDatabaseTests(unittest.TestCase):
    def _assert_formal_untouched_if_absent(self, existed_before: bool) -> None:
        if not existed_before:
            self.assertFalse(formal_db_path().exists())

    def test_missing_source_without_allow_raises_and_skips_formal_db(self) -> None:
        formal_existed = formal_db_path().is_file()
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "missing" / "sqe_v2.db"
            destination = Path(temp_dir) / "verify" / "sqe_v2.db"
            with self.assertRaisesRegex(FileNotFoundError, "AllowSchemaOnlySource"):
                prepare_verify_database(
                    source,
                    destination,
                    allow_schema_only=False,
                )
            self.assertFalse(destination.exists())
            self.assertFalse((destination.parent / SCHEMA_SOURCE_NAME).exists())
            self._assert_formal_untouched_if_absent(formal_existed)

    def test_schema_only_creates_scratch_schema_not_formal_path(self) -> None:
        formal = formal_db_path()
        formal_existed = formal.is_file()
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "missing" / "sqe_v2.db"
            destination = Path(temp_dir) / "verify" / "sqe_v2.db"
            report = prepare_verify_database(
                source,
                destination,
                allow_schema_only=True,
            )
            self.assertEqual("schema_only", report["mode"])
            self.assertTrue(report["verified"])
            self.assertTrue(destination.is_file())
            schema_source = Path(report["schema_source"])
            self.assertTrue(schema_source.is_file())
            self.assertEqual(SCHEMA_SOURCE_NAME, schema_source.name)
            self.assertEqual(schema_source.parent.resolve(), destination.parent.resolve())
            self.assertNotEqual(destination.resolve(), formal.resolve())
            self.assertNotEqual(schema_source.resolve(), formal.resolve())

            conn = sqlite3.connect(destination)
            try:
                tables = {
                    str(row[0])
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
            finally:
                conn.close()
            self.assertIn("suppliers", tables)
            self.assertIn("anomalies", tables)
            self.assertIn("defect_records", tables)
            self._assert_formal_untouched_if_absent(formal_existed)

    def test_schema_only_does_not_call_initialize_database(self) -> None:
        formal_existed = formal_db_path().is_file()
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "missing.db"
            destination = Path(temp_dir) / "verify" / "sqe_v2.db"
            with patch("database.connection.initialize_database") as initialize_database:
                report = prepare_verify_database(
                    source,
                    destination,
                    allow_schema_only=True,
                )
            initialize_database.assert_not_called()
            self.assertEqual("schema_only", report["mode"])
            self._assert_formal_untouched_if_absent(formal_existed)

    def test_formal_source_is_allowed_as_readonly_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_formal = Path(temp_dir) / "data" / "sqe_v2.db"
            destination = Path(temp_dir) / "verify" / "sqe_v2.db"
            fake_formal.parent.mkdir(parents=True)
            writer = sqlite3.connect(fake_formal)
            try:
                writer.execute("CREATE TABLE evidence(id INTEGER PRIMARY KEY, value TEXT)")
                writer.execute("INSERT INTO evidence(value) VALUES ('formal-row')")
                writer.commit()
            finally:
                writer.close()
            with patch(
                "database.verify_prepare.formal_db_path",
                return_value=fake_formal.resolve(),
            ):
                report = prepare_verify_database(fake_formal, destination)
            self.assertEqual("backup", report["mode"])
            self.assertTrue(report["verified"])
            restored = sqlite3.connect(destination)
            try:
                self.assertEqual(
                    "formal-row",
                    restored.execute("SELECT value FROM evidence").fetchone()[0],
                )
            finally:
                restored.close()
            self.assertTrue(fake_formal.is_file())

    def test_existing_source_uses_verified_backup_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.db"
            destination = Path(temp_dir) / "backup.db"
            writer = sqlite3.connect(source)
            try:
                writer.execute("CREATE TABLE evidence(id INTEGER PRIMARY KEY, value TEXT)")
                writer.execute("INSERT INTO evidence(value) VALUES ('row-one')")
                writer.commit()
            finally:
                writer.close()

            report = prepare_verify_database(source, destination)
            self.assertEqual("backup", report["mode"])
            self.assertEqual("", report["schema_source"])
            self.assertTrue(report["verified"])
            self.assertTrue(report["counts_equal"])

            restored = sqlite3.connect(destination)
            try:
                self.assertEqual(
                    "row-one",
                    restored.execute("SELECT value FROM evidence").fetchone()[0],
                )
            finally:
                restored.close()

    def test_rejects_formal_destination_without_creating_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "missing.db"
            destination = Path(temp_dir) / "sqe_v2.db"
            with patch(
                "database.verify_prepare.formal_db_path",
                return_value=destination,
            ):
                with self.assertRaisesRegex(ValueError, "formal SQE database"):
                    prepare_verify_database(
                        source,
                        destination,
                        allow_schema_only=True,
                    )
            self.assertFalse(destination.exists())

    def test_cli_missing_source_exits_nonzero_without_creating_formal_db(self) -> None:
        formal_existed = formal_db_path().is_file()
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "missing.db"
            destination = Path(temp_dir) / "verify" / "sqe_v2.db"
            completed = _run_prepare_cli(source, destination)
            self.assertNotEqual(0, completed.returncode)
            self.assertIn("AllowSchemaOnlySource", completed.stderr)
            self.assertFalse(destination.exists())
            self._assert_formal_untouched_if_absent(formal_existed)

    def test_cli_schema_only_prints_json_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "missing.db"
            destination = Path(temp_dir) / "verify" / "sqe_v2.db"
            completed = _run_prepare_cli(source, destination, "--allow-schema-only")
            self.assertEqual(0, completed.returncode, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual("schema_only", payload["mode"])
            self.assertTrue(payload["verified"])
            self.assertTrue(destination.is_file())


if __name__ == "__main__":
    unittest.main()
