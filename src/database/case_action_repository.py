"""Canonical Action persistence and deterministic legacy migration.

This module is the repository-layer owner for the Phase 1 ``case_actions``
contract. Existing databases are never upgraded merely by importing it; the
caller must invoke :func:`migrate_case_actions_v1` with ``apply=True`` from an
approved disposable/fresh install path or the formal Promotion Gate.
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from app_paths import formal_db_path
from database.repo_helpers import (
    ACTION_VERIFICATION_EFFECTIVE,
    ACTION_VERIFICATION_INCONCLUSIVE,
    ACTION_VERIFICATION_INEFFECTIVE,
    ACTION_VERIFICATION_NOT_APPLICABLE,
    ACTION_VERIFICATION_NOT_REQUIRED,
    ACTION_VERIFICATION_PENDING,
    ACTION_VERIFICATION_RESULTS,
    ANOMALY_ACTION_STATUS_CANCELLED,
    ANOMALY_ACTION_STATUS_COMPLETED,
    ANOMALY_ACTION_STATUS_OPEN,
    CASE_ACTION_LEGACY_SOURCE_CORRECTIVE_ACTION,
    CASE_ACTION_LEGACY_SOURCE_NEXT_ACTION,
    CASE_ACTION_OPEN_STATUSES,
    CASE_ACTION_STATUS_CANCELLED,
    CASE_ACTION_STATUS_COMPLETED,
    CASE_ACTION_STATUS_IN_PROGRESS,
    CASE_ACTION_STATUS_PLANNED,
    CASE_ACTION_TYPE_CORRECTIVE_ACTION,
    CASE_ACTION_TYPE_LABELS,
    CASE_ACTION_TYPE_NEXT_ACTION,
    CASE_ACTION_TYPES,
    CASE_ACTION_VERIFICATION_ELIGIBLE_TYPES,
    CASE_ACTIONS_MIGRATION_META_KEY,
    CASE_ACTIONS_SCHEMA_VERSION,
    CORRECTIVE_ACTION_STATUS_CANCELLED,
    CORRECTIVE_ACTION_STATUS_EFFECTIVE,
    CORRECTIVE_ACTION_STATUS_IMPLEMENTED,
    CORRECTIVE_ACTION_STATUS_INEFFECTIVE,
    CORRECTIVE_ACTION_STATUS_IN_PROGRESS,
    CORRECTIVE_ACTION_STATUS_PLANNED,
    CORRECTIVE_ACTION_STATUS_VERIFICATION_PENDING,
    _as_int,
    _ensure_date_not_in_future,
    _gen_id,
    _normalize_loose_iso_date,
    _normalize_strict_iso_date,
    _now_iso,
    _quote_identifier,
    _table_columns,
    _table_exists,
    get_migration_meta,
)


_UUID_NAMESPACE = uuid.UUID("d846dfe5-9a6a-5d4e-9709-e93013b6ef01")
SCHEMA_REQUIRED_ERROR = (
    "需要完成資料升級：case_actions_v1。請先執行經核准的資料庫 Promotion Gate。"
)
FORMAL_MIGRATION_REFUSED_ERROR = (
    "Formal case_actions_v1 migration refused: use the approved Promotion Gate "
    "after the exact cross-phase authorization."
)


def _enabled_environment_marker(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _connection_main_path(conn: sqlite3.Connection) -> Path | None:
    for row in conn.execute("PRAGMA database_list").fetchall():
        if str(row[1]) != "main":
            continue
        value = str(row[2] or "").strip()
        if not value or value == ":memory:":
            return None
        return Path(value).expanduser().resolve()
    return None


def _assert_migration_target_authorized(
    conn: sqlite3.Connection,
    preview: dict[str, Any],
    *,
    fresh_install: bool,
    formal_promotion: bool,
) -> None:
    target = _connection_main_path(conn)
    if target is None or target != formal_db_path().resolve():
        return
    if fresh_install:
        anomaly_count = (
            int(conn.execute("SELECT COUNT(*) FROM anomalies").fetchone()[0])
            if _table_exists(conn, "anomalies")
            else 0
        )
        if (
            anomaly_count == 0
            and int(preview["expected_case_actions"]) == 0
            and int(preview["expected_action_verifications"]) == 0
        ):
            return
    if (
        formal_promotion
        and _enabled_environment_marker("SQE_CASE_ACTIONS_PROMOTION_APPROVED")
        and _enabled_environment_marker("SQE_DAILYWORK_CONFIRM_APPLY")
    ):
        return
    raise RuntimeError(FORMAL_MIGRATION_REFUSED_ERROR)


def _fetch_dicts(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple[object, ...] = (),
) -> list[dict[str, Any]]:
    cursor = conn.execute(sql, params)
    names = [str(item[0]) for item in (cursor.description or ())]
    return [dict(zip(names, tuple(row), strict=True)) for row in cursor.fetchall()]


def _fetch_one_dict(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple[object, ...] = (),
) -> dict[str, Any] | None:
    rows = _fetch_dicts(conn, sql, params)
    return rows[0] if rows else None


def _table_row_count(conn: sqlite3.Connection, table_name: str) -> int:
    if not _table_exists(conn, table_name):
        return 0
    return int(
        conn.execute(
            f"SELECT COUNT(*) FROM {_quote_identifier(table_name)}"
        ).fetchone()[0]
    )


def _commit_if(conn: sqlite3.Connection, should_commit: bool) -> None:
    if should_commit:
        conn.commit()


def case_actions_schema_ready(conn: sqlite3.Connection) -> bool:
    if not _table_exists(conn, "migration_meta"):
        return False
    for table_name in (
        "case_actions",
        "action_verifications",
        "case_action_legacy_map",
    ):
        if not _table_exists(conn, table_name):
            return False
    return (
        get_migration_meta(conn, CASE_ACTIONS_MIGRATION_META_KEY)
        == CASE_ACTIONS_SCHEMA_VERSION
    )


def require_case_actions_schema(conn: sqlite3.Connection) -> None:
    if not case_actions_schema_ready(conn):
        raise RuntimeError(SCHEMA_REQUIRED_ERROR)


def _require_anomaly(conn: sqlite3.Connection, anomaly_id: str) -> str:
    key = str(anomaly_id or "").strip()
    if not key:
        raise ValueError("Anomaly id is required")
    if conn.execute("SELECT 1 FROM anomalies WHERE id = ?", (key,)).fetchone() is None:
        raise ValueError("Anomaly not found")
    return key


def _legacy_canonical_id(
    legacy_source: str,
    legacy_id: str,
    *,
    next_action_ids: set[str],
) -> str:
    if (
        legacy_source == CASE_ACTION_LEGACY_SOURCE_CORRECTIVE_ACTION
        and legacy_id in next_action_ids
    ):
        return uuid.uuid5(_UUID_NAMESPACE, f"{legacy_source}:{legacy_id}").hex
    return legacy_id


def preview_case_actions_v1_migration(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return a read-only source/count summary for the migration gate."""
    next_ids: set[str] = set()
    if _table_exists(conn, "anomaly_actions"):
        next_ids = {
            str(row[0])
            for row in conn.execute("SELECT id FROM anomaly_actions").fetchall()
        }

    corrective_rows: list[sqlite3.Row | tuple] = []
    corrective_ids: set[str] = set()
    if _table_exists(conn, "corrective_actions"):
        corrective_rows = conn.execute(
            "SELECT id, status FROM corrective_actions"
        ).fetchall()
        corrective_ids = {str(row[0]) for row in corrective_rows}

    verification_action_ids: set[str] = set()
    if _table_exists(conn, "effectiveness_verifications"):
        verification_action_ids = {
            str(row[0])
            for row in conn.execute(
                "SELECT DISTINCT corrective_action_id "
                "FROM effectiveness_verifications"
            ).fetchall()
        }
    synthetic_count = sum(
        1
        for row in corrective_rows
        if str(row[1] or "")
        in (CORRECTIVE_ACTION_STATUS_EFFECTIVE, CORRECTIVE_ACTION_STATUS_INEFFECTIVE)
        and str(row[0]) not in verification_action_ids
    )

    linked_attachments = 0
    if (
        _table_exists(conn, "anomaly_attachments")
        and "related_ca_id" in _table_columns(conn, "anomaly_attachments")
    ):
        linked_attachments = int(
            conn.execute(
                "SELECT COUNT(*) FROM anomaly_attachments "
                "WHERE trim(coalesce(related_ca_id, '')) <> ''"
            ).fetchone()[0]
        )

    legacy_verifications = _table_row_count(conn, "effectiveness_verifications")
    return {
        "migration_key": CASE_ACTIONS_MIGRATION_META_KEY,
        "schema_version": CASE_ACTIONS_SCHEMA_VERSION,
        "ready": case_actions_schema_ready(conn),
        "legacy_next_actions": len(next_ids),
        "legacy_corrective_actions": len(corrective_ids),
        "legacy_verifications": legacy_verifications,
        "legacy_id_collisions": len(next_ids & corrective_ids),
        "legacy_status_verifications": synthetic_count,
        "linked_attachments": linked_attachments,
        "expected_case_actions": len(next_ids) + len(corrective_ids),
        "expected_action_verifications": legacy_verifications + synthetic_count,
        "canonical_case_actions": _table_row_count(conn, "case_actions"),
        "canonical_action_verifications": _table_row_count(
            conn, "action_verifications"
        ),
    }


