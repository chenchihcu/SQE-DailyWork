"""Supplier-event workbench sub-table persistence and read models."""

from __future__ import annotations

import logging
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from database.anomaly_repository import require_anomaly
from database.case_action_repository import (
    aggregate_execution_status as _aggregate_case_action_execution_status,
    aggregate_verification_status as _aggregate_action_verification_status,
    get_case_action,
    get_current_case_action,
    is_anomaly_overdue as is_case_action_overdue,
    list_case_actions,
    require_case_actions_schema,
)
from database.repo_helpers import (
    ANOMALY_ACTION_STATUSES,
    ANOMALY_ROOT_CAUSE_STATUSES,
    CORRECTIVE_ACTION_STATUSES,
    EFFECTIVENESS_VERIFICATION_RESULTS,
    ANOMALY_ACTION_STATUS_CANCELLED,
    ANOMALY_ACTION_STATUS_COMPLETED,
    ANOMALY_ACTION_STATUS_OPEN,
    ANOMALY_ATTACHMENT_CATEGORIES,
    ANOMALY_ATTACHMENT_CATEGORY_LABELS,
    ANOMALY_ATTACHMENT_CATEGORY_OTHER,
    ANOMALY_EVIDENCE_LABELS,
    ANOMALY_EVIDENCE_TYPES,
    ANOMALY_EVIDENCE_UNKNOWN,
    ANOMALY_ROOT_CAUSE_NOT_ESTABLISHED,
    ANOMALY_ROOT_CAUSE_NOT_STARTED,
    ANOMALY_ROOT_CAUSE_VERIFIED,
    CASE_ACTION_OPEN_STATUSES,
    CASE_ACTION_VERIFICATION_ELIGIBLE_TYPES,
    CORRECTIVE_ACTION_STATUS_IMPLEMENTED,
    CORRECTIVE_ACTION_STATUS_PLANNED,
    CORRECTIVE_ACTION_STATUS_VERIFICATION_PENDING,
    EFFECTIVENESS_VERIFICATION_RESULT_EFFECTIVE,
    EFFECTIVENESS_VERIFICATION_RESULT_INEFFECTIVE,
    EFFECTIVENESS_VERIFICATION_RESULT_PENDING,
    _as_int,
    _ensure_date_not_in_future,
    _gen_id,
    _normalize_loose_iso_date,
    _normalize_non_negative_int,
    _normalize_strict_iso_date,
    _now_iso,
    _table_columns,
)
from database.anomaly_hypothesis_repository import (
    hypothesis_overview_metrics,
    validate_attachment_hypothesis_link,
)
from database.anomaly_repeat_repository import count_repeat_links_for_anomaly
from services.path_name_helpers import contains_invalid_path_char

logger = logging.getLogger(__name__)

