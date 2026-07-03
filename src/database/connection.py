"""Database connection and bootstrap for SQE DailyWork v2 local SQLite."""

from __future__ import annotations

import logging
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


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


class ClosingConnection(sqlite3.Connection):
    """A sqlite3.Connection subclass that guarantees close() is called upon exiting context."""
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Let the base class handle commit / rollback first.
        result = super().__exit__(exc_type, exc_val, exc_tb)
        # Always close the connection when leaving the with-block.
        try:
            self.close()
        except Exception as exc:
            logger.debug("Error closing connection: %s", exc)
        return result


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Create SQLite connection with row mapping and foreign key support."""
    target = db_path or DB_PATH
    conn = sqlite3.connect(target, factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def initialize_database() -> dict:
    """Initialize v2 schema and migrate legacy data once when needed."""
    from database.migration import migrate_legacy_data_if_needed
    from database.repository import (
        ANOMALY_NO_RECODE_META_KEY,
        SUPPLIER_CONSOLIDATION_META_KEY,
        align_legacy_anomaly_categories,
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

        # 對齊舊版異常分類資料與現行 UI 選項
        aligned_count = align_legacy_anomaly_categories(conn)

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
    report["align_legacy_categories"] = aligned_count
    report["ncr_migration"] = ncr_migration_report
    if report.get("migrated"):
        logger.info("已將 Legacy 資料從 %s 遷移至 %s", LEGACY_DB_PATH, DB_PATH)
    return report


if __name__ == "__main__":
    initialize_database()
