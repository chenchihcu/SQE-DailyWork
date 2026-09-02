"""SQLite schema bootstrap, migrations, and DDL helpers for SQE DailyWork v2."""

from __future__ import annotations

import logging
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from database import anomaly_hypothesis_repository as _anomaly_hypothesis_repository
from database import anomaly_repeat_repository as _anomaly_repeat_repository
from database.case_action_repository import (
    case_actions_schema_ready,
    migrate_case_actions_v1,
)
from database.connection import disposable_runtime_enabled
from database.product_item_category import (
    ITEM_CATEGORY_SEMI_FINISHED,
    ITEM_CATEGORY_OPTIONS,
    PRODUCT_ITEM_CATEGORY_META_KEY,
    PRODUCT_ITEM_CATEGORY_V2_META_KEY,
    infer_item_category_from_product_code,
    normalize_item_category,
)
from database.repo_helpers import (
    ANOMALY_ACTIONS_BACKFILL_META_KEY,
    ANOMALY_ACTIONS_MIGRATION_META_KEY,
    ANOMALY_ANALYSIS_NOTES_MIGRATION_META_KEY,
    ANOMALY_ATTACHMENTS_CONTRACT_META_KEY,
    ANOMALY_ATTACHMENTS_CONTRACT_SCHEMA_VERSION,
    ANOMALY_ATTACHMENTS_MIGRATION_META_KEY,
    ANOMALY_AUDIT_LOGS_MIGRATION_META_KEY,
    ANOMALY_EIGHT_D_REVIEWS_MIGRATION_META_KEY,
    ANOMALY_ROOT_CAUSES_MIGRATION_META_KEY,
    CORRECTIVE_ACTIONS_MIGRATION_META_KEY,
    EFFECTIVENESS_VERIFICATIONS_MIGRATION_META_KEY,
    PRODUCT_RECORDS_VIEW_IS_ACTIVE_META_KEY,
    PRODUCT_RECORDS_VIEW_IS_ACTIVE_SCHEMA_VERSION,
            _as_int,
            _gen_id,
            _table_columns,
            _table_exists,
            get_migration_meta,
            upsert_migration_meta,
        )
from database.repository_schema_helpers import (
    ensure_column as _ensure_column,
    ensure_index as _ensure_index,
    ensure_product_indexes as _ensure_product_indexes,
    has_column as _has_column,
    table_sql as _table_sql,
)
from database.supplier_category import (
    LEGACY_SUPPLIER_CATEGORY_FORMAL,
    LEGACY_SUPPLIER_CATEGORY_OUTSOURCE,
    LEGACY_SUPPLIER_CATEGORY_OUTSOURCE_FACTORY_V1,
    LEGACY_SUPPLIER_CATEGORY_RAW_MATERIAL_V1,
    SUPPLIER_CATEGORY_OUTSOURCE_FACTORY,
    SUPPLIER_CATEGORY_RAW_MATERIAL,
    SUPPLIER_CATEGORY_RENAME_META_KEY,
    SUPPLIER_CATEGORY_RENAME_V2_META_KEY,
    normalize_supplier_category,
)

_ensure_anomaly_hypotheses_v1 = _anomaly_hypothesis_repository._ensure_anomaly_hypotheses_v1
_ensure_anomaly_repeat_links_v1 = _anomaly_repeat_repository._ensure_anomaly_repeat_links_v1

logger = logging.getLogger(__name__)

_ATTACHMENT_CONTRACT_REQUIRED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("file_type", "TEXT NOT NULL DEFAULT ''"),
    ("uploaded_by", "TEXT NOT NULL DEFAULT ''"),
    ("related_note_id", "TEXT REFERENCES anomaly_analysis_notes(id)"),
    ("related_action_id", "TEXT REFERENCES case_actions(id)"),
)

ANOMALY_TRACE_FIELDS_MIGRATION_META_KEY = "anomaly_trace_fields_v1"

ANOMALY_TRACE_UNIQUE_INDEX_REMOVAL_META_KEY = "anomaly_trace_unique_index_removal_v1"

_TRACE_FIELD_COLUMNS: tuple[tuple[str, str], ...] = (
    ("material_receipt_no", "原物料進貨單號"),
    ("internal_work_order_no", "廠內製令單號"),
    ("outsource_work_order", "委外製令單號"),
    ("outsource_receipt_no", "委外進貨單號"),
)

_PRODUCT_RECORDS_VIEW_DDL = """
DROP VIEW IF EXISTS product_records;
CREATE VIEW product_records AS
SELECT
    id,
    product_code AS item_no,
    product_name,
    created_at
FROM products
WHERE is_active = 1;

CREATE TRIGGER IF NOT EXISTS trg_product_records_insert
INSTEAD OF INSERT ON product_records
BEGIN
    INSERT INTO products (id, product_code, product_name, item_category, created_at, updated_at, is_active)
    VALUES (
        COALESCE(NEW.id, hex(randomblob(16))),
        NEW.item_no,
        NEW.product_name,
        '半成品',
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
"""

def _ensure_supplier_category_rename_v1(conn: sqlite3.Connection) -> None:
    if get_migration_meta(conn, SUPPLIER_CATEGORY_RENAME_META_KEY) == "1":
        return
    conn.execute(
        "UPDATE suppliers SET category = ? WHERE category = ?",
        (SUPPLIER_CATEGORY_RAW_MATERIAL, LEGACY_SUPPLIER_CATEGORY_FORMAL),
    )
    conn.execute(
        "UPDATE suppliers SET category = ? WHERE category = ?",
        (
            normalize_supplier_category(LEGACY_SUPPLIER_CATEGORY_OUTSOURCE),
            LEGACY_SUPPLIER_CATEGORY_OUTSOURCE,
        ),
    )
    upsert_migration_meta(conn, SUPPLIER_CATEGORY_RENAME_META_KEY, "1")

