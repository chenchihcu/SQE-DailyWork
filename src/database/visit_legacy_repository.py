"""Legacy visit CRUD retained for tests and scripts (product UI retired)."""

from __future__ import annotations

import logging
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from database.product_stage import PRODUCT_STAGE_MASS_PRODUCTION
from database.anomaly_repository import (
    _insert_anomaly_row,
    _next_anomaly_no,
    _prepare_anomaly_inputs,
    _resolve_product_selection,
    _validate_visit_supplier,
    create_anomaly,
    require_anomaly,
)
from database.product_repository import get_product
from database.repo_helpers import (
    DEFECT_NOTE_IMPROVED,
    DEFECT_NOTE_PENDING_IMPROVEMENT,
    _as_int,
    _gen_id,
    _month_from_date_value,
    _normalize_date,
    _normalize_non_negative_int,
    _normalize_product_stage,
    _normalize_product_stage_for_read,
    _normalize_strict_iso_date,
    _now_iso,
    _table_exists,
)


def _refresh_monthly_cache(
    conn: sqlite3.Connection, yyyymm: str, *, _commit: bool = True
) -> None:
    from database.repository import refresh_monthly_cache

    refresh_monthly_cache(conn, yyyymm, _commit=_commit)


from database.supplier_repository import get_supplier

logger = logging.getLogger(__name__)

