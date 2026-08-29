"""Phase 3 multi-layer hypothesis schema, CRUD, and evidence-chain read model."""

from __future__ import annotations

import sqlite3
from typing import Any

from database.repo_helpers import (
    ANOMALY_EVIDENCE_LABELS,
    ANOMALY_EVIDENCE_TYPES,
    ANOMALY_EVIDENCE_UNKNOWN,
    ANOMALY_HYPOTHESIS_ADOPTED,
    ANOMALY_HYPOTHESIS_DISCARDED,
    ANOMALY_HYPOTHESIS_MAX_LEVEL,
    ANOMALY_HYPOTHESIS_PROPOSED,
    ANOMALY_HYPOTHESIS_STATUSES,
    ANOMALY_HYPOTHESES_MIGRATION_META_KEY,
    ANOMALY_HYPOTHESES_SCHEMA_VERSION,
    ANOMALY_ROOT_CAUSE_PROPOSED,
    ANOMALY_ROOT_CAUSE_UNDER_INVESTIGATION,
    _gen_id,
    _table_columns,
    _table_exists,
    get_migration_meta,
    upsert_migration_meta,
)
from database.repository_schema_helpers import ensure_column as _ensure_column
from database.repository_schema_helpers import ensure_index as _ensure_index

_ANOMALY_HYPOTHESES_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS anomaly_hypotheses (
    id TEXT PRIMARY KEY,
    anomaly_id TEXT NOT NULL,
    parent_hypothesis_id TEXT REFERENCES anomaly_hypotheses(id),
    level INTEGER NOT NULL DEFAULT 1 CHECK (level BETWEEN 1 AND 5),
    sort_order INTEGER NOT NULL DEFAULT 0,
    statement TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '提案'
        CHECK (status IN ('提案','調查中','支持','反證','採納','淘汰')),
    evidence_type TEXT NOT NULL DEFAULT 'UNKNOWN'
        CHECK (evidence_type IN ('FACT','INFERENCE','ASSUMPTION','UNKNOWN')),
    linked_note_id TEXT REFERENCES anomaly_analysis_notes(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (anomaly_id) REFERENCES anomalies(id) ON DELETE CASCADE
);
"""

_ROOT_CAUSE_PROMOTED_COLUMN = (
    "promoted_from_hypothesis_id",
    "TEXT REFERENCES anomaly_hypotheses(id)",
)
_ATTACHMENT_HYPOTHESIS_COLUMN = (
    "related_hypothesis_id",
    "TEXT REFERENCES anomaly_hypotheses(id)",
)


def _hypothesis_table_columns() -> tuple[str, ...]:
    return (
        "id",
        "anomaly_id",
        "parent_hypothesis_id",
        "level",
        "sort_order",
        "statement",
        "status",
        "evidence_type",
        "linked_note_id",
        "created_at",
        "updated_at",
    )


def preview_anomaly_hypotheses_v1(conn: sqlite3.Connection) -> dict[str, Any]:
    """Read-only summary for the Phase 3 hypothesis contract."""
    columns = (
        sorted(_table_columns(conn, "anomaly_hypotheses"))
        if _table_exists(conn, "anomaly_hypotheses")
        else []
    )
    missing_table_columns = [
        name for name in _hypothesis_table_columns() if name not in columns
    ]
    root_columns = _table_columns(conn, "anomaly_root_causes")
    attachment_columns = _table_columns(conn, "anomaly_attachments")
    missing_extensions: list[str] = []
    if _ROOT_CAUSE_PROMOTED_COLUMN[0] not in root_columns:
        missing_extensions.append(_ROOT_CAUSE_PROMOTED_COLUMN[0])
    if _ATTACHMENT_HYPOTHESIS_COLUMN[0] not in attachment_columns:
        missing_extensions.append(_ATTACHMENT_HYPOTHESIS_COLUMN[0])
    ready = (
        _table_exists(conn, "anomaly_hypotheses")
        and not missing_table_columns
        and not missing_extensions
        and get_migration_meta(conn, ANOMALY_HYPOTHESES_MIGRATION_META_KEY)
        == ANOMALY_HYPOTHESES_SCHEMA_VERSION
    )
    row_count = 0
    if _table_exists(conn, "anomaly_hypotheses"):
        row_count = int(
            conn.execute("SELECT COUNT(*) FROM anomaly_hypotheses").fetchone()[0]
        )
    return {
        "migration_key": ANOMALY_HYPOTHESES_MIGRATION_META_KEY,
        "schema_version": ANOMALY_HYPOTHESES_SCHEMA_VERSION,
        "ready": ready,
        "table_exists": _table_exists(conn, "anomaly_hypotheses"),
        "columns": columns,
        "missing_table_columns": missing_table_columns,
        "missing_extension_columns": missing_extensions,
        "hypothesis_rows": row_count,
    }


def anomaly_hypotheses_schema_ready(conn: sqlite3.Connection) -> bool:
    return bool(preview_anomaly_hypotheses_v1(conn)["ready"])


def _install_hypothesis_indexes(conn: sqlite3.Connection) -> None:
    _ensure_index(
        conn,
        "idx_anomaly_hypotheses_anomaly",
        "anomaly_hypotheses",
        "anomaly_id, level, sort_order",
    )
    _ensure_index(
        conn,
        "idx_anomaly_hypotheses_parent",
        "anomaly_hypotheses",
        "parent_hypothesis_id",
    )


def _ensure_anomaly_hypotheses_v1(
    conn: sqlite3.Connection,
    *,
    commit_meta: bool = True,
) -> dict[str, Any]:
    conn.executescript(_ANOMALY_HYPOTHESES_TABLE_DDL)
    _install_hypothesis_indexes(conn)
    if _table_exists(conn, "anomaly_root_causes"):
        _ensure_column(
            conn,
            "anomaly_root_causes",
            _ROOT_CAUSE_PROMOTED_COLUMN[0],
            _ROOT_CAUSE_PROMOTED_COLUMN[1],
        )
    if _table_exists(conn, "anomaly_attachments"):
        _ensure_column(
            conn,
            "anomaly_attachments",
            _ATTACHMENT_HYPOTHESIS_COLUMN[0],
            _ATTACHMENT_HYPOTHESIS_COLUMN[1],
        )
    if commit_meta:
        upsert_migration_meta(
            conn,
            ANOMALY_HYPOTHESES_MIGRATION_META_KEY,
            ANOMALY_HYPOTHESES_SCHEMA_VERSION,
        )
    else:
        conn.execute(
            """
            INSERT INTO migration_meta(key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (
                ANOMALY_HYPOTHESES_MIGRATION_META_KEY,
                ANOMALY_HYPOTHESES_SCHEMA_VERSION,
            ),
        )
    return preview_anomaly_hypotheses_v1(conn)


def migrate_anomaly_hypotheses_v1(
    conn: sqlite3.Connection,
    *,
    apply: bool = False,
) -> dict[str, Any]:
    preview = preview_anomaly_hypotheses_v1(conn)
    if not apply:
        return {**preview, "applied": False, "skipped": preview["ready"]}
    if preview["ready"]:
        return {**preview, "applied": False, "skipped": True}
    report = _ensure_anomaly_hypotheses_v1(conn, commit_meta=True)
    if report["missing_table_columns"] or report["missing_extension_columns"]:
        raise RuntimeError(
            "Hypothesis contract migration did not install all objects: "
            + ", ".join(
                report["missing_table_columns"] + report["missing_extension_columns"]
            )
        )
    return {**report, "applied": True, "skipped": False}


def _require_hypothesis_schema(conn: sqlite3.Connection) -> None:
    if not anomaly_hypotheses_schema_ready(conn):
        raise RuntimeError(
            "需要完成 Hypothesis 資料升級：anomaly_hypotheses_v1。"
        )


def _get_hypothesis_row(
    conn: sqlite3.Connection, hypothesis_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id, anomaly_id, parent_hypothesis_id, level, sort_order,
               statement, status, evidence_type, linked_note_id,
               created_at, updated_at
        FROM anomaly_hypotheses
        WHERE id = ?
        """,
        ((hypothesis_id or "").strip(),),
    ).fetchone()
    return dict(row) if row else None


def _validate_linked_note(
    conn: sqlite3.Connection, *, anomaly_id: str, linked_note_id: str | None
) -> None:
    if not linked_note_id:
        return
    note = conn.execute(
        "SELECT anomaly_id FROM anomaly_analysis_notes WHERE id = ?",
        (linked_note_id,),
    ).fetchone()
    if note is None or str(note[0] or "") != anomaly_id:
        raise ValueError("Linked analysis note not found")


def _would_create_hypothesis_cycle(
    conn: sqlite3.Connection,
    *,
    hypothesis_id: str,
    parent_hypothesis_id: str | None,
) -> bool:
    if not parent_hypothesis_id:
        return False
    current = parent_hypothesis_id
    visited: set[str] = set()
    while current:
        if current == hypothesis_id:
            return True
        if current in visited:
            return True
        visited.add(current)
        row = conn.execute(
            "SELECT parent_hypothesis_id FROM anomaly_hypotheses WHERE id = ?",
            (current,),
        ).fetchone()
        if row is None:
            break
        current = str(row[0] or "").strip() or ""
    return False


def _resolve_hypothesis_level(
    conn: sqlite3.Connection, parent_hypothesis_id: str | None
) -> int:
    if not parent_hypothesis_id:
        return 1
    parent = _get_hypothesis_row(conn, parent_hypothesis_id)
    if parent is None:
        raise ValueError("Parent hypothesis not found")
    level = int(parent.get("level") or 1) + 1
    if level > ANOMALY_HYPOTHESIS_MAX_LEVEL:
        raise ValueError("Hypothesis depth cannot exceed five levels")
    return level


def _next_hypothesis_sort_order(
    conn: sqlite3.Connection, *, anomaly_id: str, parent_hypothesis_id: str | None
) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(MAX(sort_order), -1)
        FROM anomaly_hypotheses
        WHERE anomaly_id = ?
          AND COALESCE(parent_hypothesis_id, '') = ?
        """,
        (anomaly_id, parent_hypothesis_id or ""),
    ).fetchone()
    return int(row[0] if row else -1) + 1


def _count_hypothesis_attachments(conn: sqlite3.Connection, hypothesis_id: str) -> int:
    if not hypothesis_id or "related_hypothesis_id" not in _table_columns(
        conn, "anomaly_attachments"
    ):
        return 0
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM anomaly_attachments WHERE related_hypothesis_id = ?",
            (hypothesis_id,),
        ).fetchone()[0]
    )


