from __future__ import annotations

import logging
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)


TABLE_COLUMNS = (
    "defect_no",
    "event_date",
    "processing_line",
    "return_slip_type",
    "work_order_no",
    "internal_work_order_no",
    "transfer_slip_no",
    "item_no",
    "product_name",
    "qty",
    "category",
    "supplier_name",
    "outsource_supplier_name",
    "defect_desc",
    "status",
    "disposition",
    "responsibility",
    "created_at",
)

_INSERT_PLACEHOLDERS = ", ".join("?" for _ in TABLE_COLUMNS)
_INSERT_COLUMNS = ", ".join(TABLE_COLUMNS)
_EDITABLE_COLUMNS = (
    "event_date",
    "processing_line",
    "return_slip_type",
    "work_order_no",
    "internal_work_order_no",
    "transfer_slip_no",
    "item_no",
    "product_name",
    "qty",
    "category",
    "supplier_name",
    "outsource_supplier_name",
    "defect_desc",
    "status",
    "disposition",
    "responsibility",
)
_UPDATE_ASSIGNMENTS = ", ".join(f"{column} = ?" for column in _EDITABLE_COLUMNS)


def insert_defect(conn: sqlite3.Connection, data: dict[str, Any]) -> int:
    values = [data.get(column) for column in TABLE_COLUMNS]
    cursor = conn.execute(
        f"INSERT INTO defect_records ({_INSERT_COLUMNS}) VALUES ({_INSERT_PLACEHOLDERS})",
        values,
    )
    conn.commit()
    row_id = cursor.lastrowid
    if row_id is None:
        raise sqlite3.DatabaseError("無法取得新增資料列 ID。")
    return int(row_id)


def get_defects(
    conn: sqlite3.Connection,
    filters: dict[str, Any] | None = None,
    exclude_status: str | None = None,
) -> list[sqlite3.Row]:
    query = """
        SELECT
            id,
            defect_no,
            event_date,
            processing_line,
            return_slip_type,
            work_order_no,
            internal_work_order_no,
            transfer_slip_no,
            item_no,
            product_name,
            qty,
            category,
            supplier_name,
            outsource_supplier_name,
            defect_desc,
            status,
            disposition,
            responsibility,
            created_at
        FROM defect_records
    """
    conditions: list[str] = []
    params: list[Any] = []
    filters = filters or {}

    if filters.get("month"):
        conditions.append("strftime('%Y-%m', event_date) = ?")
        params.append(filters["month"])
    if filters.get("processing_line"):
        conditions.append("processing_line = ?")
        params.append(filters["processing_line"])
    if filters.get("work_order_no"):
        conditions.append("(work_order_no LIKE ? OR internal_work_order_no LIKE ? OR transfer_slip_no LIKE ?)")
        search_val = f"%{filters['work_order_no'].strip()}%"
        params.extend([search_val, search_val, search_val])
    if filters.get("item_no"):
        conditions.append("item_no LIKE ?")
        params.append(f"%{filters['item_no'].strip()}%")
    if filters.get("supplier_name"):
        conditions.append("supplier_name LIKE ?")
        params.append(f"%{filters['supplier_name'].strip()}%")
    if filters.get("outsource_supplier_name"):
        conditions.append("outsource_supplier_name LIKE ?")
        params.append(f"%{filters['outsource_supplier_name'].strip()}%")
    if filters.get("status"):
        conditions.append("status = ?")
        params.append(filters["status"])
    if exclude_status:
        conditions.append("status <> ?")
        params.append(exclude_status)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY event_date DESC, id DESC"
    cursor = conn.execute(query, params)
    return list(cursor.fetchall())


def get_defect_by_id(
    conn: sqlite3.Connection, defect_id: int
) -> sqlite3.Row | None:
    cursor = conn.execute(
        """
        SELECT
            id,
            defect_no,
            event_date,
            processing_line,
            return_slip_type,
            work_order_no,
            internal_work_order_no,
            transfer_slip_no,
            item_no,
            product_name,
            qty,
            category,
            supplier_name,
            outsource_supplier_name,
            defect_desc,
            status,
            disposition,
            responsibility,
            created_at
        FROM defect_records
        WHERE id = ?
        """,
        (defect_id,),
    )
    return cursor.fetchone()


def update_defect(
    conn: sqlite3.Connection, defect_id: int, data: dict[str, Any]
) -> None:
    values = [data.get(column) for column in _EDITABLE_COLUMNS]
    values.append(defect_id)

    conn.execute("BEGIN")
    try:
        cursor = conn.execute(
            f"UPDATE defect_records SET {_UPDATE_ASSIGNMENTS} WHERE id = ?",
            values,
        )
        if cursor.rowcount <= 0:
            raise sqlite3.DatabaseError(f"找不到要更新的資料 ID: {defect_id}")
        conn.commit()
    except Exception:
        logger.exception("更新缺陷記錄 ID=%s 失敗", defect_id)
        conn.rollback()
        raise


