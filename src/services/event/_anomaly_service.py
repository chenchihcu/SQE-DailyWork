"""Anomaly CRUD — create, read, update, close, reopen, link to visit."""

from __future__ import annotations

import logging
from datetime import date

from database import connection as _connection
from database import repository
from database.repo_helpers import (
    ANOMALY_AUDIT_CASE_CLOSED,
    ANOMALY_AUDIT_CASE_REOPENED,
)

from services.appearance_preferences_service import load_application_preferences
from services.anomaly_category_preset_service import is_valid_category
from services.anomaly_trace_contract import normalize_anomaly_source
from services.anomaly_trace_validator import (
    build_trace_patterns,
    validate_anomaly_trace_payload,
)
from services.process_keyword_codec import validate_process_keywords
from services.repeat_issue_service import refresh_repeat_links_for_suppliers

from ._anomaly_folder import relocate_anomaly_folder
from ._anomaly_markdown import sync_anomaly_markdown_by_id, write_anomaly_markdown
from ._helpers import (
    _require_product_id,
    _require_supplier_record,
    _resolve_product_name,
)

logger = logging.getLogger(__name__)


def _resolve_process_keywords(payload: dict) -> str:
    if "process_keywords" not in payload:
        return ""
    return validate_process_keywords(payload.get("process_keywords", ""))


def _validate_anomaly_category(payload: dict) -> None:
    category = str(payload.get("category") or "").strip()
    if category and not is_valid_category(category):
        raise ValueError("異常類別不在辭庫中，請選擇有效選項。")


def _resolve_trace_fields(
    payload: dict,
    *,
    allow_legacy_blank_source: bool = False,
) -> dict[str, str]:
    patterns = build_trace_patterns(load_application_preferences())
    return validate_anomaly_trace_payload(
        anomaly_source=payload.get("anomaly_source", ""),
        supplier_id=payload.get("supplier_id", ""),
        payload=payload,
        patterns=patterns,
        allow_legacy_blank_source=allow_legacy_blank_source,
    )


class AnomalyNumberResult(str):
    """Backward-compatible anomaly number carrying post-commit warnings."""

    warnings: list[str]

    def __new__(cls, value: str, warnings: list[str]):
        instance = str.__new__(cls, value)
        instance.warnings = list(warnings)
        return instance


def _post_commit_warning(action: str, exc: Exception) -> str:
    return (
        f"資料庫已完成{action}，但異常 Markdown／資料夾快照同步失敗：{exc}。"
        "請勿重複執行主要動作；可稍後重新同步快照。"
    )


def _write_snapshot_with_warning(detail: dict, *, action: str) -> list[str]:
    try:
        write_anomaly_markdown(detail)
    except Exception as exc:
        logger.exception("異常資料已提交，但快照同步失敗")
        return [_post_commit_warning(action, exc)]
    return []


def _anomaly_write_fields(
    payload: dict,
    *,
    anomaly_date: str,
    supplier_id: str,
    problem_desc: str,
    product_id: str,
    product_name: str,
    anomaly_source: str,
    trace_fields: dict[str, str],
) -> dict:
    return {
        "anomaly_date": anomaly_date,
        "supplier_id": supplier_id,
        "problem_desc": problem_desc,
        "category": payload.get("category", ""),
        "product_lot_no": payload.get("product_lot_no", ""),
        "product_id": product_id,
        "product_name": product_name,
        "anomaly_source": anomaly_source,
        "material_receipt_no": trace_fields["material_receipt_no"],
        "internal_work_order_no": trace_fields["internal_work_order_no"],
        "outsource_work_order": trace_fields["outsource_work_order"],
        "outsource_receipt_no": trace_fields["outsource_receipt_no"],
        "batch_qty": payload.get("batch_qty", 0),
        "pending_items": payload.get("pending_items", ""),
        "responsible_person": payload.get("responsible_person", ""),
        "due_date": payload.get("due_date", ""),
        "rc_supplier_inventory": payload.get("rc_supplier_inventory", "unconfirmed"),
        "rc_supplier_wip": payload.get("rc_supplier_wip", "unconfirmed"),
        "rc_in_transit": payload.get("rc_in_transit", "unconfirmed"),
        "rc_internal_inventory": payload.get("rc_internal_inventory", "unconfirmed"),
        "quality_report_required": payload.get("quality_report_required"),
        "process_keywords": _resolve_process_keywords(payload),
    }


