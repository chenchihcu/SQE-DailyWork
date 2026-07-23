"""Anomaly CRUD — create, read, update, close, reopen, link to visit."""

from __future__ import annotations

import logging
from datetime import date

from database import connection as _connection
from database import repository

from ._anomaly_folder import relocate_anomaly_folder
from ._anomaly_markdown import sync_anomaly_markdown_by_id, write_anomaly_markdown
from ._helpers import (
    _require_product_id,
    _require_supplier_record,
    _resolve_product_name,
)

logger = logging.getLogger(__name__)


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


def create_anomaly(payload: dict) -> str:
    problem_desc = (payload.get("problem_desc") or "").strip()
    if not problem_desc:
        raise ValueError("Problem description is required")

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
        anomaly_no = repository.create_anomaly(
            conn,
            anomaly_date=anomaly_date,
            supplier_id=supplier_id,
            problem_desc=problem_desc,
            category=payload.get("category", ""),
            product_lot_no=payload.get("product_lot_no", ""),
            product_id=product_id,
            product_name=product_name,
            outsource_work_order=payload.get("outsource_work_order", ""),
            batch_qty=payload.get("batch_qty", 0),
            pending_items=payload.get("pending_items", ""),
            responsible_person=payload.get("responsible_person", ""),
            due_date=payload.get("due_date", ""),
            rc_supplier_inventory=payload.get("rc_supplier_inventory", "unconfirmed"),
            rc_supplier_wip=payload.get("rc_supplier_wip", "unconfirmed"),
            rc_in_transit=payload.get("rc_in_transit", "unconfirmed"),
            rc_internal_inventory=payload.get("rc_internal_inventory", "unconfirmed"),
            is_tech_transfer=bool(payload.get("is_tech_transfer", False)),
            quality_report_required=payload.get("quality_report_required"),
        )
        row = conn.execute(
            "SELECT id FROM anomalies WHERE anomaly_no = ?", (anomaly_no,)
        ).fetchone()
        detail = repository.get_anomaly_detail(conn, str(row["id"])) if row else None
    if detail is None:
        raise ValueError("Created anomaly could not be loaded")
    warnings = _write_snapshot_with_warning(detail, action="新增")
    return AnomalyNumberResult(anomaly_no, warnings)


def create_anomaly_with_visit_link(payload: dict) -> dict:
    problem_desc = (payload.get("problem_desc") or "").strip()
    if not problem_desc:
        raise ValueError("Problem description is required")

    supplier_id = (payload.get("supplier_id") or "").strip()
    product_id = _require_product_id(payload)
    anomaly_date = payload.get("anomaly_date") or date.today().isoformat()
    visit_id = (payload.get("visit_id") or "").strip() or None
    sync_visit = bool(payload.get("sync_visit", True))
    visit_summary = payload.get("visit_summary", "")

    with _connection.get_connection() as conn:
        _require_supplier_record(conn, supplier_id, require_active=True)
        product_name = _resolve_product_name(
            conn,
            supplier_id=supplier_id,
            product_id=product_id,
            require_active=True,
        )
        result = repository.create_anomaly_with_visit_link(
            conn,
            anomaly_date=anomaly_date,
            supplier_id=supplier_id,
            problem_desc=problem_desc,
            category=payload.get("category", ""),
            product_lot_no=payload.get("product_lot_no", ""),
            product_id=product_id,
            product_name=product_name,
            outsource_work_order=payload.get("outsource_work_order", ""),
            batch_qty=payload.get("batch_qty", 0),
            visit_id=visit_id,
            sync_visit=sync_visit,
            visit_summary=visit_summary,
            pending_items=payload.get("pending_items", ""),
            responsible_person=payload.get("responsible_person", ""),
            due_date=payload.get("due_date", ""),
            rc_supplier_inventory=payload.get("rc_supplier_inventory", "unconfirmed"),
            rc_supplier_wip=payload.get("rc_supplier_wip", "unconfirmed"),
            rc_in_transit=payload.get("rc_in_transit", "unconfirmed"),
            rc_internal_inventory=payload.get("rc_internal_inventory", "unconfirmed"),
            is_tech_transfer=bool(payload.get("is_tech_transfer", False)),
            quality_report_required=payload.get("quality_report_required"),
            anomaly_no=payload.get("anomaly_no"),
        )
        detail = repository.get_anomaly_detail(
            conn, str(result.get("anomaly_id") or "")
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
        repository.update_anomaly(
            conn,
            anomaly_id=anomaly_key,
            anomaly_date=anomaly_date,
            supplier_id=supplier_id,
            problem_desc=problem_desc,
            category=payload.get("category", ""),
            product_lot_no=payload.get("product_lot_no", ""),
            product_id=product_id,
            product_name=product_name,
            outsource_work_order=payload.get("outsource_work_order", ""),
            batch_qty=payload.get("batch_qty", 0),
            pending_items=payload.get("pending_items", ""),
            responsible_person=payload.get("responsible_person", ""),
            due_date=payload.get("due_date", ""),
            rc_supplier_inventory=payload.get("rc_supplier_inventory", "unconfirmed"),
            rc_supplier_wip=payload.get("rc_supplier_wip", "unconfirmed"),
            rc_in_transit=payload.get("rc_in_transit", "unconfirmed"),
            rc_internal_inventory=payload.get("rc_internal_inventory", "unconfirmed"),
            is_tech_transfer=bool(payload.get("is_tech_transfer", False)),
            quality_report_required=payload.get("quality_report_required"),
            anomaly_no=payload.get("anomaly_no"),
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


def get_latest_tech_transfer_for_supplier(supplier_id: str) -> dict | None:
    """查詢指定供應商最新一筆含技轉資料的訪廠紀錄，做為新增異常的「參考資料」。
    若查無技轉紀錄則回傳 None。"""
    normalized = (supplier_id or "").strip()
    if not normalized:
        return None
    with _connection.get_connection() as conn:
        return repository.get_latest_tech_transfer_for_supplier(conn, normalized)


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
    closed_at: str | None = None,
) -> dict:
    if not (anomaly_id or "").strip():
        raise ValueError("Anomaly id is required")
    text = (improvement_desc or "").strip()
    if not text:
        raise ValueError("Improvement description is required")
    with _connection.get_connection() as conn:
        repository.close_anomaly(
            conn,
            anomaly_id=anomaly_id,
            improvement_desc=improvement_desc,
            closed_at=closed_at,
        )
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


def reopen_anomaly(anomaly_id: str) -> dict:
    if not (anomaly_id or "").strip():
        raise ValueError("Anomaly id is required")
    with _connection.get_connection() as conn:
        repository.reopen_anomaly(conn, anomaly_id)
        detail = repository.get_anomaly_detail(conn, anomaly_id)
    if detail is None:
        raise ValueError("Reopened anomaly could not be loaded")
    warnings = _write_snapshot_with_warning(detail, action="重新處理")
    return {"anomaly_id": anomaly_id, "warnings": warnings}


def resync_anomaly_snapshot(anomaly_id: str) -> dict:
    """Idempotently rebuild the derived Markdown snapshot for one anomaly."""
    path = sync_anomaly_markdown_by_id(anomaly_id)
    return {"anomaly_id": anomaly_id, "snapshot_path": str(path), "warnings": []}
