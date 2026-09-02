"""Shared product master-data persistence and stage sync."""

from __future__ import annotations

import logging
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from database.product_item_category import (
    ITEM_CATEGORY_OPTIONS,
    ITEM_CATEGORY_SEMI_FINISHED,
    infer_item_category_from_product_code,
    normalize_item_category,
)
from database.product_stage import (
    PRODUCT_STAGE_MASS_PRODUCTION,
    normalize_product_stage_ui,
)
from database.repo_helpers import (
    DEFAULT_STAGE_CHANGED_BY,
    PRODUCT_STAGE_SYNC_META_KEY,
    ProductStageSyncOnceReport,
    ProductStageSyncReport,
    STAGE_SYNC_SCOPE_ALL_HISTORY,
    _as_int,
    _build_product_lookup_by_supplier_and_name,
    _build_product_lookup_by_supplier_and_name,
    _gen_id,
    _normalize_product_stage,
    _normalize_product_stage_for_read,
    _normalized_lookup_text,
    _now_iso,
    get_migration_meta,
    upsert_migration_meta,
)
from database.repository_schema_helpers import has_column as _has_column
from database.supplier_repository import get_supplier, list_suppliers
from services.path_name_helpers import contains_invalid_path_char

logger = logging.getLogger(__name__)

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
    has_item_category = _has_column(conn, "products", "item_category")
    secondary_select_sql = "p.secondary_supplier_id" if has_secondary else "NULL"
    secondary_name_sql = "ss.supplier_name" if has_secondary else "NULL"
    item_category_sql = (
        "p.item_category" if has_item_category else f"'{ITEM_CATEGORY_SEMI_FINISHED}'"
    )
    join_sql = (
        " LEFT JOIN suppliers ss ON ss.id = p.secondary_supplier_id"
        if has_secondary
        else ""
    )
    return {
        "stage_sql": stage_sql,
        "has_secondary": has_secondary,
        "has_item_category": has_item_category,
        "secondary_select_sql": secondary_select_sql,
        "secondary_name_sql": secondary_name_sql,
        "item_category_sql": item_category_sql,
        "join_sql": join_sql,
    }

def list_products(
    conn: sqlite3.Connection,
    *,
    include_inactive: bool = True,
    item_categories: tuple[str, ...] | None = None,
) -> list[dict]:
    frag = _product_select_fragments(conn)
    sql = """
        SELECT
            p.id AS id,
            p.product_code AS product_code,
            p.product_name AS product_name,
            """
    sql += f"{frag['stage_sql']} AS product_stage,"
    sql += f"{frag['item_category_sql']} AS item_category,"
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
    conditions: list[str] = []
    params: list[Any] = []
    if not include_inactive:
        conditions.append("p.is_active = 1")
    if item_categories:
        normalized_categories = [
            normalize_item_category(value) for value in item_categories
        ]
        placeholders = ", ".join("?" for _ in normalized_categories)
        conditions.append(f"p.item_category IN ({placeholders})")
        params.extend(normalized_categories)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY p.product_name COLLATE NOCASE, p.product_code COLLATE NOCASE"
    rows = conn.execute(sql, params).fetchall()
    items: list[dict] = []
    for row in rows:
        item = dict(row)
        item["is_active"] = bool(_as_int(item.get("is_active"), 0))
        item["product_stage"] = _normalize_product_stage_for_read(
            item.get("product_stage")
        )
        if "item_category" in item:
            item["item_category"] = normalize_item_category(item.get("item_category"))
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
            {frag['item_category_sql']} AS item_category,
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
    item_category: str = ITEM_CATEGORY_SEMI_FINISHED,
) -> str:
    normalized_code = (product_code or "").strip()
    normalized_name = (product_name or "").strip()
    normalized_product_stage = _normalize_product_stage(product_stage)
    normalized_item_category = normalize_item_category(
        infer_item_category_from_product_code(normalized_code, current=item_category)
    )
    if normalized_item_category not in ITEM_CATEGORY_OPTIONS:
        raise ValueError("Invalid item category")
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
    if _has_column(conn, "products", "item_category"):
        conn.execute(
            "UPDATE products SET item_category = ? WHERE id = ?",
            (normalized_item_category, product_id),
        )
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
    item_category: str | None = None,
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
    if _has_column(conn, "products", "item_category"):
        current_category = (
            str(item_category or "").strip()
            if item_category is not None
            else str(existing.get("item_category") or "").strip()
        )
        normalized_item_category = normalize_item_category(
            infer_item_category_from_product_code(
                normalized_code,
                current=current_category,
            )
        )
        if normalized_item_category not in ITEM_CATEGORY_OPTIONS:
            raise ValueError("Invalid item category")
        conn.execute(
            "UPDATE products SET item_category = ? WHERE id = ?",
            (normalized_item_category, product_key),
        )
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
    conn: sqlite3.Connection,
    supplier_id: str | None,
    *,
    item_categories: tuple[str, ...] | None = None,
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
    sql += f"{frag['item_category_sql']} AS item_category,"
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
        # 嚴格模式：只顯示主供或次供符合的料號。
        # 不包含 supplier_id IS NULL 的老料號（對齊 NCR 嚴格模式，audit finding SP-1）。
        sql += " AND (p.supplier_id = ? OR p.secondary_supplier_id = ?)"
        params.extend([normalized_supplier_id, normalized_supplier_id])
    else:
        # 舊版 schema（無 secondary_supplier_id 欄位）：只顯示主供符合的料號。
        # 不包含 supplier_id IS NULL 的老料號（嚴格模式）。
        sql += " AND p.supplier_id = ?"
        params.append(normalized_supplier_id)
    if item_categories and frag.get("has_item_category"):
        normalized_categories = [
            normalize_item_category(value) for value in item_categories
        ]
        placeholders = ", ".join("?" for _ in normalized_categories)
        sql += f" AND p.item_category IN ({placeholders})"
        params.extend(normalized_categories)
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