def create_anomaly_action(
    conn: sqlite3.Connection,
    *,
    anomaly_id: str,
    description: str,
    owner: str = "",
    due_date: str = "",
    status: str = ANOMALY_ACTION_STATUS_OPEN,
) -> str:
    """Insert a new next-action row for an anomaly.

    Validates that the anomaly exists and stays aligned with the v2 status
    constraint (``待處理/已結案``). Closed anomalies may still receive
    informative next actions as long as the description is non-empty, so we
    do not block creation here — UI / service layer decide when to surface
    the action.
    """
    anomaly_key = (anomaly_id or "").strip()
    if not anomaly_key:
        raise ValueError("Anomaly id is required")
    normalized_description = (description or "").strip()
    if not normalized_description:
        raise ValueError("Action description is required")
    if get_anomaly_detail(conn, anomaly_key) is None:
        raise ValueError("Anomaly not found")
    if status not in ANOMALY_ACTION_STATUSES:
        raise ValueError("Action status must be 進行中 / 已完成 / 已取消")
    normalized_due = ""
    if due_date:
        normalized_due = _normalize_loose_iso_date(
            due_date, field_name="Action due date"
        )
    action_id = _gen_id()
    conn.execute(
        """
        INSERT INTO anomaly_actions(
            id, anomaly_id, description, owner, due_date, status,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            action_id,
            anomaly_key,
            normalized_description,
            (owner or "").strip(),
            normalized_due,
            status,
        ),
    )
    conn.commit()
    return action_id

def list_anomaly_actions(
    conn: sqlite3.Connection,
    anomaly_id: str,
    *,
    include_completed: bool = True,
    include_cancelled: bool = True,
) -> list[dict]:
    """Return all actions for an anomaly, ordered by status then due date."""
    anomaly_key = (anomaly_id or "").strip()
    if not anomaly_key:
        return []
    statuses: list[str] = [ANOMALY_ACTION_STATUS_OPEN]
    if include_completed:
        statuses.append(ANOMALY_ACTION_STATUS_COMPLETED)
    if include_cancelled:
        statuses.append(ANOMALY_ACTION_STATUS_CANCELLED)
    placeholders = ",".join("?" for _ in statuses)
    rows = conn.execute(
        f"""
        SELECT id, anomaly_id, description, owner, due_date, status,
               completed_at, completed_note, cancelled_at, cancelled_note,
               created_at, updated_at
        FROM anomaly_actions
        WHERE anomaly_id = ? AND status IN ({placeholders})
        ORDER BY
            CASE status
                WHEN '進行中' THEN 0
                WHEN '已完成' THEN 1
                WHEN '已取消' THEN 2
                ELSE 3
            END,
            CASE WHEN trim(coalesce(due_date, '')) = '' THEN 1 ELSE 0 END,
            due_date ASC,
            created_at ASC
        """,
        (anomaly_key, *statuses),
    ).fetchall()
    return [dict(row) for row in rows]

def get_anomaly_action(
    conn: sqlite3.Connection, action_id: str
) -> dict | None:
    key = (action_id or "").strip()
    if not key:
        return None
    row = conn.execute(
        """
        SELECT id, anomaly_id, description, owner, due_date, status,
               completed_at, completed_note, cancelled_at, cancelled_note,
               created_at, updated_at
        FROM anomaly_actions
        WHERE id = ?
        LIMIT 1
        """,
        (key,),
    ).fetchone()
    return dict(row) if row else None

def update_anomaly_action(
    conn: sqlite3.Connection,
    action_id: str,
    *,
    description: str | None = None,
    owner: str | None = None,
    due_date: str | None = None,
) -> None:
    """Edit description / owner / due_date of an existing action.

    Status transitions go through :func:`complete_anomaly_action` or
    :func:`cancel_anomaly_action` so the audit-relevant timestamps stay
    consistent.
    """
    key = (action_id or "").strip()
    if not key:
        raise ValueError("Action id is required")
    existing = get_anomaly_action(conn, key)
    if existing is None:
        raise ValueError("Action not found")
    if existing["status"] != ANOMALY_ACTION_STATUS_OPEN:
        raise ValueError("Only 進行中 actions are editable")
    fields: dict[str, object] = {}
    if description is not None:
        normalized = (description or "").strip()
        if not normalized:
            raise ValueError("Action description is required")
        fields["description"] = normalized
    if owner is not None:
        fields["owner"] = (owner or "").strip()
    if due_date is not None:
        if due_date:
            fields["due_date"] = _normalize_loose_iso_date(
                due_date, field_name="Action due date"
            )
        else:
            fields["due_date"] = ""
    if not fields:
        return
    assignments = ", ".join(f"{col} = ?" for col in fields)
    params: list[object] = list(fields.values()) + [
        _now_iso(),
        key,
    ]
    conn.execute(
        f"""
        UPDATE anomaly_actions
        SET {assignments}, updated_at = ?
        WHERE id = ?
        """,
        params,
    )
    conn.commit()

def complete_anomaly_action(
    conn: sqlite3.Connection,
    action_id: str,
    *,
    completion_note: str = "",
    completed_at: str | None = None,
) -> None:
    """Mark an action as 已完成 with timestamp and optional note."""
    key = (action_id or "").strip()
    if not key:
        raise ValueError("Action id is required")
    existing = get_anomaly_action(conn, key)
    if existing is None:
        raise ValueError("Action not found")
    if existing["status"] != ANOMALY_ACTION_STATUS_OPEN:
        raise ValueError("Only 進行中 actions can be completed")
    normalized_at = _normalize_strict_iso_date(
        completed_at,
        field_name="Completion date",
        fallback=date.today().isoformat(),
    )
    _ensure_date_not_in_future(normalized_at, field_name="Completion date")
    conn.execute(
        """
        UPDATE anomaly_actions
        SET status = '已完成',
            completed_at = ?,
            completed_note = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            normalized_at,
            (completion_note or "").strip(),
            _now_iso(),
            key,
        ),
    )
    conn.commit()

def cancel_anomaly_action(
    conn: sqlite3.Connection,
    action_id: str,
    *,
    cancel_note: str = "",
    cancelled_at: str | None = None,
) -> None:
    """Mark an action as 已取消 with timestamp and optional reason."""
    key = (action_id or "").strip()
    if not key:
        raise ValueError("Action id is required")
    existing = get_anomaly_action(conn, key)
    if existing is None:
        raise ValueError("Action not found")
    if existing["status"] != ANOMALY_ACTION_STATUS_OPEN:
        raise ValueError("Only 進行中 actions can be cancelled")
    normalized_at = _normalize_strict_iso_date(
        cancelled_at,
        field_name="Cancellation date",
        fallback=date.today().isoformat(),
    )
    _ensure_date_not_in_future(normalized_at, field_name="Cancellation date")
    conn.execute(
        """
        UPDATE anomaly_actions
        SET status = '已取消',
            cancelled_at = ?,
            cancelled_note = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            normalized_at,
            (cancel_note or "").strip(),
            _now_iso(),
            key,
        ),
    )
    conn.commit()

def is_legacy_anomaly_action_overdue(
    conn: sqlite3.Connection,
    anomaly_id: str,
    *,
    today: str | None = None,
) -> bool:
    """Legacy overdue check against deprecated ``anomaly_actions`` table.

    New code must use ``is_case_action_overdue`` (canonical ``case_actions`` SSOT).
    """
    anomaly_key = (anomaly_id or "").strip()
    if not anomaly_key:
        return False
    detail = get_anomaly_detail(conn, anomaly_key)
    if detail is None:
        return False
    if detail.get("status") != "待處理":
        return False
    today_iso = _normalize_strict_iso_date(
        today, field_name="Today", fallback=date.today().isoformat()
    )
    row = conn.execute(
        """
        SELECT 1
        FROM anomaly_actions
        WHERE anomaly_id = ?
          AND status = '進行中'
          AND trim(coalesce(due_date, '')) <> ''
          AND due_date < ?
        LIMIT 1
        """,
        (anomaly_key, today_iso),
    ).fetchone()
    return row is not None

def get_current_anomaly_action(
    conn: sqlite3.Connection,
    anomaly_id: str,
) -> dict | None:
    """Return the most actionable 進行中 row or ``None`` when none is open."""
    anomaly_key = (anomaly_id or "").strip()
    if not anomaly_key:
        return None
    row = conn.execute(
        """
        SELECT id, anomaly_id, description, owner, due_date, status,
               completed_at, completed_note, cancelled_at, cancelled_note,
               created_at, updated_at
        FROM anomaly_actions
        WHERE anomaly_id = ? AND status = '進行中'
        ORDER BY
            CASE WHEN trim(coalesce(due_date, '')) = '' THEN 1 ELSE 0 END,
            due_date ASC,
            created_at ASC
        LIMIT 1
        """,
        (anomaly_key,),
    ).fetchone()
    return dict(row) if row else None

def create_anomaly_analysis_note(
    conn: sqlite3.Connection,
    *,
    anomaly_id: str,
    content: str,
    evidence_type: str = ANOMALY_EVIDENCE_UNKNOWN,
    author_name: str = "",
    attachment_count: int = 0,
) -> str:
    require_anomaly(conn, anomaly_id)
    text = (content or "").strip()
    if not text:
        raise ValueError("Analysis note content is required")
    ev = (evidence_type or "").strip()
    if ev not in ANOMALY_EVIDENCE_TYPES:
        raise ValueError("Evidence type must be FACT / INFERENCE / ASSUMPTION / UNKNOWN")
    note_id = _gen_id()
    conn.execute(
        """
        INSERT INTO anomaly_analysis_notes(
            id, anomaly_id, content, evidence_type, author_name,
            attachment_count, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            note_id,
            anomaly_id.strip(),
            text,
            ev,
            (author_name or "").strip(),
            _normalize_non_negative_int(attachment_count, field_name="Attachment count"),
        ),
    )
    conn.commit()
    return note_id

