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
        self.assertIn("release-gate-summary.previous.json", verify_script)
        self.assertIn('Write-ReleaseSummary -Passed $false', verify_script)

    def test_build_windows_records_zip_sha256_field(self) -> None:
        build_script = Path("scripts/build_windows.ps1").read_text(encoding="utf-8")
        self.assertIn("zip_sha256", build_script)
        self.assertIn("scratch\\release-build", build_script)
        self.assertIn("sanitized native-library PATH", build_script)
        self.assertIn("Assert-PyInstallerCollection", build_script)
        self.assertIn("Archive-VerifiedCurrentArtifact", build_script)

    def test_packaging_spec_does_not_collect_all_qt_or_tests(self) -> None:
        spec = Path("scripts/sqe_dailywork.spec").read_text(encoding="utf-8")
        self.assertNotIn("collect_all", spec)
        self.assertNotIn("collect_submodules", spec)
        self.assertIn('"ncr.tests"', spec)
        self.assertIn('"PySide6.scripts"', spec)

    def test_frozen_smoke_has_bounded_timeout(self) -> None:
        helper = Path("scripts/release_smoke_helpers.ps1").read_text(encoding="utf-8")
        portable = Path("scripts/portable_install_smoke.ps1").read_text(encoding="utf-8")
        self.assertIn("WaitForExit($TimeoutSeconds * 1000)", helper)
        self.assertIn("Stop-Process -Id $process.Id -Force", helper)
        self.assertIn("SmokeTimeoutSeconds = 120", portable)

    def test_main_baseline_refresh_is_disposable_and_fingerprinted(self) -> None:
        script = Path("scripts/refresh_main_visual_baselines.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("sqlite_backup.py", script)
        self.assertIn("SQE_REQUIRE_DISPOSABLE_DB", script)
        self.assertIn("sqlite_readonly_fingerprint.py", script)
        self.assertIn("--target main", script)
        self.assertIn("--update", script)

        event_script = Path(
            "scripts/refresh_event_create_visual_baselines.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn("sqlite_backup.py", event_script)
        self.assertIn("SQE_REQUIRE_DISPOSABLE_DB", event_script)
        self.assertIn("sqlite_readonly_fingerprint.py", event_script)
        self.assertIn("--target event-create", event_script)
        self.assertIn("--update", event_script)

        release_visual_script = Path(
            "scripts/refresh_release_visual_baselines.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn("sqlite_backup.py", release_visual_script)
        self.assertIn("SQE_REQUIRE_DISPOSABLE_DB", release_visual_script)
        self.assertIn("sqlite_readonly_fingerprint.py", release_visual_script)
        self.assertIn('"appearance-settings"', release_visual_script)
        self.assertIn('"manager-view"', release_visual_script)
        self.assertIn("--update", release_visual_script)


if __name__ == "__main__":
    unittest.main()
