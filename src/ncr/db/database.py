from __future__ import annotations

import sqlite3
from pathlib import Path


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
    work_order_no TEXT NOT NULL CHECK(TRIM(work_order_no) <> ''),
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


def _collect_issue(
    conn: sqlite3.Connection,
    *,
    label: str,
    where_clause: str,
    params: tuple[object, ...] = (),
    limit: int = 5,
) -> tuple[str, int, list[int]]:
    count_row = conn.execute(
        f"SELECT COUNT(*) FROM defect_records WHERE {where_clause}",
        params,
    ).fetchone()
    count = int(count_row[0]) if count_row is not None else 0
    if count == 0:
        return label, 0, []
    sample_rows = conn.execute(
        (
            "SELECT id FROM defect_records "
            f"WHERE {where_clause} ORDER BY id ASC LIMIT {limit}"
        ),
        params,
    ).fetchall()
    sample_ids = [int(row[0]) for row in sample_rows]
    return label, count, sample_ids


def _collect_duplicate_issue(conn: sqlite3.Connection, *, limit: int = 5) -> tuple[str, int, list[int]]:
    duplicate_group_row = conn.execute(
        """
        SELECT COUNT(*)
        FROM (
            SELECT
                event_date,
                TRIM(work_order_no) AS work_order_no,
                TRIM(item_no) AS item_no,
                TRIM(defect_desc) AS defect_desc,
                COUNT(*) AS duplicate_count
            FROM defect_records
            GROUP BY
                event_date,
                TRIM(work_order_no),
                TRIM(item_no),
                TRIM(defect_desc)
            HAVING duplicate_count > 1
        ) duplicate_groups
        """
    ).fetchone()
    duplicate_group_count = int(duplicate_group_row[0]) if duplicate_group_row is not None else 0
    if duplicate_group_count == 0:
        return "重複關鍵欄位（event_date/work_order_no/item_no/defect_desc）", 0, []

    sample_rows = conn.execute(
        f"""
        WITH duplicate_groups AS (
            SELECT
                event_date,
                TRIM(work_order_no) AS work_order_no,
                TRIM(item_no) AS item_no,
                TRIM(defect_desc) AS defect_desc
            FROM defect_records
            GROUP BY
                event_date,
                TRIM(work_order_no),
                TRIM(item_no),
                TRIM(defect_desc)
            HAVING COUNT(*) > 1
        )
        SELECT record.id
        FROM defect_records AS record
        INNER JOIN duplicate_groups AS duplicate_group
            ON record.event_date = duplicate_group.event_date
            AND TRIM(record.work_order_no) = duplicate_group.work_order_no
            AND TRIM(record.item_no) = duplicate_group.item_no
            AND TRIM(record.defect_desc) = duplicate_group.defect_desc
        ORDER BY record.id ASC
        LIMIT {limit}
        """
    ).fetchall()
    sample_ids = [int(row[0]) for row in sample_rows]
    return "重複關鍵欄位（event_date/work_order_no/item_no/defect_desc）", duplicate_group_count, sample_ids


def _run_preflight_checks(conn: sqlite3.Connection) -> list[tuple[str, int, list[int]]]:
    issues: list[tuple[str, int, list[int]]] = []
    issues.append(
        _collect_issue(
            conn,
            label="defect_no 空值",
            where_clause="defect_no IS NULL OR TRIM(defect_no) = ''",
        )
    )
    issues.append(
        _collect_issue(
            conn,
            label="work_order_no 空值",
            where_clause="work_order_no IS NULL OR TRIM(work_order_no) = ''",
        )
    )
    issues.append(
        _collect_issue(
            conn,
            label="item_no 空值",
            where_clause="item_no IS NULL OR TRIM(item_no) = ''",
        )
    )
    issues.append(
        _collect_issue(
            conn,
            label="defect_desc 空值",
            where_clause="defect_desc IS NULL OR TRIM(defect_desc) = ''",
        )
    )
    issues.append(
        _collect_issue(
            conn,
            label="qty 無效（<= 0 或非數值）",
            where_clause="qty IS NULL OR CAST(qty AS INTEGER) <= 0",
        )
    )
    issues.append(
        _collect_issue(
            conn,
            label="event_date 格式無效",
            where_clause=(
                "event_date IS NULL OR TRIM(event_date) = '' "
                "OR event_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' "
                "OR date(event_date) IS NULL"
            ),
        )
    )
    issues.append(
        _collect_issue(
            conn,
            label="event_date 晚於今天",
            where_clause=(
                "date(event_date) IS NOT NULL "
                "AND event_date > date('now', 'localtime')"
            ),
        )
    )
    issues.append(
        _collect_issue(
            conn,
            label="created_at 空值",
            where_clause="created_at IS NULL OR TRIM(created_at) = ''",
        )
    )
    issues.append(_collect_duplicate_issue(conn))
    return [issue for issue in issues if issue[1] > 0]


