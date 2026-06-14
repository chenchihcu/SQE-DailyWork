from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


from database.connection import DB_PATH
SCHEMA_VERSION = 11



SCHEMA = """
CREATE TABLE IF NOT EXISTS defect_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    defect_no TEXT NOT NULL UNIQUE CHECK(TRIM(defect_no) <> ''),
    event_date TEXT NOT NULL
        CHECK(
            event_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
            AND date(event_date) IS NOT NULL
        ),
    return_slip_type TEXT NOT NULL DEFAULT '',
    work_order_no TEXT NOT NULL DEFAULT '',
    internal_work_order_no TEXT NOT NULL DEFAULT '',
    transfer_slip_no TEXT NOT NULL DEFAULT '',
    item_no TEXT NOT NULL CHECK(TRIM(item_no) <> ''),
    product_name TEXT NOT NULL DEFAULT '',
    qty INTEGER NOT NULL CHECK(qty > 0),
    category TEXT NOT NULL DEFAULT '',
    supplier_name TEXT NOT NULL DEFAULT '',
    outsource_supplier_name TEXT NOT NULL DEFAULT '',
    defect_desc TEXT NOT NULL CHECK(TRIM(defect_desc) <> ''),
    status TEXT NOT NULL DEFAULT '',
    disposition TEXT NOT NULL DEFAULT '',
    responsibility TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL CHECK(TRIM(created_at) <> '')
);
"""

SETTINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS ui_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT NOT NULL
);
"""

SUPPLIER_SCHEMA = """
CREATE TABLE IF NOT EXISTS supplier_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE CHECK(TRIM(name) <> ''),
    category TEXT NOT NULL CHECK(category IN ('正式供應商', '委外供應商')),
    created_at TEXT NOT NULL
);
"""

PRODUCT_SCHEMA = """
CREATE TABLE IF NOT EXISTS product_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_no TEXT NOT NULL UNIQUE CHECK(TRIM(item_no) <> ''),
    product_name TEXT NOT NULL CHECK(TRIM(product_name) <> ''),
    created_at TEXT NOT NULL
);
"""

UNIQUE_BUSINESS_INDEX_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS uniq_defect_records_business_key
ON defect_records(event_date, work_order_no, internal_work_order_no, transfer_slip_no, item_no, defect_desc);


"""

FUTURE_DATE_INSERT_TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS trg_defect_records_no_future_insert
BEFORE INSERT ON defect_records
FOR EACH ROW
WHEN NEW.event_date > date('now', 'localtime')
BEGIN
    SELECT RAISE(ABORT, 'event_date cannot be in future');
END;
"""

FUTURE_DATE_UPDATE_TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS trg_defect_records_no_future_update
BEFORE UPDATE OF event_date ON defect_records
FOR EACH ROW
WHEN NEW.event_date > date('now', 'localtime')
BEGIN
    SELECT RAISE(ABORT, 'event_date cannot be in future');
END;
"""

LEGACY_SCHEMA = """
CREATE TABLE IF NOT EXISTS defect_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    defect_no TEXT UNIQUE,
    event_date TEXT,
    work_order_no TEXT,
    item_no TEXT,
    product_name TEXT,
    qty INTEGER,
    category TEXT,
    supplier_name TEXT,
    outsource_supplier_name TEXT,
    defect_desc TEXT,
    status TEXT,
    disposition TEXT,
    created_at TEXT
);
"""


class DatabaseMigrationError(RuntimeError):
    """Raised when local database cannot be safely upgraded."""


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        LIMIT 1
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(str(row[1]) == column_name for row in rows)


def _get_user_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0]) if row is not None else 0


def _set_user_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(f"PRAGMA user_version = {version}")


def _create_v2_objects(conn: sqlite3.Connection) -> None:
    conn.execute(SCHEMA)
    conn.execute(UNIQUE_BUSINESS_INDEX_SQL)
    conn.execute(FUTURE_DATE_INSERT_TRIGGER_SQL)
    conn.execute(FUTURE_DATE_UPDATE_TRIGGER_SQL)


def _create_v3_objects(conn: sqlite3.Connection) -> None:
    _create_v5_objects(conn)


def _create_v5_objects(conn: sqlite3.Connection) -> None:
    conn.execute(SCHEMA)
    conn.execute(SUPPLIER_SCHEMA)
    conn.execute(UNIQUE_BUSINESS_INDEX_SQL)
    conn.execute(FUTURE_DATE_INSERT_TRIGGER_SQL)
    conn.execute(FUTURE_DATE_UPDATE_TRIGGER_SQL)


def _create_v7_objects(conn: sqlite3.Connection) -> None:
    _create_v8_objects(conn)


def _create_v8_objects(conn: sqlite3.Connection) -> None:
    conn.execute(SCHEMA)
    conn.execute(SUPPLIER_SCHEMA)
    conn.execute(PRODUCT_SCHEMA)
    conn.execute(UNIQUE_BUSINESS_INDEX_SQL)
    conn.execute(FUTURE_DATE_INSERT_TRIGGER_SQL)
    conn.execute(FUTURE_DATE_UPDATE_TRIGGER_SQL)


def _create_current_objects(conn: sqlite3.Connection) -> None:
    _create_v8_objects(conn)
    conn.execute(SETTINGS_SCHEMA)


def _create_v6_objects(conn: sqlite3.Connection) -> None:
    _create_v7_objects(conn)


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def get_connection() -> sqlite3.Connection:
    return _connect(DB_PATH)


def apply_schema(conn: sqlite3.Connection, *, with_version: bool = False) -> None:
    _create_current_objects(conn)
    if with_version:
        _set_user_version(conn, SCHEMA_VERSION)
    conn.commit()


def initialize_database() -> sqlite3.Connection:
    connection = get_connection()
    try:
        from database.repository import create_schema

        create_schema(connection)
        try:
            connection.execute("DELETE FROM supplier_records WHERE TRIM(name) = 'N/A'")
            connection.commit()
        except sqlite3.Error:
            pass
        return connection
    except Exception:
        logger.exception("NCR 資料庫初始化失敗")
        connection.close()
        raise