def _create_schema(conn: sqlite3.Connection) -> None:
    statements = (
        """
        CREATE TABLE IF NOT EXISTS case_actions (
            id TEXT PRIMARY KEY,
            anomaly_id TEXT NOT NULL,
            action_type TEXT NOT NULL
                CHECK (action_type IN (
                    'NEXT_ACTION','CONTAINMENT','CORRECTION',
                    'CORRECTIVE_ACTION','SYSTEMIC_IMPROVEMENT'
                )),
            description TEXT NOT NULL,
            owner TEXT NOT NULL DEFAULT '',
            due_date TEXT NOT NULL DEFAULT '',
            execution_status TEXT NOT NULL DEFAULT '已規劃'
                CHECK (execution_status IN ('已規劃','執行中','已完成','已取消')),
            verification_required INTEGER NOT NULL DEFAULT 0
                CHECK (verification_required IN (0, 1)),
            implementation_evidence TEXT NOT NULL DEFAULT '',
            completed_at TEXT,
            completion_note TEXT NOT NULL DEFAULT '',
            cancelled_at TEXT,
            cancel_note TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            legacy_source TEXT,
            legacy_id TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (anomaly_id) REFERENCES anomalies(id) ON DELETE CASCADE,
            CHECK (
                verification_required = 0
                OR action_type IN ('CORRECTIVE_ACTION','SYSTEMIC_IMPROVEMENT')
            ),
            UNIQUE (legacy_source, legacy_id)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_case_actions_anomaly
        ON case_actions(anomaly_id, execution_status, due_date)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_case_actions_due
        ON case_actions(execution_status, due_date)
        """,
        """
        CREATE TABLE IF NOT EXISTS action_verifications (
            id TEXT PRIMARY KEY,
            action_id TEXT NOT NULL,
            method TEXT NOT NULL DEFAULT '',
            acceptance_criteria TEXT NOT NULL DEFAULT '',
            period_sample TEXT NOT NULL DEFAULT '',
            result TEXT NOT NULL DEFAULT '待驗證'
                CHECK (result IN ('待驗證','有效','無效','無法判定')),
            evidence TEXT NOT NULL DEFAULT '',
            conclusion TEXT NOT NULL DEFAULT '',
            verified_by TEXT NOT NULL DEFAULT '',
            verified_date TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (action_id) REFERENCES case_actions(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_action_verifications_action
        ON action_verifications(action_id, created_at DESC)
        """,
        """
        CREATE TABLE IF NOT EXISTS case_action_legacy_map (
            legacy_source TEXT NOT NULL,
            legacy_id TEXT NOT NULL,
            canonical_id TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (legacy_source, legacy_id),
            UNIQUE (canonical_id),
            FOREIGN KEY (canonical_id) REFERENCES case_actions(id) ON DELETE CASCADE
        )
        """,
    )
    for statement in statements:
        conn.execute(statement)
    if _table_exists(conn, "anomaly_attachments"):
        if "related_action_id" not in _table_columns(conn, "anomaly_attachments"):
            conn.execute(
                "ALTER TABLE anomaly_attachments ADD COLUMN related_action_id "
                "TEXT REFERENCES case_actions(id)"
            )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_anomaly_attachments_action "
            "ON anomaly_attachments(related_action_id)"
        )