def delete_defect(conn: sqlite3.Connection, defect_id: int) -> None:
    conn.execute("BEGIN")
    try:
        cursor = conn.execute("DELETE FROM defect_records WHERE id = ?", (defect_id,))
        if cursor.rowcount <= 0:
            raise sqlite3.DatabaseError(f"找不到要刪除的資料 ID: {defect_id}")
        conn.commit()
    except Exception:
        logger.exception("刪除缺陷記錄 ID=%s 失敗", defect_id)
        conn.rollback()
        raise


# Supplier CRUD

def insert_supplier(conn: sqlite3.Connection, data: dict[str, Any]) -> int:
    cursor = conn.execute(
        "INSERT INTO supplier_records (name, category, created_at) VALUES (?, ?, ?)",
        (data["name"], data["category"], data["created_at"]),
    )
    conn.commit()
    row_id = cursor.lastrowid
    if row_id is None:
        raise sqlite3.DatabaseError("無法取得新增供應商 ID。")
    return int(row_id)


def get_suppliers(
    conn: sqlite3.Connection, category: str | None = None
) -> list[sqlite3.Row]:
    query = "SELECT id, name, category, created_at FROM supplier_records"
    params = []
    if category:
        query += " WHERE category = ?"
        params.append(category)
    query += " ORDER BY name COLLATE NOCASE"
    cursor = conn.execute(query, params)
    return list(cursor.fetchall())


def update_supplier(
    conn: sqlite3.Connection, supplier_id: int, data: dict[str, Any]
) -> None:
    conn.execute("BEGIN")
    try:
        cursor = conn.execute(
            "UPDATE supplier_records SET name = ?, category = ? WHERE id = ?",
            (data["name"], data["category"], supplier_id),
        )
        if cursor.rowcount <= 0:
            raise sqlite3.DatabaseError(f"找不到要更新的供應商 ID: {supplier_id}")
        conn.commit()
    except Exception:
        logger.exception("更新供應商 ID=%s 失敗", supplier_id)
        conn.rollback()
        raise


def delete_supplier(conn: sqlite3.Connection, supplier_id: int) -> None:
    conn.execute("BEGIN")
    try:
        cursor = conn.execute("DELETE FROM supplier_records WHERE id = ?", (supplier_id,))
        if cursor.rowcount <= 0:
            raise sqlite3.DatabaseError(f"找不到要刪除的供應商 ID: {supplier_id}")
        conn.commit()
    except Exception:
        logger.exception("刪除供應商 ID=%s 失敗", supplier_id)
        conn.rollback()
        raise


def upsert_supplier_by_name(conn: sqlite3.Connection, data: dict[str, Any]) -> None:
    """
    If supplier name exists, update category. Otherwise insert.
    """
    conn.execute(
        """
        INSERT INTO supplier_records (name, category, created_at)
        VALUES (?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            category = excluded.category
        """,
        (data["name"], data["category"], data["created_at"]),
    )
    conn.commit()


def get_unique_suppliers_from_defects(conn: sqlite3.Connection) -> list[dict[str, str]]:
    """
    Retrieves unique supplier names and their categories (Formal vs Outsource) from defect_records.
    """
    query = """
        SELECT DISTINCT supplier_name as name, '正式供應商' as category
        FROM defect_records
        WHERE supplier_name IS NOT NULL AND TRIM(supplier_name) <> '' AND TRIM(supplier_name) <> 'N/A'
        UNION
        SELECT DISTINCT outsource_supplier_name as name, '委外供應商' as category
        FROM defect_records
        WHERE outsource_supplier_name IS NOT NULL AND TRIM(outsource_supplier_name) <> '' AND TRIM(outsource_supplier_name) <> 'N/A'
    """
    cursor = conn.execute(query)
    return [{"name": row["name"], "category": row["category"]} for row in cursor.fetchall()]


def get_unique_products_from_defects(conn: sqlite3.Connection) -> list[dict[str, str]]:
    """
    Retrieves one product name per item_no from defect_records.

    If the same item_no appears with multiple product names, use the newest
    defect row. This matches the schema migration behavior.
    """
    query = """
        SELECT item_no, product_name
        FROM (
            SELECT
                TRIM(item_no) AS item_no,
                TRIM(product_name) AS product_name,
                ROW_NUMBER() OVER (
                    PARTITION BY TRIM(item_no)
                    ORDER BY id DESC
                ) AS row_number
            FROM defect_records
            WHERE item_no IS NOT NULL AND TRIM(item_no) <> ''
              AND product_name IS NOT NULL AND TRIM(product_name) <> ''
        ) latest_product
        WHERE row_number = 1
        ORDER BY item_no COLLATE NOCASE
    """
    cursor = conn.execute(query)
    return [{"item_no": row["item_no"], "product_name": row["product_name"]} for row in cursor.fetchall()]


# Product CRUD

