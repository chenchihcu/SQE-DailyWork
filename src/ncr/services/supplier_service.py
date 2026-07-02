from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from ncr.db import crud
from ncr.models.defect import SUPPLIER_CATEGORY_OPTIONS
from ncr.models.labels import VALIDATION_OPTION_INVALID, VALIDATION_REQUIRED, LABEL_SUPPLIER_NAME, LABEL_SUPPLIER_TYPE
from ncr.services.service_helpers import unique_violation_as_value_error


def validate_supplier_data(data: dict[str, Any]) -> dict[str, Any]:
    name = str(data.get("name", "")).strip()
    category = str(data.get("category", "")).strip()

    if not name:
        raise ValueError(VALIDATION_REQUIRED.format(LABEL_SUPPLIER_NAME))
    if name.upper() == "N/A":
        raise ValueError(f"{LABEL_SUPPLIER_NAME} 不能為 'N/A' (此為系統保留字)。")
    if not category:
        raise ValueError(VALIDATION_REQUIRED.format(LABEL_SUPPLIER_TYPE))
    if category not in SUPPLIER_CATEGORY_OPTIONS:
        raise ValueError(VALIDATION_OPTION_INVALID.format(LABEL_SUPPLIER_TYPE))

    return {
        "name": name,
        "category": category,
    }


def create_supplier(conn: sqlite3.Connection, data: dict[str, Any]) -> int:
    normalized = validate_supplier_data(data)
    normalized["created_at"] = datetime.now().isoformat(timespec="seconds")
    with unique_violation_as_value_error(f"供應商名稱 '{normalized['name']}' 已存在。"):
        return crud.insert_supplier(conn, normalized)


def update_supplier(
    conn: sqlite3.Connection, supplier_id: int, data: dict[str, Any]
) -> None:
    normalized = validate_supplier_data(data)
    with unique_violation_as_value_error(f"供應商名稱 '{normalized['name']}' 已存在。"):
        crud.update_supplier(conn, supplier_id, normalized)


def delete_supplier(conn: sqlite3.Connection, supplier_id: int) -> None:
    crud.delete_supplier(conn, supplier_id)


def sync_supplier_from_defect(conn: sqlite3.Connection, data: dict[str, Any]) -> None:
    """
    Synchronizes supplier information from a single defect record.
    """
    suppliers_to_sync = []
    
    formal = str(data.get("supplier_name", "")).strip()
    if formal and formal.upper() != "N/A":
        suppliers_to_sync.append({"name": formal, "category": "正式供應商"})
        
    outsource = str(data.get("outsource_supplier_name", "")).strip()
    if outsource and outsource.upper() != "N/A":
        suppliers_to_sync.append({"name": outsource, "category": "委外供應商"})
        
    now = datetime.now().isoformat(timespec="seconds")
    for s in suppliers_to_sync:
        crud.upsert_supplier_by_name(conn, {
            "name": s["name"],
            "category": s["category"],
            "created_at": now
        })


def bulk_sync_suppliers_from_all_defects(conn: sqlite3.Connection) -> int:
    """
    Synchronizes all unique suppliers found in defect_records to supplier_records.
    Returns the number of suppliers synced.
    """
    unique_suppliers = crud.get_unique_suppliers_from_defects(conn)
    now = datetime.now().isoformat(timespec="seconds")
    
    for s in unique_suppliers:
        crud.upsert_supplier_by_name(conn, {
            "name": s["name"],
            "category": s["category"],
            "created_at": now
        })
        
    return len(unique_suppliers)