def create_anomaly(payload: dict) -> str:
    problem_desc = (payload.get("problem_desc") or "").strip()
    if not problem_desc:
        raise ValueError("Problem description is required")
    _validate_anomaly_category(payload)

    supplier_id = (payload.get("supplier_id") or "").strip()
    product_id = _require_product_id(payload)
    anomaly_date = payload.get("anomaly_date") or date.today().isoformat()

    with _connection.get_connection() as conn:
        _require_supplier_record(conn, supplier_id, require_active=True)
        product_name = _resolve_product_name(
            conn,
            supplier_id=supplier_id,
            product_id=product_id,
            require_active=True,
        )
        trace_fields = _resolve_trace_fields(
            payload,
            allow_legacy_blank_source=not normalize_anomaly_source(
                payload.get("anomaly_source", "")
            ),
        )
        anomaly_no = repository.create_anomaly(
            conn,
            **_anomaly_write_fields(
                payload,
                anomaly_date=anomaly_date,
                supplier_id=supplier_id,
                problem_desc=problem_desc,
                product_id=product_id,
                product_name=product_name,
                anomaly_source=normalize_anomaly_source(payload.get("anomaly_source", "")),
                trace_fields=trace_fields,
            ),
        )
        row = conn.execute(
            "SELECT id FROM anomalies WHERE anomaly_no = ?", (anomaly_no,)
        ).fetchone()
        anomaly_id = str(row["id"]) if row else ""
        if anomaly_id:
            refresh_repeat_links_for_suppliers(conn, supplier_id)
        detail = repository.get_anomaly_detail(conn, anomaly_id) if anomaly_id else None
    if detail is None:
        raise ValueError("Created anomaly could not be loaded")
    warnings = _write_snapshot_with_warning(detail, action="新增")
    return AnomalyNumberResult(anomaly_no, warnings)


def create_anomaly_with_visit_link(payload: dict) -> dict:
    problem_desc = (payload.get("problem_desc") or "").strip()
    if not problem_desc:
        raise ValueError("Problem description is required")
    _validate_anomaly_category(payload)

    supplier_id = (payload.get("supplier_id") or "").strip()
    product_id = _require_product_id(payload)
    anomaly_date = payload.get("anomaly_date") or date.today().isoformat()
    visit_id = (payload.get("visit_id") or "").strip() or None
    sync_visit = bool(payload.get("sync_visit", False))
    visit_summary = payload.get("visit_summary", "")

    with _connection.get_connection() as conn:
        _require_supplier_record(conn, supplier_id, require_active=True)
        product_name = _resolve_product_name(
            conn,
            supplier_id=supplier_id,
            product_id=product_id,
            require_active=True,
        )
        trace_fields = _resolve_trace_fields(
            payload,
            allow_legacy_blank_source=not normalize_anomaly_source(
                payload.get("anomaly_source", "")
            ),
        )
        result = repository.create_anomaly_with_visit_link(
            conn,
            **_anomaly_write_fields(
                payload,
                anomaly_date=anomaly_date,
                supplier_id=supplier_id,
                problem_desc=problem_desc,
                product_id=product_id,
                product_name=product_name,
                anomaly_source=normalize_anomaly_source(payload.get("anomaly_source", "")),
                trace_fields=trace_fields,
            ),
            visit_id=visit_id,
            sync_visit=sync_visit,
            visit_summary=visit_summary,
            anomaly_no=payload.get("anomaly_no"),
            source_defect_no=payload.get("source_defect_no", ""),
        )
        detail = repository.get_anomaly_detail(
            conn, str(result.get("anomaly_id") or "")
        )
        if detail:
            refresh_repeat_links_for_suppliers(
                conn,
                str(detail.get("supplier_id") or supplier_id),
            )
    if detail is None:
        raise ValueError("Created anomaly could not be loaded")
    result["warnings"] = _write_snapshot_with_warning(detail, action="新增")
    return result


