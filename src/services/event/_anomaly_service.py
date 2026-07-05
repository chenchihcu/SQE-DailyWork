"""Anomaly CRUD — create, read, update, close, reopen, link to visit."""

from __future__ import annotations

import logging
from datetime import date

logger = logging.getLogger(__name__)

from database import connection as _connection
from database import repository

from ._helpers import _require_product_id, _require_supplier_record, _resolve_product_name


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
        return repository.create_anomaly(
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
        )


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
        return repository.create_anomaly_with_visit_link(
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
            anomaly_no=payload.get("anomaly_no"),
        )


def get_anomaly_detail(anomaly_id: str) -> dict:
    if not (anomaly_id or "").strip():
        raise ValueError("Anomaly id is required")
    with _connection.get_connection() as conn:
        row = repository.get_anomaly_detail(conn, anomaly_id)
    if row is None:
        raise ValueError("Anomaly not found")
    return row


def update_anomaly(anomaly_id: str, payload: dict) -> None:
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
            anomaly_no=payload.get("anomaly_no"),
        )
        conn.commit()


def update_anomaly_link(anomaly_id: str, visit_id: str | None) -> None:
    """Manually update the visit association for an existing anomaly."""
    if not (anomaly_id or "").strip():
        raise ValueError("Anomaly id is required")
    with _connection.get_connection() as conn:
        repository.update_anomaly_link(conn, anomaly_id, visit_id)
        conn.commit()


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
    closed_by: str = "",
    root_cause_category: str = "",
    closed_at: str | None = None,
) -> None:
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
            closed_by=closed_by,
            root_cause_category=root_cause_category,
            closed_at=closed_at,
        )


def update_anomaly_closed_at(anomaly_id: str, closed_at: str) -> None:
    if not (anomaly_id or "").strip():
        raise ValueError("Anomaly id is required")
    with _connection.get_connection() as conn:
        repository.update_anomaly_closed_at(
            conn,
            anomaly_id=anomaly_id,
            closed_at=closed_at,
        )


def reopen_anomaly(anomaly_id: str) -> None:
    if not (anomaly_id or "").strip():
        raise ValueError("Anomaly id is required")
    with _connection.get_connection() as conn:
        repository.reopen_anomaly(conn, anomaly_id)
