"""Service layer for v2 minimalist events workflow."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from database.connection import get_connection
from database import repository
from services import event_pdf_exporter

EVENT_SCOPE_VISIT_ONLY = repository.EVENT_SCOPE_VISIT_ONLY
EVENT_SCOPE_VISIT_WITH_ANOMALY = repository.EVENT_SCOPE_VISIT_WITH_ANOMALY
EVENT_SCOPE_ANOMALY_ONLY = repository.EVENT_SCOPE_ANOMALY_ONLY
EVENT_SCOPE_CLOSED_ONLY = repository.EVENT_SCOPE_CLOSED_ONLY


def _month_now() -> str:
    return date.today().strftime("%Y%m")


def _require_supplier_record(
    conn,
    supplier_id: str,
    *,
    require_active: bool,
) -> dict:
    supplier_key = (supplier_id or "").strip()
    if not supplier_key:
        raise ValueError("Supplier is required")
    supplier = repository.get_supplier(conn, supplier_key)
    if supplier is None:
        raise ValueError("Supplier not found")
    if require_active and not bool(supplier.get("is_active")):
        raise ValueError("Supplier is inactive")
    return supplier


def _product_matches_supplier_scope(product: dict, supplier_id: str) -> bool:
    primary = str(product.get("supplier_id") or "").strip()
    secondary = str(product.get("secondary_supplier_id") or "").strip()
    if primary == supplier_id or secondary == supplier_id:
        return True
    if not primary and not secondary:
        return True
    return False


def _resolve_product_name(
    conn,
    *,
    supplier_id: str,
    product_id: str | None,
    require_active: bool = False,
) -> str:
    product_key = (product_id or "").strip()
    if not product_key:
        return ""
    product = repository.get_product(conn, product_key)
    if product is None:
        raise ValueError("Product not found")
    if require_active and not bool(product.get("is_active")):
        raise ValueError("Product is inactive")
    if not _product_matches_supplier_scope(product, supplier_id):
        raise ValueError("Product does not belong to selected supplier")
    return str(product.get("product_name") or "").strip()


def _require_product_id(payload: dict) -> str:
    product_id = (payload.get("product_id") or "").strip()
    if not product_id:
        raise ValueError("Product is required")
    return product_id


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


def _visit_note_has_content(notes: object) -> bool:
    for note in notes or []:
        item = dict(note or {})
        if any(
            str(item.get(key) or "").strip()
            for key in ("defect_desc", "defect", "description", "improvement_desc", "note", "remark")
        ):
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


def list_suppliers(*, include_inactive: bool = True) -> list[dict]:
    with get_connection() as conn:
        return repository.list_suppliers(conn, include_inactive=include_inactive)


def create_supplier(payload: dict) -> str:
    with get_connection() as conn:
        return repository.create_supplier_record(
            conn,
            supplier_name=payload.get("supplier_name", ""),
            contact_name=payload.get("contact_name", ""),
            department=payload.get("department", ""),
            phone=payload.get("phone", ""),
            contact_email=payload.get("contact_email", ""),
        )


def update_supplier(supplier_id: str, payload: dict) -> None:
    with get_connection() as conn:
        repository.update_supplier_record(
            conn,
            supplier_id=supplier_id,
            supplier_name=payload.get("supplier_name", ""),
            contact_name=payload.get("contact_name", ""),
            department=payload.get("department", ""),
            phone=payload.get("phone", ""),
            contact_email=payload.get("contact_email", ""),
        )


def set_supplier_active(supplier_id: str, is_active: bool) -> None:
    with get_connection() as conn:
        repository.set_supplier_active(conn, supplier_id, is_active)


def delete_supplier(supplier_id: str) -> None:
    with get_connection() as conn:
        repository.delete_supplier_record(conn, supplier_id)


def list_supplier_contacts(supplier_id: str) -> list[dict]:
    with get_connection() as conn:
        return repository.list_supplier_contacts(conn, supplier_id)


def add_supplier_contact(supplier_id: str, payload: dict) -> str:
    with get_connection() as conn:
        return repository.add_supplier_contact(
            conn,
            supplier_id=supplier_id,
            contact_name=payload.get("contact_name", ""),
            department=payload.get("department", ""),
            phone=payload.get("phone", ""),
            email=payload.get("email", ""),
            is_primary=bool(payload.get("is_primary", False)),
        )


def delete_supplier_contact(contact_id: str) -> None:
    with get_connection() as conn:
        repository.delete_supplier_contact(conn, contact_id)


def set_primary_contact(supplier_id: str, contact_id: str) -> None:
    with get_connection() as conn:
        repository.set_primary_contact(conn, supplier_id, contact_id)


def delete_suppliers(
    supplier_ids: list[str],
) -> repository.SupplierDeleteResult:
    with get_connection() as conn:
        return repository.delete_supplier_records(conn, supplier_ids)


def list_products(*, include_inactive: bool = True) -> list[dict]:
    with get_connection() as conn:
        return repository.list_products(conn, include_inactive=include_inactive)


def create_product(payload: dict) -> str:
    with get_connection() as conn:
        return repository.create_product_record(
            conn,
            product_code=payload.get("product_code", ""),
            product_name=payload.get("product_name", ""),
            product_stage=payload.get("product_stage", "量產"),
            supplier_id=(payload.get("supplier_id") or "").strip(),
            secondary_supplier_id=(
                payload.get("secondary_supplier_id") or ""
            ).strip()
            or None,
        )


def update_product(product_id: str, payload: dict) -> None:
    with get_connection() as conn:
        repository.update_product_record(
            conn,
            product_id=product_id,
            product_code=payload.get("product_code", ""),
            product_name=payload.get("product_name", ""),
            product_stage=payload.get("product_stage", "量產"),
            supplier_id=(payload.get("supplier_id") or "").strip(),
            secondary_supplier_id=(
                payload.get("secondary_supplier_id") or ""
            ).strip()
            or None,
            stage_change_reason=(payload.get("stage_change_reason") or "").strip(),
        )


def set_product_active(product_id: str, is_active: bool) -> None:
    with get_connection() as conn:
        repository.set_product_active(conn, product_id, is_active)


def delete_product(product_id: str) -> None:
    with get_connection() as conn:
        repository.delete_product_record(conn, product_id)


def list_active_suppliers() -> list[dict]:
    with get_connection() as conn:
        return repository.list_active_suppliers(conn)


def list_active_products_for_supplier(supplier_id: str | None) -> list[dict]:
    with get_connection() as conn:
        return repository.list_active_products_for_supplier(conn, supplier_id)


def has_active_suppliers() -> bool:
    return bool(list_active_suppliers())


def create_anomaly(payload: dict) -> str:
    problem_desc = (payload.get("problem_desc") or "").strip()
    if not problem_desc:
        raise ValueError("Problem description is required")

    supplier_id = (payload.get("supplier_id") or "").strip()
    product_id = _require_product_id(payload)
    anomaly_date = payload.get("anomaly_date") or date.today().isoformat()

    with get_connection() as conn:
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

    with get_connection() as conn:
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
        )


def get_anomaly_detail(anomaly_id: str) -> dict:
    if not (anomaly_id or "").strip():
        raise ValueError("Anomaly id is required")
    with get_connection() as conn:
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

    with get_connection() as conn:
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
        )
        conn.commit()


def update_anomaly_link(anomaly_id: str, visit_id: str | None) -> None:
    """Manually update the visit association for an existing anomaly."""
    if not (anomaly_id or "").strip():
        raise ValueError("Anomaly id is required")
    with get_connection() as conn:
        repository.update_anomaly_link(conn, anomaly_id, visit_id)
        conn.commit()


def list_visits_for_supplier(supplier_id: str) -> list[dict]:
    """Return all visit records for a specific supplier, ordered by date."""
    if not (supplier_id or "").strip():
        return []
    with get_connection() as conn:
        return repository.list_visits_by_supplier(conn, supplier_id)


def list_pending_visit_defect_notes(*, limit: int | None = None) -> list[dict]:
    with get_connection() as conn:
        return repository.list_pending_visit_defect_notes(conn, limit=limit)


def confirm_visit_defect_note_as_anomaly(note_id: str, payload: dict | None = None) -> dict:
    params = payload or {}
    with get_connection() as conn:
        return repository.confirm_visit_defect_note_as_anomaly(
            conn,
            note_id=note_id,
            product_id=params.get("product_id"),
            responsible_person=params.get("responsible_person", ""),
            due_date=params.get("due_date", ""),
        )


def delete_anomaly(anomaly_id: str) -> None:
    anomaly_key = (anomaly_id or "").strip()
    if not anomaly_key:
        raise ValueError("Anomaly id is required")
    with get_connection() as conn:
        repository.delete_anomaly(conn, anomaly_key)


def preview_anomaly_no(anomaly_date: str | None = None) -> str:
    target_date = anomaly_date or date.today().isoformat()
    with get_connection() as conn:
        return repository.preview_anomaly_no(conn, target_date)


def get_latest_tech_transfer_for_supplier(supplier_id: str) -> dict | None:
    """查詢指定供應商最新一筆含技轉資料的訪廠紀錄，做為新增異常的「參考資料」。
    若查無技轉紀錄則回傳 None。"""
    normalized = (supplier_id or "").strip()
    if not normalized:
        return None
    with get_connection() as conn:
        return repository.get_latest_tech_transfer_for_supplier(conn, normalized)


def get_latest_visit_for_supplier_on_date(
    supplier_id: str, visit_date: str
) -> dict | None:
    normalized_supplier = (supplier_id or "").strip()
    normalized_date = (visit_date or "").strip()
    if not normalized_supplier or not normalized_date:
        return None
    with get_connection() as conn:
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
) -> None:
    if not (anomaly_id or "").strip():
        raise ValueError("Anomaly id is required")
    with get_connection() as conn:
        repository.close_anomaly(
            conn,
            anomaly_id=anomaly_id,
            improvement_desc=improvement_desc,
            closed_by=closed_by,
            root_cause_category=root_cause_category,
        )


def reopen_anomaly(anomaly_id: str) -> None:
    if not (anomaly_id or "").strip():
        raise ValueError("Anomaly id is required")
    with get_connection() as conn:
        repository.reopen_anomaly(conn, anomaly_id)


def create_visit(payload: dict) -> str:
    supplier_id = (payload.get("supplier_id") or "").strip()
    if not _has_visit_record_content(payload):
        _require_product_id(payload)
    product_id = (payload.get("product_id") or "").strip()
    visit_date = payload.get("visit_date") or date.today().isoformat()
    with get_connection() as conn:
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

    with get_connection() as conn:
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
    with get_connection() as conn:
        row = repository.get_visit_detail(conn, visit_id)
    if row is None:
        raise ValueError("Visit not found")
    return row


def delete_visit(visit_id: str) -> None:
    visit_key = (visit_id or "").strip()
    if not visit_key:
        raise ValueError("Visit id is required")
    with get_connection() as conn:
        repository.delete_visit(conn, visit_key)


def list_events(filters: dict | None = None) -> list[dict]:
    params = filters or {}
    with get_connection() as conn:
        return repository.list_events(
            conn,
            event_type=params.get("event_type", "ALL"),
            status=params.get("status", "ALL"),
            supplier_keyword=params.get("supplier", ""),
            yyyymm=params.get("yyyymm"),
            limit=params.get("limit"),
            event_scope=params.get("event_scope"),
            overdue_only=bool(params.get("overdue_only", False)),
        )


def _event_pdf_payload(row: dict) -> tuple[dict, dict | None]:
    event_id = str(row.get("event_id") or "").strip()
    if not event_id:
        raise ValueError("Event id is required")
    event_type = str(row.get("event_type") or "").strip().upper()
    if event_type == "VISIT":
        return get_visit_detail(event_id), None
    if event_type == "ANOMALY":
        detail = get_anomaly_detail(event_id)
        linked_visit_id = str(
            row.get("linked_visit_id") or detail.get("visit_id") or ""
        ).strip()
        linked_visit = get_visit_detail(linked_visit_id) if linked_visit_id else None
        return detail, linked_visit
    raise ValueError("Event type is required")


def default_event_pdf_filename(row: dict) -> str:
    detail, _linked_visit = _event_pdf_payload(row)
    return event_pdf_exporter.default_event_pdf_filename(row, detail)


def export_event_pdf(path: str, row: dict) -> tuple[bool, str]:
    try:
        detail, linked_visit = _event_pdf_payload(row)
        return event_pdf_exporter.export_event_pdf(
            path,
            row,
            detail,
            linked_visit=linked_visit,
        )
    except Exception as exc:
        return False, f"匯出失敗：{exc}"


def export_brief_event_pdf(path: str, row: dict) -> tuple[bool, str]:
    try:
        detail, linked_visit = _event_pdf_payload(row)
        return event_pdf_exporter.export_brief_event_pdf(
            path,
            row,
            detail,
            linked_visit=linked_visit,
        )
    except Exception as exc:
        return False, f"匯出精簡版失敗：{exc}"


def render_brief_event_image(row: dict) -> "QImage | None":
    """將精簡報告渲染為 QImage 供 LINE 剪貼簿圖片傳送。"""
    try:
        detail, linked_visit = _event_pdf_payload(row)
        return event_pdf_exporter.render_brief_event_to_image(
            row,
            detail,
            linked_visit=linked_visit,
        )
    except Exception:
        return None


def get_dashboard_summary() -> dict:
    with get_connection() as conn:
        return repository.get_dashboard_summary(conn)


def get_monthly_stats(yyyymm: str | None = None) -> dict:
    month = yyyymm or _month_now()
    with get_connection() as conn:
        return repository.get_monthly_stats(conn, month)


def get_anomaly_trend(months: int = 6) -> list[dict]:
    with get_connection() as conn:
        return repository.get_anomaly_trend(conn, months)


def get_responsible_person_stats(yyyymm: str | None = None) -> list[dict]:
    month = yyyymm or _month_now()
    with get_connection() as conn:
        return repository.get_responsible_person_stats(conn, month)


def list_product_stage_change_logs(
    *, product_id: str | None = None, limit: int = 200
) -> list[dict]:
    with get_connection() as conn:
        return repository.list_product_stage_change_logs(
            conn,
            product_id=(product_id or "").strip() or None,
            limit=limit,
        )


def export_monthly_excel(path: str, yyyymm: str) -> tuple[bool, str]:
    import pandas as pd
    try:
        month = yyyymm or _month_now()
        stats = get_monthly_stats(month)
        rows = list_events({"yyyymm": month})
        summary_df = pd.DataFrame(
            [
                {
                    "月份": f"{month[:4]}-{month[4:]}",
                    "本月異常數": stats["anomaly_count"],
                    "訪廠數": stats["visit_count"],
                    "結案數": stats["closed_anomaly_count"],
                    "未結案數": stats["open_anomaly_count"],
                    "結案率(%)": stats["close_rate_pct"],
                    "異常/訪廠比": stats["anomaly_visit_ratio"],
                    "供應商覆蓋數": stats["supplier_coverage_count"],
                }
            ]
        )
        ranking_df = pd.DataFrame(
            [
                {
                    "排名": idx,
                    "供應商": row["supplier_name"],
                    "異常數": row["anomaly_count"],
                    "訪廠數": row["visit_count"],
                    "結案數": row["closed_anomaly_count"],
                    "未結案數": row["open_anomaly_count"],
                    "結案率(%)": row["close_rate_pct"],
                }
                for idx, row in enumerate(stats["top_suppliers_by_anomaly"], start=1)
            ],
            columns=["排名", "供應商", "異常數", "訪廠數", "結案數", "未結案數", "結案率(%)"],
        )
        detail_df = pd.DataFrame(
            [
                {
                    "日期": row["event_date"],
                    "類型": "異常" if row["event_type"] == "ANOMALY" else "訪廠",
                    "供應商": row["supplier_name"],
                    "問題/摘要": row["content"],
                    "狀態": row["status"],
                }
                for row in rows
            ]
        )
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            summary_df.to_excel(writer, sheet_name="月統計", index=False)
            ranking_df.to_excel(writer, sheet_name="供應商排行", index=False)
            detail_df.to_excel(writer, sheet_name="明細", index=False)
        return True, f"已匯出至：{output}"
    except Exception as exc:
        return False, f"匯出失敗：{exc}"
