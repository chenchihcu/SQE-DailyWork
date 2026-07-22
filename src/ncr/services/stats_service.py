from __future__ import annotations

import sqlite3

from services.date_range import validate_date_range

from ncr.models.defect import (
    PROCESSING_LINE_MATERIAL,
    PROCESSING_LINE_OUTSOURCE,
    PROCESSING_LINE_STORAGE_OPTIONS,
    PROCESSING_LINE_UNCLASSIFIED,
)

_ALLOWED_NAME_FIELDS = frozenset(
    {"product_name", "supplier_name", "outsource_supplier_name"}
)
_ALLOWED_GROUP_FIELDS = frozenset({"disposition", "return_slip_type"})


def _validate_group_field(field: str) -> str:
    if field not in _ALLOWED_GROUP_FIELDS:
        raise ValueError(f"Unsupported group field: {field}")
    return field


def _validate_name_field(name_field: str) -> str:
    if name_field not in _ALLOWED_NAME_FIELDS:
        raise ValueError(f"Unsupported stats name field: {name_field}")
    return name_field


def _build_stats_query(name_field: str) -> str:
    name_field = _validate_name_field(name_field)
    return f"""
        SELECT
            {name_field},
            disposition,
            category,
            SUBSTR(event_date, 1, 7) AS event_month,
            status,
            COUNT(*) AS case_count,
            SUM(qty) AS total_qty
        FROM defect_records
        WHERE {name_field} IS NOT NULL AND {name_field} <> '' AND {name_field} <> 'N/A'
        GROUP BY
            {name_field},
            disposition,
            category,
            SUBSTR(event_date, 1, 7),
            status
        ORDER BY
            SUM(qty) DESC,
            {name_field} ASC,
            SUBSTR(event_date, 1, 7) DESC
        """


def _build_detail_preview_query(where_clause: str) -> str:
    return f"""
        SELECT
            defect_no,
            event_date,
            processing_line,
            return_slip_type,
            work_order_no,
            item_no,
            product_name,
            qty,
            status,
            disposition,
            defect_desc,
            supplier_name,
            outsource_supplier_name
        FROM defect_records
        WHERE {where_clause}
        ORDER BY event_date DESC, defect_no DESC
        """


def _build_non_empty_name_clause(name_field: str) -> str:
    name_field = _validate_name_field(name_field)
    return f"{name_field} IS NOT NULL AND {name_field} <> '' AND {name_field} <> 'N/A'"


def _get_processing_stats_by_name(
    conn: sqlite3.Connection, *, name_field: str
) -> list[sqlite3.Row]:
    name_field = _validate_name_field(name_field)
    non_empty_name_clause = _build_non_empty_name_clause(name_field)
    cursor = conn.execute(
        f"""
        SELECT
            {name_field},
            COUNT(*) AS case_count,
            SUM(qty) AS total_qty
        FROM defect_records
        WHERE {non_empty_name_clause}
            AND status = '處理中'
        GROUP BY {name_field}
        ORDER BY total_qty DESC, {name_field} ASC
        """
    )
    return list(cursor.fetchall())


def _get_preview_rows_for_name(
    conn: sqlite3.Connection,
    *,
    name_field: str,
    status: str | None = None,
    disposition: str | None = None,
) -> list[sqlite3.Row]:
    name_field = _validate_name_field(name_field)
    clauses = [_build_non_empty_name_clause(name_field)]
    params: list[str] = []
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    if disposition is not None:
        clauses.append("disposition = ?")
        params.append(disposition)
    where_clause = " AND ".join(clauses)
    cursor = conn.execute(_build_detail_preview_query(where_clause), params)
    return list(cursor.fetchall())


