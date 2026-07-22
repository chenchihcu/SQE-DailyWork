from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database.migration import LegacyMigrationError, migrate_legacy_data_if_needed
from database.repository import count_rows, get_migration_meta


class LegacyMigrationAtomicityTests(unittest.TestCase):
    def test_error_rolls_back_rows_and_does_not_write_completion_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy = root / "sqe.db"
            target = root / "sqe_v2.db"
            conn = sqlite3.connect(legacy)
            try:
                conn.executescript(
                    """
                    CREATE TABLE suppliers(id TEXT PRIMARY KEY, supplier_name TEXT);
                    CREATE TABLE issues(
                        id TEXT PRIMARY KEY,
                        supplier_id TEXT,
                        issue_date TEXT,
                        problem TEXT
                    );
                    INSERT INTO suppliers VALUES ('sup-1', '原始供應商');
                    INSERT INTO issues VALUES ('issue-1', 'sup-1', '2026-06-01', '已匯入後故障');
                    """
                )
                conn.commit()
            finally:
                conn.close()

            with patch(
                "database.migration._migrate_visits",
                side_effect=RuntimeError("injected migration failure"),
            ):
                with self.assertRaises(LegacyMigrationError) as ctx:
                    migrate_legacy_data_if_needed(target, legacy)

            verify = sqlite3.connect(target)
            verify.row_factory = sqlite3.Row
            try:
                self.assertEqual(
                    {"suppliers": 0, "products": 0, "anomalies": 0, "visits": 0},
                    count_rows(verify),
                )
                self.assertIsNone(get_migration_meta(verify, "legacy_migrated"))
            finally:
                verify.close()
            report_path = Path(ctx.exception.report["reconciliation_report_path"])
            self.assertTrue(report_path.is_file())
            self.assertIn("injected migration failure", "\n".join(ctx.exception.report["errors"]))

    def test_duplicate_business_key_is_not_silently_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy = root / "sqe.db"
            target = root / "sqe_v2.db"
            conn = sqlite3.connect(legacy)
            try:
                conn.executescript(
                    """
                    CREATE TABLE suppliers(id TEXT PRIMARY KEY, supplier_name TEXT);
                    CREATE TABLE issues(
                        id TEXT PRIMARY KEY,
                        issue_no TEXT,
                        supplier_id TEXT,
                        issue_date TEXT,
                        problem TEXT
                    );
                    INSERT INTO suppliers VALUES ('sup-1', '原始供應商');
                    INSERT INTO issues VALUES
                        ('issue-1', '20260601001', 'sup-1', '2026-06-01', '第一筆'),
                        ('issue-2', '20260601001', 'sup-1', '2026-06-01', '重複單號');
                    """
                )
                conn.commit()
            finally:
                conn.close()

            with self.assertRaises(LegacyMigrationError) as ctx:
                migrate_legacy_data_if_needed(target, legacy)

            verify = sqlite3.connect(target)
            verify.row_factory = sqlite3.Row
            try:
                self.assertEqual(0, count_rows(verify)["anomalies"])
                self.assertIsNone(get_migration_meta(verify, "legacy_migrated"))
            finally:
                verify.close()
            self.assertIn("UNIQUE constraint failed", "\n".join(ctx.exception.report["errors"]))


if __name__ == "__main__":
    unittest.main()