def _count_note_attachments(conn: sqlite3.Connection, note_id: str) -> int:
    if not note_id:
        return 0
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM anomaly_attachments WHERE related_note_id = ?",
            (note_id,),
        ).fetchone()[0]
    )


def _decorate_hypothesis_row(row: dict[str, Any], conn: sqlite3.Connection) -> dict[str, Any]:
    item = dict(row)
    item["evidence_label"] = ANOMALY_EVIDENCE_LABELS.get(
        item.get("evidence_type"), item.get("evidence_type")
    )
    item["attachment_count"] = _count_hypothesis_attachments(
        conn, str(item.get("id") or "")
    )
    return item


def list_anomaly_hypotheses(
    conn: sqlite3.Connection, anomaly_id: str
) -> list[dict[str, Any]]:
    _require_hypothesis_schema(conn)
    rows = conn.execute(
        """
        SELECT id, anomaly_id, parent_hypothesis_id, level, sort_order,
               statement, status, evidence_type, linked_note_id,
               created_at, updated_at
        FROM anomaly_hypotheses
        WHERE anomaly_id = ?
        ORDER BY level ASC, sort_order ASC, created_at ASC, rowid ASC
        """,
        ((anomaly_id or "").strip(),),
    ).fetchall()
    return [_decorate_hypothesis_row(dict(row), conn) for row in rows]


