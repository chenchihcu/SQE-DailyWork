"""Anomaly case-workbench service (Phase 2–5).

Single read/write boundary for analysis notes, root cause, corrective
actions, effectiveness verifications, attachments, Supplier 8D reviews,
audit log, and timeline/overview projections. UI, exporters, and the Markdown
snapshot consume only these functions — never raw per-table queries across
modules.
"""

from __future__ import annotations

from typing import Any

from database import connection as _connection
from database import repository


def _open_conn():
    return _connection.get_connection()


# ---- Analysis notes -----------------------------------------------------
def list_analysis_notes(anomaly_id: str) -> list[dict[str, Any]]:
    with _open_conn() as conn:
        return repository.list_anomaly_analysis_notes(conn, anomaly_id)


def create_analysis_note(
    *,
    anomaly_id: str,
    content: str,
    evidence_type: str = "UNKNOWN",
    author_name: str = "",
) -> str:
    with _open_conn() as conn:
        return repository.create_anomaly_analysis_note(
            conn,
            anomaly_id=anomaly_id,
            content=content,
            evidence_type=evidence_type,
            author_name=author_name,
        )


# ---- Root cause ---------------------------------------------------------
def get_root_cause(anomaly_id: str) -> dict[str, Any] | None:
    with _open_conn() as conn:
        return repository.get_anomaly_root_cause(conn, anomaly_id)


def save_root_cause(
    *,
    anomaly_id: str,
    statement: str = "",
    status: str = "尚未開始",
    validation_method: str = "",
    validation_evidence: str = "",
    conclusion_note: str = "",
    not_established_reason: str = "",
) -> str:
    with _open_conn() as conn:
        return repository.upsert_anomaly_root_cause(
            conn,
            anomaly_id=anomaly_id,
            statement=statement,
            status=status,
            validation_method=validation_method,
            validation_evidence=validation_evidence,
            conclusion_note=conclusion_note,
            not_established_reason=not_established_reason,
        )


# ---- Corrective actions -------------------------------------------------
def create_corrective_action(
    *,
    anomaly_id: str,
    description: str,
    responsible_party: str = "",
    target_date: str = "",
    effectiveness_verification_required: bool = False,
    notes: str = "",
) -> str:
    with _open_conn() as conn:
        return repository.create_corrective_action(
            conn,
            anomaly_id=anomaly_id,
            description=description,
            responsible_party=responsible_party,
            target_date=target_date,
            effectiveness_verification_required=effectiveness_verification_required,
            notes=notes,
        )


def list_corrective_actions(anomaly_id: str) -> list[dict[str, Any]]:
    with _open_conn() as conn:
        return repository.list_corrective_actions(conn, anomaly_id)


def complete_corrective_action(
    *,
    corrective_action_id: str,
    implementation_evidence: str = "",
) -> None:
    with _open_conn() as conn:
        repository.complete_corrective_action(
            conn,
            corrective_action_id,
            implementation_evidence=implementation_evidence,
        )


def change_corrective_action_status(
    corrective_action_id: str, status: str
) -> None:
    with _open_conn() as conn:
        repository.change_corrective_action_status(
            conn, corrective_action_id, status
        )


# ---- Effectiveness verifications ---------------------------------------
def create_effectiveness_verification(
    *,
    corrective_action_id: str,
    method: str = "",
    acceptance_criteria: str = "",
    period_sample: str = "",
    result: str = "待驗證",
    evidence: str = "",
    conclusion: str = "",
    verified_by: str = "",
    verified_date: str | None = None,
) -> str:
    with _open_conn() as conn:
        return repository.create_effectiveness_verification(
            conn,
            corrective_action_id=corrective_action_id,
            method=method,
            acceptance_criteria=acceptance_criteria,
            period_sample=period_sample,
            result=result,
            evidence=evidence,
            conclusion=conclusion,
            verified_by=verified_by,
            verified_date=verified_date,
        )


