"""NCR (defect.db) to sqe_v2.db one-time migration helper."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from database.repository import upsert_migration_meta


NCR_MIGRATION_META_KEY = "ncr_defect_db_migrated_v1"

DEFECT_COLUMNS = (
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


def _connect_source(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _count_rows(conn: sqlite3.Connection, table_name: str) -> int:
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])
    except sqlite3.Error:
        return 0


def _table_counts(conn: sqlite3.Connection, table_names: tuple[str, ...]) -> dict[str, int]:
    return {table_name: _count_rows(conn, table_name) for table_name in table_names}


def _row_value(row: sqlite3.Row, key: str, default: Any = "") -> Any:
    return row[key] if key in row.keys() and row[key] is not None else default


def _processing_line_value(row: sqlite3.Row) -> str:
    value = str(_row_value(row, "processing_line", "未分流") or "").strip()
    return value if value in {"原物料", "委外加工", "未分流"} else "未分流"


def _archive_path(path: Path) -> Path:
    preferred = path.with_name("defect.db.migrated")
    if not preferred.exists():
        return preferred
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return path.with_name(f"defect.db.migrated.{stamp}")


def _all_source_defects_exist(
    conn: sqlite3.Connection,
    defect_nos: list[str],
) -> tuple[bool, list[str]]:
    if not defect_nos:
        return True, []
    placeholders = ", ".join("?" for _ in defect_nos)
    rows = conn.execute(
        f"""
        SELECT defect_no
        FROM defect_records
        WHERE defect_no IN ({placeholders})
        """,
        defect_nos,
    ).fetchall()
    found = {str(row["defect_no"]) for row in rows}
    missing = [defect_no for defect_no in defect_nos if defect_no not in found]
    return not missing, missing


def migrate_ncr_data_once(
    v2_conn: sqlite3.Connection,
    ncr_db_path: Path,
    *,
    dry_run: bool = False,
    archive: bool = True,
) -> dict[str, Any]:
    """Migrate legacy NCR data into the SQE DailyWork main database.

    The source database is opened read-only. The old file is archived only after
    every source defect number is visible in the destination database.
    """
    report: dict[str, Any] = {
        "migrated": False,
        "dry_run": dry_run,
        "source_path": str(ncr_db_path),
        "archive_path": "",
        "source_exists": ncr_db_path.exists(),
        "source_counts": {},
        "target_before": _table_counts(
            v2_conn,
            ("defect_records", "supplier_records", "product_records", "ui_settings"),
        ),
        "target_after": {},
        "would_insert_defect_records": 0,
        "inserted_defect_records": 0,
        "duplicate_defect_records": 0,
        "suppliers_seen": 0,
        "products_seen": 0,
        "ui_settings_seen": 0,
        "missing_defect_nos": [],
        "errors": [],
    }

    src_conn = None
    try:
        if not ncr_db_path.exists():
            report["target_after"] = report["target_before"]
            return report

        try:
            src_conn = _connect_source(ncr_db_path)
        except sqlite3.Error as exc:
            report["errors"].append(f"Failed to open source defect.db read-only: {exc}")
            report["target_after"] = report["target_before"]
            return report

        try:
            src_suppliers = src_conn.execute(
                "SELECT name, category, created_at FROM supplier_records"
            ).fetchall()
            src_products = src_conn.execute(
                "SELECT item_no, product_name, created_at FROM product_records"
            ).fetchall()
            src_defects = src_conn.execute("SELECT * FROM defect_records").fetchall()
            src_settings = src_conn.execute(
                "SELECT setting_key, setting_value FROM ui_settings"
            ).fetchall()

            report["source_counts"] = {
                "supplier_records": len(src_suppliers),
                "product_records": len(src_products),
                "defect_records": len(src_defects),
                "ui_settings": len(src_settings),
            }
            report["suppliers_seen"] = len(src_suppliers)
            report["products_seen"] = len(src_products)
            report["ui_settings_seen"] = len(src_settings)

            source_defect_nos = [str(row["defect_no"]) for row in src_defects]
            existing_rows = v2_conn.execute(
                """
                SELECT defect_no
                FROM defect_records
                WHERE defect_no IS NOT NULL AND TRIM(defect_no) <> ''
                """
            ).fetchall()
            existing_defect_nos = {str(row["defect_no"]) for row in existing_rows}
            duplicate_nos = [
                defect_no
                for defect_no in source_defect_nos
                if defect_no in existing_defect_nos
            ]
            report["duplicate_defect_records"] = len(duplicate_nos)
            report["would_insert_defect_records"] = len(src_defects) - len(duplicate_nos)

            if dry_run:
                report["target_after"] = report["target_before"]
                return report

            for row in src_suppliers:
                name = str(_row_value(row, "name")).strip()
                if not name:
                    continue
                created_at = _row_value(row, "created_at", "")
                v2_conn.execute(
                    """
                    INSERT INTO suppliers (id, supplier_name, created_at, updated_at, is_active)
                    VALUES (lower(hex(randomblob(16))), ?, COALESCE(NULLIF(?, ''), datetime('now', 'localtime')), datetime('now', 'localtime'), 1)
                    ON CONFLICT(supplier_name) DO NOTHING
                    """,
                    (name, created_at),
                )

            for row in src_products:
                item_no = str(_row_value(row, "item_no")).strip()
                product_name = str(_row_value(row, "product_name")).strip()
                if not item_no or not product_name:
                    continue
                created_at = _row_value(row, "created_at", "")
                existing = v2_conn.execute(
                    """
                    SELECT id
                    FROM products
                    WHERE product_code = ? AND is_active = 1
                    LIMIT 1
                    """,
                    (item_no,),
                ).fetchone()
                if existing:
                    v2_conn.execute(
                        """
                        UPDATE products
                        SET product_name = ?, updated_at = datetime('now', 'localtime')
                        WHERE id = ?
                        """,
                        (product_name, existing["id"]),
                    )
                else:
                    v2_conn.execute(
                        """
                        INSERT INTO products (
                            id, product_code, product_name, supplier_id, is_active,
                            created_at, updated_at, product_stage
                        )
                        VALUES (
                            lower(hex(randomblob(16))), ?, ?, NULL, 1,
                            COALESCE(NULLIF(?, ''), datetime('now', 'localtime')),
                            datetime('now', 'localtime'), '量產'
                        )
                        """,
                        (item_no, product_name, created_at),
                    )

            inserted_defects = 0
            placeholders = ", ".join("?" for _ in DEFECT_COLUMNS)
            column_names = ", ".join(DEFECT_COLUMNS)
            for row in src_defects:
                before_changes = v2_conn.total_changes
                values = [
                    _row_value(row, "defect_no"),
                    _row_value(row, "event_date"),
                    _processing_line_value(row),
                    _row_value(row, "return_slip_type"),
                    _row_value(row, "work_order_no"),
                    _row_value(row, "internal_work_order_no"),
                    _row_value(row, "transfer_slip_no"),
                    _row_value(row, "item_no"),
                    _row_value(row, "product_name"),
                    _row_value(row, "qty", 0),
                    _row_value(row, "category"),
                    _row_value(row, "supplier_name"),
                    _row_value(row, "outsource_supplier_name"),
                    _row_value(row, "defect_desc"),
                    _row_value(row, "status", "處理中"),
                    _row_value(row, "disposition"),
                    _row_value(row, "responsibility"),
                    _row_value(row, "created_at", datetime.now().isoformat(timespec="seconds")),
                ]
                v2_conn.execute(
                    f"""
                    INSERT OR IGNORE INTO defect_records ({column_names})
                    VALUES ({placeholders})
                    """,
                    values,
                )
                if v2_conn.total_changes > before_changes:
                    inserted_defects += 1
            report["inserted_defect_records"] = inserted_defects

            for row in src_settings:
                v2_conn.execute(
                    """
                    INSERT INTO ui_settings (setting_key, setting_value)
                    VALUES (?, ?)
                    ON CONFLICT(setting_key) DO UPDATE SET
                        setting_value = excluded.setting_value
                    """,
                    (row["setting_key"], row["setting_value"]),
                )

            all_present, missing = _all_source_defects_exist(v2_conn, source_defect_nos)
            report["missing_defect_nos"] = missing
            if not all_present:
                raise sqlite3.IntegrityError(
                    "Source defects missing after insert: " + ", ".join(missing)
                )

            upsert_migration_meta(v2_conn, NCR_MIGRATION_META_KEY, "1")
            v2_conn.commit()
            report["migrated"] = True
            report["target_after"] = _table_counts(
                v2_conn,
                ("defect_records", "supplier_records", "product_records", "ui_settings"),
            )
        except sqlite3.Error as exc:
            v2_conn.rollback()
            report["errors"].append(f"Database error during migration: {exc}")
            report["target_after"] = _table_counts(
                v2_conn,
                ("defect_records", "supplier_records", "product_records", "ui_settings"),
            )
    finally:
        if src_conn is not None:
            src_conn.close()

    if report["migrated"] and archive:
        try:
            archive_path = _archive_path(ncr_db_path)
            ncr_db_path.rename(archive_path)
            report["archive_path"] = str(archive_path)
            report["source_exists"] = ncr_db_path.exists()
        except OSError as exc:
            report["errors"].append(f"Failed to archive defect.db: {exc}")

    return report