def _ensure_supplier_category_rename_v2(conn: sqlite3.Connection) -> None:
    if get_migration_meta(conn, SUPPLIER_CATEGORY_RENAME_V2_META_KEY) == "1":
        return
    conn.execute(
        "UPDATE suppliers SET category = ? WHERE category = ?",
        (SUPPLIER_CATEGORY_RAW_MATERIAL, LEGACY_SUPPLIER_CATEGORY_RAW_MATERIAL_V1),
    )
    conn.execute(
        "UPDATE suppliers SET category = ? WHERE category = ?",
        (
            SUPPLIER_CATEGORY_OUTSOURCE_FACTORY,
            LEGACY_SUPPLIER_CATEGORY_OUTSOURCE_FACTORY_V1,
        ),
    )
    upsert_migration_meta(conn, SUPPLIER_CATEGORY_RENAME_V2_META_KEY, "1")

def _ensure_product_item_category_v1(conn: sqlite3.Connection) -> None:
    if get_migration_meta(conn, PRODUCT_ITEM_CATEGORY_META_KEY) == "1":
        return
    _ensure_column(
        conn,
        "products",
        "item_category",
        f"TEXT NOT NULL DEFAULT '{ITEM_CATEGORY_SEMI_FINISHED}'",
    )
    if _table_exists(conn, "defect_records"):
        rows = conn.execute(
            """
            SELECT item_no, category, COUNT(*) AS cnt
            FROM defect_records
            WHERE TRIM(category) IN ('原物料', '半成品', '成品')
              AND TRIM(item_no) <> ''
            GROUP BY item_no, category
            ORDER BY item_no, cnt DESC
            """
        ).fetchall()
        best: dict[str, str] = {}
        for row in rows:
            item_no = str(row["item_no"] or "").strip()
            category = str(row["category"] or "").strip()
            if not item_no or item_no in best:
                continue
            best[item_no] = normalize_item_category(category)
        for item_no, category in best.items():
            conn.execute(
                "UPDATE products SET item_category = ? WHERE product_code = ?",
                (category, item_no),
            )
    upsert_migration_meta(conn, PRODUCT_ITEM_CATEGORY_META_KEY, "1")

def _ensure_product_item_category_v2(conn: sqlite3.Connection) -> None:
    if get_migration_meta(conn, PRODUCT_ITEM_CATEGORY_V2_META_KEY) == "1":
        return
    if not _has_column(conn, "products", "item_category"):
        upsert_migration_meta(conn, PRODUCT_ITEM_CATEGORY_V2_META_KEY, "1")
        return
    rows = conn.execute(
        "SELECT id, product_code, item_category FROM products"
    ).fetchall()
    for row in rows:
        product_id = str(row["id"] or "").strip()
        product_code = str(row["product_code"] or "").strip()
        if not product_id or not product_code:
            continue
        current = str(row["item_category"] or "").strip()
        category = infer_item_category_from_product_code(product_code, current=current)
        conn.execute(
            "UPDATE products SET item_category = ? WHERE id = ?",
            (category, product_id),
        )
    upsert_migration_meta(conn, PRODUCT_ITEM_CATEGORY_V2_META_KEY, "1")