def get_anomaly_detail(anomaly_id: str) -> dict:
    if not (anomaly_id or "").strip():
        raise ValueError("Anomaly id is required")
    with _connection.get_connection() as conn:
        row = repository.get_anomaly_detail(conn, anomaly_id)
    if row is None:
        raise ValueError("Anomaly not found")
    return row


def update_anomaly(anomaly_id: str, payload: dict) -> dict:
    anomaly_key = (anomaly_id or "").strip()
    if not anomaly_key:
        raise ValueError("Anomaly id is required")

    supplier_id = (payload.get("supplier_id") or "").strip()
    product_id = _require_product_id(payload)
    anomaly_date = payload.get("anomaly_date") or date.today().isoformat()
    problem_desc = (payload.get("problem_desc") or "").strip()
    if not problem_desc:
        raise ValueError("Problem description is required")
    _validate_anomaly_category(payload)

    with _connection.get_connection() as conn:
        existing = repository.get_anomaly_detail(conn, anomaly_key)
        if existing is None:
            raise ValueError("Anomaly not found")
        _require_supplier_record(conn, supplier_id, require_active=False)
        product_name = _resolve_product_name(
            conn,
            supplier_id=supplier_id,
            product_id=product_id,
        )
        existing_source = normalize_anomaly_source(existing.get("anomaly_source", ""))
        requested_source = normalize_anomaly_source(payload.get("anomaly_source", ""))
        allow_legacy_blank_source = not requested_source and not existing_source
        trace_fields = _resolve_trace_fields(
            payload,
            allow_legacy_blank_source=allow_legacy_blank_source,
        )
        repository.update_anomaly(
            conn,
            anomaly_id=anomaly_key,
            **_anomaly_write_fields(
                payload,
                anomaly_date=anomaly_date,
                supplier_id=supplier_id,
                problem_desc=problem_desc,
                product_id=product_id,
                product_name=product_name,
                anomaly_source=requested_source or existing_source,
                trace_fields=trace_fields,
            ),
            anomaly_no=payload.get("anomaly_no"),
        )
        refresh_repeat_links_for_suppliers(
            conn,
            str(existing.get("supplier_id") or ""),
            supplier_id,
        )
        conn.commit()
        detail = repository.get_anomaly_detail(conn, anomaly_key)
    if detail is None:
        raise ValueError("Updated anomaly could not be loaded")
    warnings: list[str] = []
    try:
        relocate_anomaly_folder(
            old_supplier_name=str(existing.get("supplier_name") or ""),
            old_anomaly_no=str(existing.get("anomaly_no") or ""),
            new_supplier_name=str(detail.get("supplier_name") or ""),
            new_anomaly_no=str(detail.get("anomaly_no") or ""),
        )
    except Exception as exc:
        logger.exception("異常資料已更新，但資料夾重新定位失敗")
        warnings.append(_post_commit_warning("更新", exc))
    warnings.extend(_write_snapshot_with_warning(detail, action="更新"))
    return {"anomaly_id": anomaly_key, "warnings": warnings}


def update_anomaly_link(anomaly_id: str, visit_id: str | None) -> dict:
    """Manually update the visit association for an existing anomaly."""
    if not (anomaly_id or "").strip():
        raise ValueError("Anomaly id is required")
    with _connection.get_connection() as conn:
        repository.update_anomaly_link(conn, anomaly_id, visit_id)
        conn.commit()
        detail = repository.get_anomaly_detail(conn, anomaly_id)
    if detail is None:
        raise ValueError("Updated anomaly could not be loaded")
    warnings = _write_snapshot_with_warning(detail, action="更新連結")
    return {"anomaly_id": anomaly_id, "warnings": warnings}


def delete_anomaly(anomaly_id: str) -> None:
    anomaly_key = (anomaly_id or "").strip()
    if not anomaly_key:
        raise ValueError("Anomaly id is required")
    with _connection.get_connection() as conn:
        repository.delete_anomaly(conn, anomaly_key)


def preview_anomaly_no(anomaly_date: str | None = None) -> str:
    target_date = anomaly_date or date.today().isoformat()
    with _connection.get_connection() as conn:
        return repository.preview_anomaly_no(conn, target_date)


