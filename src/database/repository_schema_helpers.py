"""Small, side-effect-free SQLite schema helpers used by the repository facade."""

from __future__ import annotations

import sqlite3


def table_sql(conn: sqlite3.Connection, table_name: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    ).fetchone()
    if row is None:
        return ""
    if isinstance(row, sqlite3.Row):
        return str(row["sql"] or "")
    return str(row[0] or "")


def ensure_product_indexes(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_products_global_code
            ON products(product_code)
            WHERE supplier_id IS NULL
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_products_supplier_code
            ON products(supplier_id, product_code)
            WHERE supplier_id IS NOT NULL
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_products_supplier ON products(supplier_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_products_secondary_supplier ON products(secondary_supplier_id)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active)")


def has_column(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(str(row["name"]) == column_name for row in rows)


def ensure_column(
    conn: sqlite3.Connection, table_name: str, column_name: str, column_ddl: str
) -> None:
    if has_column(conn, table_name, column_name):
        return
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_ddl}")


def ensure_index(
    conn: sqlite3.Connection, index_name: str, table_name: str, column_name: str
) -> None:
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({column_name})"
    )
