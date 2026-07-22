from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


from database import connection as database_connection
SCHEMA_VERSION = 12


# ⚠ TESTS-ONLY schema. The runtime schema for sqe_v2.db is created by
# database.repository.create_schema() — initialize_database() below delegates
# to it and never applies this SCHEMA. This copy exists so tests can build an
# in-memory defect_records table via apply_schema(); it intentionally omits
# runtime-only performance indexes and MUST NOT be treated as the source of
# truth when changing the defect_records contract (audit finding C3).
SCHEMA = """
CREATE TABLE IF NOT EXISTS defect_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    defect_no TEXT NOT NULL UNIQUE CHECK(TRIM(defect_no) <> ''),
    event_date TEXT NOT NULL
        CHECK(
            event_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
            AND date(event_date) IS NOT NULL
        ),
    processing_line TEXT NOT NULL DEFAULT '未分流'
        CHECK(processing_line IN ('原物料', '委外加工', '未分流')),
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

PENDING_PROCESSING_LINE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_defect_records_status_processing_line
ON defect_records(status, processing_line);
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

class DatabaseMigrationError(RuntimeError):
    """Raised when local database cannot be safely upgraded."""


def _set_user_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(f"PRAGMA user_version = {version}")


def _create_v8_objects(conn: sqlite3.Connection) -> None:
    conn.execute(SCHEMA)
    conn.execute(SUPPLIER_SCHEMA)
    conn.execute(PRODUCT_SCHEMA)
    conn.execute(UNIQUE_BUSINESS_INDEX_SQL)
    conn.execute(PENDING_PROCESSING_LINE_INDEX_SQL)
    conn.execute(FUTURE_DATE_INSERT_TRIGGER_SQL)
    conn.execute(FUTURE_DATE_UPDATE_TRIGGER_SQL)


def _create_current_objects(conn: sqlite3.Connection) -> None:
    _create_v8_objects(conn)
    conn.execute(SETTINGS_SCHEMA)


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def get_connection() -> sqlite3.Connection:
    return _connect(database_connection.DB_PATH)


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
            logger.info("NCR 清潔 N/A 供應商記錄完成（無需處理）")
        return connection
    except Exception:
        logger.exception("NCR 資料庫初始化失敗")
        connection.close()
        raise