def get_anomaly_hypothesis(
    conn: sqlite3.Connection, hypothesis_id: str
) -> dict[str, Any] | None:
    _require_hypothesis_schema(conn)
    row = _get_hypothesis_row(conn, hypothesis_id)
    return _decorate_hypothesis_row(row, conn) if row else None


def create_anomaly_hypothesis(
    conn: sqlite3.Connection,
    *,
    anomaly_id: str,
    statement: str,
    status: str = ANOMALY_HYPOTHESIS_PROPOSED,
    evidence_type: str = ANOMALY_EVIDENCE_UNKNOWN,
    parent_hypothesis_id: str | None = None,
    linked_note_id: str | None = None,
    _commit: bool = True,
) -> str:
    from database.repository import require_anomaly

    _require_hypothesis_schema(conn)
    anomaly_key = (anomaly_id or "").strip()
    require_anomaly(conn, anomaly_key)
    text = (statement or "").strip()
    if not text:
        raise ValueError("Hypothesis statement is required")
    if status not in ANOMALY_HYPOTHESIS_STATUSES:
        raise ValueError("Invalid hypothesis status")
    ev = (evidence_type or "").strip() or ANOMALY_EVIDENCE_UNKNOWN
    if ev not in ANOMALY_EVIDENCE_TYPES:
        raise ValueError("Evidence type must be FACT / INFERENCE / ASSUMPTION / UNKNOWN")
    parent_key = (parent_hypothesis_id or "").strip() or None
    if parent_key:
        parent = _get_hypothesis_row(conn, parent_key)
        if parent is None or str(parent.get("anomaly_id") or "") != anomaly_key:
            raise ValueError("Parent hypothesis not found")
    note_key = (linked_note_id or "").strip() or None
    _validate_linked_note(conn, anomaly_id=anomaly_key, linked_note_id=note_key)
    level = _resolve_hypothesis_level(conn, parent_key)
    sort_order = _next_hypothesis_sort_order(
        conn, anomaly_id=anomaly_key, parent_hypothesis_id=parent_key
    )
    hypothesis_id = _gen_id()
    conn.execute(
        """
        INSERT INTO anomaly_hypotheses(
            id, anomaly_id, parent_hypothesis_id, level, sort_order,
            statement, status, evidence_type, linked_note_id,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            hypothesis_id,
            anomaly_key,
            parent_key,
            level,
            sort_order,
            text,
            status,
            ev,
            note_key,
        ),
    )
    if _commit:
        conn.commit()
    return hypothesis_id


def _cascade_hypothesis_levels_from_parent(
    conn: sqlite3.Connection,
    *,
    hypothesis_id: str,
    anomaly_id: str,
    parent_level: int,
) -> None:
    children = conn.execute(
        """
        SELECT id
        FROM anomaly_hypotheses
        WHERE anomaly_id = ? AND parent_hypothesis_id = ?
        ORDER BY sort_order ASC, created_at ASC, rowid ASC
        """,
        (anomaly_id, hypothesis_id),
    ).fetchall()
    for child in children:
        child_id = str(child["id"])
        child_level = parent_level + 1
        if child_level > ANOMALY_HYPOTHESIS_MAX_LEVEL:
            raise ValueError("Hypothesis depth cannot exceed five levels")
        conn.execute(
            """
            UPDATE anomaly_hypotheses
            SET level = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND anomaly_id = ?
            """,
            (child_level, child_id, anomaly_id),
        )
        _cascade_hypothesis_levels_from_parent(
            conn,
            hypothesis_id=child_id,
            anomaly_id=anomaly_id,
            parent_level=child_level,
        )


def update_anomaly_hypothesis(
    conn: sqlite3.Connection,
    *,
    hypothesis_id: str,
    anomaly_id: str,
    statement: str | None = None,
    status: str | None = None,
    evidence_type: str | None = None,
    parent_hypothesis_id: str | None = None,
    linked_note_id: str | None = None,
    _commit: bool = True,
) -> dict[str, Any]:
    _require_hypothesis_schema(conn)
    hypothesis_key = (hypothesis_id or "").strip()
    anomaly_key = (anomaly_id or "").strip()
    existing = _get_hypothesis_row(conn, hypothesis_key)
    if existing is None or str(existing.get("anomaly_id") or "") != anomaly_key:
        raise ValueError("Hypothesis not found")
    fields: list[str] = []
    values: list[object] = []
    if statement is not None:
        text = (statement or "").strip()
        if not text:
            raise ValueError("Hypothesis statement is required")
        fields.append("statement = ?")
        values.append(text)
    if status is not None:
        if status not in ANOMALY_HYPOTHESIS_STATUSES:
            raise ValueError("Invalid hypothesis status")
        fields.append("status = ?")
        values.append(status)
    if evidence_type is not None:
        ev = (evidence_type or "").strip() or ANOMALY_EVIDENCE_UNKNOWN
        if ev not in ANOMALY_EVIDENCE_TYPES:
            raise ValueError("Evidence type must be FACT / INFERENCE / ASSUMPTION / UNKNOWN")
        fields.append("evidence_type = ?")
        values.append(ev)
    if parent_hypothesis_id is not None:
        parent_key = (parent_hypothesis_id or "").strip() or None
        if parent_key == hypothesis_key:
            raise ValueError("Hypothesis cannot be its own parent")
        if parent_key:
            parent = _get_hypothesis_row(conn, parent_key)
            if parent is None or str(parent.get("anomaly_id") or "") != anomaly_key:
                raise ValueError("Parent hypothesis not found")
            if _would_create_hypothesis_cycle(
                conn,
                hypothesis_id=hypothesis_key,
                parent_hypothesis_id=parent_key,
            ):
                raise ValueError("Hypothesis parent would create a cycle")
            level = _resolve_hypothesis_level(conn, parent_key)
        else:
            level = 1
        fields.extend(["parent_hypothesis_id = ?", "level = ?"])
        values.extend([parent_key, level])
    if linked_note_id is not None:
        note_key = (linked_note_id or "").strip() or None
        _validate_linked_note(conn, anomaly_id=anomaly_key, linked_note_id=note_key)
        fields.append("linked_note_id = ?")
        values.append(note_key)
    if not fields:
        return _decorate_hypothesis_row(existing, conn)
    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.extend([hypothesis_key, anomaly_key])
    conn.execute(
        f"UPDATE anomaly_hypotheses SET {', '.join(fields)} "
        "WHERE id = ? AND anomaly_id = ?",
        tuple(values),
    )
    if parent_hypothesis_id is not None:
        updated_level = int(
            (_get_hypothesis_row(conn, hypothesis_key) or {}).get("level") or 1
        )
        _cascade_hypothesis_levels_from_parent(
            conn,
            hypothesis_id=hypothesis_key,
            anomaly_id=anomaly_key,
            parent_level=updated_level,
        )
    updated = _get_hypothesis_row(conn, hypothesis_key)
    if _commit:
        conn.commit()
    return _decorate_hypothesis_row(updated or existing, conn)


def promote_hypothesis_to_root_cause(
    conn: sqlite3.Connection,
    *,
    hypothesis_id: str,
    anomaly_id: str,
    root_cause_status: str | None = None,
    _commit: bool = True,
) -> dict[str, Any]:
    from database.repository import get_anomaly_root_cause, upsert_anomaly_root_cause

    _require_hypothesis_schema(conn)
    hypothesis_key = (hypothesis_id or "").strip()
    anomaly_key = (anomaly_id or "").strip()
    hypothesis = _get_hypothesis_row(conn, hypothesis_key)
    if hypothesis is None or str(hypothesis.get("anomaly_id") or "") != anomaly_key:
        raise ValueError("Hypothesis not found")
    target_status = root_cause_status or ANOMALY_ROOT_CAUSE_PROPOSED
    if target_status not in (
        ANOMALY_ROOT_CAUSE_PROPOSED,
        ANOMALY_ROOT_CAUSE_UNDER_INVESTIGATION,
    ):
        raise ValueError("Promotion cannot set root cause to verified status")
    conn.execute(
        """
        UPDATE anomaly_hypotheses
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND anomaly_id = ?
        """,
        (ANOMALY_HYPOTHESIS_ADOPTED, hypothesis_key, anomaly_key),
    )
    statement = str(hypothesis.get("statement") or "").strip()
    validation_evidence = ""
    evidence_label = ANOMALY_EVIDENCE_LABELS.get(
        hypothesis.get("evidence_type"), hypothesis.get("evidence_type")
    )
    if evidence_label:
        validation_evidence = f"來自假設（{evidence_label}）：{statement}"
    root_id = upsert_anomaly_root_cause(
        conn,
        anomaly_id=anomaly_key,
        statement=statement,
        status=target_status,
        validation_evidence=validation_evidence,
        promoted_from_hypothesis_id=hypothesis_key,
        _commit=False,
    )
    if _commit:
        conn.commit()
    return {
        "hypothesis_id": hypothesis_key,
        "root_cause_id": root_id,
        "root_cause_status": target_status,
        "promoted_from_hypothesis_id": hypothesis_key,
        "root_cause": get_anomaly_root_cause(conn, anomaly_key),
    }


def hypothesis_overview_metrics(
    conn: sqlite3.Connection, anomaly_id: str
) -> dict[str, Any]:
    if not _table_exists(conn, "anomaly_hypotheses"):
        return {
            "hypothesis_count": 0,
            "hypothesis_deepest_level": 0,
            "hypothesis_adopted": False,
        }
    rows = conn.execute(
        """
        SELECT level, status
        FROM anomaly_hypotheses
        WHERE anomaly_id = ?
        """,
        ((anomaly_id or "").strip(),),
    ).fetchall()
    active = [
        dict(row)
        for row in rows
        if dict(row).get("status") != ANOMALY_HYPOTHESIS_DISCARDED
    ]
    all_rows = [dict(row) for row in rows]
    return {
        "hypothesis_count": len(active),
        "hypothesis_deepest_level": max(
            (int(row.get("level") or 0) for row in active), default=0
        ),
        "hypothesis_adopted": any(
            row.get("status") == ANOMALY_HYPOTHESIS_ADOPTED for row in all_rows
        ),
    }


def list_anomaly_evidence_chain(
    conn: sqlite3.Connection, anomaly_id: str
) -> list[dict[str, Any]]:
    from database.repository import (
        get_anomaly_root_cause,
        list_anomaly_analysis_notes,
        list_anomaly_attachments,
    )

    anomaly_key = (anomaly_id or "").strip()
    nodes: list[dict[str, Any]] = []
    for note in list_anomaly_analysis_notes(conn, anomaly_key):
        nodes.append(
            {
                "node_type": "analysis_note",
                "node_id": note.get("id"),
                "ts": note.get("created_at") or "",
                "summary": (note.get("content") or "")[:240],
                "evidence_type": note.get("evidence_type"),
                "status": "",
                "parent_id": "",
                "attachment_count": _count_note_attachments(
                    conn, str(note.get("id") or "")
                ),
            }
        )
    if anomaly_hypotheses_schema_ready(conn):
        for hypothesis in list_anomaly_hypotheses(conn, anomaly_key):
            nodes.append(
                {
                    "node_type": "hypothesis",
                    "node_id": hypothesis.get("id"),
                    "ts": hypothesis.get("created_at") or "",
                    "summary": (hypothesis.get("statement") or "")[:240],
                    "evidence_type": hypothesis.get("evidence_type"),
                    "status": hypothesis.get("status"),
                    "parent_id": hypothesis.get("parent_hypothesis_id") or "",
                    "attachment_count": _count_hypothesis_attachments(
                        conn, str(hypothesis.get("id") or "")
                    ),
                }
            )
    for attachment in list_anomaly_attachments(conn, anomaly_key):
        nodes.append(
            {
                "node_type": "attachment",
                "node_id": attachment.get("id"),
                "ts": attachment.get("uploaded_at") or "",
                "summary": attachment.get("file_name") or "",
                "evidence_type": "",
                "status": "",
                "parent_id": attachment.get("related_note_id")
                or attachment.get("related_hypothesis_id")
                or "",
                "attachment_count": 0,
            }
        )
    root = get_anomaly_root_cause(conn, anomaly_key)
    if root and str(root.get("statement") or "").strip():
        nodes.append(
            {
                "node_type": "root_cause",
                "node_id": root.get("id"),
                "ts": root.get("updated_at") or root.get("created_at") or "",
                "summary": (root.get("statement") or "")[:240],
                "evidence_type": "",
                "status": root.get("status"),
                "parent_id": root.get("promoted_from_hypothesis_id") or "",
                "attachment_count": 0,
            }
        )
    nodes.sort(key=lambda item: (item.get("ts") or "", item.get("node_type") or ""))
    return nodes


def validate_attachment_hypothesis_link(
    conn: sqlite3.Connection,
    *,
    anomaly_id: str,
    related_note_id: str | None,
    related_hypothesis_id: str | None,
) -> str | None:
    note_key = (related_note_id or "").strip() or None
    hypothesis_key = (related_hypothesis_id or "").strip() or None
    if note_key and hypothesis_key:
        raise ValueError("Attachment cannot link to both a note and a hypothesis")
    if hypothesis_key:
        _require_hypothesis_schema(conn)
        row = conn.execute(
            "SELECT anomaly_id FROM anomaly_hypotheses WHERE id = ?",
            (hypothesis_key,),
        ).fetchone()
        if row is None or str(row[0] or "") != (anomaly_id or "").strip():
            raise ValueError("Related hypothesis not found")
    return hypothesis_key