def _count_analysis_note_attachments(conn: sqlite3.Connection, note_id: str) -> int:
    if not note_id:
        return 0
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM anomaly_attachments WHERE related_note_id = ?",
            (note_id,),
        ).fetchone()[0]
    )

def list_anomaly_analysis_notes(
    conn: sqlite3.Connection, anomaly_id: str
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, anomaly_id, content, evidence_type, author_name,
               attachment_count, created_at, updated_at
        FROM anomaly_analysis_notes
        WHERE anomaly_id = ?
        ORDER BY created_at ASC, rowid ASC
        """,
        (anomaly_id or "",),
    ).fetchall()
    result: list[dict] = []
    for row in rows:
        item = dict(row)
        item["evidence_label"] = ANOMALY_EVIDENCE_LABELS.get(
            item.get("evidence_type"), item.get("evidence_type")
        )
        item["attachment_count"] = _count_analysis_note_attachments(
            conn, str(item.get("id") or "")
        )
        result.append(item)
    return result

def get_anomaly_root_cause(
    conn: sqlite3.Connection, anomaly_id: str
) -> dict | None:
    available = _table_columns(conn, "anomaly_root_causes")
    promoted_expr = (
        "promoted_from_hypothesis_id"
        if "promoted_from_hypothesis_id" in available
        else "NULL AS promoted_from_hypothesis_id"
    )
    row = conn.execute(
        f"""
        SELECT id, anomaly_id, statement, status, validation_method,
               validation_evidence, conclusion_note, not_established_reason,
               {promoted_expr},
               created_at, updated_at
        FROM anomaly_root_causes
        WHERE anomaly_id = ?
        LIMIT 1
        """,
        (anomaly_id or "",),
    ).fetchone()
    return dict(row) if row else None

def upsert_anomaly_root_cause(
    conn: sqlite3.Connection,
    *,
    anomaly_id: str,
    statement: str = "",
    status: str = ANOMALY_ROOT_CAUSE_NOT_STARTED,
    validation_method: str = "",
    validation_evidence: str = "",
    conclusion_note: str = "",
    not_established_reason: str = "",
    promoted_from_hypothesis_id: str | None = None,
    _commit: bool = True,
) -> str:
    require_anomaly(conn, anomaly_id)
    if status not in ANOMALY_ROOT_CAUSE_STATUSES:
        raise ValueError("Invalid root cause status")
    # Conditional requirement: Verified / Not Established require a statement.
    if status in (ANOMALY_ROOT_CAUSE_VERIFIED, ANOMALY_ROOT_CAUSE_NOT_ESTABLISHED):
        if not (statement or "").strip():
            raise ValueError("Root cause statement is required for this status")
    if status == ANOMALY_ROOT_CAUSE_NOT_ESTABLISHED:
        if not (not_established_reason or "").strip():
            raise ValueError(
                "Not established reason is required when root cause status is 無法確認"
            )
    existing = get_anomaly_root_cause(conn, anomaly_id)
    promoted_key = (promoted_from_hypothesis_id or "").strip() or None
    root_columns = _table_columns(conn, "anomaly_root_causes")
    if existing is None:
        rc_id = _gen_id()
        insert_columns = [
            "id",
            "anomaly_id",
            "statement",
            "status",
            "validation_method",
            "validation_evidence",
            "conclusion_note",
            "not_established_reason",
        ]
        insert_values: list[object] = [
            rc_id,
            anomaly_id.strip(),
            (statement or "").strip(),
            status,
            (validation_method or "").strip(),
            (validation_evidence or "").strip(),
            (conclusion_note or "").strip(),
            (not_established_reason or "").strip(),
        ]
        if "promoted_from_hypothesis_id" in root_columns:
            insert_columns.append("promoted_from_hypothesis_id")
            insert_values.append(promoted_key)
        placeholders = ", ".join("?" for _ in insert_columns)
        conn.execute(
            f"""
            INSERT INTO anomaly_root_causes(
                {", ".join(insert_columns)}, created_at, updated_at
            ) VALUES ({placeholders}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            tuple(insert_values),
        )
        if _commit:
            conn.commit()
        return rc_id
    update_fields = [
        "statement = ?",
        "status = ?",
        "validation_method = ?",
        "validation_evidence = ?",
        "conclusion_note = ?",
        "not_established_reason = ?",
    ]
    update_values: list[object] = [
        (statement or "").strip(),
        status,
        (validation_method or "").strip(),
        (validation_evidence or "").strip(),
        (conclusion_note or "").strip(),
        (not_established_reason or "").strip(),
    ]
    if promoted_from_hypothesis_id is not None and "promoted_from_hypothesis_id" in root_columns:
        update_fields.append("promoted_from_hypothesis_id = ?")
        update_values.append(promoted_key)
    update_values.append(existing["id"])
    conn.execute(
        f"""
        UPDATE anomaly_root_causes
        SET {", ".join(update_fields)}, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        tuple(update_values),
    )
    if _commit:
        conn.commit()
    return str(existing["id"])

def create_corrective_action(
    conn: sqlite3.Connection,
    *,
    anomaly_id: str,
    description: str,
    responsible_party: str = "",
    target_date: str = "",
    status: str = CORRECTIVE_ACTION_STATUS_PLANNED,
    effectiveness_verification_required: bool = False,
    notes: str = "",
) -> str:
    require_anomaly(conn, anomaly_id)
    text = (description or "").strip()
    if not text:
        raise ValueError("Corrective action description is required")
    if status not in CORRECTIVE_ACTION_STATUSES:
        raise ValueError("Invalid corrective action status")
    ca_id = _gen_id()
    normalized_target = ""
    if target_date:
        normalized_target = _normalize_loose_iso_date(
            target_date, field_name="Target date"
        )
    conn.execute(
        """
        INSERT INTO corrective_actions(
            id, anomaly_id, description, responsible_party, target_date, status,
            effectiveness_verification_required, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            ca_id,
            anomaly_id.strip(),
            text,
            (responsible_party or "").strip(),
            normalized_target,
            status,
            1 if effectiveness_verification_required else 0,
            (notes or "").strip(),
        ),
    )
    conn.commit()
    return ca_id

def list_corrective_actions(
    conn: sqlite3.Connection, anomaly_id: str
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, anomaly_id, description, responsible_party, target_date,
               status, implementation_evidence, completion_date,
               effectiveness_verification_required, notes, created_at, updated_at
        FROM corrective_actions
        WHERE anomaly_id = ?
        ORDER BY created_at ASC, rowid ASC
        """,
        (anomaly_id or "",),
    ).fetchall()
    result: list[dict] = []
    for item in rows:
        d = dict(item)
        d["effectiveness_verification_required"] = bool(
            _as_int(d.get("effectiveness_verification_required"), 0)
        )
        result.append(d)
    return result

def get_corrective_action(
    conn: sqlite3.Connection, ca_id: str
) -> dict | None:
    key = (ca_id or "").strip()
    if not key:
        return None
    row = conn.execute(
        """
        SELECT id, anomaly_id, description, responsible_party, target_date,
               status, implementation_evidence, completion_date,
               effectiveness_verification_required, notes, created_at, updated_at
        FROM corrective_actions
        WHERE id = ?
        LIMIT 1
        """,
        (key,),
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["effectiveness_verification_required"] = bool(
        _as_int(d.get("effectiveness_verification_required"), 0)
    )
    return d

def update_corrective_action(
    conn: sqlite3.Connection,
    ca_id: str,
    *,
    responsible_party: str | None = None,
    target_date: str | None = None,
    notes: str | None = None,
    implementation_evidence: str | None = None,
) -> None:
    existing = get_corrective_action(conn, ca_id)
    if existing is None:
        raise ValueError("Corrective action not found")
    fields: dict[str, object] = {}
    if responsible_party is not None:
        fields["responsible_party"] = (responsible_party or "").strip()
    if target_date is not None:
        if target_date:
            fields["target_date"] = _normalize_loose_iso_date(
                target_date, field_name="Target date"
            )
        else:
            fields["target_date"] = ""
    if notes is not None:
        fields["notes"] = (notes or "").strip()
    if implementation_evidence is not None:
        fields["implementation_evidence"] = (implementation_evidence or "").strip()
    if not fields:
        return
    assignments = ", ".join(f"{col} = ?" for col in fields)
    params: list[object] = list(fields.values())
    params.append(_now_iso())
    params.append(str(existing["id"]))
    conn.execute(
        f"UPDATE corrective_actions SET {assignments}, updated_at = ? WHERE id = ?",
        params,
    )
    conn.commit()

def complete_corrective_action(
    conn: sqlite3.Connection,
    ca_id: str,
    *,
    implementation_evidence: str = "",
    completion_date: str | None = None,
) -> None:
    existing = get_corrective_action(conn, ca_id)
    if existing is None:
        raise ValueError("Corrective action not found")
    completion = _normalize_strict_iso_date(
        completion_date,
        field_name="Completion date",
        fallback=date.today().isoformat(),
    )
    _ensure_date_not_in_future(completion, field_name="Completion date")
    next_status = (
        CORRECTIVE_ACTION_STATUS_VERIFICATION_PENDING
        if existing.get("effectiveness_verification_required")
        else CORRECTIVE_ACTION_STATUS_IMPLEMENTED
    )
    conn.execute(
        """
        UPDATE corrective_actions
        SET status = ?, implementation_evidence = ?, completion_date = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            next_status,
            (implementation_evidence or "").strip(),
            completion,
            _now_iso(),
            str(existing["id"]),
        ),
    )
    conn.commit()

