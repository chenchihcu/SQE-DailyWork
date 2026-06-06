from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from ncr.db import crud
from ncr.models.labels import VALIDATION_REQUIRED, LABEL_ITEM_NO, LABEL_PRODUCT_NAME


def validate_product_data(data: dict[str, Any]) -> dict[str, Any]:
    item_no = str(data.get("item_no", "")).strip()
    product_name = str(data.get("product_name", "")).strip()

    if not item_no:
        raise ValueError(VALIDATION_REQUIRED.format(LABEL_ITEM_NO))
    if not product_name:
        raise ValueError(VALIDATION_REQUIRED.format(LABEL_PRODUCT_NAME))

    return {
        "item_no": item_no,
        "product_name": product_name,
    }


def create_product(conn: sqlite3.Connection, data: dict[str, Any]) -> int:
    normalized = validate_product_data(data)
    normalized["created_at"] = datetime.now().isoformat(timespec="seconds")
    try:
        return crud.insert_product(conn, normalized)
    except sqlite3.IntegrityError as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise ValueError(f"料號 '{normalized['item_no']}' 已存在。") from exc
        raise


def update_product(
    conn: sqlite3.Connection, product_id: int, data: dict[str, Any]
) -> None:
    normalized = validate_product_data(data)
    try:
        crud.update_product(conn, product_id, normalized)
    except sqlite3.IntegrityError as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise ValueError(f"料號 '{normalized['item_no']}' 已存在。") from exc
        raise


def delete_product(conn: sqlite3.Connection, product_id: int) -> None:
    crud.delete_product(conn, product_id)


def get_product_name_by_item_no(conn: sqlite3.Connection, item_no: str) -> str | None:
    row = crud.get_product_by_item_no(conn, item_no)
    return row["product_name"] if row else None


def list_products(conn: sqlite3.Connection) -> list[dict[str, str]]:
    return [
        {
            "item_no": str(row["item_no"] or ""),
            "product_name": str(row["product_name"] or ""),
        }
        for row in crud.get_products(conn)
    ]


def sync_product_from_defect(conn: sqlite3.Connection, data: dict[str, Any]) -> None:
    item_no = str(data.get("item_no", "")).strip()
    product_name = str(data.get("product_name", "")).strip()
    
    if not item_no or not product_name:
        return

    inserted_count = crud.insert_products_if_missing(
        conn,
        [
            {
                "item_no": item_no,
                "product_name": product_name,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
        ],
    )
    if inserted_count:
        conn.commit()


def bulk_sync_products_from_all_defects(conn: sqlite3.Connection) -> int:
    """
    Synchronizes all unique products found in defect_records to product_records.
    Returns the number of products synced.
    """
    unique_products = crud.get_unique_products_from_defects(conn)
    now = datetime.now().isoformat(timespec="seconds")
    
    rows = [
        {
            "item_no": product["item_no"],
            "product_name": product["product_name"],
            "created_at": now,
        }
        for product in unique_products
    ]
    inserted_count = crud.insert_products_if_missing(conn, rows)
    conn.commit()
    return inserted_count
