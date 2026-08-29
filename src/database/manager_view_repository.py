"""Read models for Phase 6 manager summary and operational action queue."""

from __future__ import annotations

import sqlite3
from typing import Any

from database.repo_helpers import (
    ANOMALY_ROOT_CAUSE_NOT_STARTED,
    ANOMALY_ROOT_CAUSE_UNDER_INVESTIGATION,
    format_current_action_due_date,
    format_current_action_text,
)
from database.repository import (
    get_anomaly_overview_card,
    list_events,
)


def _matches_owner_filter(owner_filter: str, *candidates: object) -> bool:
    """Case-insensitive substring match against any candidate owner value."""
    needle = str(owner_filter or "").strip().casefold()
    if not needle:
        return True
    for candidate in candidates:
        haystack = str(candidate or "").casefold()
        if needle in haystack:
            return True
    return False


def list_manager_summary_rows(
    conn: sqlite3.Connection,
    *,
    status: str = "待處理",
    overdue_only: bool = False,
    responsible_person: str = "",
) -> list[dict[str, Any]]:
    """Manager summary rows enriched from ``get_anomaly_overview_card()`` SSOT."""
    status_key = str(status or "待處理").strip()
    if status_key not in {"待處理", "已結案", "ALL"}:
        status_key = "待處理"
    events = list_events(
        conn,
        event_type="ANOMALY",
        status=status_key,
        overdue_only=bool(overdue_only),
    )
    owner_filter = str(responsible_person or "").strip().casefold()
    rows: list[dict[str, Any]] = []
    for event in events:
        event_id = str(event.get("event_id") or "").strip()
        if not event_id:
            continue
        meta = conn.execute(
            "SELECT due_date, updated_at FROM anomalies WHERE id = ?",
            (event_id,),
        ).fetchone()
        if meta is not None:
            event = {
                **event,
                "due_date": meta["due_date"],
                "updated_at": meta["updated_at"],
            }
        overview = get_anomaly_overview_card(conn, event_id)
        current = overview.get("current_action")
        if owner_filter and not _matches_owner_filter(
            owner_filter,
            event.get("responsible_person"),
            (current or {}).get("owner") if isinstance(current, dict) else None,
        ):
            continue
        rows.append(
            {
                **event,
                "anomaly_id": event_id,
                "overdue": bool(overview.get("overdue")),
                "current_action": current,
                "current_action_text": format_current_action_text(
                    current,
                    empty_fallback="—",
                ),
                "action_due_date": format_current_action_due_date(
                    current,
                    fallback=str(event.get("due_date") or ""),
                ),
                "open_action_count": int(overview.get("open_action_count") or 0),
                "root_cause_status": overview.get("root_cause_status") or "—",
                "corrective_action_status": overview.get("corrective_action_status") or "—",
                "verification_result": overview.get("verification_result") or "—",
                "last_updated": str(event.get("updated_at") or event.get("event_date") or "—"),
            }
        )
    rows.sort(
        key=lambda item: (
            0 if item.get("overdue") else 1,
            str(item.get("action_due_date") or "9999-99-99"),
            str(item.get("ref_no") or ""),
        )
    )
    return rows


def list_operational_action_queue(
    conn: sqlite3.Connection,
    *,
    responsible_person: str = "",
    overdue_only: bool = False,
) -> list[dict[str, Any]]:
    """Open canonical case actions joined to their parent anomalies."""
    owner_filter = str(responsible_person or "").strip()
    clauses = [
        "ca.execution_status IN ('已規劃', '執行中')",
        "a.status = '待處理'",
    ]
    params: list[object] = []
    if owner_filter:
        clauses.append("instr(lower(coalesce(ca.owner, '')), ?) > 0")
        params.append(owner_filter.casefold())
    if overdue_only:
        clauses.append(
            "trim(coalesce(ca.due_date, '')) <> '' "
            "AND ca.due_date < date('now', 'localtime')"
        )
    rows = conn.execute(
        f"""
        SELECT
            ca.id AS action_id,
            ca.action_type,
            ca.description,
            ca.owner,
            ca.due_date,
            ca.execution_status,
            ca.created_at AS action_created_at,
            a.id AS anomaly_id,
            a.anomaly_no AS ref_no,
            a.anomaly_date,
            a.status AS anomaly_status,
            s.supplier_name,
            a.problem_desc,
            a.responsible_person
        FROM case_actions AS ca
        JOIN anomalies AS a ON a.id = ca.anomaly_id
        JOIN suppliers AS s ON s.id = a.supplier_id
        WHERE {' AND '.join(clauses)}
        ORDER BY
            CASE
                WHEN trim(coalesce(ca.due_date, '')) <> ''
                     AND ca.due_date < date('now', 'localtime')
                THEN 0 ELSE 1
            END,
            CASE WHEN trim(coalesce(ca.due_date, '')) = '' THEN 1 ELSE 0 END,
            ca.due_date ASC,
            ca.created_at ASC,
            ca.rowid ASC
        """,
        tuple(params),
    ).fetchall()
    results: list[dict[str, Any]] = []
    today = conn.execute("SELECT date('now', 'localtime')").fetchone()[0]
    for row in rows:
        item = dict(row)
        due = str(item.get("due_date") or "").strip()
        item["overdue"] = bool(due and due < str(today))
        results.append(item)
    return results


def get_manager_operational_metrics(conn: sqlite3.Connection) -> dict[str, int]:
    """Compact operational counters for the manager summary header."""
    pending_rows = list_manager_summary_rows(conn, status="待處理")
    overdue_count = sum(1 for row in pending_rows if row.get("overdue"))
    open_action_count = sum(int(row.get("open_action_count") or 0) for row in pending_rows)
    root_cause_pending = sum(
        1
        for row in pending_rows
        if str(row.get("root_cause_status") or "")
        in {ANOMALY_ROOT_CAUSE_NOT_STARTED, ANOMALY_ROOT_CAUSE_UNDER_INVESTIGATION}
    )
    queue_count = len(list_operational_action_queue(conn))
    return {
        "pending_anomaly_count": len(pending_rows),
        "overdue_anomaly_count": overdue_count,
        "open_action_count": open_action_count,
        "root_cause_pending_count": root_cause_pending,
        "open_queue_action_count": queue_count,
    }