def insert_product(conn: sqlite3.Connection, data: dict[str, Any]) -> int:
    cursor = conn.execute(
        "INSERT INTO product_records (item_no, product_name, created_at) VALUES (?, ?, ?)",
        (data["item_no"], data["product_name"], data["created_at"]),
    )
    conn.commit()
    row_id = cursor.lastrowid
    if row_id is None:
        raise sqlite3.DatabaseError("無法取得新增產品 ID。")
    return int(row_id)


def insert_products(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    conn.executemany(
        "INSERT INTO product_records (item_no, product_name, created_at) VALUES (?, ?, ?)",
        [
            (row["item_no"], row["product_name"], row["created_at"])
            for row in rows
        ],
    )
    return len(rows)


def insert_products_if_missing(
    conn: sqlite3.Connection, rows: list[dict[str, Any]]
) -> int:
    # product_records 是 VIEW，INSERT 經 INSTEAD OF trigger 寫進 products；
    # cursor.rowcount 只反映 VIEW 上的直接變更（恆為 0，不含 trigger 動作），
    # 會讓呼叫端誤判「沒有新增」。改用 conn.total_changes 差值（涵蓋 trigger
    # 內層 INSERT），對實體表與視圖皆正確。
    inserted_count = 0
    for row in rows:
        before = conn.total_changes
        conn.execute(
            """
            INSERT OR IGNORE INTO product_records (item_no, product_name, created_at)
            VALUES (?, ?, ?)
            """,
            (row["item_no"], row["product_name"], row["created_at"]),
        )
        inserted_count += conn.total_changes - before
    return inserted_count


def update_products_by_item_no(
    conn: sqlite3.Connection, rows: list[dict[str, Any]]
) -> int:
    updated_count = 0
    for row in rows:
        cursor = conn.execute(
            """
            UPDATE product_records
            SET product_name = ?
            WHERE item_no = ?
              AND product_name <> ?
            """,
            (row["product_name"], row["item_no"], row["product_name"]),
        )
        updated_count += cursor.rowcount
    return updated_count


def count_defect_product_name_changes(
    conn: sqlite3.Connection, item_no: str, product_name: str
) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS change_count
        FROM defect_records
        WHERE TRIM(item_no) = ?
          AND COALESCE(product_name, '') <> ?
        """,
        (item_no, product_name),
    ).fetchone()
    return int(row["change_count"] if row is not None else 0)


def update_defect_product_names_by_item_no(
    conn: sqlite3.Connection, rows: list[dict[str, Any]]
) -> int:
    updated_count = 0
    for row in rows:
        cursor = conn.execute(
            """
            UPDATE defect_records
            SET product_name = ?
            WHERE TRIM(item_no) = ?
              AND COALESCE(product_name, '') <> ?
            """,
            (row["product_name"], row["item_no"], row["product_name"]),
        )
        updated_count += cursor.rowcount
    return updated_count


def get_products(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    query = "SELECT id, item_no, product_name, created_at FROM product_records ORDER BY item_no COLLATE NOCASE"
    cursor = conn.execute(query)
    return list(cursor.fetchall())


def get_product_by_item_no(conn: sqlite3.Connection, item_no: str) -> sqlite3.Row | None:
    cursor = conn.execute(
        "SELECT id, item_no, product_name, created_at FROM product_records WHERE item_no = ?",
        (item_no,),
    )
    return cursor.fetchone()


def update_product(
    conn: sqlite3.Connection, product_id: int, data: dict[str, Any]
) -> None:
    # product_records 是 VIEW，寫入經 INSTEAD OF trigger 進到 products；此時
    # cursor.rowcount 反映的是 VIEW 上的直接變更（恆為 0，不含 trigger 動作），
    # 不能用來判斷「是否找到」。改以明確存在性查詢判斷。
    conn.execute("BEGIN")
    try:
        exists = conn.execute(
            "SELECT 1 FROM product_records WHERE id = ?", (product_id,)
        ).fetchone()
        if exists is None:
            raise sqlite3.DatabaseError(f"找不到要更新的產品 ID: {product_id}")
        conn.execute(
            "UPDATE product_records SET item_no = ?, product_name = ? WHERE id = ?",
            (data["item_no"], data["product_name"], product_id),
        )
        conn.commit()
    except Exception:
        logger.exception("更新產品 ID=%s 失敗", product_id)
        conn.rollback()
        raise


def delete_product(conn: sqlite3.Connection, product_id: int) -> None:
    # 同 update_product：VIEW 上 cursor.rowcount 恆為 0，需用存在性查詢判斷。
    conn.execute("BEGIN")
    try:
        exists = conn.execute(
            "SELECT 1 FROM product_records WHERE id = ?", (product_id,)
        ).fetchone()
        if exists is None:
            raise sqlite3.DatabaseError(f"找不到要刪除的產品 ID: {product_id}")
        conn.execute("DELETE FROM product_records WHERE id = ?", (product_id,))
        conn.commit()
    except Exception:
        logger.exception("刪除產品 ID=%s 失敗", product_id)
        conn.rollback()
        raise