def change_corrective_action_status(
    conn: sqlite3.Connection, ca_id: str, status: str
) -> None:
    existing = get_corrective_action(conn, ca_id)
    if existing is None:
        raise ValueError("Corrective action not found")
    if status not in CORRECTIVE_ACTION_STATUSES:
        raise ValueError("Invalid corrective action status")
    conn.execute(
        "UPDATE corrective_actions SET status = ?, updated_at = ? WHERE id = ?",
        (status, _now_iso(), str(existing["id"])),
    )
    conn.commit()

def create_effectiveness_verification(
    conn: sqlite3.Connection,
    *,
    corrective_action_id: str,
    method: str = "",
    acceptance_criteria: str = "",
    period_sample: str = "",
    result: str = EFFECTIVENESS_VERIFICATION_RESULT_PENDING,
    evidence: str = "",
    conclusion: str = "",
    verified_by: str = "",
    verified_date: str | None = None,
) -> str:
    existing = get_corrective_action(conn, corrective_action_id)
    if existing is None:
        raise ValueError("Corrective action not found")
    if result not in EFFECTIVENESS_VERIFICATION_RESULTS:
        raise ValueError("Invalid verification result")
    vid = _gen_id()
    vdate = ""
    if verified_date:
        vdate = _normalize_strict_iso_date(verified_date, field_name="Verified date")
    conn.execute(
        """
        INSERT INTO effectiveness_verifications(
            id, corrective_action_id, method, acceptance_criteria, period_sample,
            result, evidence, conclusion, verified_by, verified_date,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            vid,
            str(existing["id"]),
            (method or "").strip(),
            (acceptance_criteria or "").strip(),
            (period_sample or "").strip(),
            result,
            (evidence or "").strip(),
            (conclusion or "").strip(),
            (verified_by or "").strip(),
            vdate or None,
        ),
    )
    # If the outcome is conclusive, reflect it on the corrective action.
    if result == EFFECTIVENESS_VERIFICATION_RESULT_EFFECTIVE:
        conn.execute(
            "UPDATE corrective_actions SET status = '有效', updated_at = ? WHERE id = ?",
            (_now_iso(), str(existing["id"])),
        )
    elif result == EFFECTIVENESS_VERIFICATION_RESULT_INEFFECTIVE:
        conn.execute(
            "UPDATE corrective_actions SET status = '無效', updated_at = ? WHERE id = ?",
            (_now_iso(), str(existing["id"])),
        )
    conn.commit()
    return vid

def list_effectiveness_verifications(
    conn: sqlite3.Connection, corrective_action_id: str
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, corrective_action_id, method, acceptance_criteria,
               period_sample, result, evidence, conclusion, verified_by,
               verified_date, created_at, updated_at
        FROM effectiveness_verifications
        WHERE corrective_action_id = ?
        ORDER BY created_at DESC, rowid DESC
        """,
        (corrective_action_id or "",),
    ).fetchall()
    return [dict(row) for row in rows]

