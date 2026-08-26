from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from database.backup import backup_sqlite_database, sqlite_state_fingerprint


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

    def test_logical_fingerprint_detects_data_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.db"
            backup = Path(temp_dir) / "backup.db"
            connection = sqlite3.connect(source)
            connection.execute("CREATE TABLE evidence(id INTEGER PRIMARY KEY, value TEXT)")
            connection.execute("INSERT INTO evidence(value) VALUES ('same-state')")
            connection.commit()
            connection.close()
            backup_sqlite_database(source, backup)

            before = sqlite_state_fingerprint(source)
            copied = sqlite_state_fingerprint(backup)
            self.assertEqual(before["state_sha256"], copied["state_sha256"])

            connection = sqlite3.connect(backup)
            connection.execute("UPDATE evidence SET value = 'changed-state'")
            connection.commit()
            connection.close()
            changed = sqlite_state_fingerprint(backup)
            self.assertNotEqual(before["state_sha256"], changed["state_sha256"])

    def test_online_backup_overwrites_existing_destination_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.db"
            destination = Path(temp_dir) / "destination.db"
            source_connection = sqlite3.connect(source)
            source_connection.execute("CREATE TABLE original(id INTEGER PRIMARY KEY)")
            source_connection.execute("INSERT INTO original VALUES (1)")
            source_connection.commit()
            source_connection.close()

            destination_connection = sqlite3.connect(destination)
            destination_connection.execute("PRAGMA journal_mode=WAL")
            destination_connection.execute("CREATE TABLE unwanted(value TEXT)")
            destination_connection.execute("INSERT INTO unwanted VALUES ('remove-me')")
            destination_connection.commit()
            destination_connection.close()

            report = backup_sqlite_database(source, destination)
            self.assertTrue(report["verified"])
            restored = sqlite3.connect(destination)
            try:
                tables = {
                    str(row[0])
                    for row in restored.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
                self.assertIn("original", tables)
                self.assertNotIn("unwanted", tables)
                self.assertEqual(
                    1,
                    restored.execute("SELECT COUNT(*) FROM original").fetchone()[0],
                )
            finally:
                restored.close()


if __name__ == "__main__":
    unittest.main()
