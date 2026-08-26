"""Single transactional service boundary for canonical case Actions."""

from __future__ import annotations

import json
from typing import Any

from database import connection as _connection
from database import repository
from database.repo_helpers import (
    ACTION_VERIFICATION_RESULTS,
    CASE_ACTION_EXECUTION_STATUSES,
    CASE_ACTION_OPEN_STATUSES,
    CASE_ACTION_STATUS_IN_PROGRESS,
    CASE_ACTION_STATUS_PLANNED,
    CASE_ACTION_TYPE_LABELS,
    CASE_ACTION_TYPE_NEXT_ACTION,
    CASE_ACTION_TYPES,
    CASE_ACTION_VERIFICATION_ELIGIBLE_TYPES,
)


def _open_conn():
    return _connection.get_connection()


def _audit_value(value: dict[str, Any] | None) -> str:
    if not value:
        return ""
    fields = (
        "id",
        "action_type",
        "description",
        "owner",
        "due_date",
        "execution_status",
        "verification_required",
        "implementation_evidence",
        "completion_note",
        "cancel_note",
        "verification_status",
    )
    payload = {name: value.get(name) for name in fields}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def list_case_actions(
    anomaly_id: str,
    *,
    action_types: tuple[str, ...] | None = None,
    include_completed: bool = True,
    include_cancelled: bool = True,
) -> list[dict[str, Any]]:
    if not str(anomaly_id or "").strip():
        return []
    with _open_conn() as conn:
        return repository.list_case_actions(
            conn,
            anomaly_id,
            action_types=action_types,
            include_completed=include_completed,
            include_cancelled=include_cancelled,
        )


def get_case_action(action_id: str) -> dict[str, Any] | None:
    with _open_conn() as conn:
        return repository.get_case_action(conn, action_id)


def get_current_case_action(anomaly_id: str) -> dict[str, Any] | None:
    with _open_conn() as conn:
        return repository.get_current_case_action(conn, anomaly_id)


def create_case_action(
    *,
    anomaly_id: str,
    action_type: str = CASE_ACTION_TYPE_NEXT_ACTION,
    description: str,
    owner: str = "",
    due_date: str = "",
    execution_status: str = CASE_ACTION_STATUS_PLANNED,
    verification_required: bool | None = None,
    notes: str = "",
    actor_name: str = "",
) -> str:
    """Create an Action and matching audit row in one transaction."""
    with _open_conn() as conn:
        action_id = repository.create_case_action(
            conn,
            anomaly_id=anomaly_id,
            action_type=action_type,
            description=description,
            owner=owner,
            due_date=due_date,
            execution_status=execution_status,
            verification_required=verification_required,
            notes=notes,
            _commit=False,
        )
        created = repository.get_case_action(conn, action_id)
        repository.append_anomaly_audit_log(
            conn,
            anomaly_id=anomaly_id,
            action="CASE_ACTION_CREATED",
            before_value="",
            after_value=_audit_value(created),
            actor_name=actor_name,
            _commit=False,
        )
    return action_id


def update_case_action(
    action_id: str,
    *,
    action_type: str | None = None,
    description: str | None = None,
    owner: str | None = None,
    due_date: str | None = None,
    execution_status: str | None = None,
    verification_required: bool | None = None,
    notes: str | None = None,
    actor_name: str = "",
) -> None:
    """Edit/advance an Action and append an atomic before/after audit row."""
    with _open_conn() as conn:
        before = repository.get_case_action(conn, action_id)
        if before is None:
            raise ValueError("Action not found")
        repository.update_case_action(
            conn,
            action_id,
            action_type=action_type,
            description=description,
            owner=owner,
            due_date=due_date,
            execution_status=execution_status,
            verification_required=verification_required,
            notes=notes,
            _commit=False,
        )
        after = repository.get_case_action(conn, action_id)
        repository.append_anomaly_audit_log(
            conn,
            anomaly_id=str(before["anomaly_id"]),
            action="CASE_ACTION_UPDATED",
            before_value=_audit_value(before),
            after_value=_audit_value(after),
            actor_name=actor_name,
            _commit=False,
        )


