"""Supplier-event anomaly CRUD, trace fields, and recode helpers."""

from __future__ import annotations

import logging
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from database.product_stage import PRODUCT_STAGE_MASS_PRODUCTION
from database.product_repository import get_product
from database.supplier_repository import get_supplier
from database.repo_helpers import (
    _as_int,
    _ensure_date_not_in_future,
    _gen_id,
    _month_from_date_value,
    _normalize_date,
    _normalize_loose_iso_date,
    _normalize_non_negative_int,
    _normalize_product_stage,
    _normalize_product_stage_for_read,
    _normalize_strict_iso_date,
    _now_iso,
    _quote_identifier,
    _table_columns,
    _table_exists,
    _today_iso,
    get_migration_meta,
    upsert_migration_meta,
)
from database.repository_schema_helpers import (
    ensure_column as _ensure_column,
    has_column as _has_column,
)
from services.path_name_helpers import contains_invalid_path_char

from database.schema_bootstrap import _TRACE_FIELD_COLUMNS


def _refresh_monthly_cache(
    conn: sqlite3.Connection, yyyymm: str, *, _commit: bool = True
) -> None:
    from database.repository import refresh_monthly_cache

    refresh_monthly_cache(conn, yyyymm, _commit=_commit)


def _resolve_next_anomaly_no(conn: sqlite3.Connection, anomaly_date: str) -> str:
    from database import repository

    return repository._next_anomaly_no(conn, anomaly_date)

logger = logging.getLogger(__name__)

ANOMALY_NO_RECODE_META_KEY = "anomaly_no_scheme_yyyymmddnnn_v1"

IMPROVEMENT_DESC_MAX_LEN = 1000