def create_anomaly_attachment(
    conn: sqlite3.Connection,
    *,
    anomaly_id: str,
    file_name: str,
    stored_name: str = "",
    category: str = "其他",
    description: str = "",
    file_size: int = 0,
    file_type: str = "",
    revision: str = "",
    uploaded_by: str = "",
    related_note_id: str | None = None,
    related_action_id: str | None = None,
    related_hypothesis_id: str | None = None,
    _commit: bool = True,
) -> str:
    require_anomaly(conn, anomaly_id)
    anomaly_key = str(anomaly_id or "").strip()
    require_case_actions_schema(conn)
    fname = (file_name or "").strip()
    if not fname:
        raise ValueError("Attachment file name is required")
    fname = _normalize_attachment_file_name(fname, field_name="Attachment file name")
    stored = (stored_name or "").strip()
    if stored:
        stored = _normalize_attachment_file_name(
            stored, field_name="Attachment stored name"
        )
    normalized_action_id = (related_action_id or "").strip() or None
    if normalized_action_id:
        action = get_case_action(conn, normalized_action_id)
        if action is None or str(action.get("anomaly_id") or "") != anomaly_key:
            raise ValueError("Related Action not found")
    normalized_note_id = (related_note_id or "").strip() or None
    if normalized_note_id:
        if "related_note_id" not in _table_columns(conn, "anomaly_attachments"):
            raise RuntimeError(
                "需要完成附件資料升級：anomaly_attachments_contract_v1。"
            )
        note = conn.execute(
            "SELECT anomaly_id FROM anomaly_analysis_notes WHERE id = ?",
            (normalized_note_id,),
        ).fetchone()
        if note is None or str(note[0] or "") != anomaly_key:
            raise ValueError("Related analysis note not found")
    normalized_hypothesis_id = validate_attachment_hypothesis_link(
        conn,
        anomaly_id=anomaly_key,
        related_note_id=normalized_note_id,
        related_hypothesis_id=related_hypothesis_id,
    )

    available = _table_columns(conn, "anomaly_attachments")
    if normalized_action_id and "related_action_id" not in available:
        raise RuntimeError(
            "需要完成附件資料升級：anomaly_attachments_contract_v1。"
        )
    normalized_category = (category or "").strip()
    if not normalized_category:
        normalized_category = ANOMALY_ATTACHMENT_CATEGORY_OTHER
    if normalized_category not in ANOMALY_ATTACHMENT_CATEGORIES:
        # Preserve legacy Traditional-Chinese values while making the new
        # contract's nine English values canonical for new callers.
        legacy_label_to_key = {
            label: key for key, label in ANOMALY_ATTACHMENT_CATEGORY_LABELS.items()
        }
        normalized_category = legacy_label_to_key.get(
            normalized_category, normalized_category
        )
    aid = _gen_id()
    values: dict[str, object] = {
        "id": aid,
        "anomaly_id": anomaly_key,
        "file_name": fname,
        "stored_name": stored,
        "category": normalized_category,
        "description": (description or "").strip(),
        "file_size": _normalize_non_negative_int(file_size, field_name="File size"),
    }
    optional_values: dict[str, object] = {
        "file_type": (file_type or "").strip(),
        "revision": (revision or "").strip(),
        "uploaded_by": (uploaded_by or "").strip(),
        "related_note_id": normalized_note_id,
        "related_action_id": normalized_action_id,
        "related_hypothesis_id": normalized_hypothesis_id,
    }
    for column_name, value in optional_values.items():
        if column_name in available:
            values[column_name] = value
    columns = list(values)
    placeholders = ", ".join("?" for _ in columns)
    conn.execute(
        f"INSERT INTO anomaly_attachments({', '.join(columns)}) "
        f"VALUES ({placeholders})",
        tuple(values[column] for column in columns),
    )
    if _commit:
        conn.commit()
    return aid