def list_effectiveness_verifications(
    corrective_action_id: str,
) -> list[dict[str, Any]]:
    with _open_conn() as conn:
        return repository.list_effectiveness_verifications(
            conn, corrective_action_id
        )


# ---- Attachments --------------------------------------------------------
def create_attachment(
    *,
    anomaly_id: str,
    file_name: str,
    stored_name: str = "",
    category: str = "其他",
    description: str = "",
    file_size: int = 0,
    revision: str = "",
    related_ca_id: str | None = None,
) -> str:
    with _open_conn() as conn:
        return repository.create_anomaly_attachment(
            conn,
            anomaly_id=anomaly_id,
            file_name=file_name,
            stored_name=stored_name,
            category=category,
            description=description,
            file_size=file_size,
            revision=revision,
            related_ca_id=related_ca_id,
        )


def list_attachments(anomaly_id: str) -> list[dict[str, Any]]:
    with _open_conn() as conn:
        return repository.list_anomaly_attachments(conn, anomaly_id)


# ---- Supplier 8D --------------------------------------------------------
def create_eight_d_review(
    *,
    anomaly_id: str,
    revision: str,
    review_status: str = "需補充證據",
    review_comment: str = "",
    attachment_id: str | None = None,
    review_date: str | None = None,
) -> str:
    with _open_conn() as conn:
        return repository.create_anomaly_eight_d_review(
            conn,
            anomaly_id=anomaly_id,
            revision=revision,
            review_status=review_status,
            review_comment=review_comment,
            attachment_id=attachment_id,
            review_date=review_date,
        )


def list_eight_d_reviews(anomaly_id: str) -> list[dict[str, Any]]:
    with _open_conn() as conn:
        return repository.list_anomaly_eight_d_reviews(conn, anomaly_id)


# ---- Audit / timeline / overview ---------------------------------------
def append_audit_log(
    *,
    anomaly_id: str,
    action: str,
    before_value: str = "",
    after_value: str = "",
    actor_name: str = "",
) -> str:
    with _open_conn() as conn:
        return repository.append_anomaly_audit_log(
            conn,
            anomaly_id=anomaly_id,
            action=action,
            before_value=before_value,
            after_value=after_value,
            actor_name=actor_name,
        )


def list_audit_logs(anomaly_id: str) -> list[dict[str, Any]]:
    with _open_conn() as conn:
        return repository.list_anomaly_audit_logs(conn, anomaly_id)


# Convenience wrappers that bundle a domain write with an audit log entry so
# the timeline projects the change without each caller needing to know the
# canonical action vocabulary. They are the recommended write boundary for the
# UI workbench dialogs (8D review, manual audit, effectiveness verification).
def create_eight_d_review_with_audit(
    *,
    anomaly_id: str,
    revision: str,
    review_status: str = "需補充證據",
    review_comment: str = "",
    attachment_id: str | None = None,
    review_date: str | None = None,
    actor_name: str = "",
) -> tuple[str, str]:
    """Create a Supplier 8D review row and append a matching audit entry.

    Returns ``(review_id, audit_log_id)``.
    """
    with _open_conn() as conn:
        review_id = repository.create_anomaly_eight_d_review(
            conn,
            anomaly_id=anomaly_id,
            revision=revision,
            review_status=review_status,
            review_comment=review_comment,
            attachment_id=attachment_id,
            review_date=review_date,
        )
        summary = f"{revision} → {review_status}"
        if review_comment:
            summary = f"{summary}（{review_comment}）"
        audit_id = repository.append_anomaly_audit_log(
            conn,
            anomaly_id=anomaly_id,
            action="EIGHT_D_REVIEWED",
            before_value="",
            after_value=summary,
            actor_name=actor_name,
        )
    return review_id, audit_id


