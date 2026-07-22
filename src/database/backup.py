"""Verified SQLite online backups that include committed WAL content."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class DatabaseBackupError(RuntimeError):
    """Raised when a SQLite backup cannot be proven complete."""


def _readonly_uri(path: Path) -> str:
    return f"file:{path.resolve().as_posix()}?mode=ro"


def _table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    tables = [
        str(row[0])
        for row in conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
    ]
    return {
        table: int(
            conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        )
        for table in tables
    }


def backup_sqlite_database(
    source_path: str | Path,
    destination_path: str | Path,
    *,
    verify: bool = True,
) -> dict[str, Any]:
    """Create a SQLite online backup and verify integrity/count parity.

    The source is opened read-only. ``sqlite3.Connection.backup`` reads the
    current committed database image, including pages still resident in WAL.
    """

    source = Path(source_path).expanduser().resolve()
    destination = Path(destination_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"SQLite source does not exist: {source}")
    if source == destination:
        raise ValueError("SQLite backup destination must differ from source")

    destination.parent.mkdir(parents=True, exist_ok=True)
    source_conn = sqlite3.connect(_readonly_uri(source), uri=True)
    destination_conn = sqlite3.connect(destination)
    try:
        source_conn.execute("PRAGMA query_only=ON")
        source_conn.backup(destination_conn)
        destination_conn.commit()
    except Exception:
        destination_conn.rollback()
        raise
    finally:
        destination_conn.close()
        source_conn.close()

    report: dict[str, Any] = {
        "source": str(source),
        "destination": str(destination),
        "verified": False,
    }
    if not verify:
        return report

    source_conn = sqlite3.connect(_readonly_uri(source), uri=True)
    backup_conn = sqlite3.connect(_readonly_uri(destination), uri=True)
    try:
        source_integrity = str(
            source_conn.execute("PRAGMA integrity_check").fetchone()[0]
        )
        backup_integrity = str(
            backup_conn.execute("PRAGMA integrity_check").fetchone()[0]
        )
        source_counts = _table_counts(source_conn)
        backup_counts = _table_counts(backup_conn)
    finally:
        backup_conn.close()
        source_conn.close()

    report.update(
        {
            "source_integrity": source_integrity,
            "backup_integrity": backup_integrity,
            "table_counts": backup_counts,
            "table_count": len(backup_counts),
            "row_count": sum(backup_counts.values()),
            "counts_equal": source_counts == backup_counts,
        }
    )
    if source_integrity != "ok" or backup_integrity != "ok":
        raise DatabaseBackupError(
            "SQLite integrity check failed: "
            f"source={source_integrity}, backup={backup_integrity}"
        )
    if source_counts != backup_counts:
        raise DatabaseBackupError("SQLite backup row-count parity check failed")
    report["verified"] = True
    return report
