"""Deprecated next-action compatibility adapter.

New application code must import ``_case_action_service``. These names remain
temporarily for external/test compatibility, but every operation delegates to
the canonical ``case_actions`` model and never reads or writes
``anomaly_actions``.
"""

from __future__ import annotations

from typing import Any

from services.event import _case_action_service


def list_actions(anomaly_id: str) -> list[dict[str, Any]]:
    """Return all actions for an anomaly, ordered by status then due date."""
    if not anomaly_id:
        return []
    return _case_action_service.list_case_actions(anomaly_id)


def get_current_action(anomaly_id: str) -> dict[str, Any] | None:
    """Return the most actionable open action for an anomaly."""
    if not anomaly_id:
        return None
    return _case_action_service.get_current_case_action(anomaly_id)


def create_action(
    *,
    anomaly_id: str,
    description: str,
    owner: str = "",
    due_date: str = "",
    actor_name: str = "",
) -> str:
    """Append a new next-action row to an anomaly and log it on the audit feed."""
    return _case_action_service.create_case_action(
        anomaly_id=anomaly_id,
        action_type="NEXT_ACTION",
        description=description,
        owner=owner,
        due_date=due_date,
        execution_status="執行中",
        verification_required=False,
        actor_name=actor_name,
    )


def update_action(
    action_id: str,
    *,
    description: str | None = None,
    owner: str | None = None,
    due_date: str | None = None,
) -> None:
    """Edit an open action's description / owner / due date."""
    _case_action_service.update_case_action(
        action_id,
        description=description,
        owner=owner,
        due_date=due_date,
    )


def complete_action(action_id: str, *, completion_note: str = "", actor_name: str = "") -> None:
    """Mark an action as 已完成 and append a matching audit log entry."""
    _case_action_service.complete_case_action(
        action_id,
        completion_note=completion_note,
        actor_name=actor_name,
    )


def cancel_action(action_id: str, *, cancel_note: str = "", actor_name: str = "") -> None:
    """Mark an action as 已取消 and append a matching audit log entry."""
    _case_action_service.cancel_case_action(
        action_id,
        cancel_note=cancel_note,
        actor_name=actor_name,
    )


def is_overdue(anomaly_id: str, *, today: str | None = None) -> bool:
    """Return True when an open anomaly has any overdue action."""
    return _case_action_service.is_anomaly_overdue(anomaly_id, today=today)


def build_anomaly_lifecycle_card(anomaly_id: str) -> dict[str, Any]:
    """Build a single read model for the current action + overdue flag.

    The card is the only object the UI / export should consume for the
    "Next Action" panel. It deliberately returns the legacy safe defaults
    so closed and pre-migration anomalies still render.
    """
    all_actions = _case_action_service.list_case_actions(anomaly_id)
    current = _case_action_service.get_current_case_action(anomaly_id)
    overdue = _case_action_service.is_anomaly_overdue(anomaly_id)
    return {
        "anomaly_id": anomaly_id,
        "status": "待處理",
        "current_action": current,
        "overdue": overdue,
        "completed_actions": sum(
            1 for a in all_actions if a.get("execution_status") == "已完成"
        ),
        "cancelled_actions": sum(
            1 for a in all_actions if a.get("execution_status") == "已取消"
        ),
        "legacy_pending_items": "",
        "legacy_responsible_person": "",
        "legacy_due_date": "",
    }
