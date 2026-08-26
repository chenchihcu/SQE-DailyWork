"""Restore the formal DB after the unauthorized Phase 1 migration incident.

The rollback is fail-closed: it first reruns the read-only forensic audit,
creates a verified snapshot of the incident state, restores via SQLite's online
backup API, and then requires exact logical-state parity with the verified
pre-migration backup.  On a failed restore check it attempts to put the
incident snapshot back before returning failure.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for candidate in (SRC_ROOT, REPO_ROOT):
    candidate_text = str(candidate)
    if candidate_text not in sys.path:
        sys.path.insert(0, candidate_text)

from app_paths import formal_db_path  # noqa: E402
from database.backup import (  # noqa: E402
    backup_sqlite_database,
    sqlite_state_fingerprint,
)
from database.case_action_repository import (  # noqa: E402
    preview_case_actions_v1_migration,
)
from scripts.audit_case_actions_phase1_databases import _audit  # noqa: E402


def _marker_enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _readonly_preview(path: Path) -> dict[str, object]:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        return preview_case_actions_v1_migration(connection)
    finally:
        connection.close()


def main() -> int:
    if not (
        _marker_enabled("SQE_CASE_ACTIONS_INCIDENT_ROLLBACK_APPROVED")
        and _marker_enabled("SQE_DAILYWORK_CONFIRM_APPLY")
    ):
        raise RuntimeError(
            "Incident rollback refused: both rollback approval markers are required"
        )

    current = formal_db_path().resolve()
    candidates = sorted(
        current.parent.glob(
            f"{current.stem}_backup_case_actions_v1_*{current.suffix}"
        ),
        key=lambda path: path.stat().st_mtime_ns,
    )
    if not current.is_file() or not candidates:
        raise FileNotFoundError("Formal DB or verified Phase 1 backup is missing")
    pre_migration = candidates[-1].resolve()
    forensic = _audit(pre_migration, current)
    if not forensic["safe_rollback_candidate"]:
        raise RuntimeError(
            "Rollback refused: current differences are not fully explained by Phase 1"
        )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    incident_snapshot = current.with_name(
        f"{current.stem}_incident_post_case_actions_v1_{stamp}{current.suffix}"
    )
    incident_backup = backup_sqlite_database(
        current,
        incident_snapshot,
        verify=True,
    )

    try:
        restore = backup_sqlite_database(
            pre_migration,
            current,
            verify=True,
        )
        expected = sqlite_state_fingerprint(pre_migration)
        restored = sqlite_state_fingerprint(current)
        if expected["state_sha256"] != restored["state_sha256"]:
            raise RuntimeError(
                "Restored formal DB does not match the pre-migration logical state"
            )
        restored_preview = _readonly_preview(current)
        if restored_preview["ready"]:
            raise RuntimeError("Restored formal DB still contains case_actions_v1")
    except Exception:
        backup_sqlite_database(incident_snapshot, current, verify=True)
        raise

    report = {
        "mode": "case_actions_v1_incident_rollback",
        "formal_database": str(current),
        "pre_migration_backup": str(pre_migration),
        "incident_snapshot": incident_backup,
        "restore": restore,
        "restored_state_sha256": restored["state_sha256"],
        "pre_migration_state_sha256": expected["state_sha256"],
        "restored_preview": restored_preview,
        "verified": True,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