_STRICT_ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_ANOMALY_NO_PATTERN = re.compile(r"^\d{11}$")

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
    anomaly_source: str = "",
    material_receipt_no: str = "",
    internal_work_order_no: str = "",
    outsource_work_order: str = "",
    outsource_receipt_no: str = "",
    batch_qty: int = 0,
    visit_id: str | None = None,
    pending_items: str = "",
    responsible_person: str = "",
    due_date: str = "",
    rc_supplier_inventory: str = "unconfirmed",
    rc_supplier_wip: str = "unconfirmed",
    rc_in_transit: str = "unconfirmed",
    rc_internal_inventory: str = "unconfirmed",
    quality_report_required: bool | None = None,
    process_keywords: str = "",
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
    _validate_visit_supplier(
        conn,
        visit_id=visit_id,
        supplier_id=inputs.normalized_supplier_id,
    )
    anomaly_no = _insert_anomaly_row(
        conn,
        anomaly_date=inputs.normalized_date,
        supplier_id=inputs.normalized_supplier_id,
        problem_desc=problem_desc,
        category=category,
        process_keywords=process_keywords,
        product_lot_no=product_lot_no,
        product_id=inputs.resolved_product_id,
        product_name=inputs.resolved_product_name,
        product_stage=inputs.normalized_product_stage,
        anomaly_source=anomaly_source,
        material_receipt_no=material_receipt_no,
        internal_work_order_no=internal_work_order_no,
        outsource_work_order=outsource_work_order,
        outsource_receipt_no=outsource_receipt_no,
        batch_qty=inputs.normalized_batch_qty,
        visit_id=visit_id,
        pending_items=pending_items,
        responsible_person=responsible_person,
        due_date=due_date,
        rc_supplier_inventory=rc_supplier_inventory,
        rc_supplier_wip=rc_supplier_wip,
        rc_in_transit=rc_in_transit,
        rc_internal_inventory=rc_internal_inventory,
        quality_report_required=quality_report_required,
    )
    try:
        _refresh_monthly_cache(
            conn,
            inputs.normalized_date[:7].replace("-", ""),
            _commit=False,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return anomaly_no

def require_anomaly(conn: sqlite3.Connection, anomaly_id: str) -> dict:
    """Return an anomaly detail or raise ``ValueError`` with a stable message."""
    detail = get_anomaly_detail(conn, anomaly_id)
    if detail is None:
        raise ValueError("Anomaly not found")
    return detail

def get_anomaly_detail(conn: sqlite3.Connection, anomaly_id: str) -> dict | None:
    anomaly_key = (anomaly_id or "").strip()
    if not anomaly_key:
        return None
    source_defect_expr = (
        "a.source_defect_no AS source_defect_no"
        if _has_column(conn, "anomalies", "source_defect_no")
        else "'' AS source_defect_no"
    )
    process_keywords_expr = (
        "a.process_keywords AS process_keywords"
        if _has_column(conn, "anomalies", "process_keywords")
        else "'' AS process_keywords"
    )
    anomaly_source_expr = (
        "a.anomaly_source AS anomaly_source"
        if _has_column(conn, "anomalies", "anomaly_source")
        else "'' AS anomaly_source"
    )
    material_receipt_expr = (
        "a.material_receipt_no AS material_receipt_no"
        if _has_column(conn, "anomalies", "material_receipt_no")
        else "'' AS material_receipt_no"
    )
    internal_work_order_expr = (
        "a.internal_work_order_no AS internal_work_order_no"
        if _has_column(conn, "anomalies", "internal_work_order_no")
        else "'' AS internal_work_order_no"
    )
    outsource_receipt_expr = (
        "a.outsource_receipt_no AS outsource_receipt_no"
        if _has_column(conn, "anomalies", "outsource_receipt_no")
        else "'' AS outsource_receipt_no"
    )
    row = conn.execute(
        f"""
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
            {anomaly_source_expr},
            {material_receipt_expr},
            {internal_work_order_expr},
            a.problem_desc AS problem_desc,
            a.category AS category,
            a.category AS category_raw,
            a.product_lot_no AS product_lot_no,
            a.outsource_work_order AS outsource_work_order,
            {outsource_receipt_expr},
            a.batch_qty AS batch_qty,
            a.status AS status,
            a.improvement_desc AS improvement_desc,
            a.closed_by AS closed_by,
            a.closed_at AS closed_at,
            a.pending_items AS pending_items,
            a.responsible_person AS responsible_person,
            a.due_date AS due_date,
            a.rc_supplier_inventory AS rc_supplier_inventory,
            a.rc_supplier_wip AS rc_supplier_wip,
            a.rc_in_transit AS rc_in_transit,
            a.rc_internal_inventory AS rc_internal_inventory,
            a.quality_report_required AS quality_report_required,
            {source_defect_expr},
            {process_keywords_expr},
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
    if result.get("quality_report_required") is not None:
        result["quality_report_required"] = bool(
            _as_int(result.get("quality_report_required"), 0)
        )
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
    anomaly_source: str = "",
    material_receipt_no: str = "",
    internal_work_order_no: str = "",
    outsource_work_order: str = "",
    outsource_receipt_no: str = "",
    batch_qty: int = 0,
    pending_items: str = "",
    responsible_person: str = "",
    due_date: str = "",
    rc_supplier_inventory: str = "unconfirmed",
    rc_supplier_wip: str = "unconfirmed",
    rc_in_transit: str = "unconfirmed",
    rc_internal_inventory: str = "unconfirmed",
    quality_report_required: bool | None = None,
    anomaly_no: str | None = None,
    source_defect_no: str = "",
    process_keywords: str = "",
) -> None:
    anomaly_key = (anomaly_id or "").strip()
    if not anomaly_key:
        raise ValueError("Anomaly id is required")
    _ensure_column(conn, "anomalies", "process_keywords", "TEXT NOT NULL DEFAULT ''")
    existing = get_anomaly_detail(conn, anomaly_key)
    if existing is None:
        raise ValueError("Anomaly not found")

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
    explicit_anomaly_no = (anomaly_no or "").strip()
    existing_anomaly_no = str(existing.get("anomaly_no") or "").strip()
    if explicit_anomaly_no:
        resolved_anomaly_no = explicit_anomaly_no
    elif existing_anomaly_no.startswith(normalized_date.replace("-", "")):
        resolved_anomaly_no = existing_anomaly_no
    else:
        resolved_anomaly_no = _resolve_next_anomaly_no(conn, normalized_date)
    validate_anomaly_number(
        conn,
        resolved_anomaly_no,
        normalized_date,
        exclude_anomaly_id=anomaly_key,
    )
    _validate_visit_supplier(
        conn,
        visit_id=existing.get("visit_id"),
        supplier_id=normalized_supplier_id,
    )
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
                anomaly_source = ?,
                material_receipt_no = ?,
                internal_work_order_no = ?,
                problem_desc = ?,
                category = ?,
                product_lot_no = ?,
                outsource_work_order = ?,
                outsource_receipt_no = ?,
                batch_qty = ?,
                pending_items = ?,
                responsible_person = ?,
                due_date = ?,
                rc_supplier_inventory = ?,
                rc_supplier_wip = ?,
                rc_in_transit = ?,
                rc_internal_inventory = ?,
                quality_report_required = ?,
                process_keywords = ?,
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
                (anomaly_source or "").strip(),
                (material_receipt_no or "").strip(),
                (internal_work_order_no or "").strip(),
                normalized_problem_desc,
                (category or "").strip(),
                (product_lot_no or "").strip(),
                (outsource_work_order or "").strip(),
                (outsource_receipt_no or "").strip(),
                normalized_batch_qty,
                (pending_items or "").strip(),
                (responsible_person or "").strip(),
                normalized_due_date,
                (rc_supplier_inventory or "unconfirmed").strip(),
                (rc_supplier_wip or "unconfirmed").strip(),
                (rc_in_transit or "unconfirmed").strip(),
                (rc_internal_inventory or "unconfirmed").strip(),
                None if quality_report_required is None else int(quality_report_required),
                (process_keywords or "").strip(),
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
    months_to_refresh = {
        month
        for month in (
            _month_from_date_value(existing.get("anomaly_date")),
            _month_from_date_value(existing.get("closed_at")),
            _month_from_date_value(normalized_date),
        )
        if month
    }
    try:
        for month in months_to_refresh:
            _refresh_monthly_cache(conn, month, _commit=False)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

def update_anomaly_link(conn: sqlite3.Connection, anomaly_id: str, visit_id: str | None) -> None:
    """Manually update the visit association for an existing anomaly."""
    anomaly_key = (anomaly_id or "").strip()
    if not anomaly_key:
        raise ValueError("Anomaly id is required")
    anomaly = get_anomaly_detail(conn, anomaly_key)
    if anomaly is None:
        raise ValueError("Anomaly not found")
    normalized_visit_id = (visit_id or "").strip() or None
    if normalized_visit_id:
        from database.visit_legacy_repository import get_visit_detail

        visit = get_visit_detail(conn, normalized_visit_id)
        if visit is None:
            raise ValueError("Visit not found")
        if str(visit.get("supplier_id") or "").strip() != str(
            anomaly.get("supplier_id") or ""
        ).strip():
            raise ValueError("Visit supplier does not match anomaly supplier")
    cur = conn.execute(
        "UPDATE anomalies SET visit_id = ?, updated_at = ? WHERE id = ?",
        (normalized_visit_id, _now_iso(), anomaly_key),
    )
    if cur.rowcount == 0:
        raise ValueError("Anomaly not found")
    conn.commit()

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
        _refresh_monthly_cache(conn, month)

def close_anomaly(
    conn: sqlite3.Connection,
    anomaly_id: str,
    improvement_desc: str,
    *,
    closed_by: str = "",
    closed_at: str | None = None,
    _commit: bool = True,
) -> None:
    text = (improvement_desc or "").strip()
    if not text:
        raise ValueError("Improvement description is required")
    if len(text) > IMPROVEMENT_DESC_MAX_LEN:
        raise ValueError(
            f"Improvement description exceeds {IMPROVEMENT_DESC_MAX_LEN} characters"
        )
    closer = (closed_by or "").strip()
    anomaly_key = (anomaly_id or "").strip()
    existing = get_anomaly_detail(conn, anomaly_key)
    if existing is None or existing.get("status") != "待處理":
        raise ValueError("Open anomaly not found")

    close_date = _normalize_strict_iso_date(
        closed_at,
        field_name="Closed date",
    )
    _ensure_date_not_in_future(close_date, field_name="Closed date")
    anomaly_date = _normalize_strict_iso_date(
        existing.get("anomaly_date"),
        field_name="Anomaly date",
    )
    if close_date < anomaly_date:
        raise ValueError("Closed date cannot be before anomaly date")
    cur = conn.execute(
        """
        UPDATE anomalies
        SET status = '已結案',
            improvement_desc = ?,
            closed_by = ?,
            closed_at = ?,
            updated_at = ?
        WHERE id = ? AND status = '待處理'
        """,
        (text, closer, close_date, _now_iso(), anomaly_key),
    )
    if cur.rowcount == 0:
        raise ValueError("Open anomaly not found")

    try:
        _refresh_monthly_cache(
            conn,
            close_date[:7].replace("-", ""),
            _commit=False,
        )
        if _commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise

def update_anomaly_closed_at(
    conn: sqlite3.Connection,
    anomaly_id: str,
    closed_at: str,
) -> None:
    anomaly_key = (anomaly_id or "").strip()
    if not anomaly_key:
        raise ValueError("Anomaly id is required")
    existing = get_anomaly_detail(conn, anomaly_key)
    if existing is None:
        raise ValueError("Anomaly not found")
    if existing.get("status") != "已結案":
        raise ValueError("Only closed anomalies can update closed date")

    close_date = _normalize_strict_iso_date(
        closed_at,
        field_name="Closed date",
    )
    _ensure_date_not_in_future(close_date, field_name="Closed date")
    anomaly_date = _normalize_strict_iso_date(
        existing.get("anomaly_date"),
        field_name="Anomaly date",
    )
    if close_date < anomaly_date:
        raise ValueError("Closed date cannot be before anomaly date")

    cur = conn.execute(
        """
        UPDATE anomalies
        SET closed_at = ?,
            updated_at = ?
        WHERE id = ? AND status = '已結案'
        """,
        (close_date, _now_iso(), anomaly_key),
    )
    if cur.rowcount == 0:
        raise ValueError("Anomaly not found")
    conn.commit()

    months_to_refresh = {
        month
        for month in (
            _month_from_date_value(existing.get("anomaly_date")),
            _month_from_date_value(existing.get("closed_at")),
            _month_from_date_value(close_date),
        )
        if month
    }
    for month in months_to_refresh:
        _refresh_monthly_cache(conn, month)

def reopen_anomaly(
    conn: sqlite3.Connection,
    anomaly_id: str,
    *,
    _commit: bool = True,
) -> dict:
    """Reopen a closed anomaly. Returns the pre-reopen detail snapshot."""
    anomaly_key = (anomaly_id or "").strip()
    if not anomaly_key:
        raise ValueError("Anomaly id is required")
    existing = get_anomaly_detail(conn, anomaly_key)
    if existing is None:
        raise ValueError("Anomaly not found")
    if existing["status"] != "已結案":
        raise ValueError("Only closed anomalies can be reopened")

    closed_at = existing.get("closed_at")
    snapshot = dict(existing)

    conn.execute(
        """
        UPDATE anomalies
        SET status = '待處理',
            improvement_desc = '',
            closed_by = '',
            closed_at = NULL,
            updated_at = ?
        WHERE id = ?
        """,
        (_now_iso(), anomaly_key),
    )
    months_to_refresh = {
        month
        for month in (
            _month_from_date_value(existing.get("anomaly_date")),
            _month_from_date_value(closed_at),
        )
        if month
    }
    try:
        for month in months_to_refresh:
            _refresh_monthly_cache(conn, month, _commit=False)
        if _commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    return snapshot

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

def find_anomaly_trace_duplicate(
    conn: sqlite3.Connection,
    *,
    supplier_id: str,
    field_name: str,
    field_value: str,
    exclude_anomaly_id: str | None = None,
) -> dict | None:
    column = str(field_name or "").strip()
    if column not in {name for name, _label in _TRACE_FIELD_COLUMNS}:
        raise ValueError(f"Unsupported trace field: {field_name}")
    normalized_value = str(field_value or "").strip()
    if not normalized_value:
        return None
    params: list[Any] = [str(supplier_id or "").strip(), normalized_value]
    sql = f"""
        SELECT id, anomaly_no
        FROM anomalies
        WHERE supplier_id = ?
          AND TRIM({column}) = ?
    """
    excluded = str(exclude_anomaly_id or "").strip()
    if excluded:
        sql += " AND id <> ?"
        params.append(excluded)
    sql += " LIMIT 1"
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row is not None else None

def validate_anomaly_number(
    conn: sqlite3.Connection,
    anomaly_no: str,
    anomaly_date: str,
    *,
    exclude_anomaly_id: str | None = None,
) -> str:
    """Validate the canonical YYYYMMDDNNN anomaly-number contract."""
    normalized_no = str(anomaly_no or "").strip()
    normalized_date = _normalize_strict_iso_date(
        anomaly_date,
        field_name="Anomaly date",
    )
    if not _ANOMALY_NO_PATTERN.fullmatch(normalized_no):
        raise ValueError("異常單號必須為 11 碼純數字（YYYYMMDDNNN）")
    expected_prefix = normalized_date.replace("-", "")
    if not normalized_no.startswith(expected_prefix):
        raise ValueError(
            f"異常單號前 8 碼必須與異常日期 {normalized_date} 一致"
        )
    params: list[Any] = [normalized_no]
    sql = "SELECT id FROM anomalies WHERE anomaly_no = ?"
    excluded = str(exclude_anomaly_id or "").strip()
    if excluded:
        sql += " AND id <> ?"
        params.append(excluded)
    if conn.execute(sql + " LIMIT 1", params).fetchone() is not None:
        raise ValueError("異常單號已存在，請使用其他單號。")
    return normalized_no

def _validate_visit_supplier(
    conn: sqlite3.Connection,
    *,
    visit_id: Any,
    supplier_id: str,
) -> None:
    normalized_visit_id = str(visit_id or "").strip()
    if not normalized_visit_id:
        return
    row = conn.execute(
        "SELECT supplier_id FROM visits WHERE id = ?",
        (normalized_visit_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Visit not found")
    if str(row["supplier_id"] or "").strip() != str(supplier_id or "").strip():
        raise ValueError("Visit supplier does not match selected supplier")

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
    anomaly_source: str = "",
    material_receipt_no: str = "",
    internal_work_order_no: str = "",
    outsource_work_order: str = "",
    outsource_receipt_no: str = "",
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
    quality_report_required: bool | None = None,
    source_defect_no: str = "",
    process_keywords: str = "",
) -> str:
    _ensure_column(conn, "anomalies", "source_defect_no", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "anomalies", "process_keywords", "TEXT NOT NULL DEFAULT ''")
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
                category, product_lot_no, product_name, product_stage,
                anomaly_source, material_receipt_no, internal_work_order_no,
                outsource_work_order, outsource_receipt_no, batch_qty,
                status, improvement_desc, closed_at, created_at, updated_at,
                pending_items, responsible_person, due_date,
                rc_supplier_inventory, rc_supplier_wip, rc_in_transit, rc_internal_inventory,
                quality_report_required, source_defect_no, process_keywords
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '待處理', '', NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                (anomaly_source or "").strip(),
                (material_receipt_no or "").strip(),
                (internal_work_order_no or "").strip(),
                (outsource_work_order or "").strip(),
                (outsource_receipt_no or "").strip(),
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
                None if quality_report_required is None else int(quality_report_required),
                (source_defect_no or "").strip(),
                (process_keywords or "").strip(),
            ),
        )

    if anomaly_no:
        # Caller already reserved this number (e.g. create_anomaly_with_visit_link
        # embeds it into a visit summary text before reaching here), so a
        # collision here is a genuine caller bug, not a race -- retrying with a
        # different number would desync it from that already-written text.
        validated_no = validate_anomaly_number(
            conn,
            anomaly_no,
            normalized_date,
        )
        try:
            _do_insert(validated_no)
            return validated_no
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
        resolved_anomaly_no = _resolve_next_anomaly_no(conn, normalized_date)
        try:
            _do_insert(resolved_anomaly_no)
            return resolved_anomaly_no
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint failed" in str(exc) and "anomaly_no" in str(exc):
                last_exc = exc
                continue
            raise
    raise last_exc

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

def preview_anomaly_no(conn: sqlite3.Connection, anomaly_date: str) -> str:
    return _resolve_next_anomaly_no(conn, anomaly_date)
