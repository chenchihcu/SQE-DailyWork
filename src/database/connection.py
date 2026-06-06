"""Database connection and bootstrap for SQETOOL v2 local SQLite."""

from __future__ import annotations

import sqlite3
import shutil
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "sqe_v2.db"
LEGACY_DB_PATH = DATA_DIR / "sqe.db"


def _backup_database_file(path: Path, *, reason: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_name(
        f"{path.stem}_backup_{reason}_{stamp}{path.suffix}"
    )
    shutil.copy2(path, backup_path)
    return backup_path


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Create SQLite connection with row mapping and foreign key support."""
    target = db_path or DB_PATH
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def initialize_database() -> dict:
    """Initialize v2 schema and migrate legacy data once when needed."""
    from database.migration import migrate_legacy_data_if_needed
    from database.repository import (
        ANOMALY_NO_RECODE_META_KEY,
        SUPPLIER_CONSOLIDATION_META_KEY,
        consolidate_suppliers,
        create_schema,
        get_migration_meta,
        recode_anomaly_numbers,
        seed_products_from_anomalies,
        sync_all_product_stages_to_events_once,
        upsert_migration_meta,
    )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with get_connection(DB_PATH) as conn:
        create_schema(conn)

    report = migrate_legacy_data_if_needed(DB_PATH, LEGACY_DB_PATH)
    with get_connection(DB_PATH) as conn:
        anomaly_no_recode = recode_anomaly_numbers(
            conn,
            apply=True,
            rewrite_text=True,
            migration_meta_key=ANOMALY_NO_RECODE_META_KEY,
        )
        seed_report = seed_products_from_anomalies(conn)
        supplier_consolidation: dict = {
            "applied": False,
            "changed": False,
            "skipped": True,
            "reason": "already_migrated",
            "backup_path": "",
        }
        if get_migration_meta(conn, SUPPLIER_CONSOLIDATION_META_KEY) != "1":
            preview_report = consolidate_suppliers(conn, apply=False)
            if bool(preview_report.get("changed")):
                backup_path = _backup_database_file(
                    DB_PATH,
                    reason="supplier_consolidation",
                )
                apply_report = consolidate_suppliers(conn, apply=True)
                upsert_migration_meta(conn, SUPPLIER_CONSOLIDATION_META_KEY, "1")
                supplier_consolidation = {
                    **apply_report,
                    "skipped": False,
                    "reason": "applied",
                    "preview": preview_report,
                    "backup_path": str(backup_path),
                }
            else:
                upsert_migration_meta(conn, SUPPLIER_CONSOLIDATION_META_KEY, "1")
                supplier_consolidation = {
                    **preview_report,
                    "applied": False,
                    "skipped": True,
                    "reason": "no_changes",
                    "backup_path": "",
                }
        product_stage_sync = sync_all_product_stages_to_events_once(conn)

        # NCR (不良品追蹤) 資料庫一次性遷移
        from database.ncr_migration import migrate_ncr_data_once
        ncr_db = PROJECT_ROOT / "ncr" / "data" / "defect.db"
        ncr_migration_report = migrate_ncr_data_once(conn, ncr_db)

    report["anomaly_no_recode"] = anomaly_no_recode
    report["product_seed"] = seed_report
    report["supplier_consolidation"] = supplier_consolidation
    report["supplier_consolidation_backup_path"] = str(
        supplier_consolidation.get("backup_path") or ""
    )
    report["product_stage_sync"] = product_stage_sync
    report["ncr_migration"] = ncr_migration_report
    if report.get("migrated"):
        print(f"Migrated legacy data from {LEGACY_DB_PATH} -> {DB_PATH}")
    return report


if __name__ == "__main__":
    initialize_database()
