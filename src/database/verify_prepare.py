"""Prepare a disposable verification SQLite database.

Local Windows verify copies an existing formal or ``SQE_DB_PATH`` source.
Clean clones and CI have no ``data/sqe_v2.db``; they may synthesize a
schema-only scratch source, then take the same verified online backup.

Never writes the formal database path. Schema-only mode uses
``create_schema`` only — not ``initialize_database()`` — so legacy/NCR
migration paths are not scanned.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app_paths import formal_db_path
from database.backup import backup_sqlite_database


SCHEMA_SOURCE_NAME = "schema-source.db"
MISSING_SOURCE_HINT = (
    "Local verify requires data/sqe_v2.db or SQE_DB_PATH. "
    "CI/clean-clone should pass --allow-schema-only "
    "(verify.ps1 -AllowSchemaOnlySource)."
)


def _resolve(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _assert_not_formal(*paths: Path) -> None:
    formal = _resolve(formal_db_path())
    for path in paths:
        if _resolve(path) == formal:
            raise ValueError(f"Refusing formal SQE database path: {path}")


def _backup_report(
    source: Path,
    destination: Path,
    *,
    mode: str,
    schema_source: str = "",
) -> dict[str, Any]:
    report = backup_sqlite_database(source, destination)
    report["mode"] = mode
    report["schema_source"] = schema_source
    return report


def prepare_verify_database(
    source: str | Path,
    destination: str | Path,
    *,
    allow_schema_only: bool = False,
) -> dict[str, Any]:
    """Backup ``source`` to ``destination``, or synthesize schema-only source.

    Returns a JSON-serializable report with ``mode`` of ``backup`` or
    ``schema_only``. ``schema_source`` is set only for schema-only mode.
    """

    destination_path = _resolve(destination)
    _assert_not_formal(destination_path)

    source_path = _resolve(source)
    if source_path.is_file():
        return _backup_report(source_path, destination_path, mode="backup")

    if not allow_schema_only:
        raise FileNotFoundError(
            f"SQLite source does not exist: {source_path}. {MISSING_SOURCE_HINT}"
        )

    schema_source = _resolve(destination_path.parent / SCHEMA_SOURCE_NAME)
    _assert_not_formal(schema_source)
    if schema_source == destination_path:
        raise ValueError("schema-source must differ from destination")

    schema_source.parent.mkdir(parents=True, exist_ok=True)
    if schema_source.exists():
        schema_source.unlink()

    from database.connection import get_connection
    from database.repository import create_schema

    with get_connection(schema_source) as conn:
        create_schema(conn)

    return _backup_report(
        schema_source,
        destination_path,
        mode="schema_only",
        schema_source=str(schema_source),
    )
