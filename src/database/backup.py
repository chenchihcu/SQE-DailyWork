"""Verified SQLite online backups that include committed WAL content."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DatabaseBackupError(RuntimeError):
    """Raised when a SQLite backup cannot be proven complete."""


def _fingerprint_value(value: object) -> object:
    if isinstance(value, bytes):
        return {"bytes_base64": base64.b64encode(value).decode("ascii")}
    return value


def sqlite_state_fingerprint(source_path: str | Path) -> dict[str, Any]:
    """Return a stable logical fingerprint without opening SQLite writable.

    The digest covers every user-defined schema object and every table row.
    It is suitable for proving that a verification command did not mutate the
    formal database even when WAL checkpoints change the physical file bytes.
    """
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"SQLite source does not exist: {source}")

    connection = sqlite3.connect(_readonly_uri(source), uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        integrity = str(
            connection.execute("PRAGMA integrity_check").fetchone()[0]
        )
        foreign_keys = [
            tuple(row)
            for row in connection.execute("PRAGMA foreign_key_check").fetchall()
        ]
        schema_rows = connection.execute(
            """
            SELECT type, name, tbl_name, coalesce(sql, '')
            FROM sqlite_master
            WHERE name NOT LIKE 'sqlite_%'
            ORDER BY type, name
            """
        ).fetchall()
        schema_payload = json.dumps(
            [tuple(row) for row in schema_rows],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        schema_digest = hashlib.sha256(schema_payload.encode("utf-8")).hexdigest()

        tables = [
            str(row[0])
            for row in connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        ]
        data_digest = hashlib.sha256()
        row_count = 0
        table_counts: dict[str, int] = {}
        for table in tables:
            quoted_table = '"' + table.replace('"', '""') + '"'
            columns = [
                str(row[1])
                for row in connection.execute(
                    f"PRAGMA table_info({quoted_table})"
                ).fetchall()
            ]
            quoted_columns = ", ".join(
                '"' + column.replace('"', '""') + '"'
                for column in columns
            )
            rows = connection.execute(
                f"SELECT {quoted_columns} FROM {quoted_table}"
            ).fetchall()
            encoded_rows = [
                json.dumps(
                    [_fingerprint_value(value) for value in tuple(row)],
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                for row in rows
            ]
            encoded_rows.sort()
            table_counts[table] = len(encoded_rows)
            row_count += len(encoded_rows)
            data_digest.update(table.encode("utf-8"))
            data_digest.update(json.dumps(columns).encode("utf-8"))
            for encoded in encoded_rows:
                data_digest.update(encoded.encode("utf-8"))
                data_digest.update(b"\n")
    finally:
        connection.close()

    combined = hashlib.sha256(
        f"{schema_digest}:{data_digest.hexdigest()}".encode("ascii")
    ).hexdigest()
    return {
        "source": str(source),
        "integrity_check": integrity,
        "foreign_key_check": foreign_keys,
        "schema_sha256": schema_digest,
        "data_sha256": data_digest.hexdigest(),
        "state_sha256": combined,
        "table_count": len(tables),
        "row_count": row_count,
        "table_counts": table_counts,
    }


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


def prune_backups(
    backup_dir: str | Path,
    max_count: int,
    *,
    pattern: str = "*backup*.db",
) -> list[Path]:
    """Prune older backups in backup_dir exceeding max_count, keeping the newest files."""
    if max_count <= 0:
        return []
    directory = Path(backup_dir).expanduser().resolve()
    if not directory.is_dir():
        return []
    files = [f for f in directory.glob(pattern) if f.is_file()]
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    removed: list[Path] = []
    if len(files) > max_count:
        for old_file in files[max_count:]:
            try:
                old_file.unlink(missing_ok=True)
                removed.append(old_file)
            except Exception:
                logger.exception("刪除舊備份失敗: %s", old_file)
    return removed
