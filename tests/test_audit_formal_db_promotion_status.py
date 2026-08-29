from __future__ import annotations

import importlib.util
import sqlite3
import unittest
from pathlib import Path

_AUDIT_MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "audit_formal_db_promotion_status.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "audit_formal_db_promotion_status",
    _AUDIT_MODULE_PATH,
)
assert _SPEC and _SPEC.loader
_AUDIT_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_AUDIT_MODULE)
MIGRATION_META_KEYS = _AUDIT_MODULE.MIGRATION_META_KEYS
build_promotion_status_report = _AUDIT_MODULE.build_promotion_status_report


class AuditFormalDbPromotionStatusTests(unittest.TestCase):
    def test_missing_database_is_not_ready(self) -> None:
        report = build_promotion_status_report(Path("scratch/missing-formal-db.db"))
        self.assertFalse(report["exists"])
        self.assertFalse(report["ready"])
        self.assertFalse(any(report["expected_keys_present"].values()))

    def test_empty_migration_meta_is_not_ready(self) -> None:
        db_path = Path("scratch/test-promotion-empty-meta.db")
        if db_path.exists():
            db_path.unlink()
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE migration_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.commit()
        conn.close()

        report = build_promotion_status_report(db_path)
        self.assertTrue(report["exists"])
        self.assertFalse(report["ready"])
        for key in MIGRATION_META_KEYS:
            self.assertFalse(report["expected_keys_present"][key])

        db_path.unlink(missing_ok=True)

    def test_script_writes_json_for_formal_db_when_present(self) -> None:
        formal_db = Path("data/sqe_v2.db")
        if not formal_db.is_file():
            self.skipTest("formal database not present in workspace")

        report = build_promotion_status_report(formal_db)
        self.assertTrue(report["ready"])
        self.assertTrue(all(report["expected_keys_present"].values()))
        product_records = report.get("product_records")
        self.assertIsInstance(product_records, dict)
        assert isinstance(product_records, dict)
        self.assertTrue(product_records.get("has_is_active_filter"))


class VerifyReleaseProfileContractTests(unittest.TestCase):
    def test_verify_ps1_declares_release_profile(self) -> None:
        verify_script = Path("scripts/verify.ps1").read_text(encoding="utf-8")
        self.assertIn('"Release"', verify_script)
        self.assertIn("Release verification passed.", verify_script)
        self.assertIn("release-gate-summary.json", verify_script)

    def test_build_windows_records_zip_sha256_field(self) -> None:
        build_script = Path("scripts/build_windows.ps1").read_text(encoding="utf-8")
        self.assertIn("zip_sha256", build_script)


if __name__ == "__main__":
    unittest.main()