def _install_legacy_write_guards(conn: sqlite3.Connection) -> None:
    """Prevent new INSERT/UPDATE calls through retired tables.

    DELETE remains available for existing anomaly cascade behavior. Formal
    rollback restores the verified pre-migration backup and previous binary.
    """
    for table_name in ("anomaly_actions", "corrective_actions"):
        if not _table_exists(conn, table_name):
            continue
        for operation in ("INSERT", "UPDATE"):
            trigger_name = f"guard_{table_name}_{operation.lower()}_case_actions_v1"
            conn.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {_quote_identifier(trigger_name)}
                BEFORE {operation} ON {_quote_identifier(table_name)}
                BEGIN
                    SELECT RAISE(
                        ABORT,
                        'Legacy action table is read-only after case_actions_v1'
                    );
                END
                """
            )


def _insert_migrated_action(
    conn: sqlite3.Connection,
    values: tuple[object, ...],
) -> None:
    conn.execute(
        """
        INSERT INTO case_actions(
            id, anomaly_id, action_type, description, owner, due_date,
            execution_status, verification_required, implementation_evidence,
            completed_at, completion_note, cancelled_at, cancel_note, notes,
            legacy_source, legacy_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO NOTHING
        """,
        values,
    )
    canonical_id = str(values[0])
    source = str(values[14])
    legacy_id = str(values[15])
    existing = conn.execute(
        "SELECT legacy_source, legacy_id FROM case_actions WHERE id = ?",
        (canonical_id,),
    ).fetchone()
    if existing is None or tuple(existing) != (source, legacy_id):
        raise RuntimeError(
            f"Canonical action id conflict: {source}:{legacy_id} -> {canonical_id}"
        )
    conn.execute(
        """
        INSERT INTO case_action_legacy_map(
            legacy_source, legacy_id, canonical_id, created_at
        ) VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(legacy_source, legacy_id) DO UPDATE SET
            canonical_id = excluded.canonical_id
        """,
        (source, legacy_id, canonical_id),
    )


def _reconcile(
    conn: sqlite3.Connection,
    expected: dict[str, Any],
) -> dict[str, Any]:
    canonical_actions = _table_row_count(conn, "case_actions")
    canonical_verifications = _table_row_count(conn, "action_verifications")
    legacy_action_rows = int(
        conn.execute(
            "SELECT COUNT(*) FROM case_actions "
            "WHERE legacy_source IN ('anomaly_actions','corrective_actions')"
        ).fetchone()[0]
    )
    mapping_rows = _table_row_count(conn, "case_action_legacy_map")
    missing_attachment_links = 0
    if expected["linked_attachments"]:
        missing_attachment_links = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM anomaly_attachments
                WHERE trim(coalesce(related_ca_id, '')) <> ''
                  AND trim(coalesce(related_action_id, '')) = ''
                """
            ).fetchone()[0]
        )
    integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
    foreign_keys = [tuple(row) for row in conn.execute("PRAGMA foreign_key_check")]
    problems: list[str] = []
    if legacy_action_rows != int(expected["expected_case_actions"]):
        problems.append(
            "legacy action reconciliation mismatch "
            f"({legacy_action_rows} != {expected['expected_case_actions']})"
        )
    if mapping_rows != int(expected["expected_case_actions"]):
        problems.append(
            "legacy mapping reconciliation mismatch "
            f"({mapping_rows} != {expected['expected_case_actions']})"
        )
    if canonical_verifications != int(expected["expected_action_verifications"]):
        problems.append(
            "verification reconciliation mismatch "
            f"({canonical_verifications} != {expected['expected_action_verifications']})"
        )
    if missing_attachment_links:
        problems.append(f"missing attachment action links: {missing_attachment_links}")
    if integrity.lower() != "ok":
        problems.append(f"integrity_check: {integrity}")
    if foreign_keys:
        problems.append(f"foreign_key_check: {foreign_keys}")
    return {
        **expected,
        "canonical_case_actions": canonical_actions,
        "canonical_action_verifications": canonical_verifications,
        "legacy_action_rows": legacy_action_rows,
        "mapping_rows": mapping_rows,
        "missing_attachment_links": missing_attachment_links,
        "integrity_check": integrity,
        "foreign_key_violations": foreign_keys,
        "problems": problems,
        "reconciled": not problems,
    }


