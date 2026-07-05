"""Visit CRUD, defect notes, and note-to-anomaly confirmation."""

from __future__ import annotations

import logging
from datetime import date

logger = logging.getLogger(__name__)

from database import connection as _connection
from database import repository

from ._helpers import _require_product_id, _require_supplier_record, _resolve_product_name


def _visit_note_has_content(notes: object) -> bool:
    for note in notes or []:
        item = dict(note or {})
        if any(
            str(item.get(key) or "").strip()
            for key in ("defect_desc", "defect", "description", "improvement_desc", "note", "remark")
        ):
            return True
    return False


def _has_visit_record_content(payload: dict) -> bool:
    if (payload.get("product_id") or "").strip():
        return True
    for section in payload.get("product_sections") or []:
        item = dict(section or {})
        if any(
            (
                (item.get("product_id") or "").strip(),
                (item.get("product_name") or "").strip(),
                (item.get("time_slot") or "").strip(),
                (item.get("work_order_no") or "").strip(),
                (item.get("summary") or "").strip(),
                str(item.get("production_qty") or "").strip() not in {"", "0"},
                _visit_note_has_content(item.get("defect_notes")),
            )
        ):
            return True
    if _visit_note_has_content(payload.get("defect_notes")):
        return True
    return False


def _validate_visit_product_scope(
    conn,
    *,
    supplier_id: str,
    payload: dict,
    require_active: bool,
) -> None:
    product_id = (payload.get("product_id") or "").strip()
    if product_id:
        _resolve_product_name(
            conn,
            supplier_id=supplier_id,
            product_id=product_id,
            require_active=require_active,
        )
    for section in payload.get("product_sections") or []:
        section_id = (dict(section or {}).get("product_id") or "").strip()
        if not section_id:
            continue
        _resolve_product_name(
            conn,
            supplier_id=supplier_id,
            product_id=section_id,
            require_active=require_active,
        )


def create_visit(payload: dict) -> str:
    supplier_id = (payload.get("supplier_id") or "").strip()
    if not _has_visit_record_content(payload):
        _require_product_id(payload)
    product_id = (payload.get("product_id") or "").strip()
    visit_date = payload.get("visit_date") or date.today().isoformat()
    with _connection.get_connection() as conn:
        _require_supplier_record(conn, supplier_id, require_active=True)
        _validate_visit_product_scope(
            conn,
            supplier_id=supplier_id,
            payload=payload,
            require_active=True,
        )
        product_name = (
            _resolve_product_name(
                conn,
                supplier_id=supplier_id,
                product_id=product_id,
                require_active=True,
            )
            if product_id
            else ""
        )
        return repository.create_visit(
            conn,
            visit_date=visit_date,
            supplier_id=supplier_id,
            product_id=product_id,
            product_name=product_name,
            visitor_name=payload.get("visitor_name", ""),
            summary=payload.get("summary", ""),
            work_order_no=payload.get("work_order_no", ""),
            production_qty=payload.get("production_qty", 0),
            product_sections=payload.get("product_sections"),
            defect_notes=payload.get("defect_notes"),
            tech_transfer=bool(payload.get("tech_transfer", False)),
            tech_transfer_doc=bool(payload.get("tech_transfer_doc", False)),
            carrier_requirement=bool(payload.get("carrier_requirement", False)),
            dispensing_process=bool(payload.get("dispensing_process", False)),
            functional_test=bool(payload.get("functional_test", False)),
            packaging_requirement=bool(payload.get("packaging_requirement", False)),
            tech_transfer_states=payload.get("tech_transfer_states"),
        )


def update_visit(visit_id: str, payload: dict) -> None:
    visit_key = (visit_id or "").strip()
    if not visit_key:
        raise ValueError("Visit id is required")

    supplier_id = (payload.get("supplier_id") or "").strip()
    if not _has_visit_record_content(payload):
        _require_product_id(payload)
    product_id = (payload.get("product_id") or "").strip()
    visit_date = payload.get("visit_date") or date.today().isoformat()

    with _connection.get_connection() as conn:
        _require_supplier_record(conn, supplier_id, require_active=False)
        _validate_visit_product_scope(
            conn,
            supplier_id=supplier_id,
            payload=payload,
            require_active=False,
        )
        product_name = (
            _resolve_product_name(
                conn,
                supplier_id=supplier_id,
                product_id=product_id,
            )
            if product_id
            else ""
        )
        repository.update_visit(
            conn,
            visit_id=visit_key,
            visit_date=visit_date,
            supplier_id=supplier_id,
            product_id=product_id,
            product_name=product_name,
            visitor_name=payload.get("visitor_name", ""),
            summary=payload.get("summary", ""),
            work_order_no=payload.get("work_order_no", ""),
            production_qty=payload.get("production_qty", 0),
            product_sections=payload.get("product_sections"),
            defect_notes=payload.get("defect_notes"),
            tech_transfer=bool(payload.get("tech_transfer", False)),
            tech_transfer_doc=bool(payload.get("tech_transfer_doc", False)),
            carrier_requirement=bool(payload.get("carrier_requirement", False)),
            dispensing_process=bool(payload.get("dispensing_process", False)),
            functional_test=bool(payload.get("functional_test", False)),
            packaging_requirement=bool(payload.get("packaging_requirement", False)),
            tech_transfer_states=payload.get("tech_transfer_states"),
        )


def get_visit_detail(visit_id: str) -> dict:
    if not (visit_id or "").strip():
        raise ValueError("Visit id is required")
    with _connection.get_connection() as conn:
        row = repository.get_visit_detail(conn, visit_id)
    if row is None:
        raise ValueError("Visit not found")
    return row


def delete_visit(visit_id: str) -> None:
    visit_key = (visit_id or "").strip()
    if not visit_key:
        raise ValueError("Visit id is required")
    with _connection.get_connection() as conn:
        repository.delete_visit(conn, visit_key)


def list_visits_for_supplier(supplier_id: str) -> list[dict]:
    """Return all visit records for a specific supplier, ordered by date."""
    if not (supplier_id or "").strip():
        return []
    with _connection.get_connection() as conn:
        return repository.list_visits_by_supplier(conn, supplier_id)


def list_pending_visit_defect_notes(*, limit: int | None = None) -> list[dict]:
    with _connection.get_connection() as conn:
        return repository.list_pending_visit_defect_notes(conn, limit=limit)


def confirm_visit_defect_note_as_anomaly(note_id: str, payload: dict | None = None) -> dict:
    params = payload or {}
    with _connection.get_connection() as conn:
        return repository.confirm_visit_defect_note_as_anomaly(
            conn,
            note_id=note_id,
            product_id=params.get("product_id"),
            responsible_person=params.get("responsible_person", ""),
            due_date=params.get("due_date", ""),
        )
