"""Anomaly case-workbench service (Phase 2–5).

Single read/write boundary for analysis notes, root cause, attachments,
Supplier 8D reviews, audit log, and timeline/overview projections. Canonical
Action and verification writes live exclusively in ``_case_action_service``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4
from typing import Any

from database import connection as _connection
from database import repository
from database.repo_helpers import (
    ANOMALY_AUDIT_HYPOTHESIS_CREATED,
    ANOMALY_AUDIT_HYPOTHESIS_PROMOTED,
    ANOMALY_AUDIT_HYPOTHESIS_STATUS_CHANGED,
    ANOMALY_AUDIT_HYPOTHESIS_UPDATED,
)
from services import attachment_manager


logger = logging.getLogger(__name__)


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


# ---- Hypotheses ---------------------------------------------------------
def list_hypotheses(anomaly_id: str) -> list[dict[str, Any]]:
    with _open_conn() as conn:
        return repository.list_anomaly_hypotheses(conn, anomaly_id)


def create_hypothesis(
    *,
    anomaly_id: str,
    statement: str,
    status: str = "提案",
    evidence_type: str = "UNKNOWN",
    parent_hypothesis_id: str | None = None,
    linked_note_id: str | None = None,
    actor_name: str = "",
) -> str:
    with _open_conn() as conn:
        hypothesis_id = repository.create_anomaly_hypothesis(
            conn,
            anomaly_id=anomaly_id,
            statement=statement,
            status=status,
            evidence_type=evidence_type,
            parent_hypothesis_id=parent_hypothesis_id,
            linked_note_id=linked_note_id,
            _commit=False,
        )
        repository.append_anomaly_audit_log(
            conn,
            anomaly_id=anomaly_id,
            action=ANOMALY_AUDIT_HYPOTHESIS_CREATED,
            after_value=(statement or "")[:240],
            actor_name=actor_name,
            _commit=False,
        )
        conn.commit()
    return hypothesis_id


def update_hypothesis(
    *,
    anomaly_id: str,
    hypothesis_id: str,
    statement: str | None = None,
    status: str | None = None,
    evidence_type: str | None = None,
    parent_hypothesis_id: str | None = None,
    linked_note_id: str | None = None,
    actor_name: str = "",
) -> dict[str, Any]:
    with _open_conn() as conn:
        before = repository.get_anomaly_hypothesis(conn, hypothesis_id) or {}
        updated = repository.update_anomaly_hypothesis(
            conn,
            hypothesis_id=hypothesis_id,
            anomaly_id=anomaly_id,
            statement=statement,
            status=status,
            evidence_type=evidence_type,
            parent_hypothesis_id=parent_hypothesis_id,
            linked_note_id=linked_note_id,
            _commit=False,
        )
        if status is not None and status != before.get("status"):
            repository.append_anomaly_audit_log(
                conn,
                anomaly_id=anomaly_id,
                action=ANOMALY_AUDIT_HYPOTHESIS_STATUS_CHANGED,
                before_value=str(before.get("status") or ""),
                after_value=str(updated.get("status") or ""),
                actor_name=actor_name,
                _commit=False,
            )
        changed_fields: list[str] = []
        if statement is not None and (statement or "").strip() != str(
            before.get("statement") or ""
        ).strip():
            changed_fields.append("statement")
        if evidence_type is not None and str(evidence_type or "").strip() != str(
            before.get("evidence_type") or ""
        ).strip():
            changed_fields.append("evidence_type")
        if parent_hypothesis_id is not None:
            before_parent = str(before.get("parent_hypothesis_id") or "").strip() or None
            after_parent = str(updated.get("parent_hypothesis_id") or "").strip() or None
            if before_parent != after_parent:
                changed_fields.append("parent_hypothesis_id")
        if linked_note_id is not None:
            before_note = str(before.get("linked_note_id") or "").strip() or None
            after_note = str(updated.get("linked_note_id") or "").strip() or None
            if before_note != after_note:
                changed_fields.append("linked_note_id")
        if changed_fields:
            repository.append_anomaly_audit_log(
                conn,
                anomaly_id=anomaly_id,
                action=ANOMALY_AUDIT_HYPOTHESIS_UPDATED,
                before_value=",".join(changed_fields),
                after_value=str(updated.get("id") or hypothesis_id),
                actor_name=actor_name,
                _commit=False,
            )
        conn.commit()
    return updated


def promote_hypothesis_to_root_cause(
    *,
    anomaly_id: str,
    hypothesis_id: str,
    root_cause_status: str | None = None,
    actor_name: str = "",
) -> dict[str, Any]:
    with _open_conn() as conn:
        result = repository.promote_hypothesis_to_root_cause(
            conn,
            hypothesis_id=hypothesis_id,
            anomaly_id=anomaly_id,
            root_cause_status=root_cause_status,
            _commit=False,
        )
        repository.append_anomaly_audit_log(
            conn,
            anomaly_id=anomaly_id,
            action=ANOMALY_AUDIT_HYPOTHESIS_PROMOTED,
            after_value=str(result.get("root_cause_status") or ""),
            actor_name=actor_name,
            _commit=False,
        )
        conn.commit()
    _sync_markdown(anomaly_id)
    return result


def list_evidence_chain(anomaly_id: str) -> list[dict[str, Any]]:
    with _open_conn() as conn:
        return repository.list_anomaly_evidence_chain(conn, anomaly_id)


# ---- Attachments --------------------------------------------------------
def create_attachment(
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
) -> str:
    with _open_conn() as conn:
        attachment_id = repository.create_anomaly_attachment(
            conn,
            anomaly_id=anomaly_id,
            file_name=file_name,
            stored_name=stored_name,
            category=category,
            description=description,
            file_size=file_size,
            file_type=file_type,
            revision=revision,
            uploaded_by=uploaded_by,
            related_note_id=related_note_id,
            related_action_id=related_action_id,
            related_hypothesis_id=related_hypothesis_id,
            _commit=False,
        )
        repository.append_anomaly_audit_log(
            conn,
            anomaly_id=anomaly_id,
            action="ATTACHMENT_CREATED",
            after_value=file_name,
            actor_name=uploaded_by,
            _commit=False,
        )
        conn.commit()
    _sync_markdown(anomaly_id)
    return attachment_id


def import_attachment_from_file(
    *,
    anomaly_id: str,
    source_path: Path | str,
    category: str = "其他",
    description: str = "",
    revision: str = "",
    uploaded_by: str = "",
    related_note_id: str | None = None,
    related_action_id: str | None = None,
    related_hypothesis_id: str | None = None,
    target_name: str | None = None,
) -> str:
    """Copy one evidence file and register its metadata with compensation.

    Filesystem and SQLite cannot share one atomic transaction. The file is
    therefore removed again when metadata insertion fails, so callers never
    receive a failed write with a newly orphaned file.
    """
    stored_path = attachment_manager.import_single_attachment(
        anomaly_id, source_path, target_name
    )
    if stored_path is None:
        raise ValueError("Attachment file type or name is not allowed")
    try:
        file_size = stored_path.stat().st_size
        attachment_id = create_attachment(
            anomaly_id=anomaly_id,
            file_name=stored_path.name,
            stored_name=stored_path.name,
            category=category,
            description=description,
            file_size=file_size,
            file_type=attachment_manager.attachment_file_type(stored_path),
            revision=revision,
            uploaded_by=uploaded_by,
            related_note_id=related_note_id,
            related_action_id=related_action_id,
            related_hypothesis_id=related_hypothesis_id,
        )
        return attachment_id
    except Exception:
        attachment_manager.delete_anomaly_attachment(
            anomaly_id, stored_path.name
        )
        raise


def update_attachment(
    *,
    anomaly_id: str,
    attachment_id: str,
    category: str,
    description: str = "",
    revision: str = "",
    related_note_id: str | None = None,
    related_action_id: str | None = None,
    related_hypothesis_id: str | None = None,
    actor_name: str = "",
) -> dict[str, Any]:
    """Update metadata and links transactionally, without renaming bytes."""
    with _open_conn() as conn:
        before = next(
            (
                row
                for row in repository.list_anomaly_attachments(conn, anomaly_id)
                if str(row.get("id") or "") == str(attachment_id or "").strip()
            ),
            None,
        )
        if before is None:
            raise ValueError("Attachment not found")
        updated = repository.update_anomaly_attachment(
            conn,
            attachment_id=attachment_id,
            anomaly_id=anomaly_id,
            category=category,
            description=description,
            revision=revision,
            related_note_id=related_note_id,
            related_action_id=related_action_id,
            related_hypothesis_id=related_hypothesis_id,
            _commit=False,
        )
        repository.append_anomaly_audit_log(
            conn,
            anomaly_id=anomaly_id,
            action="ATTACHMENT_UPDATED",
            before_value=str(before.get("file_name") or ""),
            after_value=str(updated.get("file_name") or ""),
            actor_name=actor_name,
            _commit=False,
        )
        conn.commit()
    _sync_markdown(anomaly_id)
    return updated


def delete_attachment(
    *,
    anomaly_id: str,
    attachment_id: str,
    actor_name: str = "",
) -> dict[str, Any]:
    """Delete a registered attachment with same-folder filesystem staging."""
    staged_path: Path | None = None
    original_path: Path | None = None
    with _open_conn() as conn:
        row = next(
            (
                item
                for item in repository.list_anomaly_attachments(conn, anomaly_id)
                if str(item.get("id") or "") == str(attachment_id or "").strip()
            ),
            None,
        )
        if row is None:
            raise ValueError("Attachment not found")
        filename = str(row.get("stored_name") or row.get("file_name") or "").strip()
        if not filename:
            raise ValueError("Attachment has no storage identity")
        original_path = attachment_manager.stored_attachment_path(anomaly_id, filename)
        if original_path.is_file():
            staged_path = original_path.with_name(
                f".{original_path.name}.{uuid4().hex}.phase2r-delete"
            )
            original_path.replace(staged_path)
        try:
            deleted = repository.delete_anomaly_attachment_metadata(
                conn,
                attachment_id=attachment_id,
                anomaly_id=anomaly_id,
                _commit=False,
            )
            repository.append_anomaly_audit_log(
                conn,
                anomaly_id=anomaly_id,
                action="ATTACHMENT_DELETED",
                before_value=filename,
                after_value="",
                actor_name=actor_name,
                _commit=False,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            if staged_path is not None and staged_path.exists() and original_path is not None:
                staged_path.replace(original_path)
            raise

    warnings: list[str] = []
    if staged_path is not None:
        try:
            staged_path.unlink()
        except OSError as exc:
            warnings.append(f"無法清理暫存附件：{exc}")
            logger.error("Attachment delete staging cleanup failed: %s", staged_path)
    _sync_markdown(anomaly_id)
    return {
        "attachment_id": str(deleted.get("id") or attachment_id),
        "file_name": filename,
        "physical_deleted": staged_path is not None,
        "warnings": warnings,
    }


def list_attachments(anomaly_id: str) -> list[dict[str, Any]]:
    with _open_conn() as conn:
        metadata = repository.list_anomaly_attachments(conn, anomaly_id)

    # The database row is the canonical metadata record.  Existing versions
    # stored images plus captions.json without a row, so expose those files as
    # explicit legacy projections until the approved reconciliation migration
    # registers them.  This keeps the workbench read path compatible without
    # guessing category/link/author values.
    physical_files = attachment_manager.list_stored_attachment_files(anomaly_id)
    physical_names = {path.name for path in physical_files}
    by_stored_name = {
        str(row.get("stored_name") or row.get("file_name") or "").strip(): row
        for row in metadata
        if str(row.get("stored_name") or row.get("file_name") or "").strip()
    }
    captions = attachment_manager.get_anomaly_captions(anomaly_id)
    result: list[dict[str, Any]] = []
    for row in metadata:
        item = dict(row)
        stored_name = str(item.get("stored_name") or item.get("file_name") or "")
        item["storage_state"] = (
            "present"
            if stored_name and stored_name in physical_names
            else "missing"
        )
        item["legacy_physical"] = False
        result.append(item)

    for path in physical_files:
        if path.name in by_stored_name:
            continue
        try:
            file_size = path.stat().st_size
        except OSError:
            file_size = 0
        result.append(
            {
                "id": "",
                "anomaly_id": anomaly_id,
                "file_name": path.name,
                "stored_name": path.name,
                "category": "Other",
                "category_label": "其他",
                "description": captions.get(path.name, ""),
                "file_size": file_size,
                "file_type": attachment_manager.attachment_file_type(path),
                "revision": "",
                "uploaded_by": "",
                "related_ca_id": None,
                "related_note_id": None,
                "related_action_id": None,
                "uploaded_at": "",
                "storage_state": "present",
                "legacy_physical": True,
            }
        )
    result.sort(
        key=lambda row: (
            str(row.get("uploaded_at") or "9999-12-31 23:59:59"),
            str(row.get("file_name") or "").casefold(),
        )
    )
    return result


def list_attachment_notes(anomaly_id: str) -> list[dict[str, Any]]:
    return list_analysis_notes(anomaly_id)


def list_attachment_hypotheses(anomaly_id: str) -> list[dict[str, Any]]:
    return list_hypotheses(anomaly_id)


def list_attachment_actions(anomaly_id: str) -> list[dict[str, Any]]:
    with _open_conn() as conn:
        return repository.list_case_actions(conn, anomaly_id)


def _sync_markdown(anomaly_id: str) -> None:
    try:
        # Keep the existing adapter hook as the single patch/test boundary;
        # it also preserves the non-blocking derived-output contract.
        attachment_manager._sync_anomaly_markdown(anomaly_id)
    except Exception as exc:
        # Attachment mutation is authoritative; snapshot sync remains a
        # recoverable derived-output warning, matching existing contract.
        logger.warning("Attachment Markdown sync warning: %s", exc)


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


def list_timeline(anomaly_id: str) -> list[dict[str, Any]]:
    with _open_conn() as conn:
        return repository.list_anomaly_timeline(conn, anomaly_id)


def get_overview_card(anomaly_id: str) -> dict[str, Any]:
    with _open_conn() as conn:
        return repository.get_anomaly_overview_card(conn, anomaly_id)
