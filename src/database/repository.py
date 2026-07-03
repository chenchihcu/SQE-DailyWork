"""SQLite repository for SQE DailyWork v2 minimalist desktop workflow."""

from __future__ import annotations

import logging
import sqlite3
import re
import uuid

logger = logging.getLogger(__name__)
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from database.product_stage import (
    PRODUCT_STAGE_MASS_PRODUCTION,
    PRODUCT_STAGE_OPTIONS,
)
from database.repo_helpers import (
    # ── Constants (keep in sync with source) ──
    SUPPLIER_CONSOLIDATION_META_KEY,
    PRODUCT_STAGE_SYNC_META_KEY,
    DEFAULT_STAGE_CHANGED_BY,
    STAGE_SYNC_SCOPE_ALL_HISTORY,
    VISIT_TECH_TRANSFER_ITEM_COLUMNS,
    TECH_TRANSFER_STATE_YES,
    TECH_TRANSFER_STATE_NO,
    TECH_TRANSFER_STATE_NA,
    TECH_TRANSFER_STATE_VALUES,
    VISIT_TECH_TRANSFER_STATE_COLUMNS,
    EVENT_SCOPE_VISIT_ONLY,
    EVENT_SCOPE_VISIT_WITH_ANOMALY,
    EVENT_SCOPE_ANOMALY_ONLY,
    EVENT_SCOPE_CLOSED_ONLY,
    EVENT_SCOPE_VALUES,
    DEFECT_NOTE_IMPROVED,
    DEFECT_NOTE_PENDING_IMPROVEMENT,
    # ── TypedDicts ──
    SupplierDeleteFailure,
    SupplierDeleteResult,
    ProductStageSyncReport,
    ProductStageSyncOnceReport,
    # ── Functions ──
    upsert_migration_meta,
    get_migration_meta,
    # ── Internal helpers (not re-exported; used only within repository.py) ──
    _SUPPLIER_SUFFIX_PATTERN,
    _table_exists,
    _table_columns,
    _quote_identifier,
    _now_iso,
    _today_iso,
    _gen_id,
    _as_int,
    _normalize_date,
    _normalize_strict_iso_date,
    _ensure_date_not_in_future,
    _normalize_non_negative_int,
    _normalize_month,
    _month_from_date_value,
    _normalize_product_stage,
    _normalize_product_stage_for_read,
    _normalize_tech_transfer_state,
    _resolve_tech_transfer_states,
    _normalized_lookup_text,
    _register_unique_lookup_key,
    _build_product_lookup_by_supplier_and_name,
)


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS suppliers (
            id TEXT PRIMARY KEY,
            supplier_name TEXT NOT NULL UNIQUE,
            contact_name TEXT NOT NULL DEFAULT '',
            department TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            contact_email TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '正式供應商',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_suppliers_active ON suppliers(is_active);

        CREATE TABLE IF NOT EXISTS supplier_contacts (
            id TEXT PRIMARY KEY,
            supplier_id TEXT NOT NULL,
            contact_name TEXT NOT NULL,
            department TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            is_primary INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        );
        CREATE INDEX IF NOT EXISTS idx_supplier_contacts_supplier ON supplier_contacts(supplier_id);

        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            product_code TEXT NOT NULL,
            product_name TEXT NOT NULL,
            product_stage TEXT NOT NULL DEFAULT '量產',
            supplier_id TEXT,
            secondary_supplier_id TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
            FOREIGN KEY (secondary_supplier_id) REFERENCES suppliers(id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_products_global_code
            ON products(product_code)
            WHERE supplier_id IS NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_products_supplier_code
            ON products(supplier_id, product_code)
            WHERE supplier_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_products_supplier ON products(supplier_id);
        CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active);

        CREATE TABLE IF NOT EXISTS anomalies (
            id TEXT PRIMARY KEY,
            anomaly_no TEXT NOT NULL UNIQUE,
            anomaly_date TEXT NOT NULL,
            supplier_id TEXT NOT NULL,
            visit_id TEXT,
            product_id TEXT,
            problem_desc TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '',
            product_lot_no TEXT NOT NULL DEFAULT '',
            product_name TEXT NOT NULL DEFAULT '',
            product_stage TEXT NOT NULL DEFAULT '量產',
            outsource_work_order TEXT NOT NULL DEFAULT '',
            batch_qty INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT '待處理' CHECK (status IN ('待處理','已結案')),
            improvement_desc TEXT NOT NULL DEFAULT '',
            closed_by TEXT NOT NULL DEFAULT '',
            root_cause_category TEXT NOT NULL DEFAULT '',
            closed_at TEXT,
            pending_items TEXT NOT NULL DEFAULT '',
            responsible_person TEXT NOT NULL DEFAULT '',
            due_date TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
            FOREIGN KEY (visit_id) REFERENCES visits(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
        CREATE INDEX IF NOT EXISTS idx_anomalies_date ON anomalies(anomaly_date);
        CREATE INDEX IF NOT EXISTS idx_anomalies_supplier ON anomalies(supplier_id);
        CREATE INDEX IF NOT EXISTS idx_anomalies_status ON anomalies(status);

        CREATE TABLE IF NOT EXISTS visits (
            id TEXT PRIMARY KEY,
            visit_date TEXT NOT NULL,
            supplier_id TEXT NOT NULL,
            product_id TEXT,
            product_name TEXT NOT NULL DEFAULT '',
            product_stage TEXT NOT NULL DEFAULT '量產',
            visitor_name TEXT NOT NULL DEFAULT '',
            summary TEXT NOT NULL DEFAULT '',
            work_order_no TEXT NOT NULL DEFAULT '',
            production_qty INTEGER NOT NULL DEFAULT 0,
            tech_transfer INTEGER NOT NULL DEFAULT 0,
            tech_transfer_doc INTEGER NOT NULL DEFAULT 0,
            carrier_requirement INTEGER NOT NULL DEFAULT 0,
            dispensing_process INTEGER NOT NULL DEFAULT 0,
            functional_test INTEGER NOT NULL DEFAULT 0,
            packaging_requirement INTEGER NOT NULL DEFAULT 0,
            tech_transfer_doc_state TEXT NOT NULL DEFAULT 'no',
            carrier_requirement_state TEXT NOT NULL DEFAULT 'no',
            dispensing_process_state TEXT NOT NULL DEFAULT 'no',
            functional_test_state TEXT NOT NULL DEFAULT 'no',
            packaging_requirement_state TEXT NOT NULL DEFAULT 'no',
            status TEXT NOT NULL DEFAULT '已完成' CHECK (status='已完成'),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
        CREATE INDEX IF NOT EXISTS idx_visits_date ON visits(visit_date);
        CREATE INDEX IF NOT EXISTS idx_visits_supplier ON visits(supplier_id);

        CREATE TABLE IF NOT EXISTS visit_product_sections (
            id TEXT PRIMARY KEY,
            visit_id TEXT NOT NULL,
            product_id TEXT,
            product_code TEXT NOT NULL DEFAULT '',
            product_name TEXT NOT NULL DEFAULT '',
            product_stage TEXT NOT NULL DEFAULT '量產',
            time_slot TEXT NOT NULL DEFAULT '',
            work_order_no TEXT NOT NULL DEFAULT '',
            production_qty INTEGER NOT NULL DEFAULT 0,
            summary TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (visit_id) REFERENCES visits(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
        CREATE INDEX IF NOT EXISTS idx_visit_product_sections_visit
            ON visit_product_sections(visit_id, sort_order);
        CREATE INDEX IF NOT EXISTS idx_visit_product_sections_product
            ON visit_product_sections(product_id);

        CREATE TABLE IF NOT EXISTS visit_defect_notes (
            id TEXT PRIMARY KEY,
            visit_id TEXT NOT NULL,
            visit_product_section_id TEXT,
            defect_desc TEXT NOT NULL,
            improvement_desc TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            confirmed_anomaly_id TEXT,
            confirmed_at TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (visit_id) REFERENCES visits(id),
            FOREIGN KEY (visit_product_section_id) REFERENCES visit_product_sections(id),
            FOREIGN KEY (confirmed_anomaly_id) REFERENCES anomalies(id)
        );
        CREATE INDEX IF NOT EXISTS idx_visit_defect_notes_visit
            ON visit_defect_notes(visit_id, sort_order);
        CREATE INDEX IF NOT EXISTS idx_visit_defect_notes_section
            ON visit_defect_notes(visit_product_section_id, sort_order);

        CREATE TABLE IF NOT EXISTS monthly_stats_cache (
            yyyymm TEXT PRIMARY KEY,
            visit_count INTEGER NOT NULL DEFAULT 0,
            closed_anomaly_count INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS migration_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS product_stage_change_logs (
            id TEXT PRIMARY KEY,
            product_id TEXT NOT NULL,
            from_stage TEXT NOT NULL,
            to_stage TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            changed_by TEXT NOT NULL DEFAULT 'local_user',
            sync_scope TEXT NOT NULL DEFAULT 'all_history_and_future',
            anomalies_updated INTEGER NOT NULL DEFAULT 0,
            visits_updated INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
        CREATE INDEX IF NOT EXISTS idx_stage_logs_product_changed_at
            ON product_stage_change_logs(product_id, changed_at DESC);
        CREATE INDEX IF NOT EXISTS idx_stage_logs_changed_at
            ON product_stage_change_logs(changed_at DESC);

        CREATE TABLE IF NOT EXISTS import_batches (
            id TEXT PRIMARY KEY,
            import_type TEXT NOT NULL,
            source_file TEXT NOT NULL DEFAULT '',
            source_path TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL CHECK(status IN ('completed','blocked','skipped')),
            total_rows INTEGER NOT NULL DEFAULT 0,
            added_count INTEGER NOT NULL DEFAULT 0,
            updated_count INTEGER NOT NULL DEFAULT 0,
            supplier_created_count INTEGER NOT NULL DEFAULT 0,
            skipped_count INTEGER NOT NULL DEFAULT 0,
            error_count INTEGER NOT NULL DEFAULT 0,
            backup_path TEXT NOT NULL DEFAULT '',
            message TEXT NOT NULL DEFAULT '',
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_import_batches_type_completed
            ON import_batches(import_type, completed_at DESC);

        CREATE TABLE IF NOT EXISTS import_batch_rows (
            id TEXT PRIMARY KEY,
            batch_id TEXT NOT NULL,
            row_number INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            product_code TEXT NOT NULL DEFAULT '',
            product_name TEXT NOT NULL DEFAULT '',
            supplier_name TEXT NOT NULL DEFAULT '',
            product_stage TEXT NOT NULL DEFAULT '',
            message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (batch_id) REFERENCES import_batches(id)
        );
        CREATE INDEX IF NOT EXISTS idx_import_batch_rows_batch
            ON import_batch_rows(batch_id, row_number);

        -- NCR (不良品追蹤) 整合 Table
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
        CREATE UNIQUE INDEX IF NOT EXISTS uniq_defect_records_business_key
            ON defect_records(event_date, work_order_no, internal_work_order_no, transfer_slip_no, item_no, defect_desc);
        CREATE INDEX IF NOT EXISTS idx_defect_records_status
            ON defect_records(status);
        CREATE INDEX IF NOT EXISTS idx_defect_records_event_date
            ON defect_records(event_date);

        CREATE TABLE IF NOT EXISTS ui_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL
        );
        """
    )
    _ensure_column(
        conn, "suppliers", "category", "TEXT NOT NULL DEFAULT '正式供應商'"
    )

    conn.executescript(
        """
        -- 共享品名主檔 VIEW 與 INSTEAD OF Triggers
        -- 用 DROP+CREATE（非 IF NOT EXISTS）：升級既有 DB 時會重建 VIEW，
        -- 並 cascade-drop 舊版 trigger，藉此替換掉下方修正前的損壞 trigger。
        DROP VIEW IF EXISTS product_records;
        CREATE VIEW product_records AS
        SELECT
            id,
            product_code AS item_no,
            product_name,
            created_at
        FROM products;

        -- 內層採「純 INSERT」不帶 ON CONFLICT：products.product_code 僅有部分唯一索引
        -- （idx_products_global_code WHERE supplier_id IS NULL），無法作為 ON CONFLICT 目標
        -- （否則 INSERT 會拋 OperationalError: ON CONFLICT clause does not match...）。
        -- 改由外層語句決定衝突策略，trigger 內層 INSERT 會繼承之：
        --   `INSERT INTO product_records ...`           -> 重複料號拋 UNIQUE constraint，
        --      供 create_product 轉成使用者可讀的「料號已存在」。
        --   `INSERT OR IGNORE INTO product_records ...`  -> 重複料號略過，
        --      供 sync_product_from_defect / insert_products_if_missing。
        -- 插入列的 supplier_id 預設為 NULL，故僅命中 global（共享品名主檔）唯一索引。
        CREATE TRIGGER IF NOT EXISTS trg_product_records_insert
        INSTEAD OF INSERT ON product_records
        BEGIN
            INSERT INTO products (id, product_code, product_name, created_at, updated_at, is_active)
            VALUES (
                COALESCE(NEW.id, hex(randomblob(16))),
                NEW.item_no,
                NEW.product_name,
                COALESCE(NEW.created_at, datetime('now', 'localtime')),
                datetime('now', 'localtime'),
                1
            );
        END;

        CREATE TRIGGER IF NOT EXISTS trg_product_records_update
        INSTEAD OF UPDATE ON product_records
        BEGIN
            UPDATE products
            SET product_code = NEW.item_no,
                product_name = NEW.product_name,
                updated_at = datetime('now', 'localtime')
            WHERE id = OLD.id;
        END;

        CREATE TRIGGER IF NOT EXISTS trg_product_records_delete
        INSTEAD OF DELETE ON product_records
        BEGIN
            DELETE FROM products WHERE id = OLD.id;
        END;

        -- 共享供應商主檔 VIEW 與 INSTEAD OF Triggers
        DROP VIEW IF EXISTS supplier_records;
        CREATE VIEW supplier_records AS
        SELECT
            id,
            supplier_name AS name,
            category,
            created_at
        FROM suppliers;

        CREATE TRIGGER IF NOT EXISTS trg_supplier_records_insert
        INSTEAD OF INSERT ON supplier_records
        BEGIN
            INSERT INTO suppliers (id, supplier_name, category, created_at, updated_at, is_active)
            VALUES (
                COALESCE(NEW.id, hex(randomblob(16))),
                NEW.name,
                COALESCE(NEW.category, '正式供應商'),
                COALESCE(NEW.created_at, datetime('now', 'localtime')),
                datetime('now', 'localtime'),
                1
            )
            ON CONFLICT(supplier_name) DO NOTHING;
        END;

        CREATE TRIGGER IF NOT EXISTS trg_supplier_records_update
        INSTEAD OF UPDATE ON supplier_records
        BEGIN
            UPDATE suppliers
            SET supplier_name = NEW.name,
                category = COALESCE(NEW.category, category),
                updated_at = datetime('now', 'localtime')
            WHERE id = OLD.id;
        END;

        CREATE TRIGGER IF NOT EXISTS trg_supplier_records_delete
        INSTEAD OF DELETE ON supplier_records
        BEGIN
            DELETE FROM suppliers WHERE id = OLD.id;
        END;
        """
    )
    _ensure_column(conn, "suppliers", "department", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "suppliers", "contact_email", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "products", "product_stage", "TEXT NOT NULL DEFAULT '量產'")
    _ensure_column(conn, "products", "secondary_supplier_id", "TEXT")
    _ensure_column(conn, "visit_defect_notes", "confirmed_anomaly_id", "TEXT")
    _ensure_column(conn, "visit_defect_notes", "confirmed_at", "TEXT")
    _ensure_column(conn, "anomalies", "product_lot_no", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "anomalies", "product_name", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "anomalies", "product_id", "TEXT")
    _ensure_column(conn, "anomalies", "product_stage", "TEXT NOT NULL DEFAULT '量產'")
    _ensure_column(
        conn, "anomalies", "outsource_work_order", "TEXT NOT NULL DEFAULT ''"
    )
    _ensure_column(conn, "anomalies", "batch_qty", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "anomalies", "visit_id", "TEXT REFERENCES visits(id)")
    _ensure_column(conn, "anomalies", "closed_by", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(
        conn, "anomalies", "root_cause_category", "TEXT NOT NULL DEFAULT ''"
    )
    _ensure_column(conn, "anomalies", "pending_items", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(
        conn, "anomalies", "responsible_person", "TEXT NOT NULL DEFAULT ''"
    )
    _ensure_column(conn, "anomalies", "due_date", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "visits", "product_id", "TEXT")
    _ensure_column(conn, "visits", "product_name", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "visits", "product_stage", "TEXT NOT NULL DEFAULT '量產'")
    _ensure_column(conn, "visits", "visitor_name", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "visits", "tech_transfer_doc", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "visits", "carrier_requirement", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "visits", "dispensing_process", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "visits", "functional_test", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "visits", "packaging_requirement", "INTEGER NOT NULL DEFAULT 0")
    for state_col in VISIT_TECH_TRANSFER_STATE_COLUMNS:
        _ensure_column(conn, "visits", state_col, "TEXT NOT NULL DEFAULT 'no'")
    if get_migration_meta(conn, "tech_transfer_state_backfill_v1") != "1":
        for legacy_col, state_col in zip(
            VISIT_TECH_TRANSFER_ITEM_COLUMNS,
            VISIT_TECH_TRANSFER_STATE_COLUMNS,
        ):
            conn.execute(
                f"UPDATE visits SET {state_col} = 'yes' "
                f"WHERE {legacy_col} = 1 AND {state_col} = 'no'"
            )
        upsert_migration_meta(conn, "tech_transfer_state_backfill_v1", "1")
    _ensure_index(conn, "idx_anomalies_visit", "anomalies", "visit_id")
    _ensure_index(conn, "idx_anomalies_product", "anomalies", "product_id")
    _ensure_index(conn, "idx_visits_product", "visits", "product_id")
    _ensure_product_indexes(conn)
    _normalize_event_status_tables(conn)
    _normalize_defect_records_optional_work_order(conn)
    _remove_products_spec_desc_column_if_present(conn)
    _ensure_index(conn, "idx_anomalies_date", "anomalies", "anomaly_date")
    _ensure_index(conn, "idx_anomalies_supplier", "anomalies", "supplier_id")
    _ensure_index(conn, "idx_anomalies_status", "anomalies", "status")
    _ensure_index(conn, "idx_visits_date", "visits", "visit_date")
    _ensure_index(conn, "idx_visits_supplier", "visits", "supplier_id")
    _backfill_visit_product_sections(conn)
    _ensure_column(conn, "anomalies", "rc_supplier_inventory", "TEXT NOT NULL DEFAULT 'unconfirmed'")
    _ensure_column(conn, "anomalies", "rc_supplier_wip", "TEXT NOT NULL DEFAULT 'unconfirmed'")
    _ensure_column(conn, "anomalies", "rc_in_transit", "TEXT NOT NULL DEFAULT 'unconfirmed'")
    _ensure_column(conn, "anomalies", "rc_internal_inventory", "TEXT NOT NULL DEFAULT 'unconfirmed'")
    _ensure_column(conn, "anomalies", "is_tech_transfer", "INTEGER NOT NULL DEFAULT 0")
    conn.execute(
        """
        UPDATE products
        SET product_stage = '量產'
        WHERE trim(coalesce(product_stage, '')) NOT IN ('量產', '試產')
        """
    )
    conn.execute(
        """
        UPDATE products
        SET secondary_supplier_id = NULL
        WHERE trim(coalesce(secondary_supplier_id, '')) = ''
        """
    )
    conn.execute(
        """
        UPDATE products
        SET secondary_supplier_id = NULL
        WHERE secondary_supplier_id = supplier_id
        """
    )
    conn.commit()


def _insert_product_stage_change_log(
    conn: sqlite3.Connection,
    *,
    product_id: str,
    from_stage: str,
    to_stage: str,
    reason: str,
    changed_by: str,
    sync_scope: str,
    anomalies_updated: int,
    visits_updated: int,
) -> None:
    conn.execute(
        """
        INSERT INTO product_stage_change_logs(
            id,
            product_id,
            from_stage,
            to_stage,
            reason,
            changed_at,
            changed_by,
            sync_scope,
            anomalies_updated,
            visits_updated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _gen_id(),
            product_id,
            from_stage,
            to_stage,
            reason.strip(),
            _now_iso(),
            changed_by.strip() or DEFAULT_STAGE_CHANGED_BY,
            sync_scope.strip() or STAGE_SYNC_SCOPE_ALL_HISTORY,
            int(anomalies_updated),
            int(visits_updated),
        ),
    )


def sync_product_stage_to_events(
    conn: sqlite3.Connection,
    product_id: str,
) -> dict[str, int]:
    product_key = (product_id or "").strip()
    if not product_key:
        raise ValueError("Product id is required")
    product = get_product(conn, product_key)
    if product is None:
        raise ValueError("Product not found")
    canonical_name = str(product.get("product_name") or "").strip()
    canonical_stage = _normalize_product_stage_for_read(product.get("product_stage"))
    now_iso = _now_iso()
    anomaly_cur = conn.execute(
        """
        UPDATE anomalies
        SET product_name = ?,
            product_stage = ?,
            updated_at = ?
        WHERE product_id = ?
          AND (
                trim(coalesce(product_name, '')) <> ?
             OR trim(coalesce(product_stage, '')) <> ?
          )
        """,
        (
            canonical_name,
            canonical_stage,
            now_iso,
            product_key,
            canonical_name,
            canonical_stage,
        ),
    )
    visit_cur = conn.execute(
        """
        UPDATE visits
        SET product_name = ?,
            product_stage = ?,
            updated_at = ?
        WHERE product_id = ?
          AND (
                trim(coalesce(product_name, '')) <> ?
             OR trim(coalesce(product_stage, '')) <> ?
          )
        """,
        (
            canonical_name,
            canonical_stage,
            now_iso,
            product_key,
            canonical_name,
            canonical_stage,
        ),
    )
    return {
        "anomalies_updated": int(anomaly_cur.rowcount),
        "visits_updated": int(visit_cur.rowcount),
    }


def _backfill_event_product_links_by_name(
    conn: sqlite3.Connection,
    *,
    table_name: str,
    lookup: dict[tuple[str, str], str | None],
) -> dict[str, int]:
    row_id_field = "anomaly_no" if table_name == "anomalies" else "id"
    rows = conn.execute(
        f"""
        SELECT
            id,
            supplier_id,
            trim(product_name) AS product_name
        FROM {table_name}
        WHERE (product_id IS NULL OR trim(product_id) = '')
          AND trim(product_name) <> ''
        ORDER BY {row_id_field}
        """
    ).fetchall()
    linked = 0
    skipped_ambiguous = 0
    skipped_not_found = 0
    for row in rows:
        supplier_id = _normalized_lookup_text(row["supplier_id"])
        product_name = _normalized_lookup_text(row["product_name"])
        key = (supplier_id, product_name)
        matched_product_id = lookup.get(key, "")
        if key not in lookup:
            skipped_not_found += 1
            continue
        if not matched_product_id:
            skipped_ambiguous += 1
            continue
        canonical_product = get_product(conn, str(matched_product_id)) or {}
        canonical_name = str(canonical_product.get("product_name") or product_name)
        canonical_stage = _normalize_product_stage_for_read(canonical_product.get("product_stage"))
        update_cur = conn.execute(
            f"""
            UPDATE {table_name}
            SET product_id = ?,
                product_name = ?,
                product_stage = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                str(matched_product_id),
                canonical_name,
                canonical_stage,
                _now_iso(),
                str(row["id"]),
            ),
        )
        if update_cur.rowcount > 0:
            linked += int(update_cur.rowcount)
    return {
        "linked": linked,
        "skipped_ambiguous": skipped_ambiguous,
        "skipped_not_found": skipped_not_found,
    }


def sync_all_product_stages_to_events(
    conn: sqlite3.Connection,
) -> ProductStageSyncReport:
    report: ProductStageSyncReport = {
        "applied": False,
        "product_link_updates": 0,
        "anomalies_stage_updates": 0,
        "visits_stage_updates": 0,
        "anomalies_backfilled_by_name": 0,
        "visits_backfilled_by_name": 0,
        "backfill_skipped_ambiguous": 0,
        "backfill_skipped_not_found": 0,
    }
    product_rows = conn.execute("SELECT id FROM products").fetchall()
    for row in product_rows:
        sync = sync_product_stage_to_events(conn, str(row["id"]))
        report["anomalies_stage_updates"] += int(sync["anomalies_updated"])
        report["visits_stage_updates"] += int(sync["visits_updated"])
    report["product_link_updates"] = int(
        report["anomalies_stage_updates"] + report["visits_stage_updates"]
    )

    lookup = _build_product_lookup_by_supplier_and_name(conn)
    anomaly_backfill = _backfill_event_product_links_by_name(
        conn, table_name="anomalies", lookup=lookup
    )
    visit_backfill = _backfill_event_product_links_by_name(
        conn, table_name="visits", lookup=lookup
    )
    report["anomalies_backfilled_by_name"] = int(anomaly_backfill["linked"])
    report["visits_backfilled_by_name"] = int(visit_backfill["linked"])
    report["backfill_skipped_ambiguous"] = int(
        anomaly_backfill["skipped_ambiguous"] + visit_backfill["skipped_ambiguous"]
    )
    report["backfill_skipped_not_found"] = int(
        anomaly_backfill["skipped_not_found"] + visit_backfill["skipped_not_found"]
    )
    report["applied"] = True
    conn.commit()
    return report


def sync_all_product_stages_to_events_once(
    conn: sqlite3.Connection,
) -> ProductStageSyncOnceReport:
    if get_migration_meta(conn, PRODUCT_STAGE_SYNC_META_KEY) == "1":
        return {
            "applied": False,
            "skipped": True,
            "reason": "already_migrated",
            "product_link_updates": 0,
            "anomalies_stage_updates": 0,
            "visits_stage_updates": 0,
            "anomalies_backfilled_by_name": 0,
            "visits_backfilled_by_name": 0,
            "backfill_skipped_ambiguous": 0,
            "backfill_skipped_not_found": 0,
        }
    sync_report = sync_all_product_stages_to_events(conn)
    upsert_migration_meta(conn, PRODUCT_STAGE_SYNC_META_KEY, "1")
    return {
        "applied": sync_report["applied"],
        "skipped": False,
        "reason": "",
        "product_link_updates": sync_report["product_link_updates"],
        "anomalies_stage_updates": sync_report["anomalies_stage_updates"],
        "visits_stage_updates": sync_report["visits_stage_updates"],
        "anomalies_backfilled_by_name": sync_report["anomalies_backfilled_by_name"],
        "visits_backfilled_by_name": sync_report["visits_backfilled_by_name"],
        "backfill_skipped_ambiguous": sync_report["backfill_skipped_ambiguous"],
        "backfill_skipped_not_found": sync_report["backfill_skipped_not_found"],
    }


def list_product_stage_change_logs(
    conn: sqlite3.Connection,
    *,
    product_id: str | None = None,
    limit: int = 200,
) -> list[dict]:
    normalized_product_id = (product_id or "").strip()
    try:
        normalized_limit = int(limit)
    except (TypeError, ValueError):
        normalized_limit = 200
    if normalized_limit <= 0:
        normalized_limit = 200
    params: list[Any] = []
    sql = """
        SELECT
            l.id AS id,
            l.product_id AS product_id,
            p.product_code AS product_code,
            p.product_name AS product_name,
            l.from_stage AS from_stage,
            l.to_stage AS to_stage,
            l.reason AS reason,
            l.changed_at AS changed_at,
            l.changed_by AS changed_by,
            l.sync_scope AS sync_scope,
            l.anomalies_updated AS anomalies_updated,
            l.visits_updated AS visits_updated
        FROM product_stage_change_logs l
        LEFT JOIN products p ON p.id = l.product_id
    """
    if normalized_product_id:
        sql += " WHERE l.product_id = ?"
        params.append(normalized_product_id)
    sql += " ORDER BY l.changed_at DESC, l.rowid DESC LIMIT ?"
    params.append(normalized_limit)
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


ANOMALY_NO_RECODE_META_KEY = "anomaly_no_scheme_yyyymmddnnn_v1"


def canonicalize_supplier_name(supplier_name: str) -> str:
    raw = str(supplier_name or "").strip()
    if not raw:
        return ""
    text = raw
    while True:
        trimmed = _SUPPLIER_SUFFIX_PATTERN.sub("", text).strip()
        if not trimmed:
            return text
        if trimmed == text:
            return trimmed
        text = trimmed


def _normalize_supplier_name_for_storage(supplier_name: str) -> str:
    raw = str(supplier_name or "").strip()
    if not raw:
        return ""
    canonical = canonicalize_supplier_name(raw)
    return canonical or raw


def align_legacy_anomaly_categories(conn: sqlite3.Connection) -> int:
    """Align legacy anomaly category names to the current standard options.

    Returns the total number of rows updated.
    """
    mapping = {
        "文件/SOP 不足": "規範文件缺漏",
        "文件/SOP不足": "規範文件缺漏",
        "人為操作疏失": "標準作業不落實",
        "物料/來料問題": "來料品質不良",
        "製程參數異常": "製程參數失控",
        "設計缺陷": "設計匹配不良",
    }
    changed_count = 0
    # Use TRIM to handle potential extra spaces in user input
    for old_val, new_val in mapping.items():
        # Update root_cause_category
        res1 = conn.execute(
            "UPDATE anomalies SET root_cause_category = ? WHERE TRIM(root_cause_category) = ?",
            (new_val, old_val),
        )
        changed_count += res1.rowcount
        
        # Update category
        res2 = conn.execute(
            "UPDATE anomalies SET category = ? WHERE TRIM(category) = ?",
            (new_val, old_val),
        )
        changed_count += res2.rowcount
        
    return changed_count


def recode_anomaly_numbers(
    conn: sqlite3.Connection,
    *,
    apply: bool = True,
    rewrite_text: bool = True,
    migration_meta_key: str | None = None,
) -> dict:
    has_meta_table = _table_exists(conn, "migration_meta")
    if (
        migration_meta_key
        and has_meta_table
        and get_migration_meta(conn, migration_meta_key) == "1"
    ):
        return {
            "applied": False,
            "skipped": True,
            "reason": "already_migrated",
            "table_reports": {},
            "key_changes": 0,
            "text_changes": 0,
            "text_columns": [],
        }

    target_specs = _resolve_anomaly_no_target_specs(conn)
    if not target_specs:
        return {
            "applied": False,
            "skipped": True,
            "reason": "no_target_tables",
            "table_reports": {},
            "key_changes": 0,
            "text_changes": 0,
            "text_columns": [],
        }

    table_reports: dict[str, dict[str, int]] = {}
    all_key_updates: list[dict[str, Any]] = []
    for spec in target_specs:
        rows = _build_recode_rows(conn, spec)
        changed = [item for item in rows if item["old_no"] != item["new_no"]]
        table_reports[spec["table"]] = {
            "rows": len(rows),
            "key_changes": len(changed),
        }
        all_key_updates.extend(changed)

    mapping_by_old = _build_old_to_new_mapping(all_key_updates)
    key_changes = len(all_key_updates)

    text_column_changes: list[dict[str, Any]] = []
    if not apply:
        text_column_changes = (
            _rewrite_text_columns(conn, mapping_by_old, apply=False)
            if rewrite_text
            else []
        )
        text_changes = sum(item["rows"] for item in text_column_changes)
        return {
            "applied": False,
            "skipped": False,
            "reason": "dry_run",
            "table_reports": table_reports,
            "key_changes": key_changes,
            "text_changes": text_changes,
            "text_columns": text_column_changes,
        }

    started_transaction = False
    text_column_changes = []
    try:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
            started_transaction = True
        _apply_key_updates(conn, all_key_updates)
        if rewrite_text:
            text_column_changes = _rewrite_text_columns(
                conn, mapping_by_old, apply=True
            )
        if migration_meta_key and has_meta_table:
            conn.execute(
                """
                INSERT INTO migration_meta(key, value, updated_at)
                VALUES (?, '1', CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = '1',
                    updated_at = CURRENT_TIMESTAMP
                """,
                (migration_meta_key,),
            )
        if started_transaction:
            conn.commit()
    except Exception:
        logger.exception("recode_anomaly_numbers failed")
        if started_transaction and conn.in_transaction:
            conn.rollback()
        raise

    text_changes = sum(item["rows"] for item in text_column_changes)
    return {
        "applied": True,
        "skipped": False,
        "reason": "",
        "table_reports": table_reports,
        "key_changes": key_changes,
        "text_changes": text_changes,
        "text_columns": text_column_changes,
    }


def _resolve_anomaly_no_target_specs(conn: sqlite3.Connection) -> list[dict[str, str]]:
    specs: list[dict[str, str]] = []

    anomalies_cols = _table_columns(conn, "anomalies")
    if {
        "anomaly_no",
        "anomaly_date",
    }.issubset(anomalies_cols):
        specs.append(
            {
                "table": "anomalies",
                "number_column": "anomaly_no",
                "date_column": "anomaly_date",
                "created_column": "created_at",
            }
        )

    issues_cols = _table_columns(conn, "issues")
    if {
        "issue_no",
        "issue_date",
    }.issubset(issues_cols):
        specs.append(
            {
                "table": "issues",
                "number_column": "issue_no",
                "date_column": "issue_date",
                "created_column": "created_at",
            }
        )
    return specs


def _build_recode_rows(conn: sqlite3.Connection, spec: dict[str, str]) -> list[dict[str, Any]]:
    table_name = spec["table"]
    number_column = spec["number_column"]
    date_column = spec["date_column"]
    created_column = spec["created_column"]
    table_columns = _table_columns(conn, table_name)
    created_expr = (
        _quote_identifier(created_column)
        if created_column in table_columns
        else "NULL"
    )
    rows = conn.execute(
        f"""
        SELECT
            rowid AS __rowid__,
            {_quote_identifier(number_column)} AS __old_no__,
            {_quote_identifier(date_column)} AS __event_date__,
            {created_expr} AS __created_at__
        FROM {_quote_identifier(table_name)}
        ORDER BY
            {_quote_identifier(date_column)} ASC,
            __created_at__ ASC,
            rowid ASC
        """
    ).fetchall()

    result: list[dict[str, Any]] = []
    current_day = ""
    seq = 0
    for row in rows:
        normalized_date = _normalize_date(
            row["__event_date__"], fallback=_today_iso()
        )
        day_key = normalized_date.replace("-", "")
        if day_key != current_day:
            current_day = day_key
            seq = 1
        else:
            seq += 1
        new_no = f"{day_key}{seq:03d}"
        result.append(
            {
                "table": table_name,
                "number_column": number_column,
                "rowid": int(row["__rowid__"]),
                "old_no": str(row["__old_no__"] or "").strip(),
                "new_no": new_no,
            }
        )
    return result


def _build_old_to_new_mapping(rows: list[dict[str, Any]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in rows:
        old_no = item["old_no"]
        new_no = item["new_no"]
        if not old_no or old_no == new_no:
            continue
        existing = mapping.get(old_no)
        if existing and existing != new_no:
            raise ValueError(f"Conflicting anomaly_no mapping for {old_no}")
        mapping[old_no] = new_no
    return mapping


def _apply_key_updates(conn: sqlite3.Connection, updates: list[dict[str, Any]]) -> None:
    """Apply anomaly_no/issue_no recoding with UNIQUE constraint collision retry.

    Uses a two-phase update (temp value -> final value) to avoid UNIQUE conflicts.
    If a collision occurs on the second phase (concurrent same-day same-seq),
    retries with a new sequence number.
    """
    if not updates:
        return

    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Phase 1: write temp values
            for item in updates:
                table_name = item["table"]
                number_column = item["number_column"]
                rowid = item["rowid"]
                tmp_value = f"__TMP_ANO__{uuid.uuid4().hex}__"
                conn.execute(
                    f"""
                    UPDATE {_quote_identifier(table_name)}
                    SET {_quote_identifier(number_column)} = ?
                    WHERE rowid = ?
                    """,
                    (tmp_value, rowid),
                )
            # Phase 2: write final values
            for item in updates:
                table_name = item["table"]
                number_column = item["number_column"]
                rowid = item["rowid"]
                conn.execute(
                    f"""
                    UPDATE {_quote_identifier(table_name)}
                    SET {_quote_identifier(number_column)} = ?
                    WHERE rowid = ?
                    """,
                    (item["new_no"], rowid),
                )
            return  # Success
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint failed" in str(exc) and attempt < max_retries - 1:
                # Collision on new_no: regenerate sequence for conflicting items and retry
                _regenerate_conflicting_nos(conn, updates)
                continue
            raise


def _regenerate_conflicting_nos(conn: sqlite3.Connection, updates: list[dict[str, Any]]) -> None:
    """Regenerate anomaly_no for items that hit UNIQUE collision.

    Groups by table and date, assigns fresh sequences starting from max existing + 1.
    """
    from collections import defaultdict

    # Resolve the per-table date/number columns once, not per item/group.
    specs = _resolve_anomaly_no_target_specs(conn)
    date_col_by_table = {s["table"]: s["date_column"] for s in specs}
    number_col_by_table = {s["table"]: s["number_column"] for s in specs}

    # Group updates by (table, date_column) to assign fresh sequences per day
    by_table_date: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for item in updates:
        table_name = item["table"]
        date_col = date_col_by_table.get(table_name)
        if not date_col:
            continue
        # Fetch the date for this rowid
        row = conn.execute(
            f"SELECT {_quote_identifier(date_col)} FROM {_quote_identifier(table_name)} WHERE rowid = ?",
            (item["rowid"],),
        ).fetchone()
        if row:
            day_key = _normalize_date(row[0]).replace("-", "")
            by_table_date[(table_name, day_key)].append(item)

    # Regenerate for each group
    for (table_name, day_key), group in by_table_date.items():
        number_col = number_col_by_table.get(table_name)
        if not number_col:
            continue
        # Find max existing sequence for this day
        row = conn.execute(
            f"""
            SELECT COALESCE(MAX(
                CASE
                    WHEN length({_quote_identifier(number_col)}) = 11
                         AND {_quote_identifier(number_col)} GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'
                         AND substr({_quote_identifier(number_col)}, 1, 8) = ?
                    THEN CAST(substr({_quote_identifier(number_col)}, 9) AS INTEGER)
                END
            ), 0) AS max_seq
            FROM {_quote_identifier(table_name)}
            WHERE {_quote_identifier(number_col)} LIKE ?
            """,
            (day_key, f"{day_key}%"),
        ).fetchone()
        seq = int(row["max_seq"]) + 1
        for item in group:
            item["new_no"] = f"{day_key}{seq:03d}"
            seq += 1


def _rewrite_text_columns(
    conn: sqlite3.Connection,
    mapping_by_old: dict[str, str],
    *,
    apply: bool,
) -> list[dict[str, Any]]:
    if not mapping_by_old:
        return []
    replacements = sorted(
        mapping_by_old.keys(),
        key=len,
        reverse=True,
    )
    pattern = re.compile("|".join(re.escape(key) for key in replacements))
    changes: list[dict[str, Any]] = []
    for table_name, column_name in _iter_text_columns(conn):
        rows = conn.execute(
            f"""
            SELECT rowid, {_quote_identifier(column_name)} AS __text_value__
            FROM {_quote_identifier(table_name)}
            """
        ).fetchall()
        updates: list[tuple[str, int]] = []
        for row in rows:
            raw_value = row["__text_value__"]
            if raw_value is None:
                continue
            original = str(raw_value)
            replaced = pattern.sub(lambda m: mapping_by_old[m.group(0)], original)
            if replaced != original:
                updates.append((replaced, int(row["rowid"])))
        if not updates:
            continue
        changes.append(
            {
                "table": table_name,
                "column": column_name,
                "rows": len(updates),
            }
        )
        if apply:
            conn.executemany(
                f"""
                UPDATE {_quote_identifier(table_name)}
                SET {_quote_identifier(column_name)} = ?
                WHERE rowid = ?
                """,
                updates,
            )
    return changes


def _iter_text_columns(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    columns: list[tuple[str, str]] = []
    table_rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    for table_row in table_rows:
        table_name = str(table_row["name"])
        table_cols = conn.execute(
            f"PRAGMA table_info({_quote_identifier(table_name)})"
        ).fetchall()
        for col in table_cols:
            col_name = str(col["name"])
            col_type = str(col["type"] or "").upper()
            if col_type.startswith("TEXT"):
                columns.append((table_name, col_name))
    return columns


def list_suppliers(conn: sqlite3.Connection, *, include_inactive: bool = True) -> list[dict]:
    sql = """
        SELECT id, supplier_name, contact_name, department, phone, contact_email, is_active, created_at, updated_at
        FROM suppliers
    """
    if not include_inactive:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY supplier_name COLLATE NOCASE, created_at"
    rows = conn.execute(sql).fetchall()
    items: list[dict] = []
    for row in rows:
        item = dict(row)
        item["is_active"] = bool(_as_int(item.get("is_active"), 0))
        items.append(item)
    return items


def get_supplier(conn: sqlite3.Connection, supplier_id: str) -> dict | None:
    supplier_key = (supplier_id or "").strip()
    if not supplier_key:
        return None
    row = conn.execute(
        """
        SELECT id, supplier_name, contact_name, department, phone, contact_email, is_active, created_at, updated_at
        FROM suppliers
        WHERE id = ?
        LIMIT 1
        """,
        (supplier_key,),
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["is_active"] = bool(_as_int(result.get("is_active"), 0))
    return result


def create_supplier_record(
    conn: sqlite3.Connection,
    *,
    supplier_name: str,
    contact_name: str = "",
    department: str = "",
    phone: str = "",
    contact_email: str = "",
) -> str:
    normalized_name = _normalize_supplier_name_for_storage(supplier_name)
    if not normalized_name:
        raise ValueError("Supplier name is required")
    supplier_id = _gen_id()
    try:
        conn.execute(
            """
            INSERT INTO suppliers(
                id, supplier_name, contact_name, department, phone, contact_email, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                supplier_id,
                normalized_name,
                (contact_name or "").strip(),
                (department or "").strip(),
                (phone or "").strip(),
                (contact_email or "").strip(),
                _now_iso(),
                _now_iso(),
            ),
        )
        # Automatically create the primary contact record
        conn.execute(
            """
            INSERT INTO supplier_contacts(
                id, supplier_id, contact_name, department, phone, email, is_primary, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                _gen_id(),
                supplier_id,
                (contact_name or "").strip(),
                (department or "").strip(),
                (phone or "").strip(),
                (contact_email or "").strip(),
                _now_iso(),
                _now_iso(),
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError("Supplier name already exists") from exc
    conn.commit()
    return supplier_id


def update_supplier_record(
    conn: sqlite3.Connection,
    *,
    supplier_id: str,
    supplier_name: str,
    contact_name: str = "",
    department: str = "",
    phone: str = "",
    contact_email: str = "",
) -> None:
    supplier_key = (supplier_id or "").strip()
    if not supplier_key:
        raise ValueError("Supplier id is required")
    normalized_name = _normalize_supplier_name_for_storage(supplier_name)
    if not normalized_name:
        raise ValueError("Supplier name is required")
    try:
        cur = conn.execute(
            """
            UPDATE suppliers
            SET supplier_name = ?, contact_name = ?, department = ?, phone = ?, contact_email = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                normalized_name,
                (contact_name or "").strip(),
                (department or "").strip(),
                (phone or "").strip(),
                (contact_email or "").strip(),
                _now_iso(),
                supplier_key,
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError("Supplier name already exists") from exc
    if cur.rowcount == 0:
        raise ValueError("Supplier not found")
    conn.commit()


def set_supplier_active(
    conn: sqlite3.Connection,
    supplier_id: str,
    is_active: bool,
) -> None:
    supplier_key = (supplier_id or "").strip()
    if not supplier_key:
        raise ValueError("Supplier id is required")
    cur = conn.execute(
        """
        UPDATE suppliers
        SET is_active = ?, updated_at = ?
        WHERE id = ?
        """,
        (1 if is_active else 0, _now_iso(), supplier_key),
    )
    if cur.rowcount == 0:
        raise ValueError("Supplier not found")
    conn.commit()


def delete_supplier_record(
    conn: sqlite3.Connection,
    supplier_id: str,
    *,
    commit: bool = True,
) -> None:
    supplier_key = (supplier_id or "").strip()
    if not supplier_key:
        raise ValueError("Supplier id is required")
    if get_supplier(conn, supplier_key) is None:
        raise ValueError("Supplier not found")

    referenced_by: list[str] = []
    products_where = (
        "supplier_id = ? OR secondary_supplier_id = ?"
        if _has_column(conn, "products", "secondary_supplier_id")
        else "supplier_id = ?"
    )
    products_params: tuple[str, ...] = (
        (supplier_key, supplier_key)
        if _has_column(conn, "products", "secondary_supplier_id")
        else (supplier_key,)
    )
    for table_name in ("products", "anomalies", "visits"):
        where_clause = "supplier_id = ?"
        params: tuple[str, ...] = (supplier_key,)
        if table_name == "products":
            where_clause = products_where
            params = products_params
        row = conn.execute(
            f"SELECT COUNT(*) AS c FROM {table_name} WHERE {where_clause}",
            params,
        ).fetchone()
        if row is not None and _as_int(row["c"], 0) > 0:
            referenced_by.append(table_name)
    if referenced_by:
        raise ValueError(f"Supplier is referenced by {', '.join(referenced_by)}")

    conn.execute("DELETE FROM supplier_contacts WHERE supplier_id = ?", (supplier_key,))
    conn.execute("DELETE FROM suppliers WHERE id = ?", (supplier_key,))
    if commit:
        conn.commit()


def list_supplier_contacts(conn: sqlite3.Connection, supplier_id: str) -> list[dict]:
    supplier_key = (supplier_id or "").strip()
    if not supplier_key:
        return []
    rows = conn.execute(
        """
        SELECT id, supplier_id, contact_name, department, phone, email, is_primary, created_at, updated_at
        FROM supplier_contacts
        WHERE supplier_id = ?
        ORDER BY is_primary DESC, contact_name COLLATE NOCASE
        """,
        (supplier_key,),
    ).fetchall()
    items: list[dict] = []
    for row in rows:
        item = dict(row)
        item["is_primary"] = bool(_as_int(item.get("is_primary"), 0))
        items.append(item)
    return items


def add_supplier_contact(
    conn: sqlite3.Connection,
    *,
    supplier_id: str,
    contact_name: str,
    department: str = "",
    phone: str = "",
    email: str = "",
    is_primary: bool = False,
) -> str:
    supplier_key = (supplier_id or "").strip()
    if not supplier_key:
        raise ValueError("Supplier id is required")
    contact_id = _gen_id()
    conn.execute(
        """
        INSERT INTO supplier_contacts(
            id, supplier_id, contact_name, department, phone, email, is_primary, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            contact_id,
            supplier_key,
            (contact_name or "").strip(),
            (department or "").strip(),
            (phone or "").strip(),
            (email or "").strip(),
            1 if is_primary else 0,
            _now_iso(),
            _now_iso(),
        ),
    )
    if is_primary:
        # Update other contacts to not be primary
        conn.execute(
            "UPDATE supplier_contacts SET is_primary = 0 WHERE supplier_id = ? AND id <> ?",
            (supplier_key, contact_id),
        )
        # Also update the main suppliers table with this primary contact info
        conn.execute(
            """
            UPDATE suppliers
            SET contact_name = ?, department = ?, phone = ?, contact_email = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                (contact_name or "").strip(),
                (department or "").strip(),
                (phone or "").strip(),
                (email or "").strip(),
                _now_iso(),
                supplier_key,
            ),
        )
    conn.commit()
    return contact_id


def delete_supplier_contact(conn: sqlite3.Connection, contact_id: str) -> None:
    contact_key = (contact_id or "").strip()
    if not contact_key:
        raise ValueError("Contact id is required")
    conn.execute("DELETE FROM supplier_contacts WHERE id = ?", (contact_key,))
    conn.commit()


def set_primary_contact(
    conn: sqlite3.Connection, supplier_id: str, contact_id: str
) -> None:
    supplier_key = (supplier_id or "").strip()
    contact_key = (contact_id or "").strip()
    if not supplier_key or not contact_key:
        raise ValueError("Supplier id and contact id are required")

    contact = conn.execute(
        "SELECT * FROM supplier_contacts WHERE id = ?", (contact_key,)
    ).fetchone()
    if not contact:
        raise ValueError("Contact not found")

    conn.execute(
        "UPDATE supplier_contacts SET is_primary = 0 WHERE supplier_id = ?",
        (supplier_key,),
    )
    conn.execute(
        "UPDATE supplier_contacts SET is_primary = 1 WHERE id = ?", (contact_key,)
    )

    # Sync to main suppliers table
    conn.execute(
        """
        UPDATE suppliers
        SET contact_name = ?, department = ?, phone = ?, contact_email = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            contact["contact_name"],
            contact["department"],
            contact["phone"],
            contact["email"],
            _now_iso(),
            supplier_key,
        ),
    )
    conn.commit()


def delete_supplier_records(
    conn: sqlite3.Connection,
    supplier_ids: list[str],
) -> SupplierDeleteResult:
    deleted_ids: list[str] = []
    failed: list[SupplierDeleteFailure] = []
    seen: set[str] = set()

    for supplier_id in supplier_ids or []:
        supplier_key = (supplier_id or "").strip()
        if supplier_key in seen:
            continue
        seen.add(supplier_key)
        try:
            delete_supplier_record(conn, supplier_key, commit=False)
            deleted_ids.append(supplier_key)
        except (ValueError, sqlite3.IntegrityError) as exc:
            failed.append({"id": supplier_key, "reason": str(exc)})

    conn.commit()
    return {"deleted": deleted_ids, "failed": failed}


def _supplier_recency_sort_key(item: dict) -> tuple[str, str, str]:
    return (
        str(item.get("updated_at") or ""),
        str(item.get("created_at") or ""),
        str(item.get("id") or ""),
    )


def _pick_latest_non_empty_supplier_field(rows: list[dict], field: str) -> str:
    for item in sorted(rows, key=_supplier_recency_sort_key, reverse=True):
        value = str(item.get(field) or "").strip()
        if value:
            return value
    return ""


def _pick_supplier_keeper(canonical_name: str, rows: list[dict]) -> dict:
    return sorted(
        rows,
        key=lambda item: (
            0
            if str(item.get("supplier_name") or "").strip() == canonical_name
            else 1,
            0 if bool(item.get("is_active")) else 1,
            str(item.get("created_at") or ""),
            str(item.get("id") or ""),
        ),
    )[0]


def _product_recency_sort_key(item: dict) -> tuple[str, str, str]:
    return (
        str(item.get("updated_at") or ""),
        str(item.get("created_at") or ""),
        str(item.get("id") or ""),
    )


def _pick_latest_product_name(rows: list[dict]) -> str:
    for item in sorted(rows, key=_product_recency_sort_key, reverse=True):
        value = str(item.get("product_name") or "").strip()
        if value:
            return value
    return ""


def _merge_supplier_products(
    conn: sqlite3.Connection,
    *,
    from_supplier_id: str,
    to_supplier_id: str,
    now_iso: str,
) -> dict[str, int]:
    stats = {
        "products_supplier_relinked": 0,
        "products_secondary_supplier_relinked": 0,
        "product_conflicts_resolved": 0,
        "products_updated": 0,
        "products_deleted": 0,
        "anomalies_product_relinked": 0,
        "visits_product_relinked": 0,
        "visit_sections_product_relinked": 0,
    }
    has_secondary_supplier_id = _has_column(conn, "products", "secondary_supplier_id")
    source_rows = conn.execute(
        (
            """
            SELECT id, product_code, product_name, secondary_supplier_id, is_active, created_at, updated_at
            FROM products
            WHERE supplier_id = ?
            ORDER BY created_at ASC, id ASC
            """
            if has_secondary_supplier_id
            else """
            SELECT id, product_code, product_name, is_active, created_at, updated_at
            FROM products
            WHERE supplier_id = ?
            ORDER BY created_at ASC, id ASC
            """
        ),
        (from_supplier_id,),
    ).fetchall()
    for row in source_rows:
        source_item = dict(row)
        source_product_id = str(source_item["id"])
        source_product_code = str(source_item["product_code"] or "").strip()
        target = conn.execute(
            (
                """
                SELECT id, product_name, secondary_supplier_id, is_active, created_at, updated_at
                FROM products
                WHERE supplier_id = ? AND product_code = ?
                LIMIT 1
                """
                if has_secondary_supplier_id
                else """
                SELECT id, product_name, is_active, created_at, updated_at
                FROM products
                WHERE supplier_id = ? AND product_code = ?
                LIMIT 1
                """
            ),
            (to_supplier_id, source_product_code),
        ).fetchone()
        if target is None:
            if has_secondary_supplier_id:
                merged_secondary_supplier_id = str(
                    source_item.get("secondary_supplier_id") or ""
                ).strip()
                if merged_secondary_supplier_id == to_supplier_id:
                    merged_secondary_supplier_id = ""
                cur = conn.execute(
                    """
                    UPDATE products
                    SET supplier_id = ?,
                        secondary_supplier_id = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        to_supplier_id,
                        merged_secondary_supplier_id or None,
                        now_iso,
                        source_product_id,
                    ),
                )
            else:
                cur = conn.execute(
                    """
                    UPDATE products
                    SET supplier_id = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (to_supplier_id, now_iso, source_product_id),
                )
            stats["products_supplier_relinked"] += int(cur.rowcount)
            continue

        target_item = dict(target)
        target_product_id = str(target_item["id"])
        if target_product_id == source_product_id:
            continue

        merged_product_name = _pick_latest_product_name([target_item, source_item])
        target_product_name = str(target_item.get("product_name") or "").strip()
        target_is_active = bool(_as_int(target_item.get("is_active"), 0))
        source_is_active = bool(_as_int(source_item.get("is_active"), 0))
        merged_is_active = target_is_active or source_is_active
        final_product_name = merged_product_name or target_product_name
        final_secondary_supplier_id: str | None = None
        if has_secondary_supplier_id:
            target_secondary_supplier_id = str(
                target_item.get("secondary_supplier_id") or ""
            ).strip()
            source_secondary_supplier_id = str(
                source_item.get("secondary_supplier_id") or ""
            ).strip()
            merged_secondary_supplier_id = (
                target_secondary_supplier_id or source_secondary_supplier_id
            )
            if merged_secondary_supplier_id == to_supplier_id:
                merged_secondary_supplier_id = ""
            final_secondary_supplier_id = merged_secondary_supplier_id or None

        if has_secondary_supplier_id:
            current_secondary_supplier_id = str(
                target_item.get("secondary_supplier_id") or ""
            ).strip() or None
            if (
                final_product_name != target_product_name
                or merged_is_active != target_is_active
                or final_secondary_supplier_id != current_secondary_supplier_id
            ):
                conn.execute(
                    """
                    UPDATE products
                    SET product_name = ?,
                        secondary_supplier_id = ?,
                        is_active = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        final_product_name,
                        final_secondary_supplier_id,
                        1 if merged_is_active else 0,
                        now_iso,
                        target_product_id,
                    ),
                )
                stats["products_updated"] += 1
        elif (
            final_product_name != target_product_name
            or merged_is_active != target_is_active
        ):
            conn.execute(
                """
                UPDATE products
                SET product_name = ?, is_active = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    final_product_name,
                    1 if merged_is_active else 0,
                    now_iso,
                    target_product_id,
                ),
            )
            stats["products_updated"] += 1

        anomaly_cur = conn.execute(
            """
            UPDATE anomalies
            SET product_id = ?, product_name = ?, updated_at = ?
            WHERE product_id = ?
            """,
            (
                target_product_id,
                final_product_name,
                now_iso,
                source_product_id,
            ),
        )
        visit_cur = conn.execute(
            """
            UPDATE visits
            SET product_id = ?, product_name = ?, updated_at = ?
            WHERE product_id = ?
            """,
            (
                target_product_id,
                final_product_name,
                now_iso,
                source_product_id,
            ),
        )
        visit_section_cur = conn.execute(
            """
            UPDATE visit_product_sections
            SET product_id = ?, product_name = ?, updated_at = ?
            WHERE product_id = ?
            """,
            (
                target_product_id,
                final_product_name,
                now_iso,
                source_product_id,
            ),
        )
        delete_cur = conn.execute(
            "DELETE FROM products WHERE id = ?",
            (source_product_id,),
        )
        stats["product_conflicts_resolved"] += 1
        stats["anomalies_product_relinked"] += int(anomaly_cur.rowcount)
        stats["visits_product_relinked"] += int(visit_cur.rowcount)
        stats["visit_sections_product_relinked"] += int(visit_section_cur.rowcount)
        stats["products_deleted"] += int(delete_cur.rowcount)
    return stats


def _consolidate_suppliers_inner(conn: sqlite3.Connection) -> dict[str, Any]:
    suppliers_raw = conn.execute(
        """
        SELECT id, supplier_name, contact_name, phone, is_active, created_at, updated_at
        FROM suppliers
        ORDER BY created_at ASC, id ASC
        """
    ).fetchall()
    suppliers: list[dict[str, Any]] = []
    for row in suppliers_raw:
        item = dict(row)
        item["is_active"] = bool(_as_int(item.get("is_active"), 0))
        suppliers.append(item)

    report: dict[str, Any] = {
        "suppliers_before": len(suppliers),
        "suppliers_after": len(suppliers),
        "groups_total": 0,
        "groups_merged": 0,
        "groups_renamed": 0,
        "suppliers_deleted": 0,
        "suppliers_updated": 0,
        "anomalies_supplier_relinked": 0,
        "visits_supplier_relinked": 0,
        "products_supplier_relinked": 0,
        "products_secondary_supplier_relinked": 0,
        "product_conflicts_resolved": 0,
        "products_updated": 0,
        "products_deleted": 0,
        "anomalies_product_relinked": 0,
        "visits_product_relinked": 0,
        "groups": [],
    }
    if not suppliers:
        return report

    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in suppliers:
        current_name = str(item.get("supplier_name") or "").strip()
        canonical_name = canonicalize_supplier_name(current_name) or current_name
        grouped.setdefault(canonical_name, []).append(item)

    report["groups_total"] = len(grouped)
    now_iso = _now_iso()
    for canonical_name in sorted(grouped.keys(), key=str.lower):
        group_rows = grouped[canonical_name]
        keeper = _pick_supplier_keeper(canonical_name, group_rows)
        keeper_id = str(keeper["id"])
        merged_rows = [item for item in group_rows if str(item["id"]) != keeper_id]
        merged_supplier_ids = [str(item["id"]) for item in merged_rows]
        if merged_rows:
            report["groups_merged"] += 1

        merged_is_active = any(bool(item.get("is_active")) for item in group_rows)
        merged_contact_name = _pick_latest_non_empty_supplier_field(
            group_rows, "contact_name"
        )
        merged_phone = _pick_latest_non_empty_supplier_field(group_rows, "phone")

        for merged_item in merged_rows:
            merged_supplier_id = str(merged_item["id"])
            anomaly_cur = conn.execute(
                """
                UPDATE anomalies
                SET supplier_id = ?, updated_at = ?
                WHERE supplier_id = ?
                """,
                (keeper_id, now_iso, merged_supplier_id),
            )
            visit_cur = conn.execute(
                """
                UPDATE visits
                SET supplier_id = ?, updated_at = ?
                WHERE supplier_id = ?
                """,
                (keeper_id, now_iso, merged_supplier_id),
            )
            product_stats = _merge_supplier_products(
                conn,
                from_supplier_id=merged_supplier_id,
                to_supplier_id=keeper_id,
                now_iso=now_iso,
            )
            secondary_relinked = 0
            if _has_column(conn, "products", "secondary_supplier_id"):
                secondary_relinked_cur = conn.execute(
                    """
                    UPDATE products
                    SET secondary_supplier_id = ?, updated_at = ?
                    WHERE secondary_supplier_id = ?
                    """,
                    (keeper_id, now_iso, merged_supplier_id),
                )
                secondary_relinked += int(secondary_relinked_cur.rowcount)
                conn.execute(
                    """
                    UPDATE products
                    SET secondary_supplier_id = NULL, updated_at = ?
                    WHERE supplier_id = ? AND secondary_supplier_id = ?
                    """,
                    (now_iso, keeper_id, keeper_id),
                )
            delete_cur = conn.execute(
                "DELETE FROM suppliers WHERE id = ?",
                (merged_supplier_id,),
            )
            report["anomalies_supplier_relinked"] += int(anomaly_cur.rowcount)
            report["visits_supplier_relinked"] += int(visit_cur.rowcount)
            report["products_supplier_relinked"] += int(
                product_stats["products_supplier_relinked"]
            )
            report["products_secondary_supplier_relinked"] += int(secondary_relinked)
            report["product_conflicts_resolved"] += int(
                product_stats["product_conflicts_resolved"]
            )
            report["products_updated"] += int(product_stats["products_updated"])
            report["products_deleted"] += int(product_stats["products_deleted"])
            report["anomalies_product_relinked"] += int(
                product_stats["anomalies_product_relinked"]
            )
            report["visits_product_relinked"] += int(
                product_stats["visits_product_relinked"]
            )
            report["suppliers_deleted"] += int(delete_cur.rowcount)

        keeper_row = conn.execute(
            """
            SELECT id, supplier_name, contact_name, phone, is_active
            FROM suppliers
            WHERE id = ?
            LIMIT 1
            """,
            (keeper_id,),
        ).fetchone()
        if keeper_row is None:
            continue

        keeper_item = dict(keeper_row)
        current_name = str(keeper_item.get("supplier_name") or "").strip()
        current_contact = str(keeper_item.get("contact_name") or "").strip()
        current_phone = str(keeper_item.get("phone") or "").strip()
        current_is_active = bool(_as_int(keeper_item.get("is_active"), 0))
        final_name = canonical_name or current_name
        final_contact = merged_contact_name
        final_phone = merged_phone
        final_is_active = merged_is_active
        renamed = final_name != current_name

        if (
            renamed
            or final_contact != current_contact
            or final_phone != current_phone
            or final_is_active != current_is_active
        ):
            conn.execute(
                """
                UPDATE suppliers
                SET supplier_name = ?,
                    contact_name = ?,
                    phone = ?,
                    is_active = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    final_name,
                    final_contact,
                    final_phone,
                    1 if final_is_active else 0,
                    now_iso,
                    keeper_id,
                ),
            )
            report["suppliers_updated"] += 1
            if renamed:
                report["groups_renamed"] += 1

        if merged_rows or renamed:
            report["groups"].append(
                {
                    "canonical_name": canonical_name,
                    "keeper_supplier_id": keeper_id,
                    "merged_supplier_ids": merged_supplier_ids,
                    "renamed": renamed,
                }
            )

    report["suppliers_after"] = int(
        conn.execute("SELECT COUNT(*) AS c FROM suppliers").fetchone()["c"]
    )
    return report


def consolidate_suppliers(
    conn: sqlite3.Connection,
    *,
    apply: bool = True,
) -> dict[str, Any]:
    savepoint_name = f"supplier_consolidation_{uuid.uuid4().hex}"
    conn.execute(f"SAVEPOINT {savepoint_name}")
    try:
        report = _consolidate_suppliers_inner(conn)
        report["applied"] = bool(apply)
        report["changed"] = bool(
            report.get("groups_merged")
            or report.get("groups_renamed")
            or report.get("product_conflicts_resolved")
        )
        if apply:
            conn.execute(f"RELEASE SAVEPOINT {savepoint_name}")
            conn.commit()
        else:
            conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
            conn.execute(f"RELEASE SAVEPOINT {savepoint_name}")
        return report
    except Exception:
        logger.exception("consolidate_suppliers failed")
        try:
            conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
            conn.execute(f"RELEASE SAVEPOINT {savepoint_name}")
        except sqlite3.Error:
            pass
        raise


def _product_select_fragments(conn: sqlite3.Connection) -> dict[str, Any]:
    """Shared SELECT/JOIN fragments for product-stage and secondary-supplier
    columns, used by list_products / get_product / list_active_products_for_supplier.
    Centralizes the _has_column probing so schema-migration state is checked
    once per call site instead of being re-derived independently in each
    function (audit finding D2).

    The missing-column fallbacks are NOT dead code (audit finding C2): legacy
    pre-migration databases without product_stage / secondary_supplier_id are
    a supported upgrade path — tests/test_product_spec_removal.py constructs
    exactly such schemas and create_schema's products__new rebuild migrates
    them in place."""
    stage_sql = (
        "p.product_stage"
        if _has_column(conn, "products", "product_stage")
        else "'量產'"
    )
    has_secondary = _has_column(conn, "products", "secondary_supplier_id")
    secondary_select_sql = "p.secondary_supplier_id" if has_secondary else "NULL"
    secondary_name_sql = "ss.supplier_name" if has_secondary else "NULL"
    join_sql = (
        " LEFT JOIN suppliers ss ON ss.id = p.secondary_supplier_id"
        if has_secondary
        else ""
    )
    return {
        "stage_sql": stage_sql,
        "has_secondary": has_secondary,
        "secondary_select_sql": secondary_select_sql,
        "secondary_name_sql": secondary_name_sql,
        "join_sql": join_sql,
    }


def list_products(conn: sqlite3.Connection, *, include_inactive: bool = True) -> list[dict]:
    frag = _product_select_fragments(conn)
    sql = """
        SELECT
            p.id AS id,
            p.product_code AS product_code,
            p.product_name AS product_name,
            """
    sql += f"{frag['stage_sql']} AS product_stage,"
    sql += """
            p.supplier_id AS supplier_id,
            s.supplier_name AS supplier_name,
            """
    sql += f"{frag['secondary_select_sql']} AS secondary_supplier_id,"
    sql += """
            """
    sql += f"{frag['secondary_name_sql']} AS secondary_supplier_name,"
    sql += """
            p.is_active AS is_active,
            p.created_at AS created_at,
            p.updated_at AS updated_at
        FROM products p
        LEFT JOIN suppliers s ON s.id = p.supplier_id
    """
    sql += frag["join_sql"]
    params: list[Any] = []
    if not include_inactive:
        sql += " WHERE p.is_active = 1"
    sql += " ORDER BY p.product_name COLLATE NOCASE, p.product_code COLLATE NOCASE"
    rows = conn.execute(sql, params).fetchall()
    items: list[dict] = []
    for row in rows:
        item = dict(row)
        item["is_active"] = bool(_as_int(item.get("is_active"), 0))
        item["product_stage"] = _normalize_product_stage_for_read(
            item.get("product_stage")
        )
        items.append(item)
    return items


def get_product(conn: sqlite3.Connection, product_id: str) -> dict | None:
    product_key = (product_id or "").strip()
    if not product_key:
        return None
    frag = _product_select_fragments(conn)
    row = conn.execute(
        f"""
        SELECT
            p.id AS id,
            p.product_code AS product_code,
            p.product_name AS product_name,
            {frag['stage_sql']} AS product_stage,
            p.supplier_id AS supplier_id,
            s.supplier_name AS supplier_name,
            {frag['secondary_select_sql']} AS secondary_supplier_id,
            {frag['secondary_name_sql']} AS secondary_supplier_name,
            p.is_active AS is_active,
            p.created_at AS created_at,
            p.updated_at AS updated_at
        FROM products p
        LEFT JOIN suppliers s ON s.id = p.supplier_id
        {frag['join_sql']}
        WHERE p.id = ?
        LIMIT 1
        """,
        (product_key,),
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["is_active"] = bool(_as_int(result.get("is_active"), 0))
    result["product_stage"] = _normalize_product_stage_for_read(
        result.get("product_stage")
    )
    return result


def _ensure_product_code_globally_unique(
    conn: sqlite3.Connection,
    *,
    product_code: str,
    exclude_product_id: str | None = None,
) -> None:
    normalized_code = (product_code or "").strip()
    if not normalized_code:
        return
    params: list[Any] = [normalized_code]
    sql = """
        SELECT id
        FROM products
        WHERE product_code = ?
    """
    excluded_id = (exclude_product_id or "").strip()
    if excluded_id:
        sql += " AND id <> ?"
        params.append(excluded_id)
    sql += " LIMIT 1"
    row = conn.execute(sql, params).fetchone()
    if row is not None:
        raise ValueError("Product code already exists")


def _validate_product_supplier_links(
    conn: sqlite3.Connection,
    *,
    supplier_id: str,
    secondary_supplier_id: str | None,
) -> tuple[str, str | None]:
    normalized_supplier_id = (supplier_id or "").strip()
    normalized_secondary_supplier_id = (secondary_supplier_id or "").strip() or None
    if not normalized_supplier_id:
        raise ValueError("Supplier is required")
    if get_supplier(conn, normalized_supplier_id) is None:
        raise ValueError("Supplier not found")
    if normalized_secondary_supplier_id:
        if get_supplier(conn, normalized_secondary_supplier_id) is None:
            raise ValueError("Secondary supplier not found")
        if normalized_secondary_supplier_id == normalized_supplier_id:
            raise ValueError("Secondary supplier must be different from primary supplier")
    return normalized_supplier_id, normalized_secondary_supplier_id


def create_product_record(
    conn: sqlite3.Connection,
    *,
    product_code: str,
    product_name: str,
    product_stage: str = PRODUCT_STAGE_MASS_PRODUCTION,
    supplier_id: str,
    secondary_supplier_id: str | None = None,
) -> str:
    normalized_code = (product_code or "").strip()
    normalized_name = (product_name or "").strip()
    normalized_product_stage = _normalize_product_stage(product_stage)
    if not normalized_code:
        raise ValueError("Product code is required")
    if not normalized_name:
        raise ValueError("Product name is required")
    _ensure_product_code_globally_unique(conn, product_code=normalized_code)
    normalized_supplier_id, normalized_secondary_supplier_id = (
        _validate_product_supplier_links(
            conn,
            supplier_id=supplier_id,
            secondary_supplier_id=secondary_supplier_id,
        )
    )

    product_id = _gen_id()
    has_product_stage = _has_column(conn, "products", "product_stage")
    has_secondary_supplier_id = _has_column(conn, "products", "secondary_supplier_id")
    try:
        if has_product_stage and has_secondary_supplier_id:
            conn.execute(
                """
                INSERT INTO products(
                    id, product_code, product_name, product_stage, supplier_id, secondary_supplier_id,
                    is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    product_id,
                    normalized_code,
                    normalized_name,
                    normalized_product_stage,
                    normalized_supplier_id,
                    normalized_secondary_supplier_id,
                    _now_iso(),
                    _now_iso(),
                ),
            )
        elif has_product_stage:
            conn.execute(
                """
                INSERT INTO products(
                    id, product_code, product_name, product_stage, supplier_id, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    product_id,
                    normalized_code,
                    normalized_name,
                    normalized_product_stage,
                    normalized_supplier_id,
                    _now_iso(),
                    _now_iso(),
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO products(
                    id, product_code, product_name, supplier_id, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    product_id,
                    normalized_code,
                    normalized_name,
                    normalized_supplier_id,
                    _now_iso(),
                    _now_iso(),
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise ValueError("Product code already exists") from exc
    conn.commit()
    return product_id


def update_product_record(
    conn: sqlite3.Connection,
    *,
    product_id: str,
    product_code: str,
    product_name: str,
    product_stage: str = PRODUCT_STAGE_MASS_PRODUCTION,
    supplier_id: str,
    secondary_supplier_id: str | None = None,
    stage_change_reason: str = "",
    changed_by: str = DEFAULT_STAGE_CHANGED_BY,
) -> None:
    product_key = (product_id or "").strip()
    normalized_code = (product_code or "").strip()
    normalized_name = (product_name or "").strip()
    normalized_product_stage = _normalize_product_stage(product_stage)
    if not product_key:
        raise ValueError("Product id is required")
    if not normalized_code:
        raise ValueError("Product code is required")
    if not normalized_name:
        raise ValueError("Product name is required")
    existing = get_product(conn, product_key)
    if existing is None:
        raise ValueError("Product not found")
    existing_stage = _normalize_product_stage_for_read(existing.get("product_stage"))
    if (
        existing_stage == PRODUCT_STAGE_MASS_PRODUCTION
        and normalized_product_stage != PRODUCT_STAGE_MASS_PRODUCTION
        and not (stage_change_reason or "").strip()
    ):
        raise ValueError("Stage change reason is required for mass->trial downgrade")
    _ensure_product_code_globally_unique(
        conn, product_code=normalized_code, exclude_product_id=product_key
    )
    normalized_supplier_id, normalized_secondary_supplier_id = (
        _validate_product_supplier_links(
            conn,
            supplier_id=supplier_id,
            secondary_supplier_id=secondary_supplier_id,
        )
    )
    has_product_stage = _has_column(conn, "products", "product_stage")
    has_secondary_supplier_id = _has_column(conn, "products", "secondary_supplier_id")
    try:
        if has_product_stage and has_secondary_supplier_id:
            cur = conn.execute(
                """
                UPDATE products
                SET product_code = ?,
                    product_name = ?,
                    product_stage = ?,
                    supplier_id = ?,
                    secondary_supplier_id = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    normalized_code,
                    normalized_name,
                    normalized_product_stage,
                    normalized_supplier_id,
                    normalized_secondary_supplier_id,
                    _now_iso(),
                    product_key,
                ),
            )
        elif has_product_stage:
            cur = conn.execute(
                """
                UPDATE products
                SET product_code = ?,
                    product_name = ?,
                    product_stage = ?,
                    supplier_id = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    normalized_code,
                    normalized_name,
                    normalized_product_stage,
                    normalized_supplier_id,
                    _now_iso(),
                    product_key,
                ),
            )
        else:
            cur = conn.execute(
                """
                UPDATE products
                SET product_code = ?,
                    product_name = ?,
                    supplier_id = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    normalized_code,
                    normalized_name,
                    normalized_supplier_id,
                    _now_iso(),
                    product_key,
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise ValueError("Product code already exists") from exc
    if cur.rowcount == 0:
        raise ValueError("Product not found")
    sync_report = sync_product_stage_to_events(conn, product_key)
    if existing_stage != normalized_product_stage:
        _insert_product_stage_change_log(
            conn,
            product_id=product_key,
            from_stage=existing_stage,
            to_stage=normalized_product_stage,
            reason=(stage_change_reason or "").strip(),
            changed_by=(changed_by or "").strip() or DEFAULT_STAGE_CHANGED_BY,
            sync_scope=STAGE_SYNC_SCOPE_ALL_HISTORY,
            anomalies_updated=int(sync_report["anomalies_updated"]),
            visits_updated=int(sync_report["visits_updated"]),
        )
    conn.commit()


def set_product_active(conn: sqlite3.Connection, product_id: str, is_active: bool) -> None:
    product_key = (product_id or "").strip()
    if not product_key:
        raise ValueError("Product id is required")
    product = get_product(conn, product_key)
    if product is None:
        raise ValueError("Product not found")
    if is_active:
        _validate_product_supplier_links(
            conn,
            supplier_id=str(product.get("supplier_id") or ""),
            secondary_supplier_id=str(product.get("secondary_supplier_id") or ""),
        )
    cur = conn.execute(
        """
        UPDATE products
        SET is_active = ?, updated_at = ?
        WHERE id = ?
        """,
        (1 if is_active else 0, _now_iso(), product_key),
    )
    if cur.rowcount == 0:
        raise ValueError("Product not found")
    conn.commit()


def delete_product_record(conn: sqlite3.Connection, product_id: str) -> None:
    product_key = (product_id or "").strip()
    if not product_key:
        raise ValueError("Product id is required")
    if get_product(conn, product_key) is None:
        raise ValueError("Product not found")

    referenced_by: list[str] = []
    for table_name in ("anomalies", "visits", "visit_product_sections"):
        row = conn.execute(
            f"SELECT COUNT(*) AS c FROM {table_name} WHERE product_id = ?",
            (product_key,),
        ).fetchone()
        if row is not None and _as_int(row["c"], 0) > 0:
            referenced_by.append(table_name)
    if referenced_by:
        raise ValueError(f"Product is referenced by {', '.join(referenced_by)}")

    cur = conn.execute("DELETE FROM products WHERE id = ?", (product_key,))
    if cur.rowcount == 0:
        raise ValueError("Product not found")
    conn.commit()


def list_active_suppliers(conn: sqlite3.Connection) -> list[dict]:
    return list_suppliers(conn, include_inactive=False)


def list_active_products_for_supplier(
    conn: sqlite3.Connection, supplier_id: str | None
) -> list[dict]:
    normalized_supplier_id = (supplier_id or "").strip()
    if not normalized_supplier_id:
        return []
    frag = _product_select_fragments(conn)
    has_secondary_supplier_id = frag["has_secondary"]
    sql = """
        SELECT
            p.id AS id,
            p.product_code AS product_code,
            p.product_name AS product_name,
            """
    sql += f"{frag['stage_sql']} AS product_stage,"
    sql += """
            p.supplier_id AS supplier_id,
            s.supplier_name AS supplier_name,
            """
    sql += f"{frag['secondary_select_sql']} AS secondary_supplier_id,"
    sql += f"{frag['secondary_name_sql']} AS secondary_supplier_name"
    sql += """
        FROM products p
        LEFT JOIN suppliers s ON s.id = p.supplier_id
    """
    sql += frag["join_sql"]
    sql += " WHERE p.is_active = 1"
    params: list[Any] = []
    if has_secondary_supplier_id:
        sql += " AND (p.supplier_id = ? OR p.secondary_supplier_id = ? OR p.supplier_id IS NULL)"
        params.extend([normalized_supplier_id, normalized_supplier_id])
    else:
        sql += " AND (p.supplier_id IS NULL OR p.supplier_id = ?)"
        params.append(normalized_supplier_id)
    sql += " ORDER BY p.product_name COLLATE NOCASE, p.product_code COLLATE NOCASE"
    rows = conn.execute(sql, params).fetchall()
    items: list[dict] = []
    for row in rows:
        item = dict(row)
        item["product_stage"] = _normalize_product_stage_for_read(
            item.get("product_stage")
        )
        items.append(item)
    return items


def ensure_supplier(
    conn: sqlite3.Connection,
    supplier_name: str,
    *,
    supplier_id: str | None = None,
    contact_name: str = "",
    department: str = "",
    phone: str = "",
    contact_email: str = "",
) -> str:
    normalized_name = _normalize_supplier_name_for_storage(supplier_name)
    if not normalized_name:
        normalized_name = "Unknown Supplier"

    row = conn.execute(
        "SELECT id FROM suppliers WHERE supplier_name = ?",
        (normalized_name,),
    ).fetchone()
    if row:
        return str(row["id"])

    generated_id = supplier_id or _gen_id()
    conn.execute(
        """
        INSERT INTO suppliers(
            id, supplier_name, contact_name, department, phone, contact_email,
            is_active, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
        """,
        (
            generated_id,
            normalized_name,
            (contact_name or "").strip(),
            (department or "").strip(),
            (phone or "").strip(),
            (contact_email or "").strip(),
            _now_iso(),
            _now_iso(),
        ),
    )
    return generated_id


@dataclass
class _AnomalyInputs:
    normalized_supplier_id: str
    normalized_date: str
    resolved_product_id: str | None
    resolved_product_name: str
    normalized_product_stage: str
    normalized_batch_qty: int


def _prepare_anomaly_inputs(
    conn: sqlite3.Connection,
    *,
    supplier_id: str,
    problem_desc: str,
    anomaly_date: str,
    product_id: str | None,
    product_name: str,
    product_stage: str,
    batch_qty: int,
) -> _AnomalyInputs:
    """Shared validation + normalization for create_anomaly and
    create_anomaly_with_visit_link (audit finding D1). Both callers
    previously duplicated this block verbatim; consolidating it here keeps
    validation order and error messages identical across both entry points."""
    if not (problem_desc or "").strip():
        raise ValueError("Problem description is required")
    normalized_supplier_id = (supplier_id or "").strip()
    if not normalized_supplier_id:
        raise ValueError("Supplier is required")
    if get_supplier(conn, normalized_supplier_id) is None:
        raise ValueError("Supplier not found")

    normalized_date = _normalize_strict_iso_date(
        anomaly_date,
        field_name="Anomaly date",
    )
    _ensure_date_not_in_future(normalized_date, field_name="Anomaly date")
    resolved_product_id, resolved_product_name, resolved_product_stage = _resolve_product_selection(
        conn,
        supplier_id=normalized_supplier_id,
        product_id=product_id,
        fallback_name=product_name,
    )
    normalized_product_stage = _normalize_product_stage(
        resolved_product_stage,
        fallback=PRODUCT_STAGE_MASS_PRODUCTION,
    )
    normalized_batch_qty = _normalize_non_negative_int(
        batch_qty,
        field_name="Batch quantity",
    )
    return _AnomalyInputs(
        normalized_supplier_id=normalized_supplier_id,
        normalized_date=normalized_date,
        resolved_product_id=resolved_product_id,
        resolved_product_name=resolved_product_name,
        normalized_product_stage=normalized_product_stage,
        normalized_batch_qty=normalized_batch_qty,
    )


def create_anomaly(
    conn: sqlite3.Connection,
    *,
    anomaly_date: str,
    supplier_id: str,
    problem_desc: str,
    category: str = "",
    product_lot_no: str = "",
    product_id: str | None = None,
    product_name: str = "",
    product_stage: str = PRODUCT_STAGE_MASS_PRODUCTION,
    outsource_work_order: str = "",
    batch_qty: int = 0,
    visit_id: str | None = None,
    pending_items: str = "",
    responsible_person: str = "",
    due_date: str = "",
    rc_supplier_inventory: str = "unconfirmed",
    rc_supplier_wip: str = "unconfirmed",
    rc_in_transit: str = "unconfirmed",
    rc_internal_inventory: str = "unconfirmed",
    is_tech_transfer: bool = False,
) -> str:
    inputs = _prepare_anomaly_inputs(
        conn,
        supplier_id=supplier_id,
        problem_desc=problem_desc,
        anomaly_date=anomaly_date,
        product_id=product_id,
        product_name=product_name,
        product_stage=product_stage,
        batch_qty=batch_qty,
    )
    anomaly_no = _insert_anomaly_row(
        conn,
        anomaly_date=inputs.normalized_date,
        supplier_id=inputs.normalized_supplier_id,
        problem_desc=problem_desc,
        category=category,
        product_lot_no=product_lot_no,
        product_id=inputs.resolved_product_id,
        product_name=inputs.resolved_product_name,
        product_stage=inputs.normalized_product_stage,
        outsource_work_order=outsource_work_order,
        batch_qty=inputs.normalized_batch_qty,
        visit_id=visit_id,
        pending_items=pending_items,
        responsible_person=responsible_person,
        due_date=due_date,
        rc_supplier_inventory=rc_supplier_inventory,
        rc_supplier_wip=rc_supplier_wip,
        rc_in_transit=rc_in_transit,
        rc_internal_inventory=rc_internal_inventory,
        is_tech_transfer=is_tech_transfer,
    )
    conn.commit()
    refresh_monthly_cache(conn, inputs.normalized_date[:7].replace("-", ""))
    return anomaly_no


def get_anomaly_detail(conn: sqlite3.Connection, anomaly_id: str) -> dict | None:
    anomaly_key = (anomaly_id or "").strip()
    if not anomaly_key:
        return None
    row = conn.execute(
        """
        SELECT
            a.id AS id,
            a.anomaly_no AS anomaly_no,
            a.anomaly_date AS anomaly_date,
            a.supplier_id AS supplier_id,
            s.supplier_name AS supplier_name,
            a.visit_id AS visit_id,
            a.product_id AS product_id,
            p.product_code AS product_code,
            a.product_name AS product_name,
            a.product_stage AS product_stage,
            a.problem_desc AS problem_desc,
            a.category AS category,
            a.product_lot_no AS product_lot_no,
            a.outsource_work_order AS outsource_work_order,
            a.batch_qty AS batch_qty,
            a.status AS status,
            a.improvement_desc AS improvement_desc,
            a.closed_by AS closed_by,
            a.root_cause_category AS root_cause_category,
            a.closed_at AS closed_at,
            a.pending_items AS pending_items,
            a.responsible_person AS responsible_person,
            a.due_date AS due_date,
            a.rc_supplier_inventory AS rc_supplier_inventory,
            a.rc_supplier_wip AS rc_supplier_wip,
            a.rc_in_transit AS rc_in_transit,
            a.rc_internal_inventory AS rc_internal_inventory,
            a.is_tech_transfer AS is_tech_transfer,
            a.created_at AS created_at,
            a.updated_at AS updated_at
        FROM anomalies a
        JOIN suppliers s ON s.id = a.supplier_id
        LEFT JOIN products p ON p.id = a.product_id
        WHERE a.id = ?
        LIMIT 1
        """,
        (anomaly_key,),
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["batch_qty"] = _as_int(result.get("batch_qty"), 0)
    result["product_stage"] = _normalize_product_stage(result.get("product_stage"))
    result["is_tech_transfer"] = bool(_as_int(result.get("is_tech_transfer"), 0))
    return result


def update_anomaly(
    conn: sqlite3.Connection,
    *,
    anomaly_id: str,
    anomaly_date: str,
    supplier_id: str,
    problem_desc: str,
    category: str = "",
    product_lot_no: str = "",
    product_id: str | None = None,
    product_name: str = "",
    product_stage: str = PRODUCT_STAGE_MASS_PRODUCTION,
    outsource_work_order: str = "",
    batch_qty: int = 0,
    pending_items: str = "",
    responsible_person: str = "",
    due_date: str = "",
    rc_supplier_inventory: str = "unconfirmed",
    rc_supplier_wip: str = "unconfirmed",
    rc_in_transit: str = "unconfirmed",
    rc_internal_inventory: str = "unconfirmed",
    is_tech_transfer: bool = False,
    anomaly_no: str | None = None,
) -> None:
    anomaly_key = (anomaly_id or "").strip()
    if not anomaly_key:
        raise ValueError("Anomaly id is required")
    existing = get_anomaly_detail(conn, anomaly_key)
    if existing is None:
        raise ValueError("Anomaly not found")

    resolved_anomaly_no = (anomaly_no or "").strip() or existing.get("anomaly_no") or ""
    if not resolved_anomaly_no:
        raise ValueError("Anomaly number is required")

    normalized_problem_desc = (problem_desc or "").strip()
    if not normalized_problem_desc:
        raise ValueError("Problem description is required")

    normalized_supplier_id = (supplier_id or "").strip()
    if not normalized_supplier_id:
        raise ValueError("Supplier is required")
    if get_supplier(conn, normalized_supplier_id) is None:
        raise ValueError("Supplier not found")

    normalized_date = _normalize_strict_iso_date(
        anomaly_date,
        field_name="Anomaly date",
        fallback=existing["anomaly_date"],
    )
    _ensure_date_not_in_future(normalized_date, field_name="Anomaly date")
    resolved_product_id, resolved_product_name, resolved_product_stage = _resolve_product_selection(
        conn,
        supplier_id=normalized_supplier_id,
        product_id=product_id,
        fallback_name=product_name,
    )
    normalized_product_stage = _normalize_product_stage(
        resolved_product_stage, fallback=existing.get("product_stage")
    )
    normalized_batch_qty = _normalize_non_negative_int(
        batch_qty,
        field_name="Batch quantity",
    )
    normalized_due_date = _normalize_optional_iso_date(
        due_date, field_name="Due date"
    )
    try:
        cur = conn.execute(
            """
            UPDATE anomalies
            SET anomaly_no = ?,
                anomaly_date = ?,
                supplier_id = ?,
                product_id = ?,
                product_name = ?,
                product_stage = ?,
                problem_desc = ?,
                category = ?,
                product_lot_no = ?,
                outsource_work_order = ?,
                batch_qty = ?,
                pending_items = ?,
                responsible_person = ?,
                due_date = ?,
                rc_supplier_inventory = ?,
                rc_supplier_wip = ?,
                rc_in_transit = ?,
                rc_internal_inventory = ?,
                is_tech_transfer = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                resolved_anomaly_no,
                normalized_date,
                normalized_supplier_id,
                resolved_product_id,
                resolved_product_name,
                normalized_product_stage,
                normalized_problem_desc,
                (category or "").strip(),
                (product_lot_no or "").strip(),
                (outsource_work_order or "").strip(),
                normalized_batch_qty,
                (pending_items or "").strip(),
                (responsible_person or "").strip(),
                normalized_due_date,
                (rc_supplier_inventory or "unconfirmed").strip(),
                (rc_supplier_wip or "unconfirmed").strip(),
                (rc_in_transit or "unconfirmed").strip(),
                (rc_internal_inventory or "unconfirmed").strip(),
                1 if is_tech_transfer else 0,
                _now_iso(),
                anomaly_key,
            ),
        )
    except sqlite3.IntegrityError as exc:
        if "UNIQUE constraint failed" in str(exc) and "anomaly_no" in str(exc):
            raise ValueError("異常單號已存在，請使用其他單號。") from exc
        raise
    if cur.rowcount == 0:
        raise ValueError("Anomaly not found")
    conn.commit()

    months_to_refresh = {
        month
        for month in (
            _month_from_date_value(existing.get("anomaly_date")),
            _month_from_date_value(existing.get("closed_at")),
            _month_from_date_value(normalized_date),
        )
        if month
    }
    for month in months_to_refresh:
        refresh_monthly_cache(conn, month)


def update_anomaly_link(conn: sqlite3.Connection, anomaly_id: str, visit_id: str | None) -> None:
    """Manually update the visit association for an existing anomaly."""
    conn.execute(
        "UPDATE anomalies SET visit_id = ?, updated_at = ? WHERE id = ?",
        (visit_id, _now_iso(), anomaly_id),
    )
    conn.commit()
    # No need to refresh monthly cache as linking doesn't change monthly counts
    # unless we later add per-month visit-anomaly linkage stats.


def delete_anomaly(conn: sqlite3.Connection, anomaly_id: str) -> None:
    anomaly_key = (anomaly_id or "").strip()
    if not anomaly_key:
        raise ValueError("Anomaly id is required")
    existing = get_anomaly_detail(conn, anomaly_key)
    if existing is None:
        raise ValueError("Anomaly not found")
    cur = conn.execute("DELETE FROM anomalies WHERE id = ?", (anomaly_key,))
    if cur.rowcount == 0:
        raise ValueError("Anomaly not found")
    conn.commit()

    months_to_refresh = {
        month
        for month in (
            _month_from_date_value(existing.get("anomaly_date")),
            _month_from_date_value(existing.get("closed_at")),
        )
        if month
    }
    for month in months_to_refresh:
        refresh_monthly_cache(conn, month)


IMPROVEMENT_DESC_MAX_LEN = 1000


def close_anomaly(
    conn: sqlite3.Connection,
    anomaly_id: str,
    improvement_desc: str,
    *,
    closed_by: str = "",
    root_cause_category: str = "",
    closed_at: str | None = None,
) -> None:
    text = (improvement_desc or "").strip()
    if not text:
        raise ValueError("Improvement description is required")
    if len(text) > IMPROVEMENT_DESC_MAX_LEN:
        raise ValueError(
            f"Improvement description exceeds {IMPROVEMENT_DESC_MAX_LEN} characters"
        )
    closer = (closed_by or "").strip()
    if not closer:
        raise ValueError("Closer is required")
    cause = (root_cause_category or "").strip()

    close_date = _normalize_strict_iso_date(
        closed_at,
        field_name="Closed date",
    )
    cur = conn.execute(
        """
        UPDATE anomalies
        SET status = '已結案',
            improvement_desc = ?,
            closed_by = ?,
            root_cause_category = ?,
            closed_at = ?,
            updated_at = ?
        WHERE id = ? AND status = '待處理'
        """,
        (text, closer, cause, close_date, _now_iso(), anomaly_id),
    )
    if cur.rowcount == 0:
        raise ValueError("Open anomaly not found")

    conn.commit()
    refresh_monthly_cache(conn, close_date[:7].replace("-", ""))


def reopen_anomaly(conn: sqlite3.Connection, anomaly_id: str) -> None:
    anomaly_key = (anomaly_id or "").strip()
    if not anomaly_key:
        raise ValueError("Anomaly id is required")
    existing = get_anomaly_detail(conn, anomaly_key)
    if existing is None:
        raise ValueError("Anomaly not found")
    if existing["status"] != "已結案":
        raise ValueError("Only closed anomalies can be reopened")

    closed_at = existing.get("closed_at")

    conn.execute(
        """
        UPDATE anomalies
        SET status = '待處理',
            improvement_desc = '',
            closed_by = '',
            root_cause_category = '',
            closed_at = NULL,
            updated_at = ?
        WHERE id = ?
        """,
        (_now_iso(), anomaly_key),
    )
    conn.commit()

    # Refresh cache for both the anomaly date and the original closure date
    months_to_refresh = {
        month
        for month in (
            _month_from_date_value(existing.get("anomaly_date")),
            _month_from_date_value(closed_at),
        )
        if month
    }
    for month in months_to_refresh:
        refresh_monthly_cache(conn, month)


def create_visit(
    conn: sqlite3.Connection,
    *,
    visit_date: str,
    supplier_id: str,
    product_id: str | None = None,
    product_name: str = "",
    product_stage: str = PRODUCT_STAGE_MASS_PRODUCTION,
    visitor_name: str = "",
    summary: str = "",
    work_order_no: str = "",
    production_qty: int = 0,
    product_sections: list[dict] | None = None,
    defect_notes: list[dict] | None = None,
    tech_transfer: bool = False,
    tech_transfer_doc: bool = False,
    carrier_requirement: bool = False,
    dispensing_process: bool = False,
    functional_test: bool = False,
    packaging_requirement: bool = False,
    tech_transfer_states: dict[str, str] | None = None,
) -> str:
    normalized_date = _normalize_strict_iso_date(
        visit_date,
        field_name="Visit date",
    )
    normalized_supplier_id = (supplier_id or "").strip()
    if not normalized_supplier_id:
        raise ValueError("Supplier is required")
    if get_supplier(conn, normalized_supplier_id) is None:
        raise ValueError("Supplier not found")
    normalized_sections = _normalize_visit_product_sections(
        conn,
        supplier_id=normalized_supplier_id,
        product_sections=product_sections,
        product_id=product_id,
        product_name=product_name,
        product_stage=product_stage,
        work_order_no=work_order_no,
        production_qty=production_qty,
    )
    primary_section = normalized_sections[0] if normalized_sections else {}
    visit_id = _insert_visit_row(
        conn,
        visit_date=normalized_date,
        supplier_id=normalized_supplier_id,
        product_id=primary_section.get("product_id"),
        product_name=str(primary_section.get("product_name") or ""),
        product_stage=str(primary_section.get("product_stage") or product_stage),
        visitor_name=visitor_name,
        summary=summary,
        work_order_no=str(primary_section.get("work_order_no") or ""),
        production_qty=primary_section.get("production_qty", 0),
        tech_transfer=tech_transfer,
        tech_transfer_doc=tech_transfer_doc,
        carrier_requirement=carrier_requirement,
        dispensing_process=dispensing_process,
        functional_test=functional_test,
        packaging_requirement=packaging_requirement,
        tech_transfer_states=tech_transfer_states,
    )
    _replace_visit_product_sections_and_defect_notes(
        conn,
        visit_id=visit_id,
        product_sections=normalized_sections,
        defect_notes=defect_notes,
    )
    conn.commit()
    refresh_monthly_cache(conn, normalized_date[:7].replace("-", ""))
    return visit_id


def get_visit_detail(conn: sqlite3.Connection, visit_id: str) -> dict | None:
    visit_key = (visit_id or "").strip()
    if not visit_key:
        return None
    row = conn.execute(
        """
        SELECT
            v.id AS id,
            v.visit_date AS visit_date,
            v.supplier_id AS supplier_id,
            s.supplier_name AS supplier_name,
            v.product_id AS product_id,
            p.product_code AS product_code,
            v.product_name AS product_name,
            v.product_stage AS product_stage,
            v.visitor_name AS visitor_name,
            v.summary AS summary,
            v.work_order_no AS work_order_no,
            v.production_qty AS production_qty,
            v.tech_transfer AS tech_transfer,
            v.tech_transfer_doc AS tech_transfer_doc,
            v.carrier_requirement AS carrier_requirement,
            v.dispensing_process AS dispensing_process,
            v.functional_test AS functional_test,
            v.packaging_requirement AS packaging_requirement,
            v.tech_transfer_doc_state AS tech_transfer_doc_state,
            v.carrier_requirement_state AS carrier_requirement_state,
            v.dispensing_process_state AS dispensing_process_state,
            v.functional_test_state AS functional_test_state,
            v.packaging_requirement_state AS packaging_requirement_state,
            v.status AS status,
            v.created_at AS created_at,
            v.updated_at AS updated_at
        FROM visits v
        JOIN suppliers s ON s.id = v.supplier_id
        LEFT JOIN products p ON p.id = v.product_id
        WHERE v.id = ?
        LIMIT 1
        """,
        (visit_key,),
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["tech_transfer"] = bool(_as_int(result.get("tech_transfer"), 0))
    for key in VISIT_TECH_TRANSFER_ITEM_COLUMNS:
        result[key] = bool(_as_int(result.get(key), 0))
    for key in VISIT_TECH_TRANSFER_STATE_COLUMNS:
        result[key] = _normalize_tech_transfer_state(result.get(key))
    result["production_qty"] = _as_int(result.get("production_qty"), 0)
    result["product_stage"] = _normalize_product_stage(result.get("product_stage"))
    result["product_sections"] = list_visit_product_sections(conn, visit_key)
    result["defect_notes"] = list_visit_defect_notes(conn, visit_key)
    _apply_visit_rollup(result)
    return result


def list_visit_product_sections(conn: sqlite3.Connection, visit_id: str) -> list[dict]:
    visit_key = (visit_id or "").strip()
    if not visit_key:
        return []
    rows = conn.execute(
        """
        SELECT
            s.id AS id,
            s.visit_id AS visit_id,
            s.product_id AS product_id,
            s.product_code AS product_code,
            s.product_name AS product_name,
            s.product_stage AS product_stage,
            s.time_slot AS time_slot,
            s.work_order_no AS work_order_no,
            s.production_qty AS production_qty,
            s.summary AS summary,
            s.sort_order AS sort_order
        FROM visit_product_sections s
        WHERE s.visit_id = ?
        ORDER BY s.sort_order ASC, s.created_at ASC, s.rowid ASC
        """,
        (visit_key,),
    ).fetchall()
    sections: list[dict] = []
    for row in rows:
        item = dict(row)
        item["production_qty"] = _as_int(item.get("production_qty"), 0)
        item["product_stage"] = _normalize_product_stage_for_read(
            item.get("product_stage")
        )
        item["defect_notes"] = list_visit_defect_notes(
            conn, visit_key, section_id=str(item["id"])
        )
        sections.append(item)
    return sections


def list_visit_defect_notes(
    conn: sqlite3.Connection, visit_id: str, *, section_id: str | None = None
) -> list[dict]:
    visit_key = (visit_id or "").strip()
    if not visit_key:
        return []
    params: list[Any] = [visit_key]
    sql = """
        SELECT
            id,
            visit_id,
            visit_product_section_id,
            defect_desc,
            improvement_desc,
            note,
            confirmed_anomaly_id,
            confirmed_at,
            sort_order
        FROM visit_defect_notes
        WHERE visit_id = ?
    """
    if section_id is not None:
        section_key = (section_id or "").strip()
        if section_key:
            sql += " AND visit_product_section_id = ?"
            params.append(section_key)
        else:
            sql += " AND (visit_product_section_id IS NULL OR trim(visit_product_section_id) = '')"
    sql += " ORDER BY sort_order ASC, created_at ASC, rowid ASC"
    rows = conn.execute(sql, params).fetchall()
    result: list[dict] = []
    for row in rows:
        item = dict(row)
        item["status"] = _defect_note_status(item.get("improvement_desc"))
        result.append(item)
    return result


def list_pending_visit_defect_notes(
    conn: sqlite3.Connection,
    *,
    limit: int | None = None,
) -> list[dict]:
    params: list[Any] = []
    sql = """
        SELECT
            n.id AS id,
            n.visit_id AS visit_id,
            n.visit_product_section_id AS visit_product_section_id,
            n.defect_desc AS defect_desc,
            n.improvement_desc AS improvement_desc,
            n.note AS note,
            n.sort_order AS sort_order,
            n.created_at AS created_at,
            v.visit_date AS visit_date,
            v.supplier_id AS supplier_id,
            s.supplier_name AS supplier_name,
            COALESCE(sec.product_id, v.product_id, '') AS product_id,
            COALESCE(sec.product_code, p.product_code, '') AS product_code,
            COALESCE(sec.product_name, v.product_name, p.product_name, '') AS product_name,
            COALESCE(sec.product_stage, v.product_stage, p.product_stage, '量產') AS product_stage
        FROM visit_defect_notes n
        JOIN visits v ON v.id = n.visit_id
        JOIN suppliers s ON s.id = v.supplier_id
        LEFT JOIN visit_product_sections sec ON sec.id = n.visit_product_section_id
        LEFT JOIN products p ON p.id = v.product_id
        WHERE n.confirmed_anomaly_id IS NULL OR trim(n.confirmed_anomaly_id) = ''
        ORDER BY v.visit_date DESC, n.created_at DESC, n.sort_order ASC
    """
    if limit is not None:
        normalized_limit = max(0, _as_int(limit, 0))
        sql += " LIMIT ?"
        params.append(normalized_limit)
    rows = conn.execute(sql, params).fetchall()
    result: list[dict] = []
    for row in rows:
        item = dict(row)
        item["status"] = _defect_note_status(item.get("improvement_desc"))
        item["product_stage"] = _normalize_product_stage_for_read(
            item.get("product_stage")
        )
        result.append(item)
    return result


def confirm_visit_defect_note_as_anomaly(
    conn: sqlite3.Connection,
    *,
    note_id: str,
    product_id: str | None = None,
    responsible_person: str = "",
    due_date: str = "",
) -> dict[str, str | None]:
    note_key = (note_id or "").strip()
    if not note_key:
        raise ValueError("Visit defect note id is required")
    note = conn.execute(
        """
        SELECT
            n.id AS id,
            n.visit_id AS visit_id,
            n.visit_product_section_id AS visit_product_section_id,
            n.defect_desc AS defect_desc,
            n.improvement_desc AS improvement_desc,
            n.confirmed_anomaly_id AS confirmed_anomaly_id,
            v.visit_date AS visit_date,
            v.supplier_id AS supplier_id,
            COALESCE(sec.product_id, v.product_id, '') AS inferred_product_id,
            COALESCE(sec.product_stage, v.product_stage, '量產') AS product_stage,
            COALESCE(sec.work_order_no, v.work_order_no, '') AS work_order_no,
            COALESCE(sec.production_qty, v.production_qty, 0) AS production_qty
        FROM visit_defect_notes n
        JOIN visits v ON v.id = n.visit_id
        LEFT JOIN visit_product_sections sec ON sec.id = n.visit_product_section_id
        WHERE n.id = ?
        LIMIT 1
        """,
        (note_key,),
    ).fetchone()
    if note is None:
        raise ValueError("Visit defect note not found")
    if str(note["confirmed_anomaly_id"] or "").strip():
        raise ValueError("Visit defect note is already confirmed as supplier anomaly")

    resolved_product_id = (product_id or "").strip() or str(
        note["inferred_product_id"] or ""
    ).strip()
    if not resolved_product_id:
        raise ValueError("Product is required to confirm visit defect as supplier anomaly")

    result = create_anomaly_with_visit_link(
        conn,
        anomaly_date=str(note["visit_date"]),
        supplier_id=str(note["supplier_id"]),
        problem_desc=str(note["defect_desc"]),
        category="訪廠/稽核缺失",
        product_id=resolved_product_id,
        product_stage=_normalize_product_stage_for_read(note["product_stage"]),
        outsource_work_order=str(note["work_order_no"] or ""),
        batch_qty=_as_int(note["production_qty"], 0),
        visit_id=str(note["visit_id"]),
        sync_visit=False,
        pending_items=str(note["improvement_desc"] or ""),
        responsible_person=responsible_person,
        due_date=due_date,
    )
    anomaly_id = str(result.get("anomaly_id") or "").strip()
    if not anomaly_id:
        raise ValueError("Supplier anomaly confirmation did not return anomaly id")
    conn.execute(
        """
        UPDATE visit_defect_notes
        SET confirmed_anomaly_id = ?,
            confirmed_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (anomaly_id, _now_iso(), _now_iso(), note_key),
    )
    conn.commit()
    result["visit_defect_note_id"] = note_key
    return result


def update_visit(
    conn: sqlite3.Connection,
    *,
    visit_id: str,
    visit_date: str,
    supplier_id: str,
    product_id: str | None = None,
    product_name: str = "",
    product_stage: str = PRODUCT_STAGE_MASS_PRODUCTION,
    visitor_name: str = "",
    summary: str = "",
    work_order_no: str = "",
    production_qty: int = 0,
    product_sections: list[dict] | None = None,
    defect_notes: list[dict] | None = None,
    tech_transfer: bool = False,
    tech_transfer_doc: bool = False,
    carrier_requirement: bool = False,
    dispensing_process: bool = False,
    functional_test: bool = False,
    packaging_requirement: bool = False,
    tech_transfer_states: dict[str, str] | None = None,
) -> None:
    visit_key = (visit_id or "").strip()
    if not visit_key:
        raise ValueError("Visit id is required")
    existing = get_visit_detail(conn, visit_key)
    if existing is None:
        raise ValueError("Visit not found")
    if _confirmed_visit_defect_note_count(conn, visit_key) > 0:
        raise ValueError(
            "Visit has confirmed supplier anomaly defect notes; edit the anomaly record instead"
        )

    normalized_supplier_id = (supplier_id or "").strip()
    if not normalized_supplier_id:
        raise ValueError("Supplier is required")
    if get_supplier(conn, normalized_supplier_id) is None:
        raise ValueError("Supplier not found")

    normalized_date = _normalize_strict_iso_date(
        visit_date,
        field_name="Visit date",
        fallback=existing["visit_date"],
    )
    normalized_sections = _normalize_visit_product_sections(
        conn,
        supplier_id=normalized_supplier_id,
        product_sections=product_sections,
        product_id=product_id,
        product_name=product_name,
        product_stage=product_stage,
        work_order_no=work_order_no,
        production_qty=production_qty,
    )
    primary_section = normalized_sections[0] if normalized_sections else {}
    booleans = {
        "tech_transfer_doc": tech_transfer_doc,
        "carrier_requirement": carrier_requirement,
        "dispensing_process": dispensing_process,
        "functional_test": functional_test,
        "packaging_requirement": packaging_requirement,
    }
    states = _resolve_tech_transfer_states(
        states=tech_transfer_states, booleans=booleans
    )
    has_any_yes = any(v == TECH_TRANSFER_STATE_YES for v in states.values())
    normalized_tech_transfer = bool(tech_transfer) or has_any_yes
    if not normalized_tech_transfer:
        states = {key: TECH_TRANSFER_STATE_NO for key in states}
    cur = conn.execute(
        """
        UPDATE visits
        SET visit_date = ?,
            supplier_id = ?,
            product_id = ?,
            product_name = ?,
            product_stage = ?,
            visitor_name = ?,
            summary = ?,
            work_order_no = ?,
            production_qty = ?,
            tech_transfer = ?,
            tech_transfer_doc = ?,
            carrier_requirement = ?,
            dispensing_process = ?,
            functional_test = ?,
            packaging_requirement = ?,
            tech_transfer_doc_state = ?,
            carrier_requirement_state = ?,
            dispensing_process_state = ?,
            functional_test_state = ?,
            packaging_requirement_state = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            normalized_date,
            normalized_supplier_id,
            primary_section.get("product_id"),
            str(primary_section.get("product_name") or ""),
            str(primary_section.get("product_stage") or product_stage),
            (visitor_name or "").strip(),
            (summary or "").strip(),
            str(primary_section.get("work_order_no") or ""),
            primary_section.get("production_qty", 0),
            1 if normalized_tech_transfer else 0,
            1 if states["tech_transfer_doc"] == TECH_TRANSFER_STATE_YES else 0,
            1 if states["carrier_requirement"] == TECH_TRANSFER_STATE_YES else 0,
            1 if states["dispensing_process"] == TECH_TRANSFER_STATE_YES else 0,
            1 if states["functional_test"] == TECH_TRANSFER_STATE_YES else 0,
            1 if states["packaging_requirement"] == TECH_TRANSFER_STATE_YES else 0,
            states["tech_transfer_doc"],
            states["carrier_requirement"],
            states["dispensing_process"],
            states["functional_test"],
            states["packaging_requirement"],
            _now_iso(),
            visit_key,
        ),
    )
    if cur.rowcount == 0:
        raise ValueError("Visit not found")
    _replace_visit_product_sections_and_defect_notes(
        conn,
        visit_id=visit_key,
        product_sections=normalized_sections,
        defect_notes=defect_notes,
    )
    conn.commit()

    months_to_refresh = {
        month
        for month in (
            _month_from_date_value(existing.get("visit_date")),
            _month_from_date_value(normalized_date),
        )
        if month
    }
    for month in months_to_refresh:
        refresh_monthly_cache(conn, month)


def delete_visit(conn: sqlite3.Connection, visit_id: str) -> None:
    visit_key = (visit_id or "").strip()
    if not visit_key:
        raise ValueError("Visit id is required")
    existing = get_visit_detail(conn, visit_key)
    if existing is None:
        raise ValueError("Visit not found")

    # 若已有異常關聯此訪廠，禁止刪除
    anomaly_refs = conn.execute(
        "SELECT COUNT(*) AS cnt FROM anomalies WHERE visit_id = ?",
        (visit_key,),
    ).fetchone()
    if anomaly_refs and int(anomaly_refs["cnt"]) > 0:
        raise ValueError(
            f"Visit is referenced by {anomaly_refs['cnt']} anomaly/anomalies"
        )

    conn.execute("DELETE FROM visit_defect_notes WHERE visit_id = ?", (visit_key,))
    conn.execute("DELETE FROM visit_product_sections WHERE visit_id = ?", (visit_key,))
    cur = conn.execute("DELETE FROM visits WHERE id = ?", (visit_key,))
    if cur.rowcount == 0:
        raise ValueError("Visit not found")
    conn.commit()

    month = _month_from_date_value(existing.get("visit_date"))
    if month:
        refresh_monthly_cache(conn, month)


def create_anomaly_with_visit_link(
    conn: sqlite3.Connection,
    *,
    anomaly_date: str,
    supplier_id: str,
    problem_desc: str,
    category: str = "",
    product_lot_no: str = "",
    product_id: str | None = None,
    product_name: str = "",
    product_stage: str = PRODUCT_STAGE_MASS_PRODUCTION,
    outsource_work_order: str = "",
    batch_qty: int = 0,
    visit_id: str | None = None,
    sync_visit: bool = True,
    visit_summary: str = "",
    pending_items: str = "",
    responsible_person: str = "",
    due_date: str = "",
    rc_supplier_inventory: str = "unconfirmed",
    rc_supplier_wip: str = "unconfirmed",
    rc_in_transit: str = "unconfirmed",
    rc_internal_inventory: str = "unconfirmed",
    is_tech_transfer: bool = False,
    anomaly_no: str | None = None,
) -> dict[str, str | None]:
    inputs = _prepare_anomaly_inputs(
        conn,
        supplier_id=supplier_id,
        problem_desc=problem_desc,
        anomaly_date=anomaly_date,
        product_id=product_id,
        product_name=product_name,
        product_stage=product_stage,
        batch_qty=batch_qty,
    )
    normalized_supplier_id = inputs.normalized_supplier_id
    normalized_date = inputs.normalized_date
    resolved_product_id = inputs.resolved_product_id
    resolved_product_name = inputs.resolved_product_name
    normalized_product_stage = inputs.normalized_product_stage
    normalized_batch_qty = inputs.normalized_batch_qty

    resolved_anomaly_no = (anomaly_no or "").strip()
    if not resolved_anomaly_no:
        resolved_anomaly_no = _next_anomaly_no(conn, normalized_date)

    linked_visit_id: str | None = None
    visit_action = "none"
    requested_visit_id = (visit_id or "").strip()
    if requested_visit_id:
        visit_row = conn.execute(
            "SELECT supplier_id FROM visits WHERE id = ?",
            (requested_visit_id,),
        ).fetchone()
        if visit_row is None:
            raise ValueError("Visit not found")
        if str(visit_row["supplier_id"] or "").strip() != normalized_supplier_id:
            raise ValueError("Visit supplier does not match selected supplier")
        linked_visit_id = requested_visit_id
        visit_action = "linked"
    elif sync_visit:
        linked_visit_id = _find_latest_visit_id(
            conn, supplier_id=normalized_supplier_id, visit_date=normalized_date
        )
        if linked_visit_id is None:
            note = (visit_summary or "").strip()
            if note:
                note = f"{note}\n由異常單 {resolved_anomaly_no} 同步建立訪廠紀錄。"
            else:
                note = f"由異常單 {resolved_anomaly_no} 同步建立訪廠紀錄。"
            linked_visit_id = _insert_visit_row(
                conn,
                visit_date=normalized_date,
                supplier_id=normalized_supplier_id,
                product_id=resolved_product_id,
                product_name=resolved_product_name,
                product_stage=normalized_product_stage,
                summary=note,
                work_order_no=outsource_work_order,
                production_qty=normalized_batch_qty,
                tech_transfer=is_tech_transfer,
            )
            _replace_visit_product_sections_and_defect_notes(
                conn,
                visit_id=linked_visit_id,
                product_sections=[
                    {
                        "product_id": resolved_product_id,
                        "product_code": (
                            get_product(conn, resolved_product_id) or {}
                        ).get("product_code", "")
                        if resolved_product_id
                        else "",
                        "product_name": resolved_product_name,
                        "product_stage": normalized_product_stage,
                        "time_slot": "",
                        "work_order_no": outsource_work_order,
                        "production_qty": normalized_batch_qty,
                        "summary": "",
                        "sort_order": 0,
                        "defect_notes": [],
                    }
                ],
                defect_notes=None,
            )
            visit_action = "created"
        else:
            visit_action = "reused"

    _insert_anomaly_row(
        conn,
        anomaly_date=normalized_date,
        supplier_id=normalized_supplier_id,
        problem_desc=problem_desc,
        category=category,
        product_lot_no=product_lot_no,
        product_id=resolved_product_id,
        product_name=resolved_product_name,
        product_stage=normalized_product_stage,
        outsource_work_order=outsource_work_order,
        batch_qty=normalized_batch_qty,
        visit_id=linked_visit_id,
        anomaly_no=resolved_anomaly_no,
        pending_items=pending_items,
        responsible_person=responsible_person,
        due_date=due_date,
        rc_supplier_inventory=rc_supplier_inventory,
        rc_supplier_wip=rc_supplier_wip,
        rc_in_transit=rc_in_transit,
        rc_internal_inventory=rc_internal_inventory,
        is_tech_transfer=is_tech_transfer,
    )
    id_row = conn.execute(
        "SELECT id FROM anomalies WHERE anomaly_no = ?",
        (resolved_anomaly_no,),
    ).fetchone()
    anomaly_id = str(id_row["id"]) if id_row else None
    conn.commit()
    refresh_monthly_cache(conn, normalized_date[:7].replace("-", ""))
    return {
        "anomaly_no": resolved_anomaly_no,
        "anomaly_id": anomaly_id,
        "visit_id": linked_visit_id,
        "visit_action": visit_action,
    }


def preview_anomaly_no(conn: sqlite3.Connection, anomaly_date: str) -> str:
    return _next_anomaly_no(conn, anomaly_date)


def get_latest_tech_transfer_for_supplier(
    conn: sqlite3.Connection, supplier_id: str
) -> dict | None:
    """查詢指定供應商最新一筆含技轉資料的訪廠紀錄（tech_transfer=1），
    作為新增異常表單參考資料使用。若無技轉紀錄則回傳 None。"""
    normalized_supplier_id = (supplier_id or "").strip()
    if not normalized_supplier_id:
        return None
    row = conn.execute(
        """
        SELECT
            v.id AS id,
            v.visit_date AS visit_date,
            v.tech_transfer AS tech_transfer,
            v.tech_transfer_doc AS tech_transfer_doc,
            v.carrier_requirement AS carrier_requirement,
            v.dispensing_process AS dispensing_process,
            v.functional_test AS functional_test,
            v.packaging_requirement AS packaging_requirement,
            v.tech_transfer_doc_state AS tech_transfer_doc_state,
            v.carrier_requirement_state AS carrier_requirement_state,
            v.dispensing_process_state AS dispensing_process_state,
            v.functional_test_state AS functional_test_state,
            v.packaging_requirement_state AS packaging_requirement_state,
            v.work_order_no AS work_order_no,
            v.production_qty AS production_qty
        FROM visits v
        WHERE v.supplier_id = ? AND v.tech_transfer = 1
        ORDER BY v.visit_date DESC, v.created_at DESC
        LIMIT 1
        """,
        (normalized_supplier_id,),
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["tech_transfer"] = bool(_as_int(result.get("tech_transfer"), 0))
    for key in VISIT_TECH_TRANSFER_ITEM_COLUMNS:
        result[key] = bool(_as_int(result.get(key), 0))
    for key in VISIT_TECH_TRANSFER_STATE_COLUMNS:
        result[key] = _normalize_tech_transfer_state(result.get(key))
    result["production_qty"] = _as_int(result.get("production_qty"), 0)
    return result


def get_latest_visit_for_supplier_on_date(
    conn: sqlite3.Connection, *, supplier_id: str, visit_date: str
) -> dict | None:
    normalized_supplier_id = (supplier_id or "").strip()
    if not normalized_supplier_id:
        return None
    normalized_date = _normalize_strict_iso_date(
        visit_date,
        field_name="Visit date",
    )
    row = conn.execute(
        """
        SELECT
            v.id AS id,
            v.visit_date AS visit_date,
            v.supplier_id AS supplier_id,
            v.product_id AS product_id,
            v.product_name AS product_name,
            v.product_stage AS product_stage,
            v.work_order_no AS work_order_no,
            v.production_qty AS production_qty
        FROM visits v
        WHERE v.supplier_id = ? AND v.visit_date = ?
        ORDER BY v.updated_at DESC, v.created_at DESC, v.rowid DESC
        LIMIT 1
        """,
        (normalized_supplier_id, normalized_date),
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["product_stage"] = _normalize_product_stage_for_read(
        result.get("product_stage")
    )
    result["production_qty"] = _as_int(result.get("production_qty"), 0)
    return result


def list_visits_by_supplier(conn: sqlite3.Connection, supplier_id: str) -> list[dict]:
    """Return all visit records for a specific supplier, ordered by date."""
    sid = (supplier_id or "").strip()
    if not sid:
        return []
    rows = conn.execute(
        """
        SELECT id, visit_date, summary, work_order_no, product_name
        FROM visits
        WHERE supplier_id = ?
        ORDER BY visit_date DESC, created_at DESC
        """,
        (sid,),
    ).fetchall()
    return [dict(row) for row in rows]


def _event_period_filter(date_column: str, yyyymm: str | None) -> tuple[str, list[Any]]:
    period_key = str(yyyymm or "").strip().upper()
    if not period_key or period_key == "ALL":
        return "", []
    if period_key == "YEAR":
        return f" AND substr({date_column}, 1, 4) = ?", [str(date.today().year)]
    if period_key == "HALF_YEAR":
        current_month = date.today().month
        start_month, end_month = (1, 6) if current_month <= 6 else (7, 12)
        return (
            f" AND substr({date_column}, 1, 4) = ?"
            f" AND cast(substr({date_column}, 6, 2) as integer) BETWEEN ? AND ?",
            [str(date.today().year), start_month, end_month],
        )

    month = _normalize_month(period_key)
    return f" AND replace(substr({date_column}, 1, 7), '-', '') = ?", [month]


def list_events(
    conn: sqlite3.Connection,
    *,
    event_type: str = "ALL",
    status: str = "ALL",
    supplier_keyword: str = "",
    yyyymm: str | None = None,
    limit: int | None = None,
    event_scope: str | None = None,
    overdue_only: bool = False,
) -> list[dict]:
    events: list[dict] = []
    keyword = (supplier_keyword or "").strip().lower()
    anomaly_period_sql, anomaly_period_params = _event_period_filter(
        "a.anomaly_date",
        yyyymm,
    )
    visit_period_sql, visit_period_params = _event_period_filter(
        "v.visit_date",
        yyyymm,
    )
    event_type_key = str(event_type or "ALL").strip().upper()
    scope = str(event_scope or "").strip().upper()
    if scope not in EVENT_SCOPE_VALUES:
        scope = ""

    if scope:
        include_anomalies = scope in {
            EVENT_SCOPE_VISIT_WITH_ANOMALY,
            EVENT_SCOPE_ANOMALY_ONLY,
            EVENT_SCOPE_CLOSED_ONLY,
        }
        include_visits = scope == EVENT_SCOPE_VISIT_ONLY
    else:
        include_anomalies = event_type_key in {"ALL", "ANOMALY"}
        include_visits = event_type_key in {"ALL", "VISIT"}

    if overdue_only:
        # Overdue is a due_date condition on anomalies; visits have no due_date.
        include_visits = False

    if include_anomalies:
        pending_items_expr = (
            "a.pending_items AS pending_items"
            if _has_column(conn, "anomalies", "pending_items")
            else "'' AS pending_items"
        )
        anomaly_sql = f"""
            SELECT
                a.id AS event_id,
                a.anomaly_no AS ref_no,
                a.anomaly_date AS event_date,
                'ANOMALY' AS event_type,
                s.supplier_name AS supplier_name,
                a.problem_desc AS content,
                a.status AS status,
                a.category AS category,
                a.visit_id AS linked_visit_id,
                v.visit_date AS linked_visit_date,
                a.product_id AS product_id,
                p.product_code AS product_code,
                a.product_lot_no AS product_lot_no,
                a.product_name AS product_name,
                a.product_stage AS product_stage,
                a.outsource_work_order AS work_order_no,
                a.batch_qty AS production_qty,
                a.outsource_work_order AS outsource_work_order,
                a.batch_qty AS batch_qty,
                a.improvement_desc AS improvement_desc,
                {pending_items_expr},
                a.closed_at AS closed_at
            FROM anomalies a
            JOIN suppliers s ON s.id = a.supplier_id
            LEFT JOIN visits v ON v.id = a.visit_id
            LEFT JOIN products p ON p.id = a.product_id
            WHERE 1=1
        """
        anomaly_params: list[Any] = []
        if scope == EVENT_SCOPE_VISIT_WITH_ANOMALY:
            anomaly_sql += " AND NULLIF(a.visit_id, '') IS NOT NULL"
        elif scope == EVENT_SCOPE_ANOMALY_ONLY:
            anomaly_sql += " AND NULLIF(a.visit_id, '') IS NULL"
        elif scope == EVENT_SCOPE_CLOSED_ONLY:
            anomaly_sql += " AND a.status = '已結案'"
        if status != "ALL":
            anomaly_sql += " AND a.status = ?"
            anomaly_params.append(status)
        elif scope in (EVENT_SCOPE_VISIT_WITH_ANOMALY, EVENT_SCOPE_ANOMALY_ONLY):
            # Move closed events to dedicated tab: exclude them from active tabs by default.
            anomaly_sql += " AND a.status != '已結案'"

        if overdue_only:
            anomaly_sql += " AND a.due_date <> '' AND a.due_date < date('now', 'localtime')"

        if keyword:
            anomaly_sql += " AND lower(s.supplier_name) LIKE ?"
            anomaly_params.append(f"%{keyword}%")
        anomaly_sql += anomaly_period_sql
        anomaly_params.extend(anomaly_period_params)

        for row in conn.execute(anomaly_sql, anomaly_params).fetchall():
            events.append(dict(row))

    if include_visits:
        visit_sql = """
            SELECT
                v.id AS event_id,
                '' AS ref_no,
                v.visit_date AS event_date,
                'VISIT' AS event_type,
                s.supplier_name AS supplier_name,
                v.summary AS content,
                v.status AS status,
                '' AS category,
                NULL AS linked_visit_id,
                NULL AS linked_visit_date,
                v.product_id AS product_id,
                p.product_code AS product_code,
                '' AS product_lot_no,
                v.product_name AS product_name,
                v.product_stage AS product_stage,
                v.work_order_no AS work_order_no,
                v.production_qty AS production_qty,
                '' AS outsource_work_order,
                0 AS batch_qty,
                '' AS improvement_desc,
                '' AS pending_items,
                NULL AS closed_at
            FROM visits v
            JOIN suppliers s ON s.id = v.supplier_id
            LEFT JOIN products p ON p.id = v.product_id
            WHERE 1=1
        """
        visit_params: list[Any] = []
        if scope == EVENT_SCOPE_VISIT_ONLY:
            visit_sql += """
                AND NOT EXISTS (
                    SELECT 1
                    FROM anomalies a_link
                    WHERE a_link.visit_id = v.id
                )
            """
        elif scope == EVENT_SCOPE_VISIT_WITH_ANOMALY:
            visit_sql += """
                AND EXISTS (
                    SELECT 1
                    FROM anomalies a_link
                    WHERE a_link.visit_id = v.id
                )
            """
        if status != "ALL":
            visit_sql += " AND v.status = ?"
            visit_params.append(status)
        if keyword:
            visit_sql += " AND lower(s.supplier_name) LIKE ?"
            visit_params.append(f"%{keyword}%")
        visit_sql += visit_period_sql
        visit_params.extend(visit_period_params)
        for row in conn.execute(visit_sql, visit_params).fetchall():
            visit_row = dict(row)
            visit_id = str(visit_row.get("event_id") or "").strip()
            visit_row["product_sections"] = list_visit_product_sections(conn, visit_id)
            visit_row["defect_notes"] = list_visit_defect_notes(conn, visit_id)
            _apply_visit_rollup(visit_row)
            if visit_row.get("defect_note_summary"):
                content = str(visit_row.get("content") or "").strip()
                visit_row["content"] = (
                    f"{content}\n{visit_row['defect_note_summary']}"
                    if content
                    else visit_row["defect_note_summary"]
                )
            events.append(visit_row)

    events.sort(
        key=lambda item: (
            item["event_date"] or "",
            item["event_type"],
            item["ref_no"] or "",
        ),
        reverse=True,
    )
    if limit is not None and limit >= 0:
        return events[:limit]
    return events


def get_dashboard_summary(conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        """
        SELECT
            COUNT(CASE WHEN status = '待處理' THEN 1 END) AS open_count,
            COUNT(CASE WHEN status = '已結案' THEN 1 END) AS closed_count,
            COUNT(CASE WHEN status = '待處理' AND (visit_id IS NULL OR visit_id = '') THEN 1 END) AS standalone_open_count
        FROM anomalies
        """
    ).fetchone()
    return {
        "unclosed_count": int(row["open_count"]),
        "open_count": int(row["open_count"]),
        "closed_count": int(row["closed_count"]),
        "standalone_open_count": int(row["standalone_open_count"]),
        "recent_events": list_events(conn, limit=10),
    }


def get_monthly_stats(conn: sqlite3.Connection, yyyymm: str) -> dict:
    current_year = date.today().year
    current_month = date.today().month

    is_dynamic = (yyyymm in ("ALL", "YEAR", "HALF_YEAR"))
    if is_dynamic:
        month = yyyymm
        if yyyymm == "ALL":
            anomaly_where = "1=1"
            visit_where = "1=1"
            closed_where = "1=1"
            anomaly_params = []
            visit_params = []
            closed_params = []
        elif yyyymm == "YEAR":
            anomaly_where = "substr(anomaly_date, 1, 4) = ?"
            visit_where = "substr(visit_date, 1, 4) = ?"
            closed_where = "substr(COALESCE(closed_at, anomaly_date), 1, 4) = ?"
            anomaly_params = [str(current_year)]
            visit_params = [str(current_year)]
            closed_params = [str(current_year)]
        else: # HALF_YEAR
            if current_month <= 6:
                anomaly_where = "substr(anomaly_date, 1, 4) = ? AND cast(substr(anomaly_date, 6, 2) as integer) BETWEEN 1 AND 6"
                visit_where = "substr(visit_date, 1, 4) = ? AND cast(substr(visit_date, 6, 2) as integer) BETWEEN 1 AND 6"
                closed_where = "substr(COALESCE(closed_at, anomaly_date), 1, 4) = ? AND cast(substr(COALESCE(closed_at, anomaly_date), 6, 2) as integer) BETWEEN 1 AND 6"
            else:
                anomaly_where = "substr(anomaly_date, 1, 4) = ? AND cast(substr(anomaly_date, 6, 2) as integer) BETWEEN 7 AND 12"
                visit_where = "substr(visit_date, 1, 4) = ? AND cast(substr(visit_date, 6, 2) as integer) BETWEEN 7 AND 12"
                closed_where = "substr(COALESCE(closed_at, anomaly_date), 1, 4) = ? AND cast(substr(COALESCE(closed_at, anomaly_date), 6, 2) as integer) BETWEEN 7 AND 12"
            anomaly_params = [str(current_year)]
            visit_params = [str(current_year)]
            closed_params = [str(current_year)]
    else:
        month = _normalize_month(yyyymm)
        refresh_monthly_cache(conn, month)
        yyyymm_prefix = f"{month[:4]}-{month[4:]}"
        anomaly_where = "substr(anomaly_date, 1, 7) = ?"
        visit_where = "substr(visit_date, 1, 7) = ?"
        closed_where = "substr(COALESCE(closed_at, anomaly_date), 1, 7) = ?"
        anomaly_params = [yyyymm_prefix]
        visit_params = [yyyymm_prefix]
        closed_params = [yyyymm_prefix]

    # Shared count block: both branches previously duplicated these queries
    # with hardcoded vs. fragment-built WHERE clauses (audit finding D9).
    visit_count = int(conn.execute(f"SELECT COUNT(*) AS c FROM visits WHERE {visit_where}", visit_params).fetchone()["c"])
    row = conn.execute(
        f"""
        SELECT
            COUNT(*) AS anomaly_count,
            COUNT(CASE WHEN status = '已結案' THEN 1 END) AS closed_anomaly_count,
            COUNT(CASE WHEN status = '待處理' THEN 1 END) AS open_anomaly_count,
            COUNT(CASE WHEN status = '待處理' AND visit_id IS NULL THEN 1 END) AS standalone_open_anomaly_count,
            COUNT(CASE WHEN status = '待處理' AND visit_id IS NOT NULL THEN 1 END) AS visit_open_anomaly_count,
            COUNT(CASE WHEN status = '待處理' AND due_date <> '' AND due_date < date('now', 'localtime') THEN 1 END) AS overdue_open_anomaly_count
        FROM anomalies
        WHERE {anomaly_where}
        """,
        anomaly_params,
    ).fetchone()
    anomaly_count = int(row["anomaly_count"])
    open_anomaly_count = int(row["open_anomaly_count"])
    standalone_open_anomaly_count = int(row["standalone_open_anomaly_count"])
    visit_open_anomaly_count = int(row["visit_open_anomaly_count"])
    overdue_open_anomaly_count = int(row["overdue_open_anomaly_count"])
    # closed_anomaly_count deliberately keeps its historical per-branch
    # semantics: fixed months count anomalies CLOSED in the month (the
    # monthly_stats_cache / KPI contract, cross-cohort close rate), while
    # dynamic ranges count closures within the opened-in-range cohort.
    # Do not unify these without a data-contract decision.
    if is_dynamic:
        closed_anomaly_count = int(row["closed_anomaly_count"])
    else:
        closed_anomaly_count = int(
            conn.execute(
                f"SELECT COUNT(*) AS c FROM anomalies WHERE status = '已結案' AND {closed_where}",
                closed_params,
            ).fetchone()["c"]
        )
    supplier_coverage_count = int(
        conn.execute(
            f"""
            SELECT COUNT(DISTINCT supplier_id) AS c
            FROM (
                SELECT supplier_id FROM anomalies WHERE {anomaly_where}
                UNION
                SELECT supplier_id FROM visits WHERE {visit_where}
            )
            """,
            anomaly_params + visit_params,
        ).fetchone()["c"]
    )

    top_sql = f"""
        WITH month_suppliers AS (
            SELECT supplier_id FROM anomalies WHERE {anomaly_where}
            UNION
            SELECT supplier_id FROM visits WHERE {visit_where}
            UNION
            SELECT supplier_id FROM anomalies WHERE status = '已結案' AND {closed_where}
        ),
        month_anomalies AS (
            SELECT
                supplier_id,
                COUNT(*) AS anomaly_count,
                AVG(julianday(COALESCE(NULLIF(closed_at, ''), date('now', 'localtime'))) - julianday(anomaly_date)) AS avg_resolution_time
            FROM anomalies
            WHERE {anomaly_where}
            GROUP BY supplier_id
        ),
        month_visits AS (
            SELECT supplier_id, COUNT(*) AS visit_count
            FROM visits
            WHERE {visit_where}
            GROUP BY supplier_id
        ),
        month_closed AS (
            SELECT supplier_id, COUNT(*) AS closed_anomaly_count
            FROM anomalies
            WHERE status = '已結案' AND {closed_where}
            GROUP BY supplier_id
        ),
        month_open AS (
            SELECT
                supplier_id,
                COUNT(*) AS open_anomaly_count,
                SUM(CASE WHEN (visit_id IS NULL OR visit_id = '') THEN 1 ELSE 0 END) AS standalone_open_anomaly_count,
                SUM(CASE WHEN (visit_id IS NOT NULL AND visit_id <> '') THEN 1 ELSE 0 END) AS visit_open_anomaly_count
            FROM anomalies
            WHERE status = '待處理' AND {anomaly_where}
            GROUP BY supplier_id
        ),
        month_overdue AS (
            SELECT supplier_id, COUNT(*) AS overdue_open_anomaly_count
            FROM anomalies
            WHERE status = '待處理' AND due_date <> '' AND due_date < date('now', 'localtime') AND {anomaly_where}
            GROUP BY supplier_id
        )
        SELECT
            s.supplier_name AS supplier_name,
            COALESCE(ma.anomaly_count, 0) AS anomaly_count,
            COALESCE(mv.visit_count, 0) AS visit_count,
            COALESCE(mc.closed_anomaly_count, 0) AS closed_anomaly_count,
            COALESCE(mo.open_anomaly_count, 0) AS open_anomaly_count,
            COALESCE(mod.overdue_open_anomaly_count, 0) AS overdue_open_anomaly_count,
            COALESCE(mo.standalone_open_anomaly_count, 0) AS standalone_open_anomaly_count,
            COALESCE(mo.visit_open_anomaly_count, 0) AS visit_open_anomaly_count,
            COALESCE(ma.avg_resolution_time, 0) AS avg_resolution_time
        FROM month_suppliers ms
        JOIN suppliers s ON s.id = ms.supplier_id
        LEFT JOIN month_anomalies ma ON ma.supplier_id = ms.supplier_id
        LEFT JOIN month_visits mv ON mv.supplier_id = ms.supplier_id
        LEFT JOIN month_closed mc ON mc.supplier_id = ms.supplier_id
        LEFT JOIN month_open mo ON mo.supplier_id = ms.supplier_id
        LEFT JOIN month_overdue mod ON mod.supplier_id = ms.supplier_id
        ORDER BY
            COALESCE(ma.anomaly_count, 0) DESC,
            COALESCE(mv.visit_count, 0) DESC,
            s.supplier_name COLLATE NOCASE ASC
    """
    top_params = tuple(
        anomaly_params + visit_params + closed_params
        + anomaly_params + visit_params + closed_params
        + anomaly_params + anomaly_params
    )

    top_supplier_rows = conn.execute(top_sql, top_params).fetchall()
    top_suppliers_by_anomaly: list[dict] = []
    for row in top_supplier_rows:
        item = dict(row)
        supplier_anomaly_count = int(item["anomaly_count"])
        supplier_closed_count = int(item["closed_anomaly_count"])
        supplier_close_rate = (
            round((supplier_closed_count / supplier_anomaly_count) * 100, 1)
            if supplier_anomaly_count > 0
            else (100.0 if supplier_closed_count > 0 else 0.0)
        )

        top_suppliers_by_anomaly.append(
            {
                "supplier_name": str(item["supplier_name"]),
                "anomaly_count": supplier_anomaly_count,
                "visit_count": int(item["visit_count"]),
                "closed_anomaly_count": supplier_closed_count,
                "open_anomaly_count": int(item["open_anomaly_count"]),
                "overdue_open_anomaly_count": int(item.get("overdue_open_anomaly_count") or 0),
                "standalone_open_anomaly_count": int(item.get("standalone_open_anomaly_count") or 0),
                "visit_open_anomaly_count": int(item.get("visit_open_anomaly_count") or 0),
                "close_rate_pct": supplier_close_rate,
                "avg_resolution_time": round(float(item.get("avg_resolution_time") or 0), 1),
            }
        )

    close_rate_pct = (
        round((closed_anomaly_count / anomaly_count) * 100, 1)
        if anomaly_count > 0
        else 0.0
    )
    anomaly_visit_ratio = (
        round(anomaly_count / visit_count, 2)
        if visit_count > 0
        else 0.0
    )
    return {
        "yyyymm": month,
        "visit_count": visit_count,
        "closed_anomaly_count": closed_anomaly_count,
        "anomaly_count": anomaly_count,
        "open_anomaly_count": open_anomaly_count,
        "standalone_open_anomaly_count": standalone_open_anomaly_count,
        "visit_open_anomaly_count": visit_open_anomaly_count,
        "overdue_open_anomaly_count": overdue_open_anomaly_count,
        "close_rate_pct": close_rate_pct,
        "anomaly_visit_ratio": anomaly_visit_ratio,
        "supplier_coverage_count": supplier_coverage_count,
        "top_suppliers_by_anomaly": top_suppliers_by_anomaly,
    }


def get_responsible_person_stats(conn: sqlite3.Connection, yyyymm: str) -> list[dict]:
    """Aggregate anomaly counts (closed, open, and unclosed range) by responsible person."""
    current_year = date.today().year
    current_month = date.today().month

    if yyyymm == "ALL":
        where_clause = ""
        params = ()
    elif yyyymm == "YEAR":
        where_clause = "WHERE substr(anomaly_date, 1, 4) = ?"
        params = (str(current_year),)
    elif yyyymm == "HALF_YEAR":
        if current_month <= 6:
            where_clause = "WHERE substr(anomaly_date, 1, 4) = ? AND cast(substr(anomaly_date, 6, 2) as integer) BETWEEN 1 AND 6"
        else:
            where_clause = "WHERE substr(anomaly_date, 1, 4) = ? AND cast(substr(anomaly_date, 6, 2) as integer) BETWEEN 7 AND 12"
        params = (str(current_year),)
    else:
        month = _normalize_month(yyyymm)
        yyyymm_prefix = f"{month[:4]}-{month[4:]}"
        where_clause = "WHERE substr(anomaly_date, 1, 7) = ?"
        params = (yyyymm_prefix,)

    sql = f"""
        SELECT 
            COALESCE(NULLIF(TRIM(responsible_person), ''), '未指定') AS person,
            COUNT(*) AS total_count,
            COUNT(CASE WHEN status = '已結案' THEN 1 END) AS closed_count,
            COUNT(CASE WHEN status = '待處理' THEN 1 END) AS open_count,
            AVG(julianday(COALESCE(NULLIF(closed_at, ''), date('now', 'localtime'))) - julianday(anomaly_date)) AS avg_days
        FROM anomalies
        {where_clause}
        GROUP BY person
        ORDER BY total_count DESC, person ASC
    """
    rows = conn.execute(sql, params).fetchall()

    # Get unclosed cases range for each person from all time
    unclosed_sql = """
        SELECT 
            COALESCE(NULLIF(TRIM(responsible_person), ''), '未指定') AS person,
            MIN(anomaly_date) AS min_date,
            MAX(anomaly_date) AS max_date
        FROM anomalies
        WHERE status = '待處理'
        GROUP BY person
    """
    unclosed_rows = conn.execute(unclosed_sql).fetchall()
    unclosed_dates = {r["person"]: (r["min_date"], r["max_date"]) for r in unclosed_rows}
    
    results = []
    for row in rows:
        person = row["person"]
        min_date, max_date = unclosed_dates.get(person, (None, None))
        results.append({
            "responsible_person": person,
            "total_count": int(row["total_count"]),
            "closed_count": int(row["closed_count"]),
            "open_count": int(row["open_count"]),
            "avg_resolution_time": round(float(row["avg_days"] or 0), 1),
            "min_open_date": min_date,
            "max_open_date": max_date,
        })
    return results


def refresh_monthly_cache(conn: sqlite3.Connection, yyyymm: str, *, _commit: bool = True) -> None:
    month = _normalize_month(yyyymm)
    yyyymm_prefix = f"{month[:4]}-{month[4:]}"
    visit_count = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM visits
        WHERE substr(visit_date, 1, 7) = ?
        """,
        (yyyymm_prefix,),
    ).fetchone()["c"]
    closed_anomaly_count = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM anomalies
        WHERE status = '已結案'
          AND substr(COALESCE(closed_at, anomaly_date), 1, 7) = ?
        """,
        (yyyymm_prefix,),
    ).fetchone()["c"]
    conn.execute(
        """
        INSERT INTO monthly_stats_cache(yyyymm, visit_count, closed_anomaly_count, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(yyyymm) DO UPDATE SET
            visit_count = excluded.visit_count,
            closed_anomaly_count = excluded.closed_anomaly_count,
            updated_at = CURRENT_TIMESTAMP
        """,
        (month, int(visit_count), int(closed_anomaly_count)),
    )
    if _commit:
        conn.commit()


def rebuild_all_monthly_cache(conn: sqlite3.Connection) -> None:
    months: set[str] = set()
    for row in conn.execute(
        "SELECT DISTINCT replace(substr(anomaly_date,1,7), '-', '') AS yyyymm FROM anomalies"
    ).fetchall():
        if row["yyyymm"]:
            months.add(str(row["yyyymm"]))
    for row in conn.execute(
        "SELECT DISTINCT replace(substr(visit_date,1,7), '-', '') AS yyyymm FROM visits"
    ).fetchall():
        if row["yyyymm"]:
            months.add(str(row["yyyymm"]))
    for month in sorted(months):
        refresh_monthly_cache(conn, month, _commit=False)
    conn.commit()


def count_rows(conn: sqlite3.Connection) -> dict:
    supplier_count = conn.execute(
        "SELECT COUNT(*) AS c FROM suppliers"
    ).fetchone()["c"]
    product_count = conn.execute(
        "SELECT COUNT(*) AS c FROM products"
    ).fetchone()["c"]
    anomaly_count = conn.execute(
        "SELECT COUNT(*) AS c FROM anomalies"
    ).fetchone()["c"]
    visit_count = conn.execute(
        "SELECT COUNT(*) AS c FROM visits"
    ).fetchone()["c"]
    return {
        "suppliers": int(supplier_count),
        "products": int(product_count),
        "anomalies": int(anomaly_count),
        "visits": int(visit_count),
    }


def seed_products_from_anomalies(conn: sqlite3.Connection) -> dict[str, int | bool]:
    if get_migration_meta(conn, "products_seeded_v1") == "1":
        return {"seeded": False, "created": 0, "backfilled": 0}

    rows = conn.execute(
        """
        SELECT DISTINCT supplier_id, trim(product_name) AS product_name
        FROM anomalies
        WHERE trim(product_name) <> ''
        ORDER BY supplier_id, product_name
        """
    ).fetchall()

    created = 0
    mapping: dict[tuple[str, str], str] = {}
    for row in rows:
        supplier_id = str(row["supplier_id"])
        product_name = str(row["product_name"]).strip()
        if not product_name:
            continue
        key = (supplier_id, product_name)
        existing_product_id = _find_product_id_by_name_scope(
            conn,
            product_name=product_name,
            supplier_id=supplier_id,
        )
        if existing_product_id is None:
            existing_product_id = _gen_id()
            conn.execute(
                """
                INSERT INTO products(
                    id, product_code, product_name, product_stage, supplier_id, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    existing_product_id,
                    _next_auto_product_code(conn),
                    product_name,
                    PRODUCT_STAGE_MASS_PRODUCTION,
                    supplier_id,
                    _now_iso(),
                    _now_iso(),
                ),
            )
            created += 1
        mapping[key] = existing_product_id

    backfilled = 0
    for (supplier_id, product_name), product_id in mapping.items():
        cur = conn.execute(
            """
            UPDATE anomalies
            SET product_id = ?, updated_at = ?
            WHERE product_id IS NULL
              AND supplier_id = ?
              AND trim(product_name) = ?
            """,
            (product_id, _now_iso(), supplier_id, product_name),
        )
        backfilled += int(cur.rowcount)

    upsert_migration_meta(conn, "products_seeded_v1", "1")
    conn.commit()
    return {"seeded": True, "created": created, "backfilled": backfilled}


def _resolve_product_selection(
    conn: sqlite3.Connection,
    *,
    supplier_id: str,
    product_id: str | None = None,
    fallback_name: str = "",
) -> tuple[str | None, str, str]:
    normalized_product_id = (product_id or "").strip() or None
    normalized_name = (fallback_name or "").strip()
    if not normalized_product_id:
        return None, normalized_name, PRODUCT_STAGE_MASS_PRODUCTION

    product = get_product(conn, normalized_product_id)
    if product is None:
        raise ValueError("Product not found")
    product_supplier_id = str(product.get("supplier_id") or "").strip()
    product_secondary_supplier_id = str(
        product.get("secondary_supplier_id") or ""
    ).strip()
    matched = False
    if product_supplier_id == supplier_id:
        matched = True
    if product_secondary_supplier_id == supplier_id:
        matched = True
    if not product_supplier_id and not product_secondary_supplier_id:
        matched = True
    if not matched:
        raise ValueError("Product does not belong to selected supplier")
    return (
        normalized_product_id,
        str(product.get("product_name") or normalized_name),
        _normalize_product_stage_for_read(product.get("product_stage")),
    )
_STRICT_ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _normalize_optional_iso_date(value: Any, *, field_name: str) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if not _STRICT_ISO_DATE_PATTERN.fullmatch(text):
        raise ValueError(f"{field_name} must be YYYY-MM-DD")
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field_name} must be YYYY-MM-DD") from exc


def _insert_anomaly_row(
    conn: sqlite3.Connection,
    *,
    anomaly_date: str,
    supplier_id: str,
    problem_desc: str,
    category: str = "",
    product_lot_no: str = "",
    product_id: str | None = None,
    product_name: str = "",
    product_stage: str = PRODUCT_STAGE_MASS_PRODUCTION,
    outsource_work_order: str = "",
    batch_qty: int = 0,
    visit_id: str | None = None,
    anomaly_no: str | None = None,
    pending_items: str = "",
    responsible_person: str = "",
    due_date: str = "",
    rc_supplier_inventory: str = "unconfirmed",
    rc_supplier_wip: str = "unconfirmed",
    rc_in_transit: str = "unconfirmed",
    rc_internal_inventory: str = "unconfirmed",
    is_tech_transfer: bool = False,
) -> str:
    normalized_date = _normalize_strict_iso_date(
        anomaly_date,
        field_name="Anomaly date",
    )
    _ensure_date_not_in_future(normalized_date, field_name="Anomaly date")
    normalized_product_stage = _normalize_product_stage(product_stage)
    normalized_batch_qty = _normalize_non_negative_int(
        batch_qty,
        field_name="Batch quantity",
    )
    normalized_due_date = _normalize_optional_iso_date(
        due_date, field_name="Due date"
    )

    def _do_insert(resolved_no: str) -> None:
        conn.execute(
            """
            INSERT INTO anomalies(
                id, anomaly_no, anomaly_date, supplier_id, visit_id, product_id, problem_desc,
                category, product_lot_no, product_name, product_stage, outsource_work_order, batch_qty,
                status, improvement_desc, closed_at, created_at, updated_at,
                pending_items, responsible_person, due_date,
                rc_supplier_inventory, rc_supplier_wip, rc_in_transit, rc_internal_inventory,
                is_tech_transfer
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '待處理', '', NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _gen_id(),
                resolved_no,
                normalized_date,
                supplier_id,
                visit_id,
                (product_id or "").strip() or None,
                problem_desc.strip(),
                (category or "").strip(),
                (product_lot_no or "").strip(),
                (product_name or "").strip(),
                normalized_product_stage,
                (outsource_work_order or "").strip(),
                normalized_batch_qty,
                _now_iso(),
                _now_iso(),
                (pending_items or "").strip(),
                (responsible_person or "").strip(),
                normalized_due_date,
                (rc_supplier_inventory or "unconfirmed").strip(),
                (rc_supplier_wip or "unconfirmed").strip(),
                (rc_in_transit or "unconfirmed").strip(),
                (rc_internal_inventory or "unconfirmed").strip(),
                1 if is_tech_transfer else 0,
            ),
        )

    if anomaly_no:
        # Caller already reserved this number (e.g. create_anomaly_with_visit_link
        # embeds it into a visit summary text before reaching here), so a
        # collision here is a genuine caller bug, not a race -- retrying with a
        # different number would desync it from that already-written text.
        try:
            _do_insert(anomaly_no)
            return anomaly_no
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint failed" in str(exc) and "anomaly_no" in str(exc):
                raise ValueError("異常單號已存在，請使用其他單號。") from exc
            raise

    # No anomaly_no supplied (create_anomaly's direct path): generate + insert
    # with retry-on-collision, mirroring _apply_key_updates' UNIQUE-collision
    # retry pattern (audit finding A7).
    max_retries = 3
    last_exc: sqlite3.IntegrityError | None = None
    for _attempt in range(max_retries):
        resolved_anomaly_no = _next_anomaly_no(conn, normalized_date)
        try:
            _do_insert(resolved_anomaly_no)
            return resolved_anomaly_no
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint failed" in str(exc) and "anomaly_no" in str(exc):
                last_exc = exc
                continue
            raise
    raise last_exc


def _normalize_visit_product_sections(
    conn: sqlite3.Connection,
    *,
    supplier_id: str,
    product_sections: list[dict] | None,
    product_id: str | None = None,
    product_name: str = "",
    product_stage: str = PRODUCT_STAGE_MASS_PRODUCTION,
    work_order_no: str = "",
    production_qty: int = 0,
) -> list[dict]:
    if product_sections is None:
        legacy_production_qty = _normalize_non_negative_int(
            production_qty,
            field_name="Production quantity",
        )
        legacy_has_value = any(
            (
                (product_id or "").strip(),
                (product_name or "").strip(),
                (work_order_no or "").strip(),
                legacy_production_qty > 0,
            )
        )
        raw_sections: list[dict] = (
            [
                {
                    "product_id": product_id,
                    "product_name": product_name,
                    "product_stage": product_stage,
                    "work_order_no": work_order_no,
                    "production_qty": legacy_production_qty,
                    "summary": "",
                    "time_slot": "",
                    "defect_notes": [],
                }
            ]
            if legacy_has_value
            else []
        )
    else:
        raw_sections = list(product_sections)

    normalized: list[dict] = []
    for idx, raw in enumerate(raw_sections):
        if raw is None:
            continue
        item = dict(raw)
        raw_product_id = str(item.get("product_id") or "").strip()
        raw_product_name = str(item.get("product_name") or "").strip()
        raw_stage = str(item.get("product_stage") or PRODUCT_STAGE_MASS_PRODUCTION)
        time_slot = str(item.get("time_slot") or "").strip()
        section_work_order = str(item.get("work_order_no") or "").strip()
        section_summary = str(item.get("summary") or "").strip()
        section_qty = _normalize_non_negative_int(
            item.get("production_qty", 0),
            field_name="Production quantity",
        )

        has_any_value = any(
            (
                raw_product_id,
                raw_product_name,
                time_slot,
                section_work_order,
                section_summary,
                section_qty > 0,
                item.get("defect_notes"),
            )
        )
        if not has_any_value:
            continue

        if raw_product_id:
            resolved_product_id, resolved_product_name, resolved_product_stage = (
                _resolve_product_selection(
                    conn,
                    supplier_id=supplier_id,
                    product_id=raw_product_id,
                    fallback_name=raw_product_name,
                )
            )
        else:
            resolved_product_id = None
            resolved_product_name = raw_product_name
            resolved_product_stage = raw_stage
        product = get_product(conn, resolved_product_id) if resolved_product_id else None
        product_code = str(
            (product or {}).get("product_code") or item.get("product_code") or ""
        ).strip()
        normalized.append(
            {
                "product_id": resolved_product_id,
                "product_code": product_code,
                "product_name": resolved_product_name,
                "product_stage": _normalize_product_stage(
                    resolved_product_stage or raw_stage
                ),
                "time_slot": time_slot,
                "work_order_no": section_work_order,
                "production_qty": section_qty,
                "summary": section_summary,
                "sort_order": _as_int(item.get("sort_order"), idx),
                "defect_notes": list(item.get("defect_notes") or []),
            }
        )
    return normalized


def _normalize_visit_defect_notes(raw_notes: list[dict] | None) -> list[dict]:
    normalized: list[dict] = []
    for idx, raw in enumerate(raw_notes or []):
        if raw is None:
            continue
        item = dict(raw)
        defect_desc = str(
            item.get("defect_desc") or item.get("defect") or item.get("description") or ""
        ).strip()
        improvement_desc = str(item.get("improvement_desc") or "").strip()
        note = str(item.get("note") or item.get("remark") or "").strip()
        if not any((defect_desc, improvement_desc, note)):
            continue
        if not defect_desc:
            raise ValueError("Defect description is required")
        normalized.append(
            {
                "defect_desc": defect_desc,
                "improvement_desc": improvement_desc,
                "note": note,
                "sort_order": _as_int(item.get("sort_order"), idx),
            }
        )
    return normalized


def _confirmed_visit_defect_note_count(
    conn: sqlite3.Connection,
    visit_id: str,
) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM visit_defect_notes
        WHERE visit_id = ?
          AND confirmed_anomaly_id IS NOT NULL
          AND trim(confirmed_anomaly_id) <> ''
        """,
        ((visit_id or "").strip(),),
    ).fetchone()
    return _as_int(row["c"], 0) if row is not None else 0


def _replace_visit_product_sections_and_defect_notes(
    conn: sqlite3.Connection,
    *,
    visit_id: str,
    product_sections: list[dict],
    defect_notes: list[dict] | None,
) -> None:
    visit_key = (visit_id or "").strip()
    if not visit_key:
        raise ValueError("Visit id is required")
    if _confirmed_visit_defect_note_count(conn, visit_key) > 0:
        raise ValueError(
            "Visit has confirmed supplier anomaly defect notes; edit the anomaly record instead"
        )
    conn.execute("DELETE FROM visit_defect_notes WHERE visit_id = ?", (visit_key,))
    conn.execute("DELETE FROM visit_product_sections WHERE visit_id = ?", (visit_key,))

    now = _now_iso()
    for idx, section in enumerate(product_sections):
        section_id = _gen_id()
        conn.execute(
            """
            INSERT INTO visit_product_sections(
                id, visit_id, product_id, product_code, product_name, product_stage,
                time_slot, work_order_no, production_qty, summary, sort_order,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                section_id,
                visit_key,
                section.get("product_id"),
                str(section.get("product_code") or "").strip(),
                str(section.get("product_name") or "").strip(),
                _normalize_product_stage(section.get("product_stage")),
                str(section.get("time_slot") or "").strip(),
                str(section.get("work_order_no") or "").strip(),
                _normalize_non_negative_int(
                    section.get("production_qty", 0),
                    field_name="Production quantity",
                ),
                str(section.get("summary") or "").strip(),
                _as_int(section.get("sort_order"), idx),
                now,
                now,
            ),
        )
        for note in _normalize_visit_defect_notes(section.get("defect_notes") or []):
            _insert_visit_defect_note_row(
                conn,
                visit_id=visit_key,
                section_id=section_id,
                defect_desc=note["defect_desc"],
                improvement_desc=note["improvement_desc"],
                note=note["note"],
                sort_order=note["sort_order"],
                now=now,
            )

    for note in _normalize_visit_defect_notes(defect_notes):
        _insert_visit_defect_note_row(
            conn,
            visit_id=visit_key,
            section_id=None,
            defect_desc=note["defect_desc"],
            improvement_desc=note["improvement_desc"],
            note=note["note"],
            sort_order=note["sort_order"],
            now=now,
        )


def _insert_visit_defect_note_row(
    conn: sqlite3.Connection,
    *,
    visit_id: str,
    section_id: str | None,
    defect_desc: str,
    improvement_desc: str,
    note: str,
    sort_order: int,
    now: str,
) -> None:
    conn.execute(
        """
        INSERT INTO visit_defect_notes(
            id, visit_id, visit_product_section_id, defect_desc, improvement_desc,
            note, sort_order, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _gen_id(),
            visit_id,
            (section_id or "").strip() or None,
            defect_desc.strip(),
            improvement_desc.strip(),
            note.strip(),
            int(sort_order),
            now,
            now,
        ),
    )


def _defect_note_status(improvement_desc: Any) -> str:
    return (
        DEFECT_NOTE_IMPROVED
        if str(improvement_desc or "").strip()
        else DEFECT_NOTE_PENDING_IMPROVEMENT
    )


def _apply_visit_rollup(row: dict) -> None:
    sections = list(row.get("product_sections") or [])
    notes = list(row.get("defect_notes") or [])
    product_names = _join_unique_texts(section.get("product_name") for section in sections)
    product_codes = _join_unique_texts(section.get("product_code") for section in sections)
    if product_names:
        row["product_name"] = product_names
    if product_codes:
        row["product_code"] = product_codes
    row["defect_note_count"] = len(notes)
    row["pending_improvement_count"] = sum(
        1 for note in notes if not str(note.get("improvement_desc") or "").strip()
    )
    if notes:
        row["defect_note_summary"] = (
            f"缺失 {len(notes)} 筆 / 待補改善 {row['pending_improvement_count']} 筆"
        )
    else:
        row["defect_note_summary"] = ""


def _join_unique_texts(values: Any) -> str:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return "、".join(result)


def _prepare_tech_transfer_values(
    *,
    tech_transfer: bool = False,
    tech_transfer_doc: bool = False,
    carrier_requirement: bool = False,
    dispensing_process: bool = False,
    functional_test: bool = False,
    packaging_requirement: bool = False,
    tech_transfer_states: dict[str, str] | None = None,
) -> tuple[bool, dict[str, str]]:
    booleans = {
        "tech_transfer_doc": tech_transfer_doc,
        "carrier_requirement": carrier_requirement,
        "dispensing_process": dispensing_process,
        "functional_test": functional_test,
        "packaging_requirement": packaging_requirement,
    }
    states = _resolve_tech_transfer_states(states=tech_transfer_states, booleans=booleans)
    has_any_yes = any(v == TECH_TRANSFER_STATE_YES for v in states.values())
    normalized_tech_transfer = bool(tech_transfer) or has_any_yes
    if not normalized_tech_transfer:
        states = {key: TECH_TRANSFER_STATE_NO for key in states}
    return normalized_tech_transfer, states


def _insert_visit_row(
    conn: sqlite3.Connection,
    *,
    visit_date: str,
    supplier_id: str,
    product_id: str | None = None,
    product_name: str = "",
    product_stage: str = PRODUCT_STAGE_MASS_PRODUCTION,
    visitor_name: str = "",
    summary: str = "",
    work_order_no: str = "",
    production_qty: int = 0,
    tech_transfer: bool = False,
    tech_transfer_doc: bool = False,
    carrier_requirement: bool = False,
    dispensing_process: bool = False,
    functional_test: bool = False,
    packaging_requirement: bool = False,
    tech_transfer_states: dict[str, str] | None = None,
) -> str:
    visit_id = _gen_id()
    normalized_date = _normalize_strict_iso_date(
        visit_date,
        field_name="Visit date",
    )
    normalized_product_stage = _normalize_product_stage(product_stage)
    normalized_production_qty = _normalize_non_negative_int(
        production_qty,
        field_name="Production quantity",
    )
    normalized_tech_transfer, states = _prepare_tech_transfer_values(
        tech_transfer=tech_transfer,
        tech_transfer_doc=tech_transfer_doc,
        carrier_requirement=carrier_requirement,
        dispensing_process=dispensing_process,
        functional_test=functional_test,
        packaging_requirement=packaging_requirement,
        tech_transfer_states=tech_transfer_states,
    )
    conn.execute(
        """
        INSERT INTO visits(
            id, visit_date, supplier_id, product_id, product_name, product_stage, visitor_name, summary,
            work_order_no, production_qty, tech_transfer, tech_transfer_doc,
            carrier_requirement, dispensing_process, functional_test, packaging_requirement,
            tech_transfer_doc_state, carrier_requirement_state, dispensing_process_state,
            functional_test_state, packaging_requirement_state,
            status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '已完成', ?, ?)
        """,
        (
            visit_id,
            normalized_date,
            supplier_id,
            (product_id or "").strip() or None,
            (product_name or "").strip(),
            normalized_product_stage,
            (visitor_name or "").strip(),
            (summary or "").strip(),
            (work_order_no or "").strip(),
            normalized_production_qty,
            1 if normalized_tech_transfer else 0,
            1 if states["tech_transfer_doc"] == TECH_TRANSFER_STATE_YES else 0,
            1 if states["carrier_requirement"] == TECH_TRANSFER_STATE_YES else 0,
            1 if states["dispensing_process"] == TECH_TRANSFER_STATE_YES else 0,
            1 if states["functional_test"] == TECH_TRANSFER_STATE_YES else 0,
            1 if states["packaging_requirement"] == TECH_TRANSFER_STATE_YES else 0,
            states["tech_transfer_doc"],
            states["carrier_requirement"],
            states["dispensing_process"],
            states["functional_test"],
            states["packaging_requirement"],
            _now_iso(),
            _now_iso(),
        ),
    )
    return visit_id


def _find_latest_visit_id(
    conn: sqlite3.Connection, *, supplier_id: str, visit_date: str
) -> str | None:
    normalized_date = _normalize_strict_iso_date(visit_date, field_name="Visit date")
    row = conn.execute(
        """
        SELECT id
        FROM visits
        WHERE supplier_id = ? AND visit_date = ?
        ORDER BY created_at DESC, rowid DESC
        LIMIT 1
        """,
        (supplier_id, normalized_date),
    ).fetchone()
    if row is None:
        return None
    return str(row["id"])


def _backfill_visit_product_sections(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "visit_product_sections"):
        return
    rows = conn.execute(
        """
        SELECT
            v.id AS visit_id,
            v.product_id AS product_id,
            coalesce(p.product_code, '') AS product_code,
            v.product_name AS product_name,
            v.product_stage AS product_stage,
            v.work_order_no AS work_order_no,
            v.production_qty AS production_qty
        FROM visits v
        LEFT JOIN products p ON p.id = v.product_id
        WHERE NOT EXISTS (
            SELECT 1
            FROM visit_product_sections s
            WHERE s.visit_id = v.id
        )
          AND (
              NULLIF(trim(coalesce(v.product_id, '')), '') IS NOT NULL
              OR trim(coalesce(v.product_name, '')) <> ''
              OR trim(coalesce(v.work_order_no, '')) <> ''
              OR coalesce(v.production_qty, 0) > 0
          )
        """
    ).fetchall()
    now = _now_iso()
    for row in rows:
        conn.execute(
            """
            INSERT INTO visit_product_sections(
                id, visit_id, product_id, product_code, product_name, product_stage,
                time_slot, work_order_no, production_qty, summary, sort_order,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, '', ?, ?, '', 0, ?, ?)
            """,
            (
                _gen_id(),
                row["visit_id"],
                (row["product_id"] or "").strip() or None,
                str(row["product_code"] or "").strip(),
                str(row["product_name"] or "").strip(),
                _normalize_product_stage_for_read(row["product_stage"]),
                str(row["work_order_no"] or "").strip(),
                _as_int(row["production_qty"], 0),
                now,
                now,
            ),
        )


def _next_anomaly_no(conn: sqlite3.Connection, anomaly_date: str) -> str:
    normalized_date = _normalize_date(anomaly_date)
    day_key = normalized_date.replace("-", "")
    prefix = day_key
    row = conn.execute(
        """
        SELECT COALESCE(MAX(
            CASE
                WHEN length(anomaly_no) = 11 AND anomaly_no GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'
                    AND substr(anomaly_no, 1, 8) = ?
                THEN CAST(substr(anomaly_no, 9) AS INTEGER)
            END
        ), 0) AS max_seq
        FROM anomalies
        WHERE anomaly_date = ?
        """,
        (prefix, normalized_date),
    ).fetchone()
    seq = int(row["max_seq"]) + 1
    return f"{prefix}{seq:03d}"


def _next_auto_product_code(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        """
        SELECT COALESCE(MAX(
            CASE
                WHEN product_code GLOB 'AUTO-[0-9][0-9][0-9][0-9]'
                    AND substr(product_code, 6) IS NOT NULL
                THEN CAST(substr(product_code, 6) AS INTEGER)
            END
        ), 0) AS max_seq
        FROM products
        WHERE product_code LIKE 'AUTO-%'
        """
    ).fetchone()
    return f"AUTO-{int(row['max_seq']) + 1:04d}"


def _find_product_id_by_name_scope(
    conn: sqlite3.Connection,
    *,
    product_name: str,
    supplier_id: str | None,
) -> str | None:
    normalized_name = (product_name or "").strip()
    normalized_supplier_id = (supplier_id or "").strip()
    if not normalized_name:
        return None
    if normalized_supplier_id:
        row = conn.execute(
            """
            SELECT id
            FROM products
            WHERE product_name = ? AND supplier_id = ?
            LIMIT 1
            """,
            (normalized_name, normalized_supplier_id),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT id
            FROM products
            WHERE product_name = ? AND supplier_id IS NULL
            LIMIT 1
            """,
            (normalized_name,),
        ).fetchone()
    if row is None:
        return None
    return str(row["id"])
def _table_sql(conn: sqlite3.Connection, table_name: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    ).fetchone()
    if row is None:
        return ""
    if isinstance(row, sqlite3.Row):
        return str(row["sql"] or "")
    return str(row[0] or "")


def _ensure_product_indexes(conn: sqlite3.Connection) -> None:
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
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_products_supplier ON products(supplier_id)"
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_products_secondary_supplier
            ON products(secondary_supplier_id)
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active)"
    )


def _ensure_column(
    conn: sqlite3.Connection, table_name: str, column_name: str, column_ddl: str
) -> None:
    if _has_column(conn, table_name, column_name):
        return
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_ddl}")


def _has_column(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(str(row["name"]) == column_name for row in rows)


def _ensure_index(
    conn: sqlite3.Connection, index_name: str, table_name: str, column_name: str
) -> None:
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({column_name})"
    )


def _normalize_defect_records_optional_work_order(conn: sqlite3.Connection) -> None:
    """Drop the legacy ``CHECK(TRIM(work_order_no) <> '')`` so 委外製令 is optional.

    SQLite cannot drop a CHECK constraint via ALTER, so rebuild the table when the
    old constraint is still present. Idempotent: returns early once the constraint
    is gone. ``defect_records`` has no triggers in sqe_v2.db; its only dependent
    object is the ``uniq_defect_records_business_key`` index, recreated afterwards.
    """
    table_sql = _table_sql(conn, "defect_records")
    if not table_sql or "CHECK(TRIM(work_order_no)" not in table_sql:
        return

    conn.commit()
    fk_row = conn.execute("PRAGMA foreign_keys").fetchone()
    fk_enabled = bool(_as_int((fk_row[0] if fk_row is not None else 1), 1))
    if fk_enabled:
        conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DROP TABLE IF EXISTS defect_records__new")
        conn.execute(
            """
            CREATE TABLE defect_records__new (
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
            )
            """
        )
        conn.execute(
            """
            INSERT INTO defect_records__new(
                id, defect_no, event_date, return_slip_type, work_order_no,
                internal_work_order_no, transfer_slip_no, item_no, product_name, qty,
                category, supplier_name, outsource_supplier_name, defect_desc, status,
                disposition, responsibility, created_at
            )
            SELECT
                id, defect_no, event_date, return_slip_type, work_order_no,
                internal_work_order_no, transfer_slip_no, item_no, product_name, qty,
                category, supplier_name, outsource_supplier_name, defect_desc, status,
                disposition, responsibility, created_at
            FROM defect_records
            """
        )
        conn.execute("DROP TABLE defect_records")
        conn.execute("ALTER TABLE defect_records__new RENAME TO defect_records")
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uniq_defect_records_business_key
                ON defect_records(
                    event_date, work_order_no, internal_work_order_no,
                    transfer_slip_no, item_no, defect_desc
                )
            """
        )
        conn.execute("COMMIT")
    except Exception:
        logger.exception("_normalize_defect_records_optional_work_order failed")
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        if fk_enabled:
            conn.execute("PRAGMA foreign_keys=ON")


def _normalize_event_status_tables(conn: sqlite3.Connection) -> None:
    """Normalize legacy OPEN/CLOSED/COMPLETED status values to zh-TW.

    One-time migration guarded by the ``event_status_normalized_v1`` meta key.
    A rebuild only runs when legacy status *values* still exist or a stale
    ``CHECK`` constraint mentions the legacy tokens. The anomalies/visits
    rebuilds run inside a single ``BEGIN IMMEDIATE`` transaction with foreign
    key enforcement temporarily disabled; the transaction is rolled back on any
    error and the connection's prior FK state is restored afterward. This keeps
    the migration atomic — an interrupted run leaves the original tables intact
    rather than a half-migrated schema.
    """
    if get_migration_meta(conn, "event_status_normalized_v1") == "1":
        return

    anomalies_sql = _table_sql(conn, "anomalies")
    visits_sql = _table_sql(conn, "visits")

    needs_anomaly_rebuild = False
    needs_visit_rebuild = False
    if anomalies_sql:
        needs_anomaly_rebuild = ("'OPEN'" in anomalies_sql) or ("'CLOSED'" in anomalies_sql)
    if visits_sql:
        needs_visit_rebuild = "'COMPLETED'" in visits_sql

    if (
        conn.execute(
            "SELECT 1 FROM anomalies WHERE status IN ('OPEN', 'CLOSED') LIMIT 1"
        ).fetchone()
        is not None
    ):
        needs_anomaly_rebuild = True
    if (
        conn.execute(
            "SELECT 1 FROM visits WHERE status != '已完成' LIMIT 1"
        ).fetchone()
        is not None
    ):
        needs_visit_rebuild = True

    if not needs_anomaly_rebuild and not needs_visit_rebuild:
        upsert_migration_meta(conn, "event_status_normalized_v1", "1")
        return

    conn.commit()
    fk_row = conn.execute("PRAGMA foreign_keys").fetchone()
    fk_enabled = bool(_as_int((fk_row[0] if fk_row is not None else 1), 1))
    if fk_enabled:
        conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("BEGIN IMMEDIATE")
        if needs_visit_rebuild:
            _rebuild_visits_with_zh_status(conn)
        if needs_anomaly_rebuild:
            _rebuild_anomalies_with_zh_status(conn)
        conn.execute("COMMIT")
        upsert_migration_meta(conn, "event_status_normalized_v1", "1")
    except Exception:
        logger.exception("_normalize_event_status_tables failed")
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        if fk_enabled:
            conn.execute("PRAGMA foreign_keys=ON")


def _rebuild_anomalies_with_zh_status(conn: sqlite3.Connection) -> None:
    """Rebuild anomalies, mapping legacy OPEN/CLOSED status to 待處理/已結案.

    Single-pass table reconstruction matching the canonical anomalies schema
    and restoring the ``CHECK (status IN ('待處理','已結案'))`` constraint.
    Must run inside the caller's transaction with FK enforcement disabled (see
    ``_normalize_event_status_tables``); it uses individual ``conn.execute``
    statements — never ``executescript`` — so it does not commit mid-rebuild.
    Only ``status`` (and the derived ``closed_at``) are normalized; every other
    column, including ``product_stage`` (試產/量產) and the closure-tracking
    fields, is preserved as-is.
    """
    conn.execute("DROP TABLE IF EXISTS anomalies__new")
    conn.execute(
        """
        CREATE TABLE anomalies__new (
            id TEXT PRIMARY KEY,
            anomaly_no TEXT NOT NULL UNIQUE,
            anomaly_date TEXT NOT NULL,
            supplier_id TEXT NOT NULL,
            visit_id TEXT,
            product_id TEXT,
            problem_desc TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '',
            product_lot_no TEXT NOT NULL DEFAULT '',
            product_name TEXT NOT NULL DEFAULT '',
            product_stage TEXT NOT NULL DEFAULT '量產',
            outsource_work_order TEXT NOT NULL DEFAULT '',
            batch_qty INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT '待處理' CHECK (status IN ('待處理','已結案')),
            improvement_desc TEXT NOT NULL DEFAULT '',
            closed_by TEXT NOT NULL DEFAULT '',
            root_cause_category TEXT NOT NULL DEFAULT '',
            closed_at TEXT,
            pending_items TEXT NOT NULL DEFAULT '',
            responsible_person TEXT NOT NULL DEFAULT '',
            due_date TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
            FOREIGN KEY (visit_id) REFERENCES visits(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO anomalies__new(
            id, anomaly_no, anomaly_date, supplier_id, visit_id, product_id,
            problem_desc, category, product_lot_no, product_name, product_stage,
            outsource_work_order, batch_qty, status, improvement_desc, closed_by,
            root_cause_category, closed_at, pending_items, responsible_person,
            due_date, created_at, updated_at
        )
        SELECT
            id, anomaly_no, anomaly_date, supplier_id, visit_id, product_id,
            problem_desc, category, product_lot_no, product_name, product_stage,
            outsource_work_order, batch_qty,
            CASE
                WHEN status IN ('OPEN', '待處理') THEN '待處理'
                WHEN status IN ('CLOSED', '已結案') THEN '已結案'
                ELSE '待處理'
            END AS status,
            improvement_desc, closed_by, root_cause_category,
            CASE
                WHEN status IN ('CLOSED', '已結案') THEN closed_at
                ELSE NULL
            END AS closed_at,
            pending_items, responsible_person, due_date, created_at, updated_at
        FROM anomalies
        """
    )
    conn.execute("DROP TABLE anomalies")
    conn.execute("ALTER TABLE anomalies__new RENAME TO anomalies")
    # Recreate the full index set so the rebuilt table is complete in this same
    # run (the DROP discarded every index, including idx_anomalies_visit/product
    # created earlier in create_schema).
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_anomalies_date ON anomalies(anomaly_date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_anomalies_supplier ON anomalies(supplier_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_anomalies_status ON anomalies(status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_anomalies_visit ON anomalies(visit_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_anomalies_product ON anomalies(product_id)"
    )


def _rebuild_visits_with_zh_status(conn: sqlite3.Connection) -> None:
    """Rebuild visits, normalizing legacy status values to '已完成'.

    Single-pass table reconstruction matching the canonical visits schema and
    restoring the ``CHECK (status='已完成')`` constraint. Must run inside the
    caller's transaction with FK enforcement disabled (see
    ``_normalize_event_status_tables``); it uses individual ``conn.execute``
    statements — never ``executescript`` — so it does not commit mid-rebuild.
    Every column is preserved as-is except ``status``, which is forced to
    '已完成' (the only value the constraint permits).
    """
    conn.execute("DROP TABLE IF EXISTS visits__new")
    conn.execute(
        """
        CREATE TABLE visits__new (
            id TEXT PRIMARY KEY,
            visit_date TEXT NOT NULL,
            supplier_id TEXT NOT NULL,
            product_id TEXT,
            product_name TEXT NOT NULL DEFAULT '',
            product_stage TEXT NOT NULL DEFAULT '量產',
            visitor_name TEXT NOT NULL DEFAULT '',
            summary TEXT NOT NULL DEFAULT '',
            work_order_no TEXT NOT NULL DEFAULT '',
            production_qty INTEGER NOT NULL DEFAULT 0,
            tech_transfer INTEGER NOT NULL DEFAULT 0,
            tech_transfer_doc INTEGER NOT NULL DEFAULT 0,
            carrier_requirement INTEGER NOT NULL DEFAULT 0,
            dispensing_process INTEGER NOT NULL DEFAULT 0,
            functional_test INTEGER NOT NULL DEFAULT 0,
            packaging_requirement INTEGER NOT NULL DEFAULT 0,
            tech_transfer_doc_state TEXT NOT NULL DEFAULT 'no',
            carrier_requirement_state TEXT NOT NULL DEFAULT 'no',
            dispensing_process_state TEXT NOT NULL DEFAULT 'no',
            functional_test_state TEXT NOT NULL DEFAULT 'no',
            packaging_requirement_state TEXT NOT NULL DEFAULT 'no',
            status TEXT NOT NULL DEFAULT '已完成' CHECK (status='已完成'),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO visits__new(
            id, visit_date, supplier_id, product_id, product_name, product_stage,
            visitor_name, summary, work_order_no, production_qty, tech_transfer,
            tech_transfer_doc, carrier_requirement, dispensing_process,
            functional_test, packaging_requirement, tech_transfer_doc_state,
            carrier_requirement_state, dispensing_process_state,
            functional_test_state, packaging_requirement_state, status,
            created_at, updated_at
        )
        SELECT
            id, visit_date, supplier_id, product_id, product_name, product_stage,
            visitor_name, summary, work_order_no, production_qty, tech_transfer,
            tech_transfer_doc, carrier_requirement, dispensing_process,
            functional_test, packaging_requirement, tech_transfer_doc_state,
            carrier_requirement_state, dispensing_process_state,
            functional_test_state, packaging_requirement_state,
            '已完成' AS status,
            created_at, updated_at
        FROM visits
        """
    )
    conn.execute("DROP TABLE visits")
    conn.execute("ALTER TABLE visits__new RENAME TO visits")
    # Recreate the full index set so the rebuilt table is complete in this same
    # run (the DROP discarded every index, including idx_visits_product created
    # earlier in create_schema).
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_visits_date ON visits(visit_date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_visits_supplier ON visits(supplier_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_visits_product ON visits(product_id)"
    )


def _remove_products_spec_desc_column_if_present(conn: sqlite3.Connection) -> None:
    """Remove the legacy ``spec_desc`` column from products if present.

    One-time migration guarded by the ``products_spec_desc_removed_v1`` meta
    key. The rebuild runs inside a single ``BEGIN IMMEDIATE`` transaction with
    FK enforcement temporarily disabled (products is referenced by anomalies /
    visits / sections), rolled back on error, with the prior FK state restored.
    """
    if get_migration_meta(conn, "products_spec_desc_removed_v1") == "1":
        return
    if not _has_column(conn, "products", "spec_desc"):
        upsert_migration_meta(conn, "products_spec_desc_removed_v1", "1")
        return

    conn.commit()
    fk_row = conn.execute("PRAGMA foreign_keys").fetchone()
    fk_enabled = bool(_as_int((fk_row[0] if fk_row is not None else 1), 1))
    if fk_enabled:
        conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("BEGIN IMMEDIATE")
        _rebuild_products_without_spec_desc(conn)
        conn.execute("COMMIT")
        upsert_migration_meta(conn, "products_spec_desc_removed_v1", "1")
    except Exception:
        logger.exception("_remove_products_spec_desc_column_if_present failed")
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        if fk_enabled:
            conn.execute("PRAGMA foreign_keys=ON")


def _rebuild_products_without_spec_desc(conn: sqlite3.Connection) -> None:
    """Rebuild products without the legacy ``spec_desc`` column.

    Single-pass reconstruction matching the canonical products schema
    (``product_stage`` DEFAULT '量產', plain supplier FKs, uniqueness enforced
    by the partial indexes rather than a table-level UNIQUE). Must run inside
    the caller's transaction with FK enforcement disabled; uses individual
    ``conn.execute`` statements — never ``executescript`` — so it does not
    commit mid-rebuild.

    The ``product_records`` view and its INSTEAD OF triggers reference
    ``products`` by name and remain valid across the drop/rename, so they are
    intentionally left untouched — dropping the view would silently drop those
    triggers and break NCR writes that go through the view.
    """
    has_product_stage = _has_column(conn, "products", "product_stage")
    has_secondary_supplier_id = _has_column(conn, "products", "secondary_supplier_id")
    product_stage_select_sql = (
        "CASE"
        " WHEN trim(coalesce(product_stage, '')) IN ('量產', '試產')"
        " THEN trim(product_stage)"
        " ELSE '量產'"
        " END AS product_stage"
        if has_product_stage
        else "'量產' AS product_stage"
    )
    secondary_supplier_select_sql = (
        "secondary_supplier_id"
        if has_secondary_supplier_id
        else "NULL AS secondary_supplier_id"
    )

    conn.execute("DROP TABLE IF EXISTS products__new")
    conn.execute(
        """
        CREATE TABLE products__new (
            id TEXT PRIMARY KEY,
            product_code TEXT NOT NULL,
            product_name TEXT NOT NULL,
            product_stage TEXT NOT NULL DEFAULT '量產',
            supplier_id TEXT,
            secondary_supplier_id TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
            FOREIGN KEY (secondary_supplier_id) REFERENCES suppliers(id)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO products__new(
            id, product_code, product_name, product_stage, supplier_id,
            secondary_supplier_id, is_active, created_at, updated_at
        )
        SELECT
            id,
            product_code,
            product_name,
            """
        + product_stage_select_sql
        + """,
            supplier_id,
            """
        + secondary_supplier_select_sql
        + """,
            is_active,
            created_at,
            updated_at
        FROM products
        """
    )
    # The product_records view and its INSTEAD OF triggers reference `products`
    # by name. Modern SQLite re-validates dependent views during ALTER TABLE
    # RENAME, which would raise ("no such table: main.products") while products
    # is briefly absent. legacy_alter_table=ON skips that re-validation, so the
    # table is swapped WITHOUT dropping the view or its triggers — preserving the
    # NCR product_records write path that goes through those triggers.
    conn.execute("PRAGMA legacy_alter_table=ON")
    try:
        conn.execute("DROP TABLE products")
        conn.execute("ALTER TABLE products__new RENAME TO products")
    finally:
        conn.execute("PRAGMA legacy_alter_table=OFF")
    _ensure_product_indexes(conn)
