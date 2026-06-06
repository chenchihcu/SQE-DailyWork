from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime
from typing import Any

from ncr.db import crud
from ncr.models.defect import (
    CATEGORY_OPTIONS,
    DISPOSITION_OPTIONS,
    RESPONSIBILITY_OPTIONS,
    RETURN_SLIP_TYPE_OPTIONS,
    STATUS_OPTIONS,
)
from ncr.models.labels import (
    LABEL_CATEGORY,
    LABEL_DEFECT_DESC,
    LABEL_DISPOSITION,
    LABEL_ITEM_NO,
    LABEL_QTY,
    LABEL_RESPONSIBILITY,
    LABEL_RETURN_SLIP_TYPE,
    LABEL_STATUS,
    LABEL_WORK_ORDER_NO,
    VALIDATION_DUPLICATE_RECORD,
    VALIDATION_EVENT_DATE_FORMAT,
    VALIDATION_EVENT_DATE_FUTURE,
    VALIDATION_INTERNAL_WORK_ORDER_FORMAT,
    VALIDATION_OPTION_INVALID,
    VALIDATION_QTY_INTEGER,
    VALIDATION_QTY_POSITIVE,
    VALIDATION_REQUIRED,
    VALIDATION_WORK_ORDER_FORMAT,
)
from ncr.services import product_service, supplier_service


def _to_event_date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def is_valid_work_order_format(wo: str, is_outsource: bool) -> bool:
    if len(wo) != 14:
        return False
    match = re.match(r"^(\d{4})-(\d{6})(\d{3})$", wo)
    if not match:
        return False
    prefix = match.group(1)
    yymmdd = match.group(2)
    if is_outsource:
        if prefix not in ("5102", "5104", "5202"):
            return False
    else:
        if prefix not in ("5101", "5103", "5201"):
            return False
    yy = int(yymmdd[0:2])
    mm = int(yymmdd[2:4])
    dd = int(yymmdd[4:6])
    try:
        date(2000 + yy, mm, dd)
    except ValueError:
        return False
    return True