def start_case_action(action_id: str, *, actor_name: str = "") -> None:
    update_case_action(
        action_id,
        execution_status=CASE_ACTION_STATUS_IN_PROGRESS,
        actor_name=actor_name,
    )


def complete_case_action(
    action_id: str,
    *,
    implementation_evidence: str = "",
    completion_note: str = "",
    completed_at: str | None = None,
    actor_name: str = "",
) -> None:
    with _open_conn() as conn:
        before = repository.get_case_action(conn, action_id)
        if before is None:
            raise ValueError("Action not found")
        repository.complete_case_action(
            conn,
            action_id,
            implementation_evidence=implementation_evidence,
            completion_note=completion_note,
            completed_at=completed_at,
            _commit=False,
        )
        after = repository.get_case_action(conn, action_id)
        repository.append_anomaly_audit_log(
            conn,
            anomaly_id=str(before["anomaly_id"]),
            action="CASE_ACTION_COMPLETED",
            before_value=_audit_value(before),
            after_value=_audit_value(after),
            actor_name=actor_name,
            _commit=False,
        )


def cancel_case_action(
    action_id: str,
    *,
    cancel_note: str,
    cancelled_at: str | None = None,
    actor_name: str = "",
) -> None:
    with _open_conn() as conn:
        before = repository.get_case_action(conn, action_id)
        if before is None:
            raise ValueError("Action not found")
        repository.cancel_case_action(
            conn,
            action_id,
            cancel_note=cancel_note,
            cancelled_at=cancelled_at,
            _commit=False,
        )
        after = repository.get_case_action(conn, action_id)
        repository.append_anomaly_audit_log(
            conn,
            anomaly_id=str(before["anomaly_id"]),
            action="CASE_ACTION_CANCELLED",
            before_value=_audit_value(before),
            after_value=_audit_value(after),
            actor_name=actor_name,
            _commit=False,
        )


def record_action_verification(
    *,
    action_id: str,
    method: str,
    acceptance_criteria: str = "",
    period_sample: str = "",
    result: str = "待驗證",
    evidence: str = "",
    conclusion: str = "",
    verified_by: str = "",
    verified_date: str | None = None,
    actor_name: str = "",
) -> str:
    """Append verification without mutating Action execution status."""
    with _open_conn() as conn:
        action = repository.get_case_action(conn, action_id)
        if action is None:
            raise ValueError("Action not found")
        verification_id = repository.record_action_verification(
            conn,
            action_id=action_id,
            method=method,
            acceptance_criteria=acceptance_criteria,
            period_sample=period_sample,
            result=result,
            evidence=evidence,
            conclusion=conclusion,
            verified_by=verified_by,
            verified_date=verified_date,
            _commit=False,
        )
        after = repository.get_case_action(conn, action_id)
        repository.append_anomaly_audit_log(
            conn,
            anomaly_id=str(action["anomaly_id"]),
            action="ACTION_VERIFICATION_RECORDED",
            before_value=_audit_value(action),
            after_value=_audit_value(after),
            actor_name=actor_name or verified_by,
            _commit=False,
        )
    return verification_id


def list_action_verifications(action_id: str) -> list[dict[str, Any]]:
    with _open_conn() as conn:
        return repository.list_action_verifications(conn, action_id)


def is_anomaly_overdue(anomaly_id: str, *, today: str | None = None) -> bool:
    with _open_conn() as conn:
        return repository.is_case_action_overdue(conn, anomaly_id, today=today)


__all__ = [
    "ACTION_VERIFICATION_RESULTS",
    "CASE_ACTION_EXECUTION_STATUSES",
    "CASE_ACTION_OPEN_STATUSES",
    "CASE_ACTION_STATUS_IN_PROGRESS",
    "CASE_ACTION_STATUS_PLANNED",
    "CASE_ACTION_TYPE_LABELS",
    "CASE_ACTION_TYPE_NEXT_ACTION",
    "CASE_ACTION_TYPES",
    "CASE_ACTION_VERIFICATION_ELIGIBLE_TYPES",
    "cancel_case_action",
    "complete_case_action",
    "create_case_action",
    "get_case_action",
    "get_current_case_action",
    "is_anomaly_overdue",
    "list_action_verifications",
    "list_case_actions",
    "record_action_verification",
    "start_case_action",
    "update_case_action",
]