def get_product_stats(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    cursor = conn.execute(_build_stats_query("product_name"))
    return list(cursor.fetchall())


def get_supplier_stats(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    cursor = conn.execute(_build_stats_query("supplier_name"))
    return list(cursor.fetchall())


def get_outsource_stats(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    cursor = conn.execute(_build_stats_query("outsource_supplier_name"))
    return list(cursor.fetchall())


def get_status_totals(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    cursor = conn.execute(
        """
        SELECT
            status,
            COUNT(*) AS case_count,
            SUM(qty) AS total_qty
        FROM defect_records
        WHERE status IS NOT NULL AND status <> ''
        GROUP BY status
        ORDER BY total_qty DESC, status ASC
        """
    )
    return list(cursor.fetchall())


def get_warehouse_nonconforming_summary(
    conn: sqlite3.Connection,
    *,
    processing_line: str | None = None,
) -> dict[str, int]:
    """Return physical warehouse nonconforming-product totals from defect_records only."""
    where_clause = ""
    params: tuple[str, ...] = ()
    if processing_line:
        where_clause = "WHERE processing_line = ?"
        params = (processing_line,)
    row = conn.execute(
        f"""
        SELECT
            COUNT(*) AS total_count,
            COALESCE(SUM(qty), 0) AS total_qty,
            COALESCE(SUM(CASE WHEN status = '處理中' THEN 1 ELSE 0 END), 0) AS open_count,
            COALESCE(SUM(CASE WHEN status = '處理中' THEN qty ELSE 0 END), 0) AS open_qty,
            COALESCE(SUM(CASE WHEN status = '已結案' THEN 1 ELSE 0 END), 0) AS closed_count,
            COALESCE(SUM(CASE WHEN status = '已結案' THEN qty ELSE 0 END), 0) AS closed_qty,
            COALESCE(SUM(CASE WHEN disposition = '重工' THEN qty ELSE 0 END), 0) AS rework_qty,
            COALESCE(SUM(CASE WHEN disposition = '報廢' THEN qty ELSE 0 END), 0) AS scrap_qty
        FROM defect_records
        {where_clause}
        """,
        params,
    ).fetchone()
    if row is None:
        return {
            "total_count": 0,
            "total_qty": 0,
            "open_count": 0,
            "open_qty": 0,
            "closed_count": 0,
            "closed_qty": 0,
            "rework_qty": 0,
            "scrap_qty": 0,
        }
    return {
        "total_count": int(row["total_count"] or 0),
        "total_qty": int(row["total_qty"] or 0),
        "open_count": int(row["open_count"] or 0),
        "open_qty": int(row["open_qty"] or 0),
        "closed_count": int(row["closed_count"] or 0),
        "closed_qty": int(row["closed_qty"] or 0),
        "rework_qty": int(row["rework_qty"] or 0),
        "scrap_qty": int(row["scrap_qty"] or 0),
    }


def get_pending_counts_by_processing_line(conn: sqlite3.Connection) -> dict[str, int]:
    """Return open warehouse counts grouped by the formal processing-line contract."""
    counts = {
        PROCESSING_LINE_MATERIAL: 0,
        PROCESSING_LINE_OUTSOURCE: 0,
        PROCESSING_LINE_UNCLASSIFIED: 0,
    }
    try:
        cursor = conn.execute(
            """
            SELECT processing_line, COUNT(*) AS case_count
            FROM defect_records
            WHERE status <> '已結案'
            GROUP BY processing_line
            """
        )
    except sqlite3.OperationalError as exc:
        if "no such column: processing_line" in str(exc):
            return counts
        raise
    for row in cursor.fetchall():
        line = str(row["processing_line"] or PROCESSING_LINE_UNCLASSIFIED)
        if line not in PROCESSING_LINE_STORAGE_OPTIONS:
            line = PROCESSING_LINE_UNCLASSIFIED
        counts[line] += int(row["case_count"] or 0)
    return counts


def _get_top_entity_stats_filtered(
    conn: sqlite3.Connection,
    entity_field: str,
    yyyymm: str | None = None,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[sqlite3.Row]:
    _validate_name_field(entity_field)
    from datetime import date
    current_year = date.today().year
    current_month = date.today().month

    if start_date and end_date:
        start_date, end_date = validate_date_range(start_date, end_date)
        time_clause = "event_date BETWEEN ? AND ?"
        params = [start_date, end_date]
    elif not yyyymm or yyyymm == "ALL":
        time_clause = "1=1"
        params = []
    elif yyyymm == "YEAR":
        time_clause = "SUBSTR(event_date, 1, 4) = ?"
        params = [str(current_year)]
    elif yyyymm == "HALF_YEAR":
        if current_month <= 6:
            time_clause = "SUBSTR(event_date, 1, 4) = ? AND CAST(SUBSTR(event_date, 6, 2) AS INTEGER) BETWEEN 1 AND 6"
        else:
            time_clause = "SUBSTR(event_date, 1, 4) = ? AND CAST(SUBSTR(event_date, 6, 2) AS INTEGER) BETWEEN 7 AND 12"
        params = [str(current_year)]
    else:
        formatted_month = f"{yyyymm[:4]}-{yyyymm[4:]}"
        time_clause = "SUBSTR(event_date, 1, 7) = ?"
        params = [formatted_month]

    cursor = conn.execute(
        f"""
        SELECT
            {entity_field},
            COUNT(*) AS case_count,
            SUM(qty) AS total_qty
        FROM defect_records
        WHERE {entity_field} IS NOT NULL AND {entity_field} <> '' AND {entity_field} <> 'N/A'
          AND {time_clause}
        GROUP BY {entity_field}
        ORDER BY total_qty DESC
        LIMIT 5
        """,
        params,
    )
    return list(cursor.fetchall())


def _get_grouped_stats_filtered(
    conn: sqlite3.Connection,
    group_field: str,
    where_values: tuple[str, ...],
    yyyymm: str | None = None,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[sqlite3.Row]:
    _validate_group_field(group_field)
    placeholders = ", ".join("?" * len(where_values))
    filter_clause = f"{group_field} IN ({placeholders})"
    
    from datetime import date
    current_year = date.today().year
    current_month = date.today().month

    if start_date and end_date:
        start_date, end_date = validate_date_range(start_date, end_date)
        time_clause = "event_date BETWEEN ? AND ?"
        time_params = [start_date, end_date]
    elif not yyyymm or yyyymm == "ALL":
        time_clause = "1=1"
        time_params = []
    elif yyyymm == "YEAR":
        time_clause = "SUBSTR(event_date, 1, 4) = ?"
        time_params = [str(current_year)]
    elif yyyymm == "HALF_YEAR":
        if current_month <= 6:
            time_clause = "SUBSTR(event_date, 1, 4) = ? AND CAST(SUBSTR(event_date, 6, 2) AS INTEGER) BETWEEN 1 AND 6"
        else:
            time_clause = "SUBSTR(event_date, 1, 4) = ? AND CAST(SUBSTR(event_date, 6, 2) AS INTEGER) BETWEEN 7 AND 12"
        time_params = [str(current_year)]
    else:
        formatted_month = f"{yyyymm[:4]}-{yyyymm[4:]}"
        time_clause = "SUBSTR(event_date, 1, 7) = ?"
        time_params = [formatted_month]

    params = list(where_values) + time_params
    cursor = conn.execute(
        f"""
        SELECT
            {group_field},
            COUNT(*) AS case_count,
            SUM(qty) AS total_qty
        FROM defect_records
        WHERE {filter_clause}
          AND {time_clause}
        GROUP BY {group_field}
        ORDER BY total_qty DESC
        """,
        params,
    )
    return list(cursor.fetchall())


def _get_return_slip_ratio_filtered(
    conn: sqlite3.Connection,
    yyyymm: str | None = None,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[sqlite3.Row]:
    from datetime import date
    current_year = date.today().year
    current_month = date.today().month

    if start_date and end_date:
        start_date, end_date = validate_date_range(start_date, end_date)
        time_clause = "event_date BETWEEN ? AND ?"
        params = [start_date, end_date]
    elif not yyyymm or yyyymm == "ALL":
        time_clause = "1=1"
        params = []
    elif yyyymm == "YEAR":
        time_clause = "SUBSTR(event_date, 1, 4) = ?"
        params = [str(current_year)]
    elif yyyymm == "HALF_YEAR":
        if current_month <= 6:
            time_clause = "SUBSTR(event_date, 1, 4) = ? AND CAST(SUBSTR(event_date, 6, 2) AS INTEGER) BETWEEN 1 AND 6"
        else:
            time_clause = "SUBSTR(event_date, 1, 4) = ? AND CAST(SUBSTR(event_date, 6, 2) AS INTEGER) BETWEEN 7 AND 12"
        params = [str(current_year)]
    else:
        formatted_month = f"{yyyymm[:4]}-{yyyymm[4:]}"
        time_clause = "SUBSTR(event_date, 1, 7) = ?"
        params = [formatted_month]

    normalized_field = "COALESCE(NULLIF(TRIM(return_slip_type), ''), '未註明')"
    cursor = conn.execute(
        f"""
        SELECT
            {normalized_field} AS return_slip_type,
            COUNT(*) AS case_count,
            COALESCE(SUM(qty), 0) AS total_qty
        FROM defect_records
        WHERE {time_clause}
        GROUP BY {normalized_field}
        ORDER BY
            CASE return_slip_type
                WHEN '廠內退料' THEN 0
                WHEN '託外退料' THEN 1
                WHEN '未註明' THEN 2
                ELSE 3
            END,
            total_qty DESC,
            return_slip_type ASC
        """,
        params,
    )
    return list(cursor.fetchall())


def get_outsource_processing_stats(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return _get_processing_stats_by_name(conn, name_field="outsource_supplier_name")


def get_supplier_processing_stats(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return _get_processing_stats_by_name(conn, name_field="supplier_name")


def get_outsource_scrap_stats(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    cursor = conn.execute(
        """
        SELECT
            outsource_supplier_name,
            item_no,
            COUNT(*) AS case_count,
            SUM(qty) AS total_qty
        FROM defect_records
        WHERE outsource_supplier_name IS NOT NULL
            AND outsource_supplier_name <> ''
            AND outsource_supplier_name <> 'N/A'
            AND disposition = '報廢'
        GROUP BY outsource_supplier_name, item_no
        ORDER BY total_qty DESC, outsource_supplier_name ASC, item_no ASC
        """
    )
    return list(cursor.fetchall())


def get_outsource_processing_preview_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return _get_preview_rows_for_name(
        conn,
        name_field="outsource_supplier_name",
        status="處理中",
    )


def get_supplier_processing_preview_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return _get_preview_rows_for_name(
        conn,
        name_field="supplier_name",
        status="處理中",
    )


def get_outsource_scrap_preview_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return _get_preview_rows_for_name(
        conn,
        name_field="outsource_supplier_name",
        disposition="報廢",
    )


def get_top_suppliers_stats_by_range(
    conn: sqlite3.Connection, start_date: str, end_date: str
) -> list[sqlite3.Row]:
    return _get_top_entity_stats_filtered(conn, "supplier_name", start_date=start_date, end_date=end_date)


def get_top_products_stats_by_range(
    conn: sqlite3.Connection, start_date: str, end_date: str
) -> list[sqlite3.Row]:
    return _get_top_entity_stats_filtered(conn, "product_name", start_date=start_date, end_date=end_date)


def get_scrap_rework_ratio_by_range(
    conn: sqlite3.Connection, start_date: str, end_date: str
) -> list[sqlite3.Row]:
    return _get_grouped_stats_filtered(
        conn, "disposition", ("報廢", "重工"), start_date=start_date, end_date=end_date
    )


def get_return_slip_ratio_by_range(
    conn: sqlite3.Connection, start_date: str, end_date: str
) -> list[sqlite3.Row]:
    return _get_return_slip_ratio_filtered(
        conn, start_date=start_date, end_date=end_date
    )


def get_defects_detail_by_range(
    conn: sqlite3.Connection, start_date: str, end_date: str
) -> list[sqlite3.Row]:
    """取得指定日期範圍內的所有不合格品明細。"""
    start_date, end_date = validate_date_range(start_date, end_date)
    cursor = conn.execute(
        """
        SELECT *
        FROM defect_records
        WHERE event_date BETWEEN ? AND ?
        ORDER BY event_date DESC, defect_no DESC
        """,
        (start_date, end_date),
    )
    return list(cursor.fetchall())