def _migrate_to_v3(conn: sqlite3.Connection) -> None:
    # v3 adds internal_work_order_no and updates unique index.
    # No preflight issues expected for adding a field with default empty.
    conn.execute("BEGIN")
    try:
        conn.execute("ALTER TABLE defect_records RENAME TO defect_records_legacy")
        conn.execute("DROP TRIGGER IF EXISTS trg_defect_records_no_future_insert")
        conn.execute("DROP TRIGGER IF EXISTS trg_defect_records_no_future_update")
        _create_v3_objects(conn)
        conn.execute(
            """
            INSERT INTO defect_records (
                id,
                defect_no,
                event_date,
                work_order_no,
                internal_work_order_no,
                item_no,
                product_name,
                qty,
                category,
                supplier_name,
                outsource_supplier_name,
                defect_desc,
                status,
                disposition,
                created_at
            )
            SELECT
                id,
                defect_no,
                event_date,
                work_order_no,
                '',
                item_no,
                product_name,
                qty,
                category,
                supplier_name,
                outsource_supplier_name,
                defect_desc,
                status,
                disposition,
                created_at
            FROM defect_records_legacy
            ORDER BY id ASC
            """
        )
        conn.execute("DROP TABLE defect_records_legacy")
        _set_user_version(conn, 3)

        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _create_v3_objects(conn: sqlite3.Connection) -> None:
    _create_v5_objects(conn)


def _migrate_to_v4(conn: sqlite3.Connection) -> None:
    # v4 adds transfer_slip_no and updates unique index.
    conn.execute("BEGIN")
    try:
        conn.execute("ALTER TABLE defect_records RENAME TO defect_records_legacy")
        conn.execute("DROP TRIGGER IF EXISTS trg_defect_records_no_future_insert")
        conn.execute("DROP TRIGGER IF EXISTS trg_defect_records_no_future_update")
        _create_v5_objects(conn)
        conn.execute(
            """
            INSERT INTO defect_records (
                id,
                defect_no,
                event_date,
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
                created_at
            )
            SELECT
                id,
                defect_no,
                event_date,
                work_order_no,
                internal_work_order_no,
                '',
                item_no,
                product_name,
                qty,
                category,
                supplier_name,
                outsource_supplier_name,
                defect_desc,
                status,
                disposition,
                created_at
            FROM defect_records_legacy
            ORDER BY id ASC
            """
        )
        conn.execute("DROP TABLE defect_records_legacy")
        _set_user_version(conn, 4)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _create_v5_objects(conn: sqlite3.Connection) -> None:
    conn.execute(SCHEMA)
    conn.execute(SUPPLIER_SCHEMA)
    conn.execute(UNIQUE_BUSINESS_INDEX_SQL)
    conn.execute(FUTURE_DATE_INSERT_TRIGGER_SQL)
    conn.execute(FUTURE_DATE_UPDATE_TRIGGER_SQL)


def _migrate_to_v5(conn: sqlite3.Connection) -> None:
    # v5 adds supplier_records table and seeds it from existing defect_records.
    conn.execute("BEGIN")
    try:
        _create_v5_objects(conn)
        
        # Seed Formal Suppliers
        conn.execute(
            """
            INSERT OR IGNORE INTO supplier_records (name, category, created_at)
            SELECT DISTINCT supplier_name, '正式供應商', datetime('now', 'localtime')
            FROM defect_records
            WHERE supplier_name IS NOT NULL AND TRIM(supplier_name) <> '' AND TRIM(supplier_name) <> 'N/A'
            """
        )
        
        # Seed Outsource Suppliers
        conn.execute(
            """
            INSERT OR IGNORE INTO supplier_records (name, category, created_at)
            SELECT DISTINCT outsource_supplier_name, '委外供應商', datetime('now', 'localtime')
            FROM defect_records
            WHERE outsource_supplier_name IS NOT NULL AND TRIM(outsource_supplier_name) <> '' AND TRIM(outsource_supplier_name) <> 'N/A'
            """
        )
        
        _set_user_version(conn, 5)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _migrate_to_v6(conn: sqlite3.Connection) -> None:
    # v6 adds responsibility field.
    conn.execute("BEGIN")
    try:
        conn.execute("ALTER TABLE defect_records RENAME TO defect_records_legacy")
        conn.execute("DROP TRIGGER IF EXISTS trg_defect_records_no_future_insert")
        conn.execute("DROP TRIGGER IF EXISTS trg_defect_records_no_future_update")
        _create_v6_objects(conn)
        conn.execute(
            """
            INSERT INTO defect_records (
                id,
                defect_no,
                event_date,
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
            )
            SELECT
                id,
                defect_no,
                event_date,
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
                '',
                created_at
            FROM defect_records_legacy
            ORDER BY id ASC
            """
        )
        conn.execute("DROP TABLE defect_records_legacy")
        _set_user_version(conn, 6)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _migrate_to_v7(conn: sqlite3.Connection) -> None:
    # v7 adds product_records table and seeds it from existing defect_records.
    conn.execute("BEGIN")
    try:
        _create_v7_objects(conn)
        
        # Seed Products from defect_records
        # For each item_no, we take the most recently used product_name (max id)
        conn.execute(
            """
            INSERT OR IGNORE INTO product_records (item_no, product_name, created_at)
            SELECT item_no, product_name, datetime('now', 'localtime')
            FROM (
                SELECT item_no, product_name, 
                       ROW_NUMBER() OVER (PARTITION BY item_no ORDER BY id DESC) as rn
                FROM defect_records
                WHERE item_no IS NOT NULL AND TRIM(item_no) <> ''
            ) t
            WHERE rn = 1
            """
        )
        
        _set_user_version(conn, 7)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _create_v7_objects(conn: sqlite3.Connection) -> None:
    _create_v8_objects(conn)