def create_schema(conn: sqlite3.Connection) -> None:
    fresh_install = not _table_exists(conn, "anomalies")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS suppliers (
            id TEXT PRIMARY KEY,
            supplier_name TEXT NOT NULL UNIQUE,
            contact_name TEXT NOT NULL DEFAULT '',
            department TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            contact_email TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '原物料供應商',
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
            anomaly_source TEXT NOT NULL DEFAULT '',
            material_receipt_no TEXT NOT NULL DEFAULT '',
            internal_work_order_no TEXT NOT NULL DEFAULT '',
            outsource_work_order TEXT NOT NULL DEFAULT '',
            outsource_receipt_no TEXT NOT NULL DEFAULT '',
            batch_qty INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT '待處理' CHECK (status IN ('待處理','已結案')),
            improvement_desc TEXT NOT NULL DEFAULT '',
            closed_by TEXT NOT NULL DEFAULT '',
            closed_at TEXT,
            pending_items TEXT NOT NULL DEFAULT '',
            responsible_person TEXT NOT NULL DEFAULT '',
            due_date TEXT NOT NULL DEFAULT '',
            quality_report_required INTEGER CHECK (quality_report_required IN (0, 1)),
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

        -- Anomaly next-action sub-table (Phase 1).
        -- Each anomaly may have one or more actions; lifecycle is tracked here
        -- rather than implicitly on anomalies.pending_items + due_date so that
        -- "in progress / completed / cancelled" history is preserved.
        CREATE TABLE IF NOT EXISTS anomaly_actions (
            id TEXT PRIMARY KEY,
            anomaly_id TEXT NOT NULL,
            description TEXT NOT NULL,
            owner TEXT NOT NULL DEFAULT '',
            due_date TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT '進行中'
                CHECK (status IN ('進行中','已完成','已取消')),
            completed_at TEXT,
            completed_note TEXT NOT NULL DEFAULT '',
            cancelled_at TEXT,
            cancelled_note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (anomaly_id) REFERENCES anomalies(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_anomaly_actions_anomaly
            ON anomaly_actions(anomaly_id, status, due_date);
        CREATE INDEX IF NOT EXISTS idx_anomaly_actions_due
            ON anomaly_actions(status, due_date);

        -- Anomaly analysis notes + root cause (Phase 2).
        CREATE TABLE IF NOT EXISTS anomaly_analysis_notes (
            id TEXT PRIMARY KEY,
            anomaly_id TEXT NOT NULL,
            content TEXT NOT NULL,
            evidence_type TEXT NOT NULL DEFAULT 'UNKNOWN'
                CHECK (evidence_type IN ('FACT','INFERENCE','ASSUMPTION','UNKNOWN')),
            author_name TEXT NOT NULL DEFAULT '',
            attachment_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (anomaly_id) REFERENCES anomalies(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_anomaly_notes_anomaly
            ON anomaly_analysis_notes(anomaly_id, created_at);

        CREATE TABLE IF NOT EXISTS anomaly_root_causes (
            id TEXT PRIMARY KEY,
            anomaly_id TEXT NOT NULL UNIQUE,
            statement TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT '尚未開始'
                CHECK (status IN ('尚未開始','調查中','提案','已驗證','無法確認')),
            validation_method TEXT NOT NULL DEFAULT '',
            validation_evidence TEXT NOT NULL DEFAULT '',
            conclusion_note TEXT NOT NULL DEFAULT '',
            not_established_reason TEXT NOT NULL DEFAULT '',
            promoted_from_hypothesis_id TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (anomaly_id) REFERENCES anomalies(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_anomaly_root_causes_anomaly
            ON anomaly_root_causes(anomaly_id);

        CREATE TABLE IF NOT EXISTS anomaly_hypotheses (
            id TEXT PRIMARY KEY,
            anomaly_id TEXT NOT NULL,
            parent_hypothesis_id TEXT REFERENCES anomaly_hypotheses(id),
            level INTEGER NOT NULL DEFAULT 1 CHECK (level BETWEEN 1 AND 5),
            sort_order INTEGER NOT NULL DEFAULT 0,
            statement TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT '提案'
                CHECK (status IN ('提案','調查中','支持','反證','採納','淘汰')),
            evidence_type TEXT NOT NULL DEFAULT 'UNKNOWN'
                CHECK (evidence_type IN ('FACT','INFERENCE','ASSUMPTION','UNKNOWN')),
            linked_note_id TEXT REFERENCES anomaly_analysis_notes(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (anomaly_id) REFERENCES anomalies(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_anomaly_hypotheses_anomaly
            ON anomaly_hypotheses(anomaly_id, level, sort_order);
        CREATE INDEX IF NOT EXISTS idx_anomaly_hypotheses_parent
            ON anomaly_hypotheses(parent_hypothesis_id);

        -- Corrective actions + effectiveness verifications (Phase 3).
        CREATE TABLE IF NOT EXISTS corrective_actions (
            id TEXT PRIMARY KEY,
            anomaly_id TEXT NOT NULL,
            description TEXT NOT NULL,
            responsible_party TEXT NOT NULL DEFAULT '',
            target_date TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT '已規劃'
                CHECK (status IN ('已規劃','執行中','已實施','待有效性驗證','有效','無效','已取消')),
            implementation_evidence TEXT NOT NULL DEFAULT '',
            completion_date TEXT,
            effectiveness_verification_required INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (anomaly_id) REFERENCES anomalies(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_corrective_actions_anomaly
            ON corrective_actions(anomaly_id, status);

        CREATE TABLE IF NOT EXISTS effectiveness_verifications (
            id TEXT PRIMARY KEY,
            corrective_action_id TEXT NOT NULL,
            method TEXT NOT NULL DEFAULT '',
            acceptance_criteria TEXT NOT NULL DEFAULT '',
            period_sample TEXT NOT NULL DEFAULT '',
            result TEXT NOT NULL DEFAULT '待驗證'
                CHECK (result IN ('待驗證','有效','無效','無法判定')),
            evidence TEXT NOT NULL DEFAULT '',
            conclusion TEXT NOT NULL DEFAULT '',
            verified_by TEXT NOT NULL DEFAULT '',
            verified_date TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (corrective_action_id)
                REFERENCES corrective_actions(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_eff_verifications_ca
            ON effectiveness_verifications(corrective_action_id);

        -- Anomaly attachments (Phase 4). Existing physical files are managed by
        -- the attachment store; this table adds classification + relationship.
        CREATE TABLE IF NOT EXISTS anomaly_attachments (
            id TEXT PRIMARY KEY,
            anomaly_id TEXT NOT NULL,
            file_name TEXT NOT NULL DEFAULT '',
            stored_name TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '其他',
            description TEXT NOT NULL DEFAULT '',
            file_size INTEGER NOT NULL DEFAULT 0,
            file_type TEXT NOT NULL DEFAULT '',
            revision TEXT NOT NULL DEFAULT '',
            uploaded_by TEXT NOT NULL DEFAULT '',
            related_ca_id TEXT,
            related_note_id TEXT,
            related_action_id TEXT,
            related_hypothesis_id TEXT,
            uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (anomaly_id) REFERENCES anomalies(id) ON DELETE CASCADE,
            FOREIGN KEY (related_ca_id) REFERENCES corrective_actions(id),
            FOREIGN KEY (related_note_id) REFERENCES anomaly_analysis_notes(id),
            FOREIGN KEY (related_action_id) REFERENCES case_actions(id),
            FOREIGN KEY (related_hypothesis_id) REFERENCES anomaly_hypotheses(id)
        );
        CREATE INDEX IF NOT EXISTS idx_anomaly_attachments_anomaly
            ON anomaly_attachments(anomaly_id);

        -- Supplier 8D revision reviews (append-only, Phase 4).
        CREATE TABLE IF NOT EXISTS anomaly_eight_d_reviews (
            id TEXT PRIMARY KEY,
            anomaly_id TEXT NOT NULL,
            revision TEXT NOT NULL DEFAULT '',
            review_status TEXT NOT NULL DEFAULT '需補充證據'
                CHECK (review_status IN ('接受','退回修正','需補充證據')),
            review_comment TEXT NOT NULL DEFAULT '',
            attachment_id TEXT,
            review_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (anomaly_id) REFERENCES anomalies(id) ON DELETE CASCADE,
            FOREIGN KEY (attachment_id) REFERENCES anomaly_attachments(id)
        );
        CREATE INDEX IF NOT EXISTS idx_anomaly_8d_anomaly
            ON anomaly_eight_d_reviews(anomaly_id, review_date);

        -- Anomaly audit log (append-only, Phase 4).
        CREATE TABLE IF NOT EXISTS anomaly_audit_logs (
            id TEXT PRIMARY KEY,
            anomaly_id TEXT NOT NULL,
            action TEXT NOT NULL,
            before_value TEXT NOT NULL DEFAULT '',
            after_value TEXT NOT NULL DEFAULT '',
            actor_name TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (anomaly_id) REFERENCES anomalies(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_anomaly_audit_anomaly
            ON anomaly_audit_logs(anomaly_id, created_at);

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
            supplier_id TEXT,
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
        conn, "suppliers", "category", "TEXT NOT NULL DEFAULT '原物料供應商'"
    )
    _ensure_column(
        conn,
        "defect_records",
        "processing_line",
        "TEXT NOT NULL DEFAULT '未分流' CHECK(processing_line IN ('原物料', '委外加工', '未分流'))",
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_defect_records_status_processing_line
            ON defect_records(status, processing_line)
        """
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
        FROM products
        WHERE is_active = 1;

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
            INSERT INTO products (id, product_code, product_name, item_category, created_at, updated_at, is_active)
            VALUES (
                COALESCE(NEW.id, hex(randomblob(16))),
                NEW.item_no,
                NEW.product_name,
                '半成品',
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
                COALESCE(NEW.category, '原物料供應商'),
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
    cur = conn.execute("PRAGMA table_info(anomalies)")
    anomaly_cols = [row[1] for row in cur.fetchall()]
    if "root_cause_category" in anomaly_cols:
        conn.execute("ALTER TABLE anomalies DROP COLUMN root_cause_category")
    _ensure_column(conn, "anomalies", "pending_items", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(
        conn, "anomalies", "responsible_person", "TEXT NOT NULL DEFAULT ''"
    )
    _ensure_column(conn, "anomalies", "due_date", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(
        conn,
        "anomalies",
        "quality_report_required",
        "INTEGER CHECK (quality_report_required IN (0, 1))",
    )
    _ensure_column(conn, "visits", "product_id", "TEXT")
    _ensure_column(conn, "visits", "product_name", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "visits", "product_stage", "TEXT NOT NULL DEFAULT '量產'")
    _ensure_column(conn, "visits", "visitor_name", "TEXT NOT NULL DEFAULT ''")
    _ensure_index(conn, "idx_anomalies_visit", "anomalies", "visit_id")
    _ensure_index(conn, "idx_anomalies_product", "anomalies", "product_id")
    _ensure_index(conn, "idx_visits_product", "visits", "product_id")
    _ensure_product_indexes(conn)
    _normalize_event_status_tables(conn)
    _remove_tech_transfer_columns(conn)
    _normalize_defect_records_optional_work_order(conn)
    _remove_products_spec_desc_column_if_present(conn)
    _ensure_index(conn, "idx_anomalies_date", "anomalies", "anomaly_date")
    _ensure_index(conn, "idx_anomalies_supplier", "anomalies", "supplier_id")
    _ensure_index(conn, "idx_anomalies_status", "anomalies", "status")
    _ensure_index(conn, "idx_visits_date", "visits", "visit_date")
    _ensure_index(conn, "idx_visits_supplier", "visits", "supplier_id")
    from database.visit_legacy_repository import _backfill_visit_product_sections

    _backfill_visit_product_sections(conn)
    _ensure_column(conn, "anomalies", "rc_supplier_inventory", "TEXT NOT NULL DEFAULT 'unconfirmed'")
    _ensure_column(conn, "anomalies", "rc_supplier_wip", "TEXT NOT NULL DEFAULT 'unconfirmed'")
    _ensure_column(conn, "anomalies", "rc_in_transit", "TEXT NOT NULL DEFAULT 'unconfirmed'")
    _ensure_column(conn, "anomalies", "rc_internal_inventory", "TEXT NOT NULL DEFAULT 'unconfirmed'")
    _ensure_column(conn, "defect_records", "supplier_id", "TEXT")
    _ensure_column(conn, "anomalies", "source_defect_no", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "anomalies", "process_keywords", "TEXT NOT NULL DEFAULT ''")
    _ensure_anomaly_trace_fields_v1(conn)
    _ensure_index(conn, "idx_defect_records_supplier", "defect_records", "supplier_id")
    if get_migration_meta(conn, "defect_supplier_id_backfill_v1") != "1":
        conn.execute(
            """
            UPDATE defect_records
            SET supplier_id = (
                SELECT s.id
                FROM suppliers s
                WHERE s.supplier_name = CASE
                    WHEN processing_line = '委外加工'
                         AND TRIM(COALESCE(outsource_supplier_name, '')) <> ''
                        THEN outsource_supplier_name
                    ELSE supplier_name
                END
                LIMIT 1
            )
            WHERE TRIM(COALESCE(supplier_id, '')) = ''
            """
        )
        upsert_migration_meta(conn, "defect_supplier_id_backfill_v1", "1")
    _ensure_anomaly_actions_v1(conn)
    _ensure_anomaly_evidence_tables_v1(conn)
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
    _ensure_supplier_category_rename_v1(conn)
    _ensure_supplier_category_rename_v2(conn)
    _ensure_product_item_category_v1(conn)
    _ensure_product_item_category_v2(conn)
    conn.commit()
    # The canonical Action migration is intentionally not an automatic upgrade
    # for an existing production database. Fresh databases receive the current
    # schema from their first row. Existing databases may auto-upgrade only
    # while the verified disposable-runtime guard is explicitly enabled; the
    # formal database still has to pass the separately approved Promotion Gate.
    disposable_upgrade = disposable_runtime_enabled()
    if fresh_install or disposable_upgrade:
        _ensure_anomaly_attachment_contract_v1(conn)
        _ensure_anomaly_hypotheses_v1(conn)
        _ensure_anomaly_repeat_links_v1(conn)
        migrate_case_actions_v1(
            conn,
            apply=True,
            fresh_install=fresh_install,
        )

def _ensure_anomaly_actions_v1(conn: sqlite3.Connection) -> None:
    """Idempotent upgrade helper for the ``anomaly_actions`` sub-table.

    Older databases may have been created before the schema was extended. The
    ``CREATE TABLE IF NOT EXISTS`` clause in :func:`create_schema` only handles
    fresh databases, so this helper creates the table and indexes on existing
    installs as well. It also performs a one-shot back-fill of a single
    "history" action per open anomaly that already carries pending items,
    responsible person, or due date so that the new read model has data to
    surface for historical rows.
    """
    # Once canonical Actions are promoted, legacy tables are immutable rollback
    # snapshots. Even if an old migration marker is manually removed, never
    # repopulate the retired table or bypass its installed write guard.
    if case_actions_schema_ready(conn):
        return
    if not _table_exists(conn, "anomaly_actions"):
        conn.executescript(
            """
            CREATE TABLE anomaly_actions (
                id TEXT PRIMARY KEY,
                anomaly_id TEXT NOT NULL,
                description TEXT NOT NULL,
                owner TEXT NOT NULL DEFAULT '',
                due_date TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT '進行中'
                    CHECK (status IN ('進行中','已完成','已取消')),
                completed_at TEXT,
                completed_note TEXT NOT NULL DEFAULT '',
                cancelled_at TEXT,
                cancelled_note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (anomaly_id) REFERENCES anomalies(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_anomaly_actions_anomaly
                ON anomaly_actions(anomaly_id, status, due_date);
            CREATE INDEX IF NOT EXISTS idx_anomaly_actions_due
                ON anomaly_actions(status, due_date);
            """
        )
    if get_migration_meta(conn, ANOMALY_ACTIONS_MIGRATION_META_KEY) == "1":
        return
    upsert_migration_meta(conn, ANOMALY_ACTIONS_MIGRATION_META_KEY, "1")
    if get_migration_meta(conn, ANOMALY_ACTIONS_BACKFILL_META_KEY) == "1":
        return
    _backfill_legacy_anomaly_actions(conn)
    conn.commit()
    upsert_migration_meta(conn, ANOMALY_ACTIONS_BACKFILL_META_KEY, "1")

def _backfill_legacy_anomaly_actions(conn: sqlite3.Connection) -> None:
    """Create a single legacy action per open anomaly that has actionable data.

    Only writes when the anomaly has :attr:`pending_items`, :attr:`responsible_person`,
    or :attr:`due_date` populated. Closed anomalies are intentionally skipped
    because their ``improvement_desc`` is already part of the closed-state
    snapshot; we do not want to back-fill a "history" action that duplicates
    an already-completed closure record.
    """
    rows = conn.execute(
        """
        SELECT id AS anomaly_id,
               trim(coalesce(pending_items, '')) AS pending_items,
               trim(coalesce(responsible_person, '')) AS responsible_person,
               trim(coalesce(due_date, '')) AS due_date
        FROM anomalies
        WHERE status = '待處理'
        """
    ).fetchall()
    for row in rows:
        if not (
            row["pending_items"]
            or row["responsible_person"]
            or row["due_date"]
        ):
            continue
        conn.execute(
            """
            INSERT INTO anomaly_actions(
                id, anomaly_id, description, owner, due_date, status,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, '進行中', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                _gen_id(),
                row["anomaly_id"],
                row["pending_items"] or "（歷史待追蹤）",
                row["responsible_person"],
                row["due_date"],
            ),
        )

def _ensure_anomaly_evidence_tables_v1(conn: sqlite3.Connection) -> None:
    """Idempotent upgrade helper for the Phase 2–4 sub-tables.

    Fresh installs get these tables via :func:`create_schema`; older databases
    that predate the extension rely on this helper to create the tables and
    indexes. Each table is gated by its own ``migration_meta`` key so a partial
    upgrade never re-runs half-applied schema work.
    """
    _create_if_missing(
        conn,
        ANOMALY_ANALYSIS_NOTES_MIGRATION_META_KEY,
        "anomaly_analysis_notes",
        """
        CREATE TABLE anomaly_analysis_notes (
            id TEXT PRIMARY KEY,
            anomaly_id TEXT NOT NULL,
            content TEXT NOT NULL,
            evidence_type TEXT NOT NULL DEFAULT 'UNKNOWN'
                CHECK (evidence_type IN ('FACT','INFERENCE','ASSUMPTION','UNKNOWN')),
            author_name TEXT NOT NULL DEFAULT '',
            attachment_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (anomaly_id) REFERENCES anomalies(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_anomaly_notes_anomaly
            ON anomaly_analysis_notes(anomaly_id, created_at);
        """,
    )
    _create_if_missing(
        conn,
        ANOMALY_ROOT_CAUSES_MIGRATION_META_KEY,
        "anomaly_root_causes",
        """
        CREATE TABLE anomaly_root_causes (
            id TEXT PRIMARY KEY,
            anomaly_id TEXT NOT NULL UNIQUE,
            statement TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT '尚未開始'
                CHECK (status IN ('尚未開始','調查中','提案','已驗證','無法確認')),
            validation_method TEXT NOT NULL DEFAULT '',
            validation_evidence TEXT NOT NULL DEFAULT '',
            conclusion_note TEXT NOT NULL DEFAULT '',
            not_established_reason TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (anomaly_id) REFERENCES anomalies(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_anomaly_root_causes_anomaly
            ON anomaly_root_causes(anomaly_id);
        """,
    )
    _create_if_missing(
        conn,
        CORRECTIVE_ACTIONS_MIGRATION_META_KEY,
        "corrective_actions",
        """
        CREATE TABLE corrective_actions (
            id TEXT PRIMARY KEY,
            anomaly_id TEXT NOT NULL,
            description TEXT NOT NULL,
            responsible_party TEXT NOT NULL DEFAULT '',
            target_date TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT '已規劃'
                CHECK (status IN ('已規劃','執行中','已實施','待有效性驗證','有效','無效','已取消')),
            implementation_evidence TEXT NOT NULL DEFAULT '',
            completion_date TEXT,
            effectiveness_verification_required INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (anomaly_id) REFERENCES anomalies(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_corrective_actions_anomaly
            ON corrective_actions(anomaly_id, status);
        """,
    )
    _create_if_missing(
        conn,
        EFFECTIVENESS_VERIFICATIONS_MIGRATION_META_KEY,
        "effectiveness_verifications",
        """
        CREATE TABLE effectiveness_verifications (
            id TEXT PRIMARY KEY,
            corrective_action_id TEXT NOT NULL,
            method TEXT NOT NULL DEFAULT '',
            acceptance_criteria TEXT NOT NULL DEFAULT '',
            period_sample TEXT NOT NULL DEFAULT '',
            result TEXT NOT NULL DEFAULT '待驗證'
                CHECK (result IN ('待驗證','有效','無效','無法判定')),
            evidence TEXT NOT NULL DEFAULT '',
            conclusion TEXT NOT NULL DEFAULT '',
            verified_by TEXT NOT NULL DEFAULT '',
            verified_date TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (corrective_action_id)
                REFERENCES corrective_actions(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_eff_verifications_ca
            ON effectiveness_verifications(corrective_action_id);
        """,
    )
    _create_if_missing(
        conn,
        ANOMALY_ATTACHMENTS_MIGRATION_META_KEY,
        "anomaly_attachments",
        """
        CREATE TABLE anomaly_attachments (
            id TEXT PRIMARY KEY,
            anomaly_id TEXT NOT NULL,
            file_name TEXT NOT NULL DEFAULT '',
            stored_name TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '其他',
            description TEXT NOT NULL DEFAULT '',
            file_size INTEGER NOT NULL DEFAULT 0,
            file_type TEXT NOT NULL DEFAULT '',
            revision TEXT NOT NULL DEFAULT '',
            uploaded_by TEXT NOT NULL DEFAULT '',
            related_ca_id TEXT,
            related_note_id TEXT,
            related_action_id TEXT,
            uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (anomaly_id) REFERENCES anomalies(id) ON DELETE CASCADE,
            FOREIGN KEY (related_ca_id) REFERENCES corrective_actions(id),
            FOREIGN KEY (related_note_id) REFERENCES anomaly_analysis_notes(id),
            FOREIGN KEY (related_action_id) REFERENCES case_actions(id)
        );
        CREATE INDEX IF NOT EXISTS idx_anomaly_attachments_anomaly
            ON anomaly_attachments(anomaly_id);
        """,
    )
    _create_if_missing(
        conn,
        ANOMALY_EIGHT_D_REVIEWS_MIGRATION_META_KEY,
        "anomaly_eight_d_reviews",
        """
        CREATE TABLE anomaly_eight_d_reviews (
            id TEXT PRIMARY KEY,
            anomaly_id TEXT NOT NULL,
            revision TEXT NOT NULL DEFAULT '',
            review_status TEXT NOT NULL DEFAULT '需補充證據'
                CHECK (review_status IN ('接受','退回修正','需補充證據')),
            review_comment TEXT NOT NULL DEFAULT '',
            attachment_id TEXT,
            review_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (anomaly_id) REFERENCES anomalies(id) ON DELETE CASCADE,
            FOREIGN KEY (attachment_id) REFERENCES anomaly_attachments(id)
        );
        CREATE INDEX IF NOT EXISTS idx_anomaly_8d_anomaly
            ON anomaly_eight_d_reviews(anomaly_id, review_date);
        """,
    )
    _create_if_missing(
        conn,
        ANOMALY_AUDIT_LOGS_MIGRATION_META_KEY,
        "anomaly_audit_logs",
        """
        CREATE TABLE anomaly_audit_logs (
            id TEXT PRIMARY KEY,
            anomaly_id TEXT NOT NULL,
            action TEXT NOT NULL,
            before_value TEXT NOT NULL DEFAULT '',
            after_value TEXT NOT NULL DEFAULT '',
            actor_name TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (anomaly_id) REFERENCES anomalies(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_anomaly_audit_anomaly
            ON anomaly_audit_logs(anomaly_id, created_at);
        """,
    )
    conn.commit()

def _create_if_missing(
    conn: sqlite3.Connection,
    meta_key: str,
    table_name: str,
    ddl: str,
) -> None:
    """Create a table/index set once, guarded by a migration meta key."""
    if get_migration_meta(conn, meta_key) == "1":
        return
    # A fresh install already created this table via create_schema's
    # executescript (IF NOT EXISTS). If it is present, just record the meta
    # marker so we do not try to re-create it with the plain CREATE TABLE DDL.
    if _table_exists(conn, table_name):
        upsert_migration_meta(conn, meta_key, "1")
        return
    conn.executescript(ddl)
    conn.commit()
    upsert_migration_meta(conn, meta_key, "1")

def preview_anomaly_attachments_contract_v1(
    conn: sqlite3.Connection,
) -> dict[str, Any]:
    """Return a read-only summary for the Phase 2 attachment contract.

    The preview deliberately reports missing columns instead of silently
    altering an existing database. The formal Promotion Gate can consume
    this result before deciding whether an apply is authorized.
    """
    columns = _table_columns(conn, "anomaly_attachments")
    missing = [
        name
        for name, _ddl in _ATTACHMENT_CONTRACT_REQUIRED_COLUMNS
        if name not in columns
    ]
    ready = (
        _table_exists(conn, "anomaly_attachments")
        and not missing
        and get_migration_meta(
            conn, ANOMALY_ATTACHMENTS_CONTRACT_META_KEY
        ) == ANOMALY_ATTACHMENTS_CONTRACT_SCHEMA_VERSION
    )
    row_count = 0
    if _table_exists(conn, "anomaly_attachments"):
        row_count = int(
            conn.execute("SELECT COUNT(*) FROM anomaly_attachments").fetchone()[0]
        )
    return {
        "migration_key": ANOMALY_ATTACHMENTS_CONTRACT_META_KEY,
        "schema_version": ANOMALY_ATTACHMENTS_CONTRACT_SCHEMA_VERSION,
        "ready": ready,
        "table_exists": _table_exists(conn, "anomaly_attachments"),
        "columns": sorted(columns),
        "missing_columns": missing,
        "attachment_rows": row_count,
    }

def anomaly_attachments_contract_ready(conn: sqlite3.Connection) -> bool:
    """Return whether the attachment metadata contract is fully promoted.

    This is intentionally a read-only predicate so startup can inspect an
    existing formal database before opening it for writable bootstrap.
    """
    return bool(preview_anomaly_attachments_contract_v1(conn)["ready"])

def _ensure_anomaly_attachment_contract_v1(
    conn: sqlite3.Connection,
    *,
    commit_meta: bool = True,
) -> dict[str, Any]:
    """Install the Phase 2 columns on a fresh/disposable database only."""
    if not _table_exists(conn, "anomaly_attachments"):
        return preview_anomaly_attachments_contract_v1(conn)
    for column_name, column_ddl in _ATTACHMENT_CONTRACT_REQUIRED_COLUMNS:
        _ensure_column(conn, "anomaly_attachments", column_name, column_ddl)
    _ensure_index(
        conn,
        "idx_anomaly_attachments_note",
        "anomaly_attachments",
        "related_note_id",
    )
    _ensure_index(
        conn,
        "idx_anomaly_attachments_action",
        "anomaly_attachments",
        "related_action_id",
    )
    if commit_meta:
        upsert_migration_meta(
            conn,
            ANOMALY_ATTACHMENTS_CONTRACT_META_KEY,
            ANOMALY_ATTACHMENTS_CONTRACT_SCHEMA_VERSION,
        )
    else:
        conn.execute(
            """
            INSERT INTO migration_meta(key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (
                ANOMALY_ATTACHMENTS_CONTRACT_META_KEY,
                ANOMALY_ATTACHMENTS_CONTRACT_SCHEMA_VERSION,
            ),
        )
    return preview_anomaly_attachments_contract_v1(conn)

def migrate_anomaly_attachments_contract_v1(
    conn: sqlite3.Connection,
    *,
    apply: bool = False,
) -> dict[str, Any]:
    """Preview or atomically apply the attachment metadata contract.

    Callers must provide the same approved disposable/formal-gate boundary as
    the Phase 1 migration. This function itself never selects a database path
    and never treats a preview as an apply.
    """
    preview = preview_anomaly_attachments_contract_v1(conn)
    if not apply:
        return {**preview, "applied": False, "skipped": preview["ready"]}
    if preview["ready"]:
        return {**preview, "applied": False, "skipped": True}
    conn.execute("SAVEPOINT anomaly_attachments_contract_v1")
    try:
        report = _ensure_anomaly_attachment_contract_v1(conn, commit_meta=False)
        if report["missing_columns"]:
            raise RuntimeError(
                "Attachment contract migration did not install all columns: "
                + ", ".join(report["missing_columns"])
            )
        conn.execute("RELEASE SAVEPOINT anomaly_attachments_contract_v1")
        return {**report, "applied": True, "skipped": False}
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT anomaly_attachments_contract_v1")
        conn.execute("RELEASE SAVEPOINT anomaly_attachments_contract_v1")
        raise

def _ensure_anomaly_trace_fields_v1(conn: sqlite3.Connection) -> None:
    if get_migration_meta(conn, ANOMALY_TRACE_FIELDS_MIGRATION_META_KEY) != "1":
        _ensure_column(conn, "anomalies", "anomaly_source", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "anomalies", "material_receipt_no", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "anomalies", "internal_work_order_no", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "anomalies", "outsource_receipt_no", "TEXT NOT NULL DEFAULT ''")
        upsert_migration_meta(conn, ANOMALY_TRACE_FIELDS_MIGRATION_META_KEY, "1")
    _remove_anomaly_trace_supplier_unique_indexes(conn)

def _remove_anomaly_trace_supplier_unique_indexes(conn: sqlite3.Connection) -> None:
    """Drop retired supplier-scoped trace unique indexes from earlier builds."""
    if get_migration_meta(conn, ANOMALY_TRACE_UNIQUE_INDEX_REMOVAL_META_KEY) == "1":
        return
    for column, _label in _TRACE_FIELD_COLUMNS:
        conn.execute(f"DROP INDEX IF EXISTS uniq_anomalies_{column}_supplier")
    upsert_migration_meta(conn, ANOMALY_TRACE_UNIQUE_INDEX_REMOVAL_META_KEY, "1")

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
    processing_line_expr = (
        "COALESCE(NULLIF(TRIM(processing_line), ''), '未分流')"
        if _has_column(conn, "defect_records", "processing_line")
        else "'未分流'"
    )

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
            )
            """
        )
        conn.execute(
            f"""
            INSERT INTO defect_records__new(
                id, defect_no, event_date, processing_line, return_slip_type, work_order_no,
                internal_work_order_no, transfer_slip_no, item_no, product_name, qty,
                category, supplier_name, outsource_supplier_name, defect_desc, status,
                disposition, responsibility, created_at
            )
            SELECT
                id, defect_no, event_date,
                {processing_line_expr} AS processing_line,
                return_slip_type, work_order_no,
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
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_defect_records_status_processing_line
                ON defect_records(status, processing_line)
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

def _remove_tech_transfer_columns(conn: sqlite3.Connection) -> None:
    """Remove the retired technical-transfer fields from legacy databases."""
    if get_migration_meta(conn, "tech_transfer_removal_v1") == "1":
        return

    visit_columns = (
        "tech_transfer",
        "tech_transfer_doc",
        "carrier_requirement",
        "dispensing_process",
        "functional_test",
        "packaging_requirement",
        "tech_transfer_doc_state",
        "carrier_requirement_state",
        "dispensing_process_state",
        "functional_test_state",
        "packaging_requirement_state",
    )
    existing_visit_columns = set(_table_columns(conn, "visits"))
    for column in visit_columns:
        if column in existing_visit_columns:
            conn.execute(f'ALTER TABLE visits DROP COLUMN "{column}"')

    if "is_tech_transfer" in set(_table_columns(conn, "anomalies")):
        conn.execute('ALTER TABLE anomalies DROP COLUMN "is_tech_transfer"')

    upsert_migration_meta(conn, "tech_transfer_removal_v1", "1")

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
            closed_at TEXT,
            pending_items TEXT NOT NULL DEFAULT '',
            responsible_person TEXT NOT NULL DEFAULT '',
            due_date TEXT NOT NULL DEFAULT '',
            quality_report_required INTEGER CHECK (quality_report_required IN (0, 1)),
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
            closed_at, pending_items, responsible_person,
            due_date, quality_report_required, created_at, updated_at
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
            improvement_desc, closed_by,
            CASE
                WHEN status IN ('CLOSED', '已結案') THEN closed_at
                ELSE NULL
            END AS closed_at,
            pending_items, responsible_person, due_date, quality_report_required,
            created_at, updated_at
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
            visitor_name, summary, work_order_no, production_qty, status,
            created_at, updated_at
        )
        SELECT
            id, visit_date, supplier_id, product_id, product_name, product_stage,
            visitor_name, summary, work_order_no, production_qty,
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

def _product_records_view_sql(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'view' AND name = 'product_records'"
    ).fetchone()
    if row is None or row[0] is None:
        return ""
    return str(row[0])

def _product_records_view_has_is_active_filter(view_sql: str) -> bool:
    normalized = "".join(view_sql.lower().split())
    return "whereis_active=1" in normalized or "whereis_active=1;" in normalized

def preview_product_records_view_is_active_v1(conn: sqlite3.Connection) -> dict[str, Any]:
    view_sql = _product_records_view_sql(conn)
    has_filter = _product_records_view_has_is_active_filter(view_sql)
    inactive_products = int(
        conn.execute("SELECT COUNT(*) FROM products WHERE is_active = 0").fetchone()[0]
    )
    active_products = int(
        conn.execute("SELECT COUNT(*) FROM products WHERE is_active = 1").fetchone()[0]
    )
    product_records_rows = 0
    if view_sql.strip():
        product_records_rows = int(
            conn.execute("SELECT COUNT(*) FROM product_records").fetchone()[0]
        )
    meta_applied = (
        get_migration_meta(conn, PRODUCT_RECORDS_VIEW_IS_ACTIVE_META_KEY)
        == PRODUCT_RECORDS_VIEW_IS_ACTIVE_SCHEMA_VERSION
    )
    return {
        "ready": has_filter,
        "view_has_is_active_filter": has_filter,
        "meta_applied": meta_applied,
        "inactive_products": inactive_products,
        "active_products": active_products,
        "product_records_rows": product_records_rows,
        "counts_aligned": product_records_rows == active_products,
    }

def product_records_view_is_active_schema_ready(conn: sqlite3.Connection) -> bool:
    return bool(preview_product_records_view_is_active_v1(conn)["ready"])

def migrate_product_records_view_is_active_v1(
    conn: sqlite3.Connection,
    *,
    apply: bool = False,
) -> dict[str, Any]:
    preview = preview_product_records_view_is_active_v1(conn)
    if not apply:
        return {**preview, "applied": False, "skipped": preview["ready"]}
    if preview["ready"] and preview["meta_applied"]:
        return {**preview, "applied": False, "skipped": True}
    conn.executescript(_PRODUCT_RECORDS_VIEW_DDL)
    upsert_migration_meta(
        conn,
        PRODUCT_RECORDS_VIEW_IS_ACTIVE_META_KEY,
        PRODUCT_RECORDS_VIEW_IS_ACTIVE_SCHEMA_VERSION,
    )
    conn.commit()
    report = preview_product_records_view_is_active_v1(conn)
    if not report["ready"]:
        raise RuntimeError(
            "product_records_view_is_active_v1 migration did not install the filtered view."
        )
    return {**report, "applied": True, "skipped": False}