def get_latest_visit_for_supplier_on_date(
    supplier_id: str, visit_date: str
) -> dict | None:
    normalized_supplier = (supplier_id or "").strip()
    normalized_date = (visit_date or "").strip()
    if not normalized_supplier or not normalized_date:
        return None
    with _connection.get_connection() as conn:
        return repository.get_latest_visit_for_supplier_on_date(
            conn,
            supplier_id=normalized_supplier,
            visit_date=normalized_date,
        )


def close_anomaly(
    anomaly_id: str,
    improvement_desc: str,
    *,
    closed_by: str | None = None,
    closed_at: str | None = None,
    actor_name: str | None = None,
) -> dict:
    if not (anomaly_id or "").strip():
        raise ValueError("Anomaly id is required")
    text = (improvement_desc or "").strip()
    if not text:
        raise ValueError("Improvement description is required")
    closer = (closed_by or actor_name or "").strip()
    with _connection.get_connection() as conn:
        repository.close_anomaly(
            conn,
            anomaly_id=anomaly_id,
            improvement_desc=improvement_desc,
            closed_by=closer,
            closed_at=closed_at,
            _commit=False,
        )
        repository.append_anomaly_audit_log(
            conn,
            anomaly_id=anomaly_id,
            action=ANOMALY_AUDIT_CASE_CLOSED,
            after_value=text[:240],
            actor_name=closer,
            _commit=False,
        )
        conn.commit()
        detail = repository.get_anomaly_detail(conn, anomaly_id)
    if detail is None:
        raise ValueError("Closed anomaly could not be loaded")
    warnings = _write_snapshot_with_warning(detail, action="結案")
    return {"anomaly_id": anomaly_id, "warnings": warnings}


def update_anomaly_closed_at(anomaly_id: str, closed_at: str) -> dict:
    if not (anomaly_id or "").strip():
        raise ValueError("Anomaly id is required")
    with _connection.get_connection() as conn:
        repository.update_anomaly_closed_at(
            conn,
            anomaly_id=anomaly_id,
            closed_at=closed_at,
        )
        detail = repository.get_anomaly_detail(conn, anomaly_id)
    if detail is None:
        raise ValueError("Updated anomaly could not be loaded")
    warnings = _write_snapshot_with_warning(detail, action="更新結案日期")
    return {"anomaly_id": anomaly_id, "warnings": warnings}


def reopen_anomaly(
    anomaly_id: str,
    *,
    reopen_reason: str,
    actor_name: str | None = None,
) -> dict:
    if not (anomaly_id or "").strip():
        raise ValueError("Anomaly id is required")
    reason = (reopen_reason or "").strip()
    if not reason:
        raise ValueError("Reopen reason is required")
    actor = (actor_name or "").strip()
    with _connection.get_connection() as conn:
        before = repository.reopen_anomaly(conn, anomaly_id, _commit=False)
        closed_at = before.get("closed_at") or "—"
        improvement = str(before.get("improvement_desc") or "").strip()
        before_summary = f"closed_at={closed_at}"
        if improvement:
            before_summary = f"{before_summary}; improvement={improvement[:200]}"
        repository.append_anomaly_audit_log(
            conn,
            anomaly_id=anomaly_id,
            action=ANOMALY_AUDIT_CASE_REOPENED,
            before_value=before_summary[:240],
            after_value=reason[:240],
            actor_name=actor,
            _commit=False,
        )
        conn.commit()
        detail = repository.get_anomaly_detail(conn, anomaly_id)
    if detail is None:
        raise ValueError("Reopened anomaly could not be loaded")
    warnings = _write_snapshot_with_warning(detail, action="重新處理")
    return {"anomaly_id": anomaly_id, "warnings": warnings}


def resync_anomaly_snapshot(anomaly_id: str) -> dict:
    """Idempotently rebuild the derived Markdown snapshot for one anomaly."""
    path = sync_anomaly_markdown_by_id(anomaly_id)
    return {"anomaly_id": anomaly_id, "snapshot_path": str(path), "warnings": []}
