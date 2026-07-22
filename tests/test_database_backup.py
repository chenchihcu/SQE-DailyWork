from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from database.backup import backup_sqlite_database


class DatabaseBackupTests(unittest.TestCase):
    def test_online_backup_includes_committed_uncheckpointed_wal_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.db"
            backup = Path(temp_dir) / "backup.db"
            writer = sqlite3.connect(source)
            try:
                self.assertEqual("wal", writer.execute("PRAGMA journal_mode=WAL").fetchone()[0])
                writer.execute("PRAGMA wal_autocheckpoint=0")
                writer.execute("CREATE TABLE evidence(id INTEGER PRIMARY KEY, value TEXT)")
                writer.commit()
                writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                writer.execute("INSERT INTO evidence(value) VALUES ('committed-in-wal')")
                writer.commit()
                self.assertTrue(source.with_name(source.name + "-wal").exists())

                report = backup_sqlite_database(source, backup)
            finally:
                writer.close()

            self.assertTrue(report["verified"])
            restored = sqlite3.connect(backup)
            try:
                self.assertEqual(
                    "committed-in-wal",
                    restored.execute("SELECT value FROM evidence").fetchone()[0],
                )
            finally:
                restored.close()

    def test_backup_rejects_same_source_and_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.db"
            sqlite3.connect(source).close()
            with self.assertRaises(ValueError):
                backup_sqlite_database(source, source)


if __name__ == "__main__":
    unittest.main()