def append_manual_audit(
    *,
    anomaly_id: str,
    action: str,
    after_value: str,
    actor_name: str = "",
) -> str:
    """Append a free-form audit entry authored from the UI workbench.

    Use sparingly: most state transitions should go through the dedicated
    repository functions so timestamps stay consistent.
    """
    with _open_conn() as conn:
        return repository.append_anomaly_audit_log(
            conn,
            anomaly_id=anomaly_id,
            action=action,
            before_value="",
            after_value=after_value,
            actor_name=actor_name,
        )


def record_verification_with_audit(
    *,
    corrective_action_id: str,
    method: str = "",
    acceptance_criteria: str = "",
    period_sample: str = "",
    result: str = "待驗證",
    evidence: str = "",
    conclusion: str = "",
    verified_by: str = "",
    verified_date: str | None = None,
    actor_name: str = "",
) -> tuple[str, str]:
    """Create an effectiveness verification and append a matching audit entry.

    Returns ``(verification_id, audit_log_id)``.
    """
    with _open_conn() as conn:
        ca = repository.get_corrective_action(conn, corrective_action_id)
        if ca is None:
            raise ValueError("Corrective action not found")
        verification_id = repository.create_effectiveness_verification(
            conn,
            corrective_action_id=corrective_action_id,
            method=method,
            acceptance_criteria=acceptance_criteria,
            period_sample=period_sample,
            result=result,
            evidence=evidence,
            conclusion=conclusion,
            verified_by=verified_by,
            verified_date=verified_date,
        )
        summary = f"驗證結果：{result}"
        if conclusion:
            summary = f"{summary}（{conclusion}）"
        audit_id = repository.append_anomaly_audit_log(
            conn,
            anomaly_id=str(ca.get("anomaly_id") or ""),
            action="EFFECTIVENESS_VERIFIED",
            before_value="",
            after_value=summary,
            actor_name=actor_name or verified_by,
        )
    return verification_id, audit_id


def record_ca_completion_with_audit(
    *,
    corrective_action_id: str,
    implementation_evidence: str = "",
    actor_name: str = "",
) -> str:
    """Mark a corrective action as completed and append a matching audit entry."""
    with _open_conn() as conn:
        ca = repository.get_corrective_action(conn, corrective_action_id)
        if ca is None:
            raise ValueError("Corrective action not found")
        repository.complete_corrective_action(
            conn,
            corrective_action_id,
            implementation_evidence=implementation_evidence,
        )
        next_ca = repository.get_corrective_action(conn, corrective_action_id)
        audit_id = repository.append_anomaly_audit_log(
            conn,
            anomaly_id=str(ca.get("anomaly_id") or ""),
            action="CA_COMPLETED",
            before_value=str(ca.get("status") or ""),
            after_value=str((next_ca or {}).get("status") or ""),
            actor_name=actor_name,
        )
    return audit_id


def record_ca_status_change_with_audit(
    *,
    corrective_action_id: str,
    status: str,
    actor_name: str = "",
) -> str:
    """Change a corrective action's status and append a matching audit entry."""
    with _open_conn() as conn:
        ca = repository.get_corrective_action(conn, corrective_action_id)
        if ca is None:
            raise ValueError("Corrective action not found")
        repository.change_corrective_action_status(
            conn, corrective_action_id, status
        )
        audit_id = repository.append_anomaly_audit_log(
            conn,
            anomaly_id=str(ca.get("anomaly_id") or ""),
            action="CA_STATUS_CHANGED",
            before_value=str(ca.get("status") or ""),
            after_value=status,
            actor_name=actor_name,
        )
    return audit_id


def list_timeline(anomaly_id: str) -> list[dict[str, Any]]:
    with _open_conn() as conn:
        return repository.list_anomaly_timeline(conn, anomaly_id)


def get_overview_card(anomaly_id: str) -> dict[str, Any]:
    with _open_conn() as conn:
        return repository.get_anomaly_overview_card(conn, anomaly_id)