def update_anomaly_attachment(
    conn: sqlite3.Connection,
    *,
    attachment_id: str,
    anomaly_id: str,
    category: str,
    description: str = "",
    revision: str = "",
    related_note_id: str | None = None,
    related_action_id: str | None = None,
    related_hypothesis_id: str | None = None,
    _commit: bool = True,
) -> dict:
    """Update editable Evidence metadata while preserving storage identity."""
    require_anomaly(conn, anomaly_id)
    attachment_key = str(attachment_id or "").strip()
    anomaly_key = str(anomaly_id or "").strip()
    if not attachment_key:
        raise ValueError("Attachment id is required")
    row = conn.execute(
        "SELECT * FROM anomaly_attachments WHERE id = ? AND anomaly_id = ?",
        (attachment_key, anomaly_key),
    ).fetchone()
    if row is None:
        raise ValueError("Attachment not found")

    normalized_category = (category or "").strip() or ANOMALY_ATTACHMENT_CATEGORY_OTHER
    if normalized_category not in ANOMALY_ATTACHMENT_CATEGORIES:
        legacy_label_to_key = {
            label: key for key, label in ANOMALY_ATTACHMENT_CATEGORY_LABELS.items()
        }
        normalized_category = legacy_label_to_key.get(
            normalized_category, normalized_category
        )
    if normalized_category not in ANOMALY_ATTACHMENT_CATEGORIES:
        raise ValueError("Invalid attachment category")

    normalized_note_id = (related_note_id or "").strip() or None
    if normalized_note_id:
        note = conn.execute(
            "SELECT anomaly_id FROM anomaly_analysis_notes WHERE id = ?",
            (normalized_note_id,),
        ).fetchone()
        if note is None or str(note[0] or "") != anomaly_key:
            raise ValueError("Related analysis note not found")

    normalized_action_id = (related_action_id or "").strip() or None
    if normalized_action_id:
        action = get_case_action(conn, normalized_action_id)
        if action is None or str(action.get("anomaly_id") or "") != anomaly_key:
            raise ValueError("Related Action not found")
    normalized_hypothesis_id = validate_attachment_hypothesis_link(
        conn,
        anomaly_id=anomaly_key,
        related_note_id=normalized_note_id,
        related_hypothesis_id=related_hypothesis_id,
    )

    available = _table_columns(conn, "anomaly_attachments")
    fields = ["category = ?", "description = ?", "revision = ?"]
    values: list[object] = [
        normalized_category,
        (description or "").strip(),
        (revision or "").strip(),
    ]
    if "related_note_id" in available:
        fields.append("related_note_id = ?")
        values.append(normalized_note_id)
    if "related_action_id" in available:
        fields.append("related_action_id = ?")
        values.append(normalized_action_id)
    if "related_hypothesis_id" in available:
        fields.append("related_hypothesis_id = ?")
        values.append(normalized_hypothesis_id)
    values.extend([attachment_key, anomaly_key])
    conn.execute(
        f"UPDATE anomaly_attachments SET {', '.join(fields)} "
        "WHERE id = ? AND anomaly_id = ?",
        tuple(values),
    )
    updated = conn.execute(
        "SELECT * FROM anomaly_attachments WHERE id = ? AND anomaly_id = ?",
        (attachment_key, anomaly_key),
    ).fetchone()
    if _commit:
        conn.commit()
    return dict(updated) if updated is not None else dict(row)

def delete_anomaly_attachment_metadata(
    conn: sqlite3.Connection,
    *,
    attachment_id: str,
    anomaly_id: str,
    _commit: bool = True,
) -> dict:
    """Delete one registered metadata row; physical bytes are service-owned."""
    anomaly_key = str(anomaly_id or "").strip()
    attachment_key = str(attachment_id or "").strip()
    require_anomaly(conn, anomaly_key)
    if not attachment_key:
        raise ValueError("Attachment id is required")
    row = conn.execute(
        "SELECT * FROM anomaly_attachments WHERE id = ? AND anomaly_id = ?",
        (attachment_key, anomaly_key),
    ).fetchone()
    if row is None:
        raise ValueError("Attachment not found")
    conn.execute(
        "DELETE FROM anomaly_attachments WHERE id = ? AND anomaly_id = ?",
        (attachment_key, anomaly_key),
    )
    if _commit:
        conn.commit()
    return dict(row)

