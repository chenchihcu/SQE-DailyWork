"""Preview or apply the explicit attachment metadata Promotion migration.

Preview is read-only. ``--apply`` is intentionally double-gated by
``SQE_ANOMALY_ATTACHMENTS_PROMOTION_APPROVED=1`` and
``SQE_DAILYWORK_CONFIRM_APPLY=1``.  This entrypoint prepares the formal
Promotion path but is never invoked with ``--apply`` as part of ordinary
startup or Phase 2R verification.
"""

from __future__ import annotations

import argparse
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

from app_paths import resolve_db_path  # noqa: E402
from database.backup import backup_sqlite_database  # noqa: E402
from database.repository import (  # noqa: E402
    migrate_anomaly_attachments_contract_v1,
    preview_anomaly_attachments_contract_v1,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview/apply the explicit attachment metadata contract migration."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite target; defaults to SQE_DB_PATH/formal runtime path.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply after verified backup; otherwise preview read-only.",
    )
    return parser.parse_args()


def _readonly_connection(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _writable_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def _promotion_marker_enabled() -> bool:
    enabled = {"1", "true", "yes", "on"}
    return all(
        os.environ.get(name, "").strip().lower() in enabled
        for name in (
            "SQE_ANOMALY_ATTACHMENTS_PROMOTION_APPROVED",
            "SQE_DAILYWORK_CONFIRM_APPLY",
        )
    )


def _integrity_report(connection: sqlite3.Connection) -> dict[str, str]:
    return {
        "integrity_check": str(
            connection.execute("PRAGMA integrity_check").fetchone()[0]
        ),
        "foreign_key_check": str(
            connection.execute("PRAGMA foreign_key_check").fetchall()
        ),
    }


def main() -> int:
    args = _parse_args()
    target = Path(args.db or resolve_db_path()).expanduser().resolve()
    if not target.is_file():
        raise FileNotFoundError(f"SQLite target does not exist: {target}")

    if not args.apply:
        connection = _readonly_connection(target)
        try:
            report = preview_anomaly_attachments_contract_v1(connection)
        finally:
            connection.close()
        print(
            json.dumps(
                {"mode": "preview", "db": str(target), **report},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not _promotion_marker_enabled():
        raise RuntimeError(
            "Apply refused: SQE_ANOMALY_ATTACHMENTS_PROMOTION_APPROVED=1 and "
            "SQE_DAILYWORK_CONFIRM_APPLY=1 are required"
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = target.with_name(
        f"{target.stem}_backup_anomaly_attachments_v1_{timestamp}{target.suffix}"
    )
    backup_report = backup_sqlite_database(target, backup_path, verify=True)

    connection = _writable_connection(target)
    try:
        preview = preview_anomaly_attachments_contract_v1(connection)
        migration = migrate_anomaly_attachments_contract_v1(connection, apply=True)
        connection.commit()
        integrity = _integrity_report(connection)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    report = {
        "mode": "apply",
        "db": str(target),
        "backup": backup_report,
        "preview": preview,
        "migration": migration,
        "integrity": integrity,
        "rollback": {
            "database_backup": str(backup_path),
            "application": "previous verified version",
            "strategy": "restore complete pre-migration backup; do not use reverse SQL",
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