def _migrate_to_v8(conn: sqlite3.Connection) -> None:
    # v8 adds return_slip_type. Existing rows stay blank by business decision.
    conn.execute("BEGIN")
    try:
        if not _column_exists(conn, "defect_records", "return_slip_type"):
            conn.execute(
                "ALTER TABLE defect_records "
                "ADD COLUMN return_slip_type TEXT NOT NULL DEFAULT ''"
            )
        _create_v8_objects(conn)
        _set_user_version(conn, 8)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _migrate_to_v9(conn: sqlite3.Connection) -> None:
    # v9 adds ui_settings table.
    conn.execute("BEGIN")
    try:
        conn.execute(SETTINGS_SCHEMA)
        _set_user_version(conn, 9)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _migrate_to_v10(conn: sqlite3.Connection) -> None:
    # v10 re-numbers all existing defect_no to NCR-#### format
    conn.execute("BEGIN")
    try:
        # First pass: rename to a temporary safe prefix to avoid UNIQUE constraint conflicts
        conn.execute("UPDATE defect_records SET defect_no = 'TEMP-NCR-' || id")
        
        # Second pass: renumber starting from 10001, ordered by event_date, then id
        cursor = conn.execute("SELECT id FROM defect_records ORDER BY event_date ASC, id ASC")
        rows = cursor.fetchall()
        
        sequence = 10001
        for row in rows:
            new_no = f"NCR-{sequence}"
            conn.execute(
                "UPDATE defect_records SET defect_no = ? WHERE id = ?",
                (new_no, row["id"])
            )
            sequence += 1
            
        _set_user_version(conn, 10)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _migrate_to_v11(conn: sqlite3.Connection) -> None:
    # v11 normalizes legacy disposition values to "重工".
    conn.execute("BEGIN")
    try:
        conn.execute(
            """
            UPDATE defect_records
            SET disposition = '重工'
            WHERE TRIM(disposition) IN ('退貨', '換料', '特採')
            """
        )
        _set_user_version(conn, 11)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


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


def _format_preflight_failure(issues: list[tuple[str, int, list[int]]]) -> str:
    detail_lines = []
    for label, count, sample_ids in issues:
        sample = ", ".join(str(sample_id) for sample_id in sample_ids) or "無"
        detail_lines.append(f"- {label}：{count} 筆（樣本 ID：{sample}）")
    details = "\n".join(detail_lines)
    return (
        "資料庫升級已中止：偵測到不符合新防呆約束的舊資料。\n"
        "請先修正資料後再重新啟動。\n"
        f"{details}"
    )


def _migrate_to_v2(conn: sqlite3.Connection) -> None:
    issues = _run_preflight_checks(conn)
    if issues:
        raise DatabaseMigrationError(_format_preflight_failure(issues))

    conn.execute("BEGIN")
    try:
        conn.execute("ALTER TABLE defect_records RENAME TO defect_records_legacy")
        conn.execute("DROP TRIGGER IF EXISTS trg_defect_records_no_future_insert")
        conn.execute("DROP TRIGGER IF EXISTS trg_defect_records_no_future_update")
        _create_v2_objects(conn)
        conn.execute(
            """
            INSERT INTO defect_records (
                id,
                defect_no,
                event_date,
                work_order_no,
                item_no,
                product_name,
                qty,
                category,
                supplier_name,
                outsource_supplier_name,
                defect_desc,
                status,
                disposition,
                created_at
            )
            SELECT
                id,
                TRIM(defect_no),
                event_date,
                TRIM(work_order_no),
                TRIM(item_no),
                TRIM(COALESCE(product_name, '')),
                CAST(qty AS INTEGER),
                TRIM(COALESCE(category, '')),
                TRIM(COALESCE(supplier_name, '')),
                TRIM(COALESCE(outsource_supplier_name, '')),
                TRIM(defect_desc),
                TRIM(COALESCE(status, '')),
                TRIM(COALESCE(disposition, '')),
                TRIM(created_at)
            FROM defect_records_legacy
            ORDER BY id ASC
            """
        )
        conn.execute("DROP TABLE defect_records_legacy")
        _set_user_version(conn, 2)

        conn.commit()
    except Exception:
        conn.rollback()
        raise


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
        connection.close()
        raise
