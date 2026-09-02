"""Supplier-event queries, global search projection, and monthly stats cache."""

from __future__ import annotations

import logging
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from database.case_action_repository import is_anomaly_overdue as is_case_action_overdue
from database.repo_helpers import (
    EVENT_SCOPE_ANOMALY_ONLY,
    EVENT_SCOPE_CLOSED_ONLY,
    EVENT_SCOPE_VALUES,
    EVENT_SCOPE_VISIT_ONLY,
    EVENT_SCOPE_VISIT_WITH_ANOMALY,
    _as_int,
    _month_from_date_value,
    _normalize_month,
    _table_exists,
)
from database.repository_schema_helpers import has_column as _has_column

logger = logging.getLogger(__name__)

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

def search_global(
    conn: sqlite3.Connection,
    keyword: str,
    *,
    limit: int = 30,
) -> list[dict]:
    """Search the four business sources without merging their data contracts."""
    value = str(keyword or "").strip()
    if not value:
        return []
    pattern = f"%{value}%"
    per_source_limit = max(1, min(int(limit), 100))
    results: list[dict] = []

    queries = (
        (
            "供應商",
            """
            SELECT id, supplier_name AS ref_no, supplier_name AS title,
                   contact_name AS subtitle, updated_at AS event_date, category
            FROM suppliers
            WHERE is_active = 1 AND supplier_name LIKE ?
            ORDER BY supplier_name
            LIMIT ?
            """,
            (pattern, per_source_limit),
        ),
        (
            "產品",
            """
            SELECT p.id, p.product_code AS ref_no, p.product_name AS title,
                   COALESCE(s.supplier_name, '') AS subtitle,
                   p.updated_at AS event_date, p.item_category
            FROM products p
            LEFT JOIN suppliers s ON s.id = p.supplier_id
            WHERE p.is_active = 1
              AND (
                  p.product_code LIKE ?
                  OR p.product_name LIKE ?
                  OR s.supplier_name LIKE ?
              )
            ORDER BY p.product_code
            LIMIT ?
            """,
            (pattern, pattern, pattern, per_source_limit),
        ),
        (
            "異常",
            """
            SELECT a.id, a.anomaly_no AS ref_no, a.problem_desc AS title,
                   s.supplier_name AS subtitle, a.anomaly_date AS event_date,
                   a.supplier_id
            FROM anomalies a
            JOIN suppliers s ON s.id = a.supplier_id
            WHERE a.anomaly_no LIKE ?
               OR a.problem_desc LIKE ?
               OR a.product_name LIKE ?
               OR s.supplier_name LIKE ?
            ORDER BY a.anomaly_date DESC, a.created_at DESC
            LIMIT ?
            """,
            (pattern, pattern, pattern, pattern, per_source_limit),
        ),
        (
            "不合格品",
            """
            SELECT id, defect_no AS ref_no, defect_desc AS title,
                   COALESCE(NULLIF(outsource_supplier_name, ''), supplier_name) AS subtitle,
                   event_date, supplier_name, processing_line, status
            FROM defect_records
            WHERE defect_no LIKE ?
               OR defect_desc LIKE ?
               OR item_no LIKE ?
               OR product_name LIKE ?
               OR supplier_name LIKE ?
               OR outsource_supplier_name LIKE ?
            ORDER BY event_date DESC, created_at DESC
            LIMIT ?
            """,
            (pattern, pattern, pattern, pattern, pattern, pattern, per_source_limit),
        ),
    )
    for source, sql, params in queries:
        for row in conn.execute(sql, params).fetchall():
            item = dict(row)
            item["source"] = source
            results.append(item)
    return results[: max(1, int(limit))]

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
    event_type_key = str(event_type or "ALL").strip().upper()
    scope = str(event_scope or "").strip().upper()
    if scope in {EVENT_SCOPE_VISIT_ONLY, EVENT_SCOPE_VISIT_WITH_ANOMALY}:
        scope = ""
    if scope not in EVENT_SCOPE_VALUES:
        scope = ""

    if scope:
        include_anomalies = scope in {
            EVENT_SCOPE_ANOMALY_ONLY,
            EVENT_SCOPE_CLOSED_ONLY,
        }
    else:
        include_anomalies = event_type_key in {"ALL", "ANOMALY"}

    if overdue_only:
        include_anomalies = True

    if include_anomalies:
        pending_items_expr = (
            "a.pending_items AS pending_items"
            if _has_column(conn, "anomalies", "pending_items")
            else "'' AS pending_items"
        )
        process_keywords_expr = (
            "a.process_keywords AS process_keywords"
            if _has_column(conn, "anomalies", "process_keywords")
            else "'' AS process_keywords"
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
                {process_keywords_expr},
                a.visit_id AS linked_visit_id,
                v.visit_date AS linked_visit_date,
                a.product_id AS product_id,
                p.product_code AS product_code,
                a.product_lot_no AS product_lot_no,
                a.product_name AS product_name,
                a.product_stage AS product_stage,
                a.anomaly_source AS anomaly_source,
                a.material_receipt_no AS material_receipt_no,
                a.internal_work_order_no AS internal_work_order_no,
                a.outsource_work_order AS work_order_no,
                a.batch_qty AS production_qty,
                a.outsource_work_order AS outsource_work_order,
                a.outsource_receipt_no AS outsource_receipt_no,
                a.batch_qty AS batch_qty,
                a.improvement_desc AS improvement_desc,
                {pending_items_expr},
                a.responsible_person AS responsible_person,
                a.closed_at AS closed_at,
                a.quality_report_required AS quality_report_required
            FROM anomalies a
            JOIN suppliers s ON s.id = a.supplier_id
            LEFT JOIN visits v ON v.id = a.visit_id
            LEFT JOIN products p ON p.id = a.product_id
            WHERE 1=1
        """
        anomaly_params: list[Any] = []
        if scope == EVENT_SCOPE_ANOMALY_ONLY:
            anomaly_sql += " AND a.status != '已結案'"
        elif scope == EVENT_SCOPE_CLOSED_ONLY:
            anomaly_sql += " AND a.status = '已結案'"
        if status != "ALL":
            anomaly_sql += " AND a.status = ?"
            anomaly_params.append(status)

        if keyword:
            kw = f"%{keyword.lower()}%"
            if keyword.strip() == "未指定":
                anomaly_sql += " AND (lower(s.supplier_name) LIKE ? OR lower(a.responsible_person) LIKE ? OR TRIM(COALESCE(a.responsible_person, '')) = '')"
                anomaly_params.extend([kw, kw])
            else:
                anomaly_sql += " AND (lower(s.supplier_name) LIKE ? OR lower(a.responsible_person) LIKE ?)"
                anomaly_params.extend([kw, kw])
        anomaly_sql += anomaly_period_sql
        anomaly_params.extend(anomaly_period_params)

        for row in conn.execute(anomaly_sql, anomaly_params).fetchall():
            events.append(dict(row))
        if overdue_only:
            events = [
                event
                for event in events
                if is_case_action_overdue(conn, str(event.get("event_id") or ""))
            ]

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
    from database.anomaly_workbench_repository import (
        count_overdue_open_anomalies,
        count_overdue_open_anomalies_by_supplier,
    )

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
            COUNT(CASE WHEN status = '待處理' AND (visit_id IS NULL OR visit_id = '') THEN 1 END) AS standalone_open_anomaly_count,
            COUNT(CASE WHEN status = '待處理' AND (visit_id IS NOT NULL AND visit_id <> '') THEN 1 END) AS visit_open_anomaly_count
        FROM anomalies
        WHERE {anomaly_where}
        """,
        anomaly_params,
    ).fetchone()
    anomaly_count = int(row["anomaly_count"])
    open_anomaly_count = int(row["open_anomaly_count"])
    standalone_open_anomaly_count = int(row["standalone_open_anomaly_count"])
    visit_open_anomaly_count = int(row["visit_open_anomaly_count"])
    overdue_open_anomaly_count = count_overdue_open_anomalies(
        conn,
        anomaly_where=anomaly_where,
        anomaly_params=anomaly_params,
    )
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
        )
        SELECT
            s.id AS supplier_id,
            s.supplier_name AS supplier_name,
            COALESCE(ma.anomaly_count, 0) AS anomaly_count,
            COALESCE(mv.visit_count, 0) AS visit_count,
            COALESCE(mc.closed_anomaly_count, 0) AS closed_anomaly_count,
            COALESCE(mo.open_anomaly_count, 0) AS open_anomaly_count,
            COALESCE(mo.standalone_open_anomaly_count, 0) AS standalone_open_anomaly_count,
            COALESCE(mo.visit_open_anomaly_count, 0) AS visit_open_anomaly_count,
            COALESCE(ma.avg_resolution_time, 0) AS avg_resolution_time
        FROM month_suppliers ms
        JOIN suppliers s ON s.id = ms.supplier_id
        LEFT JOIN month_anomalies ma ON ma.supplier_id = ms.supplier_id
        LEFT JOIN month_visits mv ON mv.supplier_id = ms.supplier_id
        LEFT JOIN month_closed mc ON mc.supplier_id = ms.supplier_id
        LEFT JOIN month_open mo ON mo.supplier_id = ms.supplier_id
        ORDER BY
            COALESCE(ma.anomaly_count, 0) DESC,
            COALESCE(mv.visit_count, 0) DESC,
            s.supplier_name COLLATE NOCASE ASC
    """
    top_params = tuple(
        anomaly_params + visit_params + closed_params
        + anomaly_params + visit_params + closed_params
        + anomaly_params
    )
    overdue_by_supplier = count_overdue_open_anomalies_by_supplier(
        conn,
        anomaly_where=anomaly_where,
        anomaly_params=anomaly_params,
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
                "overdue_open_anomaly_count": overdue_by_supplier.get(
                    str(item.get("supplier_id") or ""),
                    0,
                ),
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

def rebuild_all_monthly_cache(
    conn: sqlite3.Connection,
    *,
    _commit: bool = True,
) -> None:
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
    if _commit:
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