def _normalize_attachment_file_name(value: str, *, field_name: str) -> str:
    """Keep attachment metadata names to one safe filesystem component."""
    name = str(value or "").strip()
    if not name or name in {".", ".."}:
        raise ValueError(f"{field_name} is required")
    if contains_invalid_path_char(name):
        raise ValueError(f"{field_name} must be a file name")
    if len(name) >= 2 and name[1] == ":":
        raise ValueError(f"{field_name} must be a file name")
    return name

def list_anomaly_attachments(
    conn: sqlite3.Connection, anomaly_id: str
) -> list[dict]:
    available = _table_columns(conn, "anomaly_attachments")
    columns = [
        "id",
        "anomaly_id",
        "file_name",
        "stored_name",
        "category",
        "description",
        "file_size",
    ]
    for optional in (
        "file_type",
        "revision",
        "uploaded_by",
        "related_ca_id",
        "related_note_id",
        "related_action_id",
        "related_hypothesis_id",
        "uploaded_at",
    ):
        if optional in available:
            columns.append(optional)
        else:
            columns.append(f"NULL AS {optional}")
    rows = conn.execute(
        f"SELECT {', '.join(columns)} FROM anomaly_attachments "
        "WHERE anomaly_id = ? ORDER BY uploaded_at ASC, rowid ASC",
        (anomaly_id or "",),
    ).fetchall()
    result = [dict(row) for row in rows]
    for item in result:
        item["category_label"] = ANOMALY_ATTACHMENT_CATEGORY_LABELS.get(
            str(item.get("category") or ""), str(item.get("category") or "")
        )
    return result

def _count_anomaly_attachment_manifest(
    conn: sqlite3.Connection,
    anomaly_id: str,
) -> int:
    """Count metadata rows plus unregistered legacy physical files.

    The storage adapter is imported lazily so database bootstrap remains free
    of a service-layer import.  If a legacy store cannot be read, the DB
    metadata count remains a truthful lower bound rather than failing an
    otherwise valid anomaly overview query.
    """
    metadata = list_anomaly_attachments(conn, anomaly_id)
    metadata_names: set[str] = set()
    unnamed_metadata_rows = 0
    for row in metadata:
        name = str(row.get("stored_name") or row.get("file_name") or "").strip()
        if name:
            metadata_names.add(name)
        else:
            unnamed_metadata_rows += 1
    try:
        from services import attachment_manager

        physical_names = {
            path.name
            for path in attachment_manager.list_stored_attachment_files(anomaly_id)
        }
    except (OSError, ValueError):
        physical_names = set()
    return (
        len(metadata_names)
        + unnamed_metadata_rows
        + len(physical_names - metadata_names)
    )

def create_anomaly_eight_d_review(
    conn: sqlite3.Connection,
    *,
    anomaly_id: str,
    revision: str,
    review_status: str = "需補充證據",
    review_comment: str = "",
    attachment_id: str | None = None,
    review_date: str | None = None,
) -> str:
    require_anomaly(conn, anomaly_id)
    rev = (revision or "").strip()
    if not rev:
        raise ValueError("8D revision is required")
    if review_status not in ("接受", "退回修正", "需補充證據"):
        raise ValueError("Invalid 8D review status")
    if attachment_id:
        att = conn.execute(
            "SELECT 1 FROM anomaly_attachments WHERE id = ?", (attachment_id,)
        ).fetchone()
        if att is None:
            raise ValueError("Attachment not found")
    rid = _gen_id()
    rdate = "CURRENT_TIMESTAMP"
    rval: list[object] = [
        rid,
        anomaly_id.strip(),
        rev,
        review_status,
        (review_comment or "").strip(),
        (attachment_id or "").strip() or None,
    ]
    if review_date:
        rdate = "?"
        rval.append(
            _normalize_strict_iso_date(review_date, field_name="Review date")
        )
    conn.execute(
        f"""
        INSERT INTO anomaly_eight_d_reviews(
            id, anomaly_id, revision, review_status, review_comment,
            attachment_id, review_date
        ) VALUES (?, ?, ?, ?, ?, ?, {rdate})
        """,
        tuple(rval),
    )
    conn.commit()
    return rid

def list_anomaly_eight_d_reviews(
    conn: sqlite3.Connection, anomaly_id: str
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, anomaly_id, revision, review_status, review_comment,
               attachment_id, review_date
        FROM anomaly_eight_d_reviews
        WHERE anomaly_id = ?
        ORDER BY review_date ASC, rowid ASC
        """,
        (anomaly_id or "",),
    ).fetchall()
    return [dict(row) for row in rows]

def append_anomaly_audit_log(
    conn: sqlite3.Connection,
    *,
    anomaly_id: str,
    action: str,
    before_value: str = "",
    after_value: str = "",
    actor_name: str = "",
    _commit: bool = True,
) -> str:
    require_anomaly(conn, anomaly_id)
    act = (action or "").strip()
    if not act:
        raise ValueError("Audit action is required")
    lid = _gen_id()
    conn.execute(
        """
        INSERT INTO anomaly_audit_logs(
            id, anomaly_id, action, before_value, after_value, actor_name,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            lid,
            anomaly_id.strip(),
            act,
            (before_value or "").strip(),
            (after_value or "").strip(),
            (actor_name or "").strip(),
        ),
    )
    if _commit:
        conn.commit()
    return lid