def migrate_case_actions_v1(
    conn: sqlite3.Connection,
    *,
    apply: bool = False,
    fresh_install: bool = False,
    formal_promotion: bool = False,
) -> dict[str, Any]:
    """Preview or atomically apply legacy Action migration and guards."""
    preview = preview_case_actions_v1_migration(conn)
    if not apply:
        return {**preview, "applied": False, "skipped": preview["ready"]}
    if preview["ready"]:
        report = _reconcile(conn, preview)
        if report["problems"]:
            raise RuntimeError("; ".join(report["problems"]))
        return {**report, "applied": False, "skipped": True, "ready": True}

    _assert_migration_target_authorized(
        conn,
        preview,
        fresh_install=fresh_install,
        formal_promotion=formal_promotion,
    )

    conn.execute("SAVEPOINT case_actions_v1")
    try:
        _create_schema(conn)
        next_rows = (
            _fetch_dicts(
                conn,
                """
                SELECT id, anomaly_id, description, owner, due_date, status,
                       completed_at, completed_note, cancelled_at, cancelled_note,
                       created_at, updated_at
                FROM anomaly_actions
                ORDER BY rowid
                """,
            )
            if _table_exists(conn, "anomaly_actions")
            else []
        )
        next_ids = {str(row["id"]) for row in next_rows}
        next_status_map = {
            ANOMALY_ACTION_STATUS_OPEN: CASE_ACTION_STATUS_IN_PROGRESS,
            ANOMALY_ACTION_STATUS_COMPLETED: CASE_ACTION_STATUS_COMPLETED,
            ANOMALY_ACTION_STATUS_CANCELLED: CASE_ACTION_STATUS_CANCELLED,
        }
        for row in next_rows:
            legacy_id = str(row["id"])
            status = str(row.get("status") or "")
            if status not in next_status_map:
                raise RuntimeError(f"Unsupported anomaly_actions status: {status}")
            _insert_migrated_action(
                conn,
                (
                    legacy_id,
                    str(row["anomaly_id"]),
                    CASE_ACTION_TYPE_NEXT_ACTION,
                    str(row.get("description") or "").strip(),
                    str(row.get("owner") or "").strip(),
                    str(row.get("due_date") or "").strip(),
                    next_status_map[status],
                    0,
                    "",
                    row.get("completed_at"),
                    str(row.get("completed_note") or "").strip(),
                    row.get("cancelled_at"),
                    str(row.get("cancelled_note") or "").strip(),
                    "",
                    CASE_ACTION_LEGACY_SOURCE_NEXT_ACTION,
                    legacy_id,
                    row.get("created_at") or _now_iso(),
                    row.get("updated_at") or row.get("created_at") or _now_iso(),
                ),
            )

        corrective_rows = (
            _fetch_dicts(
                conn,
                """
                SELECT id, anomaly_id, description, responsible_party, target_date,
                       status, implementation_evidence, completion_date,
                       effectiveness_verification_required, notes, created_at,
                       updated_at
                FROM corrective_actions
                ORDER BY rowid
                """,
            )
            if _table_exists(conn, "corrective_actions")
            else []
        )
        corrective_status_map = {
            CORRECTIVE_ACTION_STATUS_PLANNED: CASE_ACTION_STATUS_PLANNED,
            CORRECTIVE_ACTION_STATUS_IN_PROGRESS: CASE_ACTION_STATUS_IN_PROGRESS,
            CORRECTIVE_ACTION_STATUS_IMPLEMENTED: CASE_ACTION_STATUS_COMPLETED,
            CORRECTIVE_ACTION_STATUS_VERIFICATION_PENDING: CASE_ACTION_STATUS_COMPLETED,
            CORRECTIVE_ACTION_STATUS_EFFECTIVE: CASE_ACTION_STATUS_COMPLETED,
            CORRECTIVE_ACTION_STATUS_INEFFECTIVE: CASE_ACTION_STATUS_COMPLETED,
            CORRECTIVE_ACTION_STATUS_CANCELLED: CASE_ACTION_STATUS_CANCELLED,
        }
        corrective_map: dict[str, str] = {}
        for row in corrective_rows:
            legacy_id = str(row["id"])
            canonical_id = _legacy_canonical_id(
                CASE_ACTION_LEGACY_SOURCE_CORRECTIVE_ACTION,
                legacy_id,
                next_action_ids=next_ids,
            )
            corrective_map[legacy_id] = canonical_id
            status = str(row.get("status") or "")
            if status not in corrective_status_map:
                raise RuntimeError(f"Unsupported corrective_actions status: {status}")
            cancelled = status == CORRECTIVE_ACTION_STATUS_CANCELLED
            _insert_migrated_action(
                conn,
                (
                    canonical_id,
                    str(row["anomaly_id"]),
                    CASE_ACTION_TYPE_CORRECTIVE_ACTION,
                    str(row.get("description") or "").strip(),
                    str(row.get("responsible_party") or "").strip(),
                    str(row.get("target_date") or "").strip(),
                    corrective_status_map[status],
                    1
                    if _as_int(row.get("effectiveness_verification_required"), 0)
                    else 0,
                    str(row.get("implementation_evidence") or "").strip(),
                    row.get("completion_date"),
                    "",
                    row.get("updated_at") if cancelled else None,
                    "Legacy status: 已取消" if cancelled else "",
                    str(row.get("notes") or "").strip(),
                    CASE_ACTION_LEGACY_SOURCE_CORRECTIVE_ACTION,
                    legacy_id,
                    row.get("created_at") or _now_iso(),
                    row.get("updated_at") or row.get("created_at") or _now_iso(),
                ),
            )

        verification_rows = (
            _fetch_dicts(
                conn,
                """
                SELECT id, corrective_action_id, method, acceptance_criteria,
                       period_sample, result, evidence, conclusion, verified_by,
                       verified_date, created_at
                FROM effectiveness_verifications
                ORDER BY rowid
                """,
            )
            if _table_exists(conn, "effectiveness_verifications")
            else []
        )
        verified_legacy_actions: set[str] = set()
        for row in verification_rows:
            legacy_action_id = str(row["corrective_action_id"])
            canonical_id = corrective_map.get(legacy_action_id)
            if not canonical_id:
                raise RuntimeError(
                    "Verification references unmapped corrective action: "
                    f"{legacy_action_id}"
                )
            verified_legacy_actions.add(legacy_action_id)
            conn.execute(
                """
                INSERT INTO action_verifications(
                    id, action_id, method, acceptance_criteria, period_sample,
                    result, evidence, conclusion, verified_by, verified_date,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (
                    str(row["id"]),
                    canonical_id,
                    str(row.get("method") or "").strip(),
                    str(row.get("acceptance_criteria") or "").strip(),
                    str(row.get("period_sample") or "").strip(),
                    str(row.get("result") or ACTION_VERIFICATION_PENDING),
                    str(row.get("evidence") or "").strip(),
                    str(row.get("conclusion") or "").strip(),
                    str(row.get("verified_by") or "").strip(),
                    row.get("verified_date"),
                    row.get("created_at") or _now_iso(),
                ),
            )

        for row in corrective_rows:
            legacy_id = str(row["id"])
            legacy_status = str(row.get("status") or "")
            if legacy_id in verified_legacy_actions or legacy_status not in (
                CORRECTIVE_ACTION_STATUS_EFFECTIVE,
                CORRECTIVE_ACTION_STATUS_INEFFECTIVE,
            ):
                continue
            result = (
                ACTION_VERIFICATION_EFFECTIVE
                if legacy_status == CORRECTIVE_ACTION_STATUS_EFFECTIVE
                else ACTION_VERIFICATION_INEFFECTIVE
            )
            verification_id = uuid.uuid5(
                _UUID_NAMESPACE,
                f"legacy-status-verification:{legacy_id}:{legacy_status}",
            ).hex
            conn.execute(
                """
                INSERT INTO action_verifications(
                    id, action_id, method, acceptance_criteria, period_sample,
                    result, evidence, conclusion, verified_by, verified_date,
                    created_at
                ) VALUES (?, ?, 'LEGACY_STATUS', '', '', ?, '', ?, '', ?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (
                    verification_id,
                    corrective_map[legacy_id],
                    result,
                    "legacy-incomplete：舊改善狀態已有結果，但未建立結構化驗證內容",
                    row.get("completion_date"),
                    row.get("updated_at") or row.get("created_at") or _now_iso(),
                ),
            )

        if _table_exists(conn, "anomaly_attachments"):
            for legacy_id, canonical_id in corrective_map.items():
                conn.execute(
                    "UPDATE anomaly_attachments SET related_action_id = ? "
                    "WHERE related_ca_id = ?",
                    (canonical_id, legacy_id),
                )

        _install_legacy_write_guards(conn)
        conn.execute(
            """
            INSERT INTO migration_meta(key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (CASE_ACTIONS_MIGRATION_META_KEY, CASE_ACTIONS_SCHEMA_VERSION),
        )
        report = _reconcile(conn, preview)
        if report["problems"]:
            raise RuntimeError("; ".join(report["problems"]))
        conn.execute("RELEASE SAVEPOINT case_actions_v1")
        return {
            **report,
            "applied": True,
            "skipped": False,
            "ready": True,
        }
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT case_actions_v1")
        conn.execute("RELEASE SAVEPOINT case_actions_v1")
        raise


def _latest_verification(
    conn: sqlite3.Connection,
    action_id: str,
) -> dict[str, Any] | None:
    return _fetch_one_dict(
        conn,
        """
        SELECT id, action_id, method, acceptance_criteria, period_sample,
               result, evidence, conclusion, verified_by, verified_date,
               created_at
        FROM action_verifications
        WHERE action_id = ?
        ORDER BY created_at DESC, rowid DESC
        LIMIT 1
        """,
        (action_id,),
    )


def _verification_status(
    conn: sqlite3.Connection,
    action: dict[str, Any],
) -> str:
    if action.get("action_type") not in CASE_ACTION_VERIFICATION_ELIGIBLE_TYPES:
        return ACTION_VERIFICATION_NOT_APPLICABLE
    if not bool(_as_int(action.get("verification_required"), 0)):
        return ACTION_VERIFICATION_NOT_REQUIRED
    if action.get("execution_status") != CASE_ACTION_STATUS_COMPLETED:
        return ACTION_VERIFICATION_PENDING
    latest = _latest_verification(conn, str(action["id"]))
    return str((latest or {}).get("result") or ACTION_VERIFICATION_PENDING)


def _enrich_action(
    conn: sqlite3.Connection,
    action: dict[str, Any],
) -> dict[str, Any]:
    result = dict(action)
    result["verification_required"] = bool(
        _as_int(result.get("verification_required"), 0)
    )
    result["action_type_label"] = CASE_ACTION_TYPE_LABELS.get(
        str(result.get("action_type") or ""),
        str(result.get("action_type") or ""),
    )
    result["verification_status"] = _verification_status(conn, result)
    result["latest_verification"] = _latest_verification(conn, str(result["id"]))
    return result


def create_case_action(
    conn: sqlite3.Connection,
    *,
    anomaly_id: str,
    action_type: str,
    description: str,
    owner: str = "",
    due_date: str = "",
    execution_status: str = CASE_ACTION_STATUS_PLANNED,
    verification_required: bool | None = None,
    notes: str = "",
    _commit: bool = True,
) -> str:
    require_case_actions_schema(conn)
    anomaly_key = _require_anomaly(conn, anomaly_id)
    normalized_type = str(action_type or "").strip()
    if normalized_type not in CASE_ACTION_TYPES:
        raise ValueError("Invalid Action type")
    text = str(description or "").strip()
    if not text:
        raise ValueError("Action description is required")
    if execution_status not in (CASE_ACTION_STATUS_PLANNED, CASE_ACTION_STATUS_IN_PROGRESS):
        raise ValueError("New Action status must be 已規劃 or 執行中")
    eligible = normalized_type in CASE_ACTION_VERIFICATION_ELIGIBLE_TYPES
    wants_verification = eligible if verification_required is None else bool(verification_required)
    if wants_verification and not eligible:
        raise ValueError("Only improvement Actions can require verification")
    normalized_due = (
        _normalize_loose_iso_date(due_date, field_name="Action due date")
        if due_date
        else ""
    )
    action_id = _gen_id()
    conn.execute(
        """
        INSERT INTO case_actions(
            id, anomaly_id, action_type, description, owner, due_date,
            execution_status, verification_required, notes,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            action_id,
            anomaly_key,
            normalized_type,
            text,
            str(owner or "").strip(),
            normalized_due,
            execution_status,
            1 if wants_verification else 0,
            str(notes or "").strip(),
            _now_iso(),
            _now_iso(),
        ),
    )
    _commit_if(conn, _commit)
    return action_id


def list_case_actions(
    conn: sqlite3.Connection,
    anomaly_id: str,
    *,
    action_types: tuple[str, ...] | None = None,
    include_completed: bool = True,
    include_cancelled: bool = True,
) -> list[dict[str, Any]]:
    require_case_actions_schema(conn)
    anomaly_key = str(anomaly_id or "").strip()
    if not anomaly_key:
        return []
    clauses = ["anomaly_id = ?"]
    params: list[object] = [anomaly_key]
    statuses = list(CASE_ACTION_OPEN_STATUSES)
    if include_completed:
        statuses.append(CASE_ACTION_STATUS_COMPLETED)
    if include_cancelled:
        statuses.append(CASE_ACTION_STATUS_CANCELLED)
    clauses.append(f"execution_status IN ({','.join('?' for _ in statuses)})")
    params.extend(statuses)
    if action_types:
        invalid = [value for value in action_types if value not in CASE_ACTION_TYPES]
        if invalid:
            raise ValueError(f"Invalid Action type: {invalid[0]}")
        clauses.append(f"action_type IN ({','.join('?' for _ in action_types)})")
        params.extend(action_types)
    rows = _fetch_dicts(
        conn,
        f"""
        SELECT id, anomaly_id, action_type, description, owner, due_date,
               execution_status, verification_required, implementation_evidence,
               completed_at, completion_note, cancelled_at, cancel_note, notes,
               legacy_source, legacy_id, created_at, updated_at
        FROM case_actions
        WHERE {' AND '.join(clauses)}
        ORDER BY
            CASE execution_status
                WHEN '執行中' THEN 0
                WHEN '已規劃' THEN 1
                WHEN '已完成' THEN 2
                WHEN '已取消' THEN 3
                ELSE 4
            END,
            CASE WHEN trim(coalesce(due_date, '')) = '' THEN 1 ELSE 0 END,
            due_date ASC,
            created_at ASC,
            rowid ASC
        """,
        tuple(params),
    )
    return [_enrich_action(conn, row) for row in rows]


def get_case_action(
    conn: sqlite3.Connection,
    action_id: str,
) -> dict[str, Any] | None:
    require_case_actions_schema(conn)
    key = str(action_id or "").strip()
    if not key:
        return None
    row = _fetch_one_dict(
        conn,
        """
        SELECT id, anomaly_id, action_type, description, owner, due_date,
               execution_status, verification_required, implementation_evidence,
               completed_at, completion_note, cancelled_at, cancel_note, notes,
               legacy_source, legacy_id, created_at, updated_at
        FROM case_actions
        WHERE id = ?
        LIMIT 1
        """,
        (key,),
    )
    return _enrich_action(conn, row) if row else None


def update_case_action(
    conn: sqlite3.Connection,
    action_id: str,
    *,
    action_type: str | None = None,
    description: str | None = None,
    owner: str | None = None,
    due_date: str | None = None,
    execution_status: str | None = None,
    verification_required: bool | None = None,
    notes: str | None = None,
    _commit: bool = True,
) -> None:
    existing = get_case_action(conn, action_id)
    if existing is None:
        raise ValueError("Action not found")
    if existing["execution_status"] not in CASE_ACTION_OPEN_STATUSES:
        raise ValueError("Only planned or in-progress Actions are editable")
    fields: dict[str, object] = {}
    next_type = str(existing["action_type"])
    if action_type is not None:
        next_type = str(action_type or "").strip()
        if next_type not in CASE_ACTION_TYPES:
            raise ValueError("Invalid Action type")
        fields["action_type"] = next_type
    if description is not None:
        text = str(description or "").strip()
        if not text:
            raise ValueError("Action description is required")
        fields["description"] = text
    if owner is not None:
        fields["owner"] = str(owner or "").strip()
    if due_date is not None:
        fields["due_date"] = (
            _normalize_loose_iso_date(due_date, field_name="Action due date")
            if due_date
            else ""
        )
    if execution_status is not None:
        if execution_status != CASE_ACTION_STATUS_IN_PROGRESS:
            raise ValueError("Editable Action status can only advance to 執行中")
        if existing["execution_status"] != CASE_ACTION_STATUS_PLANNED:
            raise ValueError("Only 已規劃 Actions can advance to 執行中")
        fields["execution_status"] = execution_status
    next_required = (
        bool(existing["verification_required"])
        if verification_required is None
        else bool(verification_required)
    )
    if next_type not in CASE_ACTION_VERIFICATION_ELIGIBLE_TYPES:
        if verification_required:
            raise ValueError("Only improvement Actions can require verification")
        next_required = False
    if verification_required is not None or action_type is not None:
        fields["verification_required"] = 1 if next_required else 0
    if notes is not None:
        fields["notes"] = str(notes or "").strip()
    if not fields:
        return
    assignments = ", ".join(f"{name} = ?" for name in fields)
    conn.execute(
        f"UPDATE case_actions SET {assignments}, updated_at = ? WHERE id = ?",
        (*fields.values(), _now_iso(), str(existing["id"])),
    )
    _commit_if(conn, _commit)


def complete_case_action(
    conn: sqlite3.Connection,
    action_id: str,
    *,
    implementation_evidence: str = "",
    completion_note: str = "",
    completed_at: str | None = None,
    _commit: bool = True,
) -> None:
    existing = get_case_action(conn, action_id)
    if existing is None:
        raise ValueError("Action not found")
    if existing["execution_status"] != CASE_ACTION_STATUS_IN_PROGRESS:
        raise ValueError("Only 執行中 Actions can be completed")
    completion = _normalize_strict_iso_date(
        completed_at,
        field_name="Completion date",
        fallback=date.today().isoformat(),
    )
    _ensure_date_not_in_future(completion, field_name="Completion date")
    conn.execute(
        """
        UPDATE case_actions
        SET execution_status = '已完成', implementation_evidence = ?,
            completed_at = ?, completion_note = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            str(implementation_evidence or "").strip(),
            completion,
            str(completion_note or "").strip(),
            _now_iso(),
            str(existing["id"]),
        ),
    )
    _commit_if(conn, _commit)


def cancel_case_action(
    conn: sqlite3.Connection,
    action_id: str,
    *,
    cancel_note: str,
    cancelled_at: str | None = None,
    _commit: bool = True,
) -> None:
    existing = get_case_action(conn, action_id)
    if existing is None:
        raise ValueError("Action not found")
    if existing["execution_status"] not in CASE_ACTION_OPEN_STATUSES:
        raise ValueError("Only planned or in-progress Actions can be cancelled")
    reason = str(cancel_note or "").strip()
    if not reason:
        raise ValueError("Cancel reason is required")
    cancelled = _normalize_strict_iso_date(
        cancelled_at,
        field_name="Cancellation date",
        fallback=date.today().isoformat(),
    )
    _ensure_date_not_in_future(cancelled, field_name="Cancellation date")
    conn.execute(
        """
        UPDATE case_actions
        SET execution_status = '已取消', cancelled_at = ?, cancel_note = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (cancelled, reason, _now_iso(), str(existing["id"])),
    )
    _commit_if(conn, _commit)


def record_action_verification(
    conn: sqlite3.Connection,
    *,
    action_id: str,
    method: str,
    acceptance_criteria: str = "",
    period_sample: str = "",
    result: str = ACTION_VERIFICATION_PENDING,
    evidence: str = "",
    conclusion: str = "",
    verified_by: str = "",
    verified_date: str | None = None,
    _commit: bool = True,
) -> str:
    existing = get_case_action(conn, action_id)
    if existing is None:
        raise ValueError("Action not found")
    if existing["action_type"] not in CASE_ACTION_VERIFICATION_ELIGIBLE_TYPES:
        raise ValueError("This Action type does not support verification")
    if not existing["verification_required"]:
        raise ValueError("This Action does not require verification")
    if existing["execution_status"] != CASE_ACTION_STATUS_COMPLETED:
        raise ValueError("Only completed Actions can be verified")
    normalized_method = str(method or "").strip()
    if not normalized_method:
        raise ValueError("Verification method is required")
    if result not in ACTION_VERIFICATION_RESULTS:
        raise ValueError("Invalid verification result")
    normalized_date = None
    if verified_date:
        normalized_date = _normalize_strict_iso_date(
            verified_date,
            field_name="Verified date",
        )
        _ensure_date_not_in_future(normalized_date, field_name="Verified date")
    verification_id = _gen_id()
    conn.execute(
        """
        INSERT INTO action_verifications(
            id, action_id, method, acceptance_criteria, period_sample,
            result, evidence, conclusion, verified_by, verified_date,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            verification_id,
            str(existing["id"]),
            normalized_method,
            str(acceptance_criteria or "").strip(),
            str(period_sample or "").strip(),
            result,
            str(evidence or "").strip(),
            str(conclusion or "").strip(),
            str(verified_by or "").strip(),
            normalized_date,
            _now_iso(),
        ),
    )
    _commit_if(conn, _commit)
    return verification_id


def list_action_verifications(
    conn: sqlite3.Connection,
    action_id: str,
) -> list[dict[str, Any]]:
    require_case_actions_schema(conn)
    return _fetch_dicts(
        conn,
        """
        SELECT id, action_id, method, acceptance_criteria, period_sample,
               result, evidence, conclusion, verified_by, verified_date,
               created_at
        FROM action_verifications
        WHERE action_id = ?
        ORDER BY created_at DESC, rowid DESC
        """,
        (str(action_id or "").strip(),),
    )


def get_current_case_action(
    conn: sqlite3.Connection,
    anomaly_id: str,
) -> dict[str, Any] | None:
    require_case_actions_schema(conn)
    row = _fetch_one_dict(
        conn,
        """
        SELECT id, anomaly_id, action_type, description, owner, due_date,
               execution_status, verification_required, implementation_evidence,
               completed_at, completion_note, cancelled_at, cancel_note, notes,
               legacy_source, legacy_id, created_at, updated_at
        FROM case_actions
        WHERE anomaly_id = ? AND execution_status IN ('已規劃','執行中')
        ORDER BY
            CASE execution_status WHEN '執行中' THEN 0 ELSE 1 END,
            CASE WHEN trim(coalesce(due_date, '')) = '' THEN 1 ELSE 0 END,
            due_date ASC,
            created_at ASC,
            rowid ASC
        LIMIT 1
        """,
        (str(anomaly_id or "").strip(),),
    )
    return _enrich_action(conn, row) if row else None


def is_anomaly_overdue(
    conn: sqlite3.Connection,
    anomaly_id: str,
    *,
    today: str | None = None,
) -> bool:
    require_case_actions_schema(conn)
    key = str(anomaly_id or "").strip()
    if not key:
        return False
    anomaly = conn.execute(
        "SELECT status FROM anomalies WHERE id = ?",
        (key,),
    ).fetchone()
    if anomaly is None or str(anomaly[0]) != "待處理":
        return False
    today_iso = _normalize_strict_iso_date(
        today,
        field_name="Today",
        fallback=date.today().isoformat(),
    )
    return (
        conn.execute(
            """
            SELECT 1
            FROM case_actions
            WHERE anomaly_id = ?
              AND execution_status IN ('已規劃','執行中')
              AND trim(coalesce(due_date, '')) <> ''
              AND due_date < ?
            LIMIT 1
            """,
            (key, today_iso),
        ).fetchone()
        is not None
    )


def aggregate_execution_status(actions: list[dict[str, Any]]) -> str:
    if not actions:
        return "—"
    order = {
        CASE_ACTION_STATUS_IN_PROGRESS: 0,
        CASE_ACTION_STATUS_PLANNED: 1,
        CASE_ACTION_STATUS_COMPLETED: 2,
        CASE_ACTION_STATUS_CANCELLED: 3,
    }
    return str(min(actions, key=lambda row: order.get(str(row.get("execution_status")), 9)).get("execution_status") or "—")


def aggregate_verification_status(actions: list[dict[str, Any]]) -> str:
    eligible = [
        action
        for action in actions
        if action.get("action_type") in CASE_ACTION_VERIFICATION_ELIGIBLE_TYPES
    ]
    if not eligible:
        return "—"
    statuses = {str(action.get("verification_status") or "") for action in eligible}
    for status in (
        ACTION_VERIFICATION_INEFFECTIVE,
        ACTION_VERIFICATION_PENDING,
        ACTION_VERIFICATION_INCONCLUSIVE,
        ACTION_VERIFICATION_EFFECTIVE,
        ACTION_VERIFICATION_NOT_REQUIRED,
    ):
        if status in statuses:
            return status
    return "—"
