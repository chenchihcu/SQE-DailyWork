"""Anomaly next-action service.

Phase 1 service layer that wraps the ``anomaly_actions`` repository. It
exists as a single read/write boundary so the UI, exporters, and Markdown
snapshot only consume one canonical interface. The legacy flat columns
(``pending_items`` / ``responsible_person`` / ``due_date``) are kept on
``anomalies`` for backward compatibility; the new service treats them as
historical snapshots and supplements them with the actionable sub-table.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from database import repository
from database import connection as _connection


def _open_conn():
    return _connection.get_connection()


def list_actions(anomaly_id: str) -> list[dict[str, Any]]:
    """Return all actions for an anomaly, ordered by status then due date."""
    if not anomaly_id:
        return []
    with _open_conn() as conn:
        return repository.list_anomaly_actions(conn, anomaly_id)


def get_current_action(anomaly_id: str) -> dict[str, Any] | None:
    """Return the most actionable open action for an anomaly."""
    if not anomaly_id:
        return None
    with _open_conn() as conn:
        return repository.get_current_anomaly_action(conn, anomaly_id)


def create_action(
    *,
    anomaly_id: str,
    description: str,
    owner: str = "",
    due_date: str = "",
    actor_name: str = "",
) -> str:
    """Append a new next-action row to an anomaly and log it on the audit feed."""
    with _open_conn() as conn:
        action_id = repository.create_anomaly_action(
            conn,
            anomaly_id=anomaly_id,
            description=description,
            owner=owner,
            due_date=due_date,
        )
        summary = description
        if owner:
            summary = f"{summary}（{owner}）"
        if due_date:
            summary = f"{summary} → {due_date}"
        repository.append_anomaly_audit_log(
            conn,
            anomaly_id=anomaly_id,
            action="ACTION_CREATED",
            before_value="",
            after_value=summary,
            actor_name=actor_name,
        )
    return action_id


def update_action(
    action_id: str,
    *,
    description: str | None = None,
    owner: str | None = None,
    due_date: str | None = None,
) -> None:
    """Edit an open action's description / owner / due date."""
    with _open_conn() as conn:
        repository.update_anomaly_action(
            conn,
            action_id,
            description=description,
            owner=owner,
            due_date=due_date,
        )


def complete_action(action_id: str, *, completion_note: str = "", actor_name: str = "") -> None:
    """Mark an action as 已完成 and append a matching audit log entry."""
    with _open_conn() as conn:
        existing = repository.get_anomaly_action(conn, action_id)
        if existing is None:
            raise ValueError("Action not found")
        anomaly_id = str(existing.get("anomaly_id") or "")
        repository.complete_anomaly_action(
            conn,
            action_id,
            completion_note=completion_note,
        )
        repository.append_anomaly_audit_log(
            conn,
            anomaly_id=anomaly_id,
            action="ACTION_COMPLETED",
            before_value=str(existing.get("description") or ""),
            after_value=completion_note or "已完成",
            actor_name=actor_name,
        )


def cancel_action(action_id: str, *, cancel_note: str = "", actor_name: str = "") -> None:
    """Mark an action as 已取消 and append a matching audit log entry."""
    with _open_conn() as conn:
        existing = repository.get_anomaly_action(conn, action_id)
        if existing is None:
            raise ValueError("Action not found")
        anomaly_id = str(existing.get("anomaly_id") or "")
        repository.cancel_anomaly_action(
            conn,
            action_id,
            cancel_note=cancel_note,
        )
        repository.append_anomaly_audit_log(
            conn,
            anomaly_id=anomaly_id,
            action="ACTION_CANCELLED",
            before_value=str(existing.get("description") or ""),
            after_value=cancel_note or "已取消",
            actor_name=actor_name,
        )


def is_overdue(anomaly_id: str, *, today: str | None = None) -> bool:
    """Return True when an open anomaly has any overdue action."""
    with _open_conn() as conn:
        return repository.is_anomaly_overdue(conn, anomaly_id, today=today)


def build_anomaly_lifecycle_card(anomaly_id: str) -> dict[str, Any]:
    """Build a single read model for the current action + overdue flag.

    The card is the only object the UI / export should consume for the
    "Next Action" panel. It deliberately returns the legacy safe defaults
    so closed and pre-migration anomalies still render.
    """
    today_iso = date.today().isoformat()
    with _open_conn() as conn:
        detail = repository.get_anomaly_detail(conn, anomaly_id)
        if detail is None:
            return {
                "anomaly_id": anomaly_id,
                "status": "待處理",
                "current_action": None,
                "overdue": False,
                "completed_actions": 0,
                "cancelled_actions": 0,
                "legacy_pending_items": "",
                "legacy_responsible_person": "",
                "legacy_due_date": "",
            }
        all_actions = repository.list_anomaly_actions(conn, anomaly_id)
        current = repository.get_current_anomaly_action(conn, anomaly_id)
        overdue = repository.is_anomaly_overdue(conn, anomaly_id, today=today_iso)
    return {
        "anomaly_id": anomaly_id,
        "status": detail.get("status") or "待處理",
        "current_action": current,
        "overdue": overdue if detail.get("status") == "待處理" else False,
        "completed_actions": sum(
            1 for a in all_actions if a.get("status") == "已完成"
        ),
        "cancelled_actions": sum(
            1 for a in all_actions if a.get("status") == "已取消"
        ),
        "legacy_pending_items": detail.get("pending_items") or "",
        "legacy_responsible_person": detail.get("responsible_person") or "",
        "legacy_due_date": detail.get("due_date") or "",
    }