def create_visit(
    conn: sqlite3.Connection,
    *,
    visit_date: str,
    supplier_id: str,
    product_id: str | None = None,
    product_name: str = "",
    product_stage: str = PRODUCT_STAGE_MASS_PRODUCTION,
    visitor_name: str = "",
    summary: str = "",
    work_order_no: str = "",
    production_qty: int = 0,
    product_sections: list[dict] | None = None,
    defect_notes: list[dict] | None = None,
) -> str:
    normalized_date = _normalize_strict_iso_date(
        visit_date,
        field_name="Visit date",
    )
    normalized_supplier_id = (supplier_id or "").strip()
    if not normalized_supplier_id:
        raise ValueError("Supplier is required")
    if get_supplier(conn, normalized_supplier_id) is None:
        raise ValueError("Supplier not found")
    normalized_sections = _normalize_visit_product_sections(
        conn,
        supplier_id=normalized_supplier_id,
        product_sections=product_sections,
        product_id=product_id,
        product_name=product_name,
        product_stage=product_stage,
        work_order_no=work_order_no,
        production_qty=production_qty,
    )
    primary_section = normalized_sections[0] if normalized_sections else {}
    visit_id = _insert_visit_row(
        conn,
        visit_date=normalized_date,
        supplier_id=normalized_supplier_id,
        product_id=primary_section.get("product_id"),
        product_name=str(primary_section.get("product_name") or ""),
        product_stage=str(primary_section.get("product_stage") or product_stage),
        visitor_name=visitor_name,
        summary=summary,
        work_order_no=str(primary_section.get("work_order_no") or ""),
        production_qty=primary_section.get("production_qty", 0),
    )
    _replace_visit_product_sections_and_defect_notes(
        conn,
        visit_id=visit_id,
        product_sections=normalized_sections,
        defect_notes=defect_notes,
    )
    try:
        _refresh_monthly_cache(
            conn,
            normalized_date[:7].replace("-", ""),
            _commit=False,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return visit_id

def get_visit_detail(conn: sqlite3.Connection, visit_id: str) -> dict | None:
    visit_key = (visit_id or "").strip()
    if not visit_key:
        return None
    row = conn.execute(
        """
        SELECT
            v.id AS id,
            v.visit_date AS visit_date,
            v.supplier_id AS supplier_id,
            s.supplier_name AS supplier_name,
            v.product_id AS product_id,
            p.product_code AS product_code,
            v.product_name AS product_name,
            v.product_stage AS product_stage,
            v.visitor_name AS visitor_name,
            v.summary AS summary,
            v.work_order_no AS work_order_no,
            v.production_qty AS production_qty,
            v.status AS status,
            v.created_at AS created_at,
            v.updated_at AS updated_at
        FROM visits v
        JOIN suppliers s ON s.id = v.supplier_id
        LEFT JOIN products p ON p.id = v.product_id
        WHERE v.id = ?
        LIMIT 1
        """,
        (visit_key,),
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["production_qty"] = _as_int(result.get("production_qty"), 0)
    result["product_stage"] = _normalize_product_stage(result.get("product_stage"))
    result["product_sections"] = list_visit_product_sections(conn, visit_key)
    result["defect_notes"] = list_visit_defect_notes(conn, visit_key)
    _apply_visit_rollup(result)
    return result

def list_visit_product_sections(conn: sqlite3.Connection, visit_id: str) -> list[dict]:
    visit_key = (visit_id or "").strip()
    if not visit_key:
        return []
    rows = conn.execute(
        """
        SELECT
            s.id AS id,
            s.visit_id AS visit_id,
            s.product_id AS product_id,
            s.product_code AS product_code,
            s.product_name AS product_name,
            s.product_stage AS product_stage,
            s.time_slot AS time_slot,
            s.work_order_no AS work_order_no,
            s.production_qty AS production_qty,
            s.summary AS summary,
            s.sort_order AS sort_order
        FROM visit_product_sections s
        WHERE s.visit_id = ?
        ORDER BY s.sort_order ASC, s.created_at ASC, s.rowid ASC
        """,
        (visit_key,),
    ).fetchall()
    sections: list[dict] = []
    for row in rows:
        item = dict(row)
        item["production_qty"] = _as_int(item.get("production_qty"), 0)
        item["product_stage"] = _normalize_product_stage_for_read(
            item.get("product_stage")
        )
        item["defect_notes"] = list_visit_defect_notes(
            conn, visit_key, section_id=str(item["id"])
        )
        sections.append(item)
    return sections

def list_visit_defect_notes(
    conn: sqlite3.Connection, visit_id: str, *, section_id: str | None = None
) -> list[dict]:
    visit_key = (visit_id or "").strip()
    if not visit_key:
        return []
    params: list[Any] = [visit_key]
    sql = """
        SELECT
            id,
            visit_id,
            visit_product_section_id,
            defect_desc,
            improvement_desc,
            note,
            confirmed_anomaly_id,
            confirmed_at,
            sort_order
        FROM visit_defect_notes
        WHERE visit_id = ?
    """
    if section_id is not None:
        section_key = (section_id or "").strip()
        if section_key:
            sql += " AND visit_product_section_id = ?"
            params.append(section_key)
        else:
            sql += " AND (visit_product_section_id IS NULL OR trim(visit_product_section_id) = '')"
    sql += " ORDER BY sort_order ASC, created_at ASC, rowid ASC"
    rows = conn.execute(sql, params).fetchall()
    result: list[dict] = []
    for row in rows:
        item = dict(row)
        item["status"] = _defect_note_status(item.get("improvement_desc"))
        result.append(item)
    return result

def list_pending_visit_defect_notes(
    conn: sqlite3.Connection,
    *,
    limit: int | None = None,
) -> list[dict]:
    params: list[Any] = []
    sql = """
        SELECT
            n.id AS id,
            n.visit_id AS visit_id,
            n.visit_product_section_id AS visit_product_section_id,
            n.defect_desc AS defect_desc,
            n.improvement_desc AS improvement_desc,
            n.note AS note,
            n.sort_order AS sort_order,
            n.created_at AS created_at,
            v.visit_date AS visit_date,
            v.supplier_id AS supplier_id,
            s.supplier_name AS supplier_name,
            COALESCE(sec.product_id, v.product_id, '') AS product_id,
            COALESCE(sec.product_code, p.product_code, '') AS product_code,
            COALESCE(sec.product_name, v.product_name, p.product_name, '') AS product_name,
            COALESCE(sec.product_stage, v.product_stage, p.product_stage, '量產') AS product_stage
        FROM visit_defect_notes n
        JOIN visits v ON v.id = n.visit_id
        JOIN suppliers s ON s.id = v.supplier_id
        LEFT JOIN visit_product_sections sec ON sec.id = n.visit_product_section_id
        LEFT JOIN products p ON p.id = v.product_id
        WHERE n.confirmed_anomaly_id IS NULL OR trim(n.confirmed_anomaly_id) = ''
        ORDER BY v.visit_date DESC, n.created_at DESC, n.sort_order ASC
    """
    if limit is not None:
        normalized_limit = max(0, _as_int(limit, 0))
        sql += " LIMIT ?"
        params.append(normalized_limit)
    rows = conn.execute(sql, params).fetchall()
    result: list[dict] = []
    for row in rows:
        item = dict(row)
        item["status"] = _defect_note_status(item.get("improvement_desc"))
        item["product_stage"] = _normalize_product_stage_for_read(
            item.get("product_stage")
        )
        result.append(item)
    return result

def confirm_visit_defect_note_as_anomaly(
    conn: sqlite3.Connection,
    *,
    note_id: str,
    product_id: str | None = None,
    responsible_person: str = "",
    due_date: str = "",
) -> dict[str, str | None]:
    note_key = (note_id or "").strip()
    if not note_key:
        raise ValueError("Visit defect note id is required")
    note = conn.execute(
        """
        SELECT
            n.id AS id,
            n.visit_id AS visit_id,
            n.visit_product_section_id AS visit_product_section_id,
            n.defect_desc AS defect_desc,
            n.improvement_desc AS improvement_desc,
            n.confirmed_anomaly_id AS confirmed_anomaly_id,
            v.visit_date AS visit_date,
            v.supplier_id AS supplier_id,
            COALESCE(sec.product_id, v.product_id, '') AS inferred_product_id,
            COALESCE(sec.product_stage, v.product_stage, '量產') AS product_stage,
            COALESCE(sec.work_order_no, v.work_order_no, '') AS work_order_no,
            COALESCE(sec.production_qty, v.production_qty, 0) AS production_qty
        FROM visit_defect_notes n
        JOIN visits v ON v.id = n.visit_id
        LEFT JOIN visit_product_sections sec ON sec.id = n.visit_product_section_id
        WHERE n.id = ?
        LIMIT 1
        """,
        (note_key,),
    ).fetchone()
    if note is None:
        raise ValueError("Visit defect note not found")
    if str(note["confirmed_anomaly_id"] or "").strip():
        raise ValueError("Visit defect note is already confirmed as supplier anomaly")

    resolved_product_id = (product_id or "").strip() or str(
        note["inferred_product_id"] or ""
    ).strip()
    if not resolved_product_id:
        raise ValueError("Product is required to confirm visit defect as supplier anomaly")

    result = create_anomaly_with_visit_link(
        conn,
        anomaly_date=str(note["visit_date"]),
        supplier_id=str(note["supplier_id"]),
        problem_desc=str(note["defect_desc"]),
        category="訪廠/稽核缺失",
        product_id=resolved_product_id,
        product_stage=_normalize_product_stage_for_read(note["product_stage"]),
        outsource_work_order=str(note["work_order_no"] or ""),
        batch_qty=_as_int(note["production_qty"], 0),
        visit_id=str(note["visit_id"]),
        sync_visit=False,
        pending_items=str(note["improvement_desc"] or ""),
        responsible_person=responsible_person,
        due_date=due_date,
    )
    anomaly_id = str(result.get("anomaly_id") or "").strip()
    if not anomaly_id:
        raise ValueError("Supplier anomaly confirmation did not return anomaly id")
    conn.execute(
        """
        UPDATE visit_defect_notes
        SET confirmed_anomaly_id = ?,
            confirmed_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (anomaly_id, _now_iso(), _now_iso(), note_key),
    )
    conn.commit()
    result["visit_defect_note_id"] = note_key
    return result

def update_visit(
    conn: sqlite3.Connection,
    *,
    visit_id: str,
    visit_date: str,
    supplier_id: str,
    product_id: str | None = None,
    product_name: str = "",
    product_stage: str = PRODUCT_STAGE_MASS_PRODUCTION,
    visitor_name: str = "",
    summary: str = "",
    work_order_no: str = "",
    production_qty: int = 0,
    product_sections: list[dict] | None = None,
    defect_notes: list[dict] | None = None,
) -> None:
    visit_key = (visit_id or "").strip()
    if not visit_key:
        raise ValueError("Visit id is required")
    existing = get_visit_detail(conn, visit_key)
    if existing is None:
        raise ValueError("Visit not found")
    if _confirmed_visit_defect_note_count(conn, visit_key) > 0:
        raise ValueError(
            "Visit has confirmed supplier anomaly defect notes; edit the anomaly record instead"
        )

    normalized_supplier_id = (supplier_id or "").strip()
    if not normalized_supplier_id:
        raise ValueError("Supplier is required")
    if get_supplier(conn, normalized_supplier_id) is None:
        raise ValueError("Supplier not found")
    linked_supplier_rows = conn.execute(
        """
        SELECT DISTINCT supplier_id
        FROM anomalies
        WHERE visit_id = ?
        """,
        (visit_key,),
    ).fetchall()
    if any(
        str(row["supplier_id"] or "").strip() != normalized_supplier_id
        for row in linked_supplier_rows
    ):
        raise ValueError("Visit supplier does not match linked anomaly supplier")

    normalized_date = _normalize_strict_iso_date(
        visit_date,
        field_name="Visit date",
        fallback=existing["visit_date"],
    )
    normalized_sections = _normalize_visit_product_sections(
        conn,
        supplier_id=normalized_supplier_id,
        product_sections=product_sections,
        product_id=product_id,
        product_name=product_name,
        product_stage=product_stage,
        work_order_no=work_order_no,
        production_qty=production_qty,
    )
    primary_section = normalized_sections[0] if normalized_sections else {}
    cur = conn.execute(
        """
        UPDATE visits
        SET visit_date = ?,
            supplier_id = ?,
            product_id = ?,
            product_name = ?,
            product_stage = ?,
            visitor_name = ?,
            summary = ?,
            work_order_no = ?,
            production_qty = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            normalized_date,
            normalized_supplier_id,
            primary_section.get("product_id"),
            str(primary_section.get("product_name") or ""),
            str(primary_section.get("product_stage") or product_stage),
            (visitor_name or "").strip(),
            (summary or "").strip(),
            str(primary_section.get("work_order_no") or ""),
            primary_section.get("production_qty", 0),
            _now_iso(),
            visit_key,
        ),
    )
    if cur.rowcount == 0:
        raise ValueError("Visit not found")
    _replace_visit_product_sections_and_defect_notes(
        conn,
        visit_id=visit_key,
        product_sections=normalized_sections,
        defect_notes=defect_notes,
    )
    conn.commit()

    months_to_refresh = {
        month
        for month in (
            _month_from_date_value(existing.get("visit_date")),
            _month_from_date_value(normalized_date),
        )
        if month
    }
    for month in months_to_refresh:
        _refresh_monthly_cache(conn, month)

def delete_visit(conn: sqlite3.Connection, visit_id: str) -> None:
    visit_key = (visit_id or "").strip()
    if not visit_key:
        raise ValueError("Visit id is required")
    existing = get_visit_detail(conn, visit_key)
    if existing is None:
        raise ValueError("Visit not found")

    # 若已有異常關聯此訪廠，禁止刪除
    anomaly_refs = conn.execute(
        "SELECT COUNT(*) AS cnt FROM anomalies WHERE visit_id = ?",
        (visit_key,),
    ).fetchone()
    if anomaly_refs and int(anomaly_refs["cnt"]) > 0:
        raise ValueError(
            f"Visit is referenced by {anomaly_refs['cnt']} anomaly/anomalies"
        )

    conn.execute("DELETE FROM visit_defect_notes WHERE visit_id = ?", (visit_key,))
    conn.execute("DELETE FROM visit_product_sections WHERE visit_id = ?", (visit_key,))
    cur = conn.execute("DELETE FROM visits WHERE id = ?", (visit_key,))
    if cur.rowcount == 0:
        raise ValueError("Visit not found")
    conn.commit()

    month = _month_from_date_value(existing.get("visit_date"))
    if month:
        _refresh_monthly_cache(conn, month)

def create_anomaly_with_visit_link(
    conn: sqlite3.Connection,
    *,
    anomaly_date: str,
    supplier_id: str,
    problem_desc: str,
    category: str = "",
    product_lot_no: str = "",
    product_id: str | None = None,
    product_name: str = "",
    product_stage: str = PRODUCT_STAGE_MASS_PRODUCTION,
    anomaly_source: str = "",
    material_receipt_no: str = "",
    internal_work_order_no: str = "",
    outsource_work_order: str = "",
    outsource_receipt_no: str = "",
    batch_qty: int = 0,
    visit_id: str | None = None,
    sync_visit: bool = False,
    visit_summary: str = "",
    pending_items: str = "",
    responsible_person: str = "",
    due_date: str = "",
    rc_supplier_inventory: str = "unconfirmed",
    rc_supplier_wip: str = "unconfirmed",
    rc_in_transit: str = "unconfirmed",
    rc_internal_inventory: str = "unconfirmed",
    quality_report_required: bool | None = None,
    anomaly_no: str | None = None,
    source_defect_no: str = "",
    process_keywords: str = "",
) -> dict[str, str | None]:
    inputs = _prepare_anomaly_inputs(
        conn,
        supplier_id=supplier_id,
        problem_desc=problem_desc,
        anomaly_date=anomaly_date,
        product_id=product_id,
        product_name=product_name,
        product_stage=product_stage,
        batch_qty=batch_qty,
    )
    normalized_supplier_id = inputs.normalized_supplier_id
    normalized_date = inputs.normalized_date
    resolved_product_id = inputs.resolved_product_id
    resolved_product_name = inputs.resolved_product_name
    normalized_product_stage = inputs.normalized_product_stage
    normalized_batch_qty = inputs.normalized_batch_qty

    resolved_anomaly_no = (anomaly_no or "").strip()
    if not resolved_anomaly_no:
        resolved_anomaly_no = _next_anomaly_no(conn, normalized_date)

    linked_visit_id: str | None = None
    visit_action = "none"
    requested_visit_id = (visit_id or "").strip()
    if requested_visit_id:
        visit_row = conn.execute(
            "SELECT supplier_id FROM visits WHERE id = ?",
            (requested_visit_id,),
        ).fetchone()
        if visit_row is None:
            raise ValueError("Visit not found")
        if str(visit_row["supplier_id"] or "").strip() != normalized_supplier_id:
            raise ValueError("Visit supplier does not match selected supplier")
        linked_visit_id = requested_visit_id
        visit_action = "linked"
    elif sync_visit:
        linked_visit_id = _find_latest_visit_id(
            conn, supplier_id=normalized_supplier_id, visit_date=normalized_date
        )
        if linked_visit_id is None:
            note = (visit_summary or "").strip()
            if note:
                note = f"{note}\n由異常單 {resolved_anomaly_no} 同步建立訪廠紀錄。"
            else:
                note = f"由異常單 {resolved_anomaly_no} 同步建立訪廠紀錄。"
            linked_visit_id = _insert_visit_row(
                conn,
                visit_date=normalized_date,
                supplier_id=normalized_supplier_id,
                product_id=resolved_product_id,
                product_name=resolved_product_name,
                product_stage=normalized_product_stage,
                summary=note,
                work_order_no=outsource_work_order,
                production_qty=normalized_batch_qty,
            )
            _replace_visit_product_sections_and_defect_notes(
                conn,
                visit_id=linked_visit_id,
                product_sections=[
                    {
                        "product_id": resolved_product_id,
                        "product_code": (
                            get_product(conn, resolved_product_id) or {}
                        ).get("product_code", "")
                        if resolved_product_id
                        else "",
                        "product_name": resolved_product_name,
                        "product_stage": normalized_product_stage,
                        "time_slot": "",
                        "work_order_no": outsource_work_order,
                        "production_qty": normalized_batch_qty,
                        "summary": "",
                        "sort_order": 0,
                        "defect_notes": [],
                    }
                ],
                defect_notes=None,
            )
            visit_action = "created"
        else:
            visit_action = "reused"

    _insert_anomaly_row(
        conn,
        anomaly_date=normalized_date,
        supplier_id=normalized_supplier_id,
        problem_desc=problem_desc,
        category=category,
        product_lot_no=product_lot_no,
        product_id=resolved_product_id,
        product_name=resolved_product_name,
        product_stage=normalized_product_stage,
        anomaly_source=anomaly_source,
        material_receipt_no=material_receipt_no,
        internal_work_order_no=internal_work_order_no,
        outsource_work_order=outsource_work_order,
        outsource_receipt_no=outsource_receipt_no,
        batch_qty=normalized_batch_qty,
        visit_id=linked_visit_id,
        anomaly_no=resolved_anomaly_no,
        pending_items=pending_items,
        responsible_person=responsible_person,
        due_date=due_date,
        rc_supplier_inventory=rc_supplier_inventory,
        rc_supplier_wip=rc_supplier_wip,
        rc_in_transit=rc_in_transit,
        rc_internal_inventory=rc_internal_inventory,
        quality_report_required=quality_report_required,
        source_defect_no=source_defect_no,
        process_keywords=process_keywords,
    )
    id_row = conn.execute(
        "SELECT id FROM anomalies WHERE anomaly_no = ?",
        (resolved_anomaly_no,),
    ).fetchone()
    anomaly_id = str(id_row["id"]) if id_row else None
    try:
        _refresh_monthly_cache(
            conn,
            normalized_date[:7].replace("-", ""),
            _commit=False,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {
        "anomaly_no": resolved_anomaly_no,
        "anomaly_id": anomaly_id,
        "visit_id": linked_visit_id,
        "visit_action": visit_action,
    }

def get_latest_visit_for_supplier_on_date(
    conn: sqlite3.Connection, *, supplier_id: str, visit_date: str
) -> dict | None:
    normalized_supplier_id = (supplier_id or "").strip()
    if not normalized_supplier_id:
        return None
    normalized_date = _normalize_strict_iso_date(
        visit_date,
        field_name="Visit date",
    )
    row = conn.execute(
        """
        SELECT
            v.id AS id,
            v.visit_date AS visit_date,
            v.supplier_id AS supplier_id,
            v.product_id AS product_id,
            v.product_name AS product_name,
            v.product_stage AS product_stage,
            v.work_order_no AS work_order_no,
            v.production_qty AS production_qty
        FROM visits v
        WHERE v.supplier_id = ? AND v.visit_date = ?
        ORDER BY v.updated_at DESC, v.created_at DESC, v.rowid DESC
        LIMIT 1
        """,
        (normalized_supplier_id, normalized_date),
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["product_stage"] = _normalize_product_stage_for_read(
        result.get("product_stage")
    )
    result["production_qty"] = _as_int(result.get("production_qty"), 0)
    return result

def list_visits_by_supplier(conn: sqlite3.Connection, supplier_id: str) -> list[dict]:
    """Return all visit records for a specific supplier, ordered by date."""
    sid = (supplier_id or "").strip()
    if not sid:
        return []
    rows = conn.execute(
        """
        SELECT id, visit_date, summary, work_order_no, product_name
        FROM visits
        WHERE supplier_id = ?
        ORDER BY visit_date DESC, created_at DESC
        """,
        (sid,),
    ).fetchall()
    return [dict(row) for row in rows]

def _normalize_visit_product_sections(
    conn: sqlite3.Connection,
    *,
    supplier_id: str,
    product_sections: list[dict] | None,
    product_id: str | None = None,
    product_name: str = "",
    product_stage: str = PRODUCT_STAGE_MASS_PRODUCTION,
    work_order_no: str = "",
    production_qty: int = 0,
) -> list[dict]:
    if product_sections is None:
        legacy_production_qty = _normalize_non_negative_int(
            production_qty,
            field_name="Production quantity",
        )
        legacy_has_value = any(
            (
                (product_id or "").strip(),
                (product_name or "").strip(),
                (work_order_no or "").strip(),
                legacy_production_qty > 0,
            )
        )
        raw_sections: list[dict] = (
            [
                {
                    "product_id": product_id,
                    "product_name": product_name,
                    "product_stage": product_stage,
                    "work_order_no": work_order_no,
                    "production_qty": legacy_production_qty,
                    "summary": "",
                    "time_slot": "",
                    "defect_notes": [],
                }
            ]
            if legacy_has_value
            else []
        )
    else:
        raw_sections = list(product_sections)

    normalized: list[dict] = []
    for idx, raw in enumerate(raw_sections):
        if raw is None:
            continue
        item = dict(raw)
        raw_product_id = str(item.get("product_id") or "").strip()
        raw_product_name = str(item.get("product_name") or "").strip()
        raw_stage = str(item.get("product_stage") or PRODUCT_STAGE_MASS_PRODUCTION)
        time_slot = str(item.get("time_slot") or "").strip()
        section_work_order = str(item.get("work_order_no") or "").strip()
        section_summary = str(item.get("summary") or "").strip()
        section_qty = _normalize_non_negative_int(
            item.get("production_qty", 0),
            field_name="Production quantity",
        )

        has_any_value = any(
            (
                raw_product_id,
                raw_product_name,
                time_slot,
                section_work_order,
                section_summary,
                section_qty > 0,
                item.get("defect_notes"),
            )
        )
        if not has_any_value:
            continue

        if raw_product_id:
            resolved_product_id, resolved_product_name, resolved_product_stage = (
                _resolve_product_selection(
                    conn,
                    supplier_id=supplier_id,
                    product_id=raw_product_id,
                    fallback_name=raw_product_name,
                )
            )
        else:
            resolved_product_id = None
            resolved_product_name = raw_product_name
            resolved_product_stage = raw_stage
        product = get_product(conn, resolved_product_id) if resolved_product_id else None
        product_code = str(
            (product or {}).get("product_code") or item.get("product_code") or ""
        ).strip()
        normalized.append(
            {
                "product_id": resolved_product_id,
                "product_code": product_code,
                "product_name": resolved_product_name,
                "product_stage": _normalize_product_stage(
                    resolved_product_stage or raw_stage
                ),
                "time_slot": time_slot,
                "work_order_no": section_work_order,
                "production_qty": section_qty,
                "summary": section_summary,
                "sort_order": _as_int(item.get("sort_order"), idx),
                "defect_notes": list(item.get("defect_notes") or []),
            }
        )
    return normalized

def _normalize_visit_defect_notes(raw_notes: list[dict] | None) -> list[dict]:
    normalized: list[dict] = []
    for idx, raw in enumerate(raw_notes or []):
        if raw is None:
            continue
        item = dict(raw)
        defect_desc = str(
            item.get("defect_desc") or item.get("defect") or item.get("description") or ""
        ).strip()
        improvement_desc = str(item.get("improvement_desc") or "").strip()
        note = str(item.get("note") or item.get("remark") or "").strip()
        if not any((defect_desc, improvement_desc, note)):
            continue
        if not defect_desc:
            raise ValueError("Defect description is required")
        normalized.append(
            {
                "defect_desc": defect_desc,
                "improvement_desc": improvement_desc,
                "note": note,
                "sort_order": _as_int(item.get("sort_order"), idx),
            }
        )
    return normalized

def _confirmed_visit_defect_note_count(
    conn: sqlite3.Connection,
    visit_id: str,
) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM visit_defect_notes
        WHERE visit_id = ?
          AND confirmed_anomaly_id IS NOT NULL
          AND trim(confirmed_anomaly_id) <> ''
        """,
        ((visit_id or "").strip(),),
    ).fetchone()
    return _as_int(row["c"], 0) if row is not None else 0

def _replace_visit_product_sections_and_defect_notes(
    conn: sqlite3.Connection,
    *,
    visit_id: str,
    product_sections: list[dict],
    defect_notes: list[dict] | None,
) -> None:
    visit_key = (visit_id or "").strip()
    if not visit_key:
        raise ValueError("Visit id is required")
    if _confirmed_visit_defect_note_count(conn, visit_key) > 0:
        raise ValueError(
            "Visit has confirmed supplier anomaly defect notes; edit the anomaly record instead"
        )
    conn.execute("DELETE FROM visit_defect_notes WHERE visit_id = ?", (visit_key,))
    conn.execute("DELETE FROM visit_product_sections WHERE visit_id = ?", (visit_key,))

    now = _now_iso()
    for idx, section in enumerate(product_sections):
        section_id = _gen_id()
        conn.execute(
            """
            INSERT INTO visit_product_sections(
                id, visit_id, product_id, product_code, product_name, product_stage,
                time_slot, work_order_no, production_qty, summary, sort_order,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                section_id,
                visit_key,
                section.get("product_id"),
                str(section.get("product_code") or "").strip(),
                str(section.get("product_name") or "").strip(),
                _normalize_product_stage(section.get("product_stage")),
                str(section.get("time_slot") or "").strip(),
                str(section.get("work_order_no") or "").strip(),
                _normalize_non_negative_int(
                    section.get("production_qty", 0),
                    field_name="Production quantity",
                ),
                str(section.get("summary") or "").strip(),
                _as_int(section.get("sort_order"), idx),
                now,
                now,
            ),
        )
        for note in _normalize_visit_defect_notes(section.get("defect_notes") or []):
            _insert_visit_defect_note_row(
                conn,
                visit_id=visit_key,
                section_id=section_id,
                defect_desc=note["defect_desc"],
                improvement_desc=note["improvement_desc"],
                note=note["note"],
                sort_order=note["sort_order"],
                now=now,
            )

    for note in _normalize_visit_defect_notes(defect_notes):
        _insert_visit_defect_note_row(
            conn,
            visit_id=visit_key,
            section_id=None,
            defect_desc=note["defect_desc"],
            improvement_desc=note["improvement_desc"],
            note=note["note"],
            sort_order=note["sort_order"],
            now=now,
        )

def _insert_visit_defect_note_row(
    conn: sqlite3.Connection,
    *,
    visit_id: str,
    section_id: str | None,
    defect_desc: str,
    improvement_desc: str,
    note: str,
    sort_order: int,
    now: str,
) -> None:
    conn.execute(
        """
        INSERT INTO visit_defect_notes(
            id, visit_id, visit_product_section_id, defect_desc, improvement_desc,
            note, sort_order, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _gen_id(),
            visit_id,
            (section_id or "").strip() or None,
            defect_desc.strip(),
            improvement_desc.strip(),
            note.strip(),
            int(sort_order),
            now,
            now,
        ),
    )

def _defect_note_status(improvement_desc: Any) -> str:
    return (
        DEFECT_NOTE_IMPROVED
        if str(improvement_desc or "").strip()
        else DEFECT_NOTE_PENDING_IMPROVEMENT
    )

def _apply_visit_rollup(row: dict) -> None:
    sections = list(row.get("product_sections") or [])
    notes = list(row.get("defect_notes") or [])
    product_names = _join_unique_texts(section.get("product_name") for section in sections)
    product_codes = _join_unique_texts(section.get("product_code") for section in sections)
    if product_names:
        row["product_name"] = product_names
    if product_codes:
        row["product_code"] = product_codes
    row["defect_note_count"] = len(notes)
    row["pending_improvement_count"] = sum(
        1 for note in notes if not str(note.get("improvement_desc") or "").strip()
    )
    if notes:
        row["defect_note_summary"] = (
            f"缺失 {len(notes)} 筆 / 待補改善 {row['pending_improvement_count']} 筆"
        )
    else:
        row["defect_note_summary"] = ""

def _join_unique_texts(values: Any) -> str:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return "、".join(result)

def _insert_visit_row(
    conn: sqlite3.Connection,
    *,
    visit_date: str,
    supplier_id: str,
    product_id: str | None = None,
    product_name: str = "",
    product_stage: str = PRODUCT_STAGE_MASS_PRODUCTION,
    visitor_name: str = "",
    summary: str = "",
    work_order_no: str = "",
    production_qty: int = 0,
) -> str:
    visit_id = _gen_id()
    normalized_date = _normalize_strict_iso_date(
        visit_date,
        field_name="Visit date",
    )
    normalized_product_stage = _normalize_product_stage(product_stage)
    normalized_production_qty = _normalize_non_negative_int(
        production_qty,
        field_name="Production quantity",
    )
    conn.execute(
        """
        INSERT INTO visits(
            id, visit_date, supplier_id, product_id, product_name, product_stage, visitor_name, summary,
            work_order_no, production_qty,
            status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '已完成', ?, ?)
        """,
        (
            visit_id,
            normalized_date,
            supplier_id,
            (product_id or "").strip() or None,
            (product_name or "").strip(),
            normalized_product_stage,
            (visitor_name or "").strip(),
            (summary or "").strip(),
            (work_order_no or "").strip(),
            normalized_production_qty,
            _now_iso(),
            _now_iso(),
        ),
    )
    return visit_id

def _find_latest_visit_id(
    conn: sqlite3.Connection, *, supplier_id: str, visit_date: str
) -> str | None:
    normalized_date = _normalize_strict_iso_date(visit_date, field_name="Visit date")
    row = conn.execute(
        """
        SELECT id
        FROM visits
        WHERE supplier_id = ? AND visit_date = ?
        ORDER BY created_at DESC, rowid DESC
        LIMIT 1
        """,
        (supplier_id, normalized_date),
    ).fetchone()
    if row is None:
        return None
    return str(row["id"])

def _backfill_visit_product_sections(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "visit_product_sections"):
        return
    rows = conn.execute(
        """
        SELECT
            v.id AS visit_id,
            v.product_id AS product_id,
            coalesce(p.product_code, '') AS product_code,
            v.product_name AS product_name,
            v.product_stage AS product_stage,
            v.work_order_no AS work_order_no,
            v.production_qty AS production_qty
        FROM visits v
        LEFT JOIN products p ON p.id = v.product_id
        WHERE NOT EXISTS (
            SELECT 1
            FROM visit_product_sections s
            WHERE s.visit_id = v.id
        )
          AND (
              NULLIF(trim(coalesce(v.product_id, '')), '') IS NOT NULL
              OR trim(coalesce(v.product_name, '')) <> ''
              OR trim(coalesce(v.work_order_no, '')) <> ''
              OR coalesce(v.production_qty, 0) > 0
          )
        """
    ).fetchall()
    now = _now_iso()
    for row in rows:
        conn.execute(
            """
            INSERT INTO visit_product_sections(
                id, visit_id, product_id, product_code, product_name, product_stage,
                time_slot, work_order_no, production_qty, summary, sort_order,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, '', ?, ?, '', 0, ?, ?)
            """,
            (
                _gen_id(),
                row["visit_id"],
                (row["product_id"] or "").strip() or None,
                str(row["product_code"] or "").strip(),
                str(row["product_name"] or "").strip(),
                _normalize_product_stage_for_read(row["product_stage"]),
                str(row["work_order_no"] or "").strip(),
                _as_int(row["production_qty"], 0),
                now,
                now,
            ),
        )