def list_anomaly_audit_logs(
    conn: sqlite3.Connection, anomaly_id: str
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, anomaly_id, action, before_value, after_value, actor_name,
               created_at
        FROM anomaly_audit_logs
        WHERE anomaly_id = ?
        ORDER BY created_at ASC, rowid ASC
        """,
        (anomaly_id or "",),
    ).fetchall()
    return [dict(row) for row in rows]

def list_anomaly_timeline(conn: sqlite3.Connection, anomaly_id: str) -> list[dict]:
    """Return a merged, deduped event feed for an anomaly.

    Timeline is a projection across the append-only audit log and the mutable
    sub-tables. To avoid double counting, the audit log is the authoritative
    event source when present; sub-table rows are only included when they are
    not already represented by an audit entry (keyed by a stable action).

    Returns rows ordered newest-first, each with ``ts``, ``kind``, ``summary``,
    ``actor``.
    """
    audit = list_anomaly_audit_logs(conn, anomaly_id)
    events: list[dict] = []
    for entry in audit:
        events.append(
            {
                "ts": entry.get("created_at") or "",
                "kind": entry.get("action") or "AUDIT",
                "summary": entry.get("after_value") or entry.get("before_value") or "",
                "actor": entry.get("actor_name") or "",
                "source": "audit",
            }
        )
    # The audit log is authoritative; canonical rows only supply legacy events
    # that predate transactional Action audit entries.
    seen_kinds = {e["kind"] for e in events}
    rc = get_anomaly_root_cause(conn, anomaly_id)
    if rc and rc.get("status") != ANOMALY_ROOT_CAUSE_NOT_STARTED and "ROOT_CAUSE_UPDATED" not in seen_kinds:
        events.append(
            {
                "ts": rc.get("updated_at") or "",
                "kind": "ROOT_CAUSE_UPDATED",
                "summary": rc.get("statement") or "",
                "actor": "",
                "source": "root_cause",
            }
        )
    for action in list_case_actions(conn, anomaly_id):
        if (
            "CASE_ACTION_CREATED" not in seen_kinds
            and str(action.get("legacy_source") or "")
        ):
            events.append(
                {
                    "ts": action.get("created_at") or "",
                    "kind": "LEGACY_ACTION_IMPORTED",
                    "summary": action.get("description") or "",
                    "actor": "",
                    "source": "case_action",
                }
            )
    events.sort(key=lambda e: e["ts"] or "", reverse=True)
    return events

def get_anomaly_overview_card(conn: sqlite3.Connection, anomaly_id: str) -> dict:
    """Aggregate the case-overview summary used by UI / export / snapshot."""
    detail = require_anomaly(conn, anomaly_id)
    actions = list_case_actions(conn, anomaly_id)
    current = get_current_case_action(conn, anomaly_id)
    overdue = is_case_action_overdue(conn, anomaly_id)
    rc = get_anomaly_root_cause(conn, anomaly_id)
    improvement_actions = [
        action
        for action in actions
        if action.get("action_type") in CASE_ACTION_VERIFICATION_ELIGIBLE_TYPES
    ]
    action_status = _aggregate_case_action_execution_status(actions)
    improvement_status = _aggregate_case_action_execution_status(improvement_actions)
    verify_result = _aggregate_action_verification_status(improvement_actions)
    overview = {
        "anomaly_id": anomaly_id,
        "status": detail.get("status") or "待處理",
        "overdue": overdue if detail.get("status") == "待處理" else False,
        "current_action": current,
        "open_action_count": sum(
            1 for action in actions
            if action.get("execution_status") in CASE_ACTION_OPEN_STATUSES
        ),
        "action_count": len(actions),
        "action_status": action_status,
        "root_cause_status": (rc or {}).get("status", ANOMALY_ROOT_CAUSE_NOT_STARTED),
        "corrective_action_status": improvement_status or "—",
        "verification_result": verify_result or "—",
        "has_analysis_notes": bool(list_anomaly_analysis_notes(conn, anomaly_id)),
        "attachment_count": _count_anomaly_attachment_manifest(conn, anomaly_id),
        "repeat_link_count": count_repeat_links_for_anomaly(conn, anomaly_id),
    }
    overview.update(hypothesis_overview_metrics(conn, anomaly_id))
    return overview

def count_overdue_open_anomalies(
    conn: sqlite3.Connection,
    *,
    supplier_id: str | None = None,
    anomaly_where: str | None = None,
    anomaly_params: list[Any] | None = None,
) -> int:
    """Count open anomalies overdue per case-action due-date SSOT."""
    sql = "SELECT id FROM anomalies WHERE status = '待處理'"
    params: list[Any] = list(anomaly_params or [])
    if anomaly_where:
        sql += f" AND {anomaly_where}"
    if supplier_id:
        sql += " AND supplier_id = ?"
        params.append(str(supplier_id).strip())
    return sum(
        1
        for row in conn.execute(sql, params).fetchall()
        if is_case_action_overdue(conn, str(row["id"]))
    )

def count_overdue_open_anomalies_by_supplier(
    conn: sqlite3.Connection,
    *,
    anomaly_where: str | None = None,
    anomaly_params: list[Any] | None = None,
) -> dict[str, int]:
    """Return per-supplier overdue open anomaly counts (case-action SSOT)."""
    sql = "SELECT id, supplier_id FROM anomalies WHERE status = '待處理'"
    params: list[Any] = list(anomaly_params or [])
    if anomaly_where:
        sql += f" AND {anomaly_where}"
    counts: dict[str, int] = {}
    for row in conn.execute(sql, params).fetchall():
        if is_case_action_overdue(conn, str(row["id"])):
            sid = str(row["supplier_id"])
            counts[sid] = counts.get(sid, 0) + 1
    return counts