def validate_defect_data(
    data: dict[str, Any], *, require_status_default: bool = False
) -> dict[str, Any]:
    event_date = _to_event_date(data.get("event_date") or date.today())
    try:
        event_date_obj = date.fromisoformat(event_date)
    except ValueError as exc:
        raise ValueError(VALIDATION_EVENT_DATE_FORMAT) from exc
    if event_date_obj > date.today():
        raise ValueError(VALIDATION_EVENT_DATE_FUTURE)
    event_date = event_date_obj.isoformat()
    return_slip_type = str(data.get("return_slip_type", "")).strip()
    work_order_no = str(data.get("work_order_no", "")).strip()
    internal_work_order_no = str(data.get("internal_work_order_no", "")).strip()
    transfer_slip_no = str(data.get("transfer_slip_no", "")).strip()
    item_no = str(data.get("item_no", "")).strip()
    product_name = str(data.get("product_name", "")).strip()
    supplier_name = str(data.get("supplier_name", "")).strip()
    outsource_supplier_name = str(data.get("outsource_supplier_name", "")).strip()
    defect_desc = str(data.get("defect_desc", "")).strip()
    category = str(data.get("category", CATEGORY_OPTIONS[0])).strip()
    responsibility = str(data.get("responsibility", "")).strip()
    status = str(data.get("status", STATUS_OPTIONS[0])).strip()
    disposition = str(data.get("disposition", "")).strip()

    if not return_slip_type:
        raise ValueError(VALIDATION_REQUIRED.format(LABEL_RETURN_SLIP_TYPE))
    if not work_order_no:
        raise ValueError(VALIDATION_REQUIRED.format(LABEL_WORK_ORDER_NO))
    if not is_valid_work_order_format(work_order_no, is_outsource=True):
        raise ValueError(VALIDATION_WORK_ORDER_FORMAT)
    if internal_work_order_no and not is_valid_work_order_format(internal_work_order_no, is_outsource=False):
        raise ValueError(VALIDATION_INTERNAL_WORK_ORDER_FORMAT)
    if not item_no:
        raise ValueError(VALIDATION_REQUIRED.format(LABEL_ITEM_NO))
    if not defect_desc:
        raise ValueError(VALIDATION_REQUIRED.format(LABEL_DEFECT_DESC))

    qty_raw: object = data.get("qty")
    if qty_raw in (None, ""):
        raise ValueError(VALIDATION_REQUIRED.format(LABEL_QTY))

    try:
        qty_value = int(str(qty_raw).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(VALIDATION_QTY_INTEGER) from exc

    if qty_value <= 0:
        raise ValueError(VALIDATION_QTY_POSITIVE)
    if category not in CATEGORY_OPTIONS:
        raise ValueError(VALIDATION_OPTION_INVALID.format(LABEL_CATEGORY))
    if return_slip_type not in RETURN_SLIP_TYPE_OPTIONS:
        raise ValueError(VALIDATION_OPTION_INVALID.format(LABEL_RETURN_SLIP_TYPE))
    if require_status_default and not status:
        status = STATUS_OPTIONS[0]
    if status not in STATUS_OPTIONS:
        raise ValueError(VALIDATION_OPTION_INVALID.format(LABEL_STATUS))
    if disposition and disposition not in DISPOSITION_OPTIONS:
        raise ValueError(VALIDATION_OPTION_INVALID.format(LABEL_DISPOSITION))
    if responsibility and responsibility not in RESPONSIBILITY_OPTIONS:
        raise ValueError(VALIDATION_OPTION_INVALID.format(LABEL_RESPONSIBILITY))

    return {
        "event_date": event_date,
        "return_slip_type": return_slip_type,
        "work_order_no": work_order_no,
        "internal_work_order_no": internal_work_order_no,
        "transfer_slip_no": transfer_slip_no,
        "item_no": item_no,
        "product_name": product_name,
        "qty": qty_value,
        "category": category,
        "supplier_name": supplier_name,
        "outsource_supplier_name": outsource_supplier_name,
        "defect_desc": defect_desc,
        "status": status or STATUS_OPTIONS[0],
        "disposition": disposition,
        "responsibility": responsibility,
    }


def _find_duplicate_business_key(
    conn: sqlite3.Connection,
    normalized: dict[str, Any],
    *,
    exclude_id: int | None = None,
) -> sqlite3.Row | None:
    query = """
        SELECT id, defect_no
        FROM defect_records
        WHERE event_date = ?
          AND work_order_no = ?
          AND internal_work_order_no = ?
          AND transfer_slip_no = ?
          AND item_no = ?
          AND defect_desc = ?
    """
    params: list[object] = [
        normalized["event_date"],
        normalized["work_order_no"],
        normalized["internal_work_order_no"],
        normalized["transfer_slip_no"],
        normalized["item_no"],
        normalized["defect_desc"],
    ]
    if exclude_id is not None:
        query += " AND id <> ?"
        params.append(exclude_id)
    query += " LIMIT 1"
    return conn.execute(query, params).fetchone()


def ensure_not_duplicate_business_key(
    conn: sqlite3.Connection,
    normalized: dict[str, Any],
    *,
    exclude_id: int | None = None,
) -> None:
    duplicate_row = _find_duplicate_business_key(
        conn, normalized, exclude_id=exclude_id
    )
    if duplicate_row is None:
        return
    defect_no = str(duplicate_row["defect_no"] or "").strip() or f"ID {duplicate_row['id']}"
    raise ValueError(VALIDATION_DUPLICATE_RECORD.format(defect_no))


def generate_defect_no(conn: sqlite3.Connection, event_date: Any) -> str:
    prefix = "NCR-"
    cursor = conn.execute(
        """
        SELECT defect_no
        FROM defect_records
        WHERE defect_no LIKE ? AND defect_no NOT LIKE ?
        """,
        (f"{prefix}%", f"{prefix}%-%"),
    )
    max_seq = 10000
    for row in cursor.fetchall():
        seq_str = str(row["defect_no"])[len(prefix):]
        if seq_str.isdigit():
            max_seq = max(max_seq, int(seq_str))
            
    return f"{prefix}{max_seq + 1}"


def create_defect(conn: sqlite3.Connection, data: dict[str, Any]) -> str:
    normalized = validate_defect_data(data, require_status_default=True)
    ensure_not_duplicate_business_key(conn, normalized)
    normalized["defect_no"] = generate_defect_no(conn, normalized["event_date"])
    normalized["created_at"] = datetime.now().isoformat(timespec="seconds")
    try:
        crud.insert_defect(conn, normalized)
    except sqlite3.IntegrityError as exc:
        if "uniq_defect_records_business_key" in str(exc):
            raise ValueError(VALIDATION_DUPLICATE_RECORD.format("資料庫既有資料")) from exc
        raise
    
    product_service.sync_product_from_defect(conn, normalized)
    supplier_service.sync_supplier_from_defect(conn, normalized)
    return str(normalized["defect_no"])


def update_defect(
    conn: sqlite3.Connection, defect_id: int, data: dict[str, Any]
) -> None:
    normalized = validate_defect_data(data)
    ensure_not_duplicate_business_key(conn, normalized, exclude_id=defect_id)
    try:
        crud.update_defect(conn, defect_id, normalized)
    except sqlite3.IntegrityError as exc:
        if "uniq_defect_records_business_key" in str(exc):
            raise ValueError(VALIDATION_DUPLICATE_RECORD.format("資料庫既有資料")) from exc
        raise
    
    product_service.sync_product_from_defect(conn, normalized)
    supplier_service.sync_supplier_from_defect(conn, normalized)
