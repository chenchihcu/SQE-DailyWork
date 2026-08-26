"""Read-only forensic audit for the Phase 1 formal-database incident.

This script never opens either database in writable mode.  It compares the
formal database with the newest verified ``case_actions_v1`` pre-migration
backup and reports whether every committed difference is explained by the
deterministic Phase 1 migration.  It intentionally does not perform rollback.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for candidate in (SRC_ROOT, REPO_ROOT):
    candidate_text = str(candidate)
    if candidate_text not in sys.path:
        sys.path.insert(0, candidate_text)

from app_paths import formal_db_path  # noqa: E402
from database.backup import sqlite_state_fingerprint  # noqa: E402
from database.case_action_repository import (  # noqa: E402
    preview_case_actions_v1_migration,
)
from database.repo_helpers import CASE_ACTIONS_MIGRATION_META_KEY  # noqa: E402


CANONICAL_TABLES = {
    "action_verifications",
    "case_action_legacy_map",
    "case_actions",
}
EXPECTED_COMMON_TABLE_COLUMN_ADDITIONS = {
    "anomaly_attachments": {"related_action_id"},
}
EXPECTED_INDEX_ADDITIONS = {
    "idx_action_verifications_action",
    "idx_anomaly_attachments_action",
    "idx_case_actions_anomaly",
    "idx_case_actions_due",
}
EXPECTED_DERIVED_REFRESH_COLUMNS = {
    "monthly_stats_cache": {"updated_at"},
}


def _readonly_connection(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _names(connection: sqlite3.Connection, object_type: str) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = ? AND name NOT LIKE 'sqlite_%'",
            (object_type,),
        ).fetchall()
    }


def _columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [
        str(row[1])
        for row in connection.execute(
            f"PRAGMA table_info({_quote(table)})"
        ).fetchall()
    ]


def _json_value(value: object) -> object:
    if isinstance(value, bytes):
        return {"bytes_base64": base64.b64encode(value).decode("ascii")}
    return value


def _row_fingerprint(
    connection: sqlite3.Connection,
    table: str,
    columns: list[str],
    *,
    exclude_case_actions_meta: bool = False,
) -> dict[str, Any]:
    projection = ", ".join(_quote(column) for column in columns)
    where = ""
    params: tuple[object, ...] = ()
    if exclude_case_actions_meta:
        where = " WHERE key <> ?"
        params = (CASE_ACTIONS_MIGRATION_META_KEY,)
    rows = connection.execute(
        f"SELECT {projection} FROM {_quote(table)}{where}",
        params,
    ).fetchall()
    encoded_rows = [
        json.dumps(
            [_json_value(value) for value in tuple(row)],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        for row in rows
    ]
    encoded_rows.sort()
    digest = hashlib.sha256()
    for encoded in encoded_rows:
        digest.update(encoded.encode("utf-8"))
        digest.update(b"\n")
    return {"rows": len(encoded_rows), "sha256": digest.hexdigest()}


def _integrity(connection: sqlite3.Connection) -> dict[str, Any]:
    return {
        "integrity_check": str(
            connection.execute("PRAGMA integrity_check").fetchone()[0]
        ),
        "foreign_key_check": [
            tuple(row)
            for row in connection.execute("PRAGMA foreign_key_check").fetchall()
        ],
    }


def _trigger_additions(
    backup: sqlite3.Connection,
    current: sqlite3.Connection,
) -> tuple[list[str], list[str]]:
    backup_triggers = _names(backup, "trigger")
    added = sorted(_names(current, "trigger") - backup_triggers)
    unexpected = [
        name
        for name in added
        if not (
            name.startswith("guard_anomaly_actions_")
            or name.startswith("guard_corrective_actions_")
        )
        or not name.endswith("_case_actions_v1")
    ]
    return added, unexpected


def _audit(backup_path: Path, current_path: Path) -> dict[str, Any]:
    backup = _readonly_connection(backup_path)
    current = _readonly_connection(current_path)
    try:
        backup_tables = _names(backup, "table")
        current_tables = _names(current, "table")
        added_tables = current_tables - backup_tables
        removed_tables = backup_tables - current_tables

        common_table_data: dict[str, Any] = {}
        unexpected_column_changes: dict[str, Any] = {}
        data_mismatches: list[str] = []
        explained_derived_refreshes: list[str] = []
        unexplained_data_mismatches: list[str] = []
        for table in sorted(backup_tables & current_tables):
            backup_columns = _columns(backup, table)
            current_columns = _columns(current, table)
            common_columns = [
                column for column in backup_columns if column in current_columns
            ]
            removed_columns = sorted(set(backup_columns) - set(current_columns))
            added_columns = sorted(set(current_columns) - set(backup_columns))
            expected_added = EXPECTED_COMMON_TABLE_COLUMN_ADDITIONS.get(
                table,
                set(),
            ) if added_tables == CANONICAL_TABLES else set()
            if removed_columns or set(added_columns) != expected_added:
                unexpected_column_changes[table] = {
                    "removed": removed_columns,
                    "added": added_columns,
                    "expected_added": sorted(expected_added),
                }

            exclude_meta = table == "migration_meta"
            before = _row_fingerprint(
                backup,
                table,
                common_columns,
                exclude_case_actions_meta=exclude_meta,
            )
            after = _row_fingerprint(
                current,
                table,
                common_columns,
                exclude_case_actions_meta=exclude_meta,
            )
            matches = before == after
            common_table_data[table] = {
                "matches": matches,
                "backup": before,
                "current": after,
            }
            if not matches:
                data_mismatches.append(table)
                ignored_columns = EXPECTED_DERIVED_REFRESH_COLUMNS.get(
                    table,
                    set(),
                )
                stable_columns = [
                    column
                    for column in common_columns
                    if column not in ignored_columns
                ]
                stable_before = _row_fingerprint(
                    backup,
                    table,
                    stable_columns,
                )
                stable_after = _row_fingerprint(
                    current,
                    table,
                    stable_columns,
                )
                stable_matches = bool(ignored_columns) and (
                    stable_before == stable_after
                )
                common_table_data[table]["derived_refresh_analysis"] = {
                    "ignored_columns": sorted(ignored_columns),
                    "stable_columns_match": stable_matches,
                    "backup": stable_before,
                    "current": stable_after,
                }
                if stable_matches:
                    explained_derived_refreshes.append(table)
                else:
                    unexplained_data_mismatches.append(table)

        backup_preview = preview_case_actions_v1_migration(backup)
        current_preview = preview_case_actions_v1_migration(current)
        current_counts = {
            table: int(
                current.execute(
                    f"SELECT COUNT(*) FROM {_quote(table)}"
                ).fetchone()[0]
            )
            for table in CANONICAL_TABLES
            if table in current_tables
        }
        canonical_counts_match = (
            current_counts.get("case_actions", -1)
            == int(backup_preview["expected_case_actions"])
            and current_counts.get("case_action_legacy_map", -1)
            == int(backup_preview["expected_case_actions"])
            and current_counts.get("action_verifications", -1)
            == int(backup_preview["expected_action_verifications"])
        )
        nonlegacy_actions = (
            int(
                current.execute(
                    "SELECT COUNT(*) FROM case_actions "
                    "WHERE legacy_source NOT IN "
                    "('anomaly_actions','corrective_actions') "
                    "OR legacy_source IS NULL"
                ).fetchone()[0]
            )
            if "case_actions" in current_tables
            else -1
        )
        attachment_link_mismatches = 0
        if (
            "anomaly_attachments" in current_tables
            and "case_action_legacy_map" in current_tables
            and "related_action_id" in _columns(current, "anomaly_attachments")
        ):
            attachment_link_mismatches = int(
                current.execute(
                    """
                    SELECT COUNT(*)
                    FROM anomaly_attachments AS attachment
                    LEFT JOIN case_action_legacy_map AS mapping
                      ON mapping.legacy_source = 'corrective_actions'
                     AND mapping.legacy_id = attachment.related_ca_id
                    WHERE trim(coalesce(attachment.related_ca_id, '')) <> ''
                      AND coalesce(attachment.related_action_id, '')
                          <> coalesce(mapping.canonical_id, '')
                    """
                ).fetchone()[0]
            )

        backup_indexes = _names(backup, "index")
        added_indexes = sorted(_names(current, "index") - backup_indexes)
        unexpected_indexes = sorted(
            set(added_indexes) - EXPECTED_INDEX_ADDITIONS
        )
        added_triggers, unexpected_triggers = _trigger_additions(backup, current)
        backup_integrity = _integrity(backup)
        current_integrity = _integrity(current)

        checks = {
            "backup_predates_current": (
                backup_path.stat().st_mtime_ns <= current_path.stat().st_mtime_ns
            ),
            "backup_has_no_canonical_tables": not bool(
                backup_tables & CANONICAL_TABLES
            ),
            "current_added_only_canonical_tables": added_tables
            == CANONICAL_TABLES,
            "no_tables_removed": not removed_tables,
            "no_unexpected_column_changes": not unexpected_column_changes,
            "no_unexplained_preexisting_row_changes": not (
                unexplained_data_mismatches
            ),
            "canonical_counts_match_legacy_preview": canonical_counts_match,
            "no_post_migration_actions": nonlegacy_actions == 0,
            "attachment_links_match_mapping": attachment_link_mismatches == 0,
            "no_unexpected_indexes": not unexpected_indexes,
            "no_unexpected_triggers": not unexpected_triggers,
            "backup_integrity_ok": (
                backup_integrity["integrity_check"] == "ok"
                and not backup_integrity["foreign_key_check"]
            ),
            "current_integrity_ok": (
                current_integrity["integrity_check"] == "ok"
                and not current_integrity["foreign_key_check"]
            ),
            "current_schema_ready": bool(current_preview["ready"]),
        }
        safe_rollback_candidate = all(checks.values())
        backup_state = sqlite_state_fingerprint(backup_path)
        current_state = sqlite_state_fingerprint(current_path)
        restored_pre_migration_state = (
            backup_state["state_sha256"] == current_state["state_sha256"]
        )
        formal_state = (
            "PRE_MIGRATION_RESTORED"
            if restored_pre_migration_state
            else (
                "MIGRATED_ROLLBACK_CANDIDATE"
                if safe_rollback_candidate
                else "UNEXPLAINED"
            )
        )
        return {
            "mode": "read_only_forensic_audit",
            "backup": str(backup_path),
            "current": str(current_path),
            "backup_integrity": backup_integrity,
            "current_integrity": current_integrity,
            "backup_preview": backup_preview,
            "current_preview": current_preview,
            "schema_diff": {
                "added_tables": sorted(added_tables),
                "removed_tables": sorted(removed_tables),
                "unexpected_column_changes": unexpected_column_changes,
                "added_indexes": added_indexes,
                "unexpected_indexes": unexpected_indexes,
                "added_triggers": added_triggers,
                "unexpected_triggers": unexpected_triggers,
            },
            "data_diff": {
                "mismatched_preexisting_tables": data_mismatches,
                "explained_derived_refreshes": explained_derived_refreshes,
                "unexplained_preexisting_tables": unexplained_data_mismatches,
                "common_table_fingerprints": common_table_data,
                "canonical_counts": current_counts,
                "nonlegacy_case_actions": nonlegacy_actions,
                "attachment_link_mismatches": attachment_link_mismatches,
            },
            "checks": checks,
            "backup_state_sha256": backup_state["state_sha256"],
            "current_state_sha256": current_state["state_sha256"],
            "formal_state": formal_state,
            "restored_pre_migration_state": restored_pre_migration_state,
            "safe_rollback_candidate": safe_rollback_candidate,
            "verified_expected_state": (
                restored_pre_migration_state or safe_rollback_candidate
            ),
        }
    finally:
        current.close()
        backup.close()


def main() -> int:
    current = formal_db_path().resolve()
    candidates = sorted(
        current.parent.glob(
            f"{current.stem}_backup_case_actions_v1_*{current.suffix}"
        ),
        key=lambda path: path.stat().st_mtime_ns,
    )
    if not current.is_file():
        raise FileNotFoundError(f"Formal SQLite database not found: {current}")
    if not candidates:
        raise FileNotFoundError("No case_actions_v1 pre-migration backup found")
    report = _audit(candidates[-1].resolve(), current)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verified_expected_state"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
