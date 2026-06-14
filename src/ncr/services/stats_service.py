from __future__ import annotations

import sqlite3

_ALLOWED_NAME_FIELDS = frozenset(
    {"product_name", "supplier_name", "outsource_supplier_name"}
)


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


def get_warehouse_nonconforming_summary(conn: sqlite3.Connection) -> dict[str, int]:
    """Return physical warehouse nonconforming-product totals from defect_records only."""
    row = conn.execute(
        """
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
        """
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


def get_disposition_stats(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    cursor = conn.execute(
        """
        SELECT
            disposition,
            COUNT(*) AS case_count,
            SUM(qty) AS total_qty
        FROM defect_records
        WHERE disposition IS NOT NULL AND disposition <> ''
        GROUP BY disposition
        ORDER BY total_qty DESC
        """
    )
    return list(cursor.fetchall())


def get_top_suppliers_stats(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    cursor = conn.execute(
        """
        SELECT
            supplier_name,
            COUNT(*) AS case_count,
            SUM(qty) AS total_qty
        FROM defect_records
        WHERE supplier_name IS NOT NULL AND supplier_name <> '' AND supplier_name <> 'N/A'
        GROUP BY supplier_name
        ORDER BY total_qty DESC
        LIMIT 5
        """
    )
    return list(cursor.fetchall())


def get_top_suppliers_stats_filtered(
    conn: sqlite3.Connection, yyyymm: str | None = None
) -> list[sqlite3.Row]:
    if yyyymm and yyyymm != "ALL":
        formatted_month = f"{yyyymm[:4]}-{yyyymm[4:]}"
        cursor = conn.execute(
            """
            SELECT
                supplier_name,
                COUNT(*) AS case_count,
                SUM(qty) AS total_qty
            FROM defect_records
            WHERE supplier_name IS NOT NULL AND supplier_name <> '' AND supplier_name <> 'N/A'
              AND SUBSTR(event_date, 1, 7) = ?
            GROUP BY supplier_name
            ORDER BY total_qty DESC
            LIMIT 5
            """,
            (formatted_month,),
        )
    else:
        cursor = conn.execute(
            """
            SELECT
                supplier_name,
                COUNT(*) AS case_count,
                SUM(qty) AS total_qty
            FROM defect_records
            WHERE supplier_name IS NOT NULL AND supplier_name <> '' AND supplier_name <> 'N/A'
            GROUP BY supplier_name
            ORDER BY total_qty DESC
            LIMIT 5
            """
        )
    return list(cursor.fetchall())


def get_top_products_stats(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    cursor = conn.execute(
        """
        SELECT
            product_name,
            COUNT(*) AS case_count,
            SUM(qty) AS total_qty
        FROM defect_records
        WHERE product_name IS NOT NULL AND product_name <> '' AND product_name <> 'N/A'
        GROUP BY product_name
        ORDER BY total_qty DESC
        LIMIT 5
        """
    )
    return list(cursor.fetchall())


def get_top_products_stats_filtered(
    conn: sqlite3.Connection, yyyymm: str | None = None
) -> list[sqlite3.Row]:
    if yyyymm and yyyymm != "ALL":
        formatted_month = f"{yyyymm[:4]}-{yyyymm[4:]}"
        cursor = conn.execute(
            """
            SELECT
                product_name,
                COUNT(*) AS case_count,
                SUM(qty) AS total_qty
            FROM defect_records
            WHERE product_name IS NOT NULL AND product_name <> '' AND product_name <> 'N/A'
              AND SUBSTR(event_date, 1, 7) = ?
            GROUP BY product_name
            ORDER BY total_qty DESC
            LIMIT 5
            """,
            (formatted_month,),
        )
    else:
        cursor = conn.execute(
            """
            SELECT
                product_name,
                COUNT(*) AS case_count,
                SUM(qty) AS total_qty
            FROM defect_records
            WHERE product_name IS NOT NULL AND product_name <> '' AND product_name <> 'N/A'
            GROUP BY product_name
            ORDER BY total_qty DESC
            LIMIT 5
            """
        )
    return list(cursor.fetchall())


def get_scrap_rework_ratio_filtered(
    conn: sqlite3.Connection, yyyymm: str | None = None
) -> list[sqlite3.Row]:
    if yyyymm and yyyymm != "ALL":
        formatted_month = f"{yyyymm[:4]}-{yyyymm[4:]}"
        cursor = conn.execute(
            """
            SELECT
                disposition,
                COUNT(*) AS case_count,
                SUM(qty) AS total_qty
            FROM defect_records
            WHERE disposition IN ('報廢', '重工')
              AND SUBSTR(event_date, 1, 7) = ?
            GROUP BY disposition
            ORDER BY total_qty DESC
            """,
            (formatted_month,),
        )
    else:
        cursor = conn.execute(
            """
            SELECT
                disposition,
                COUNT(*) AS case_count,
                SUM(qty) AS total_qty
            FROM defect_records
            WHERE disposition IN ('報廢', '重工')
            GROUP BY disposition
            ORDER BY total_qty DESC
            """
        )
    return list(cursor.fetchall())


def get_return_slip_ratio_filtered(
    conn: sqlite3.Connection, yyyymm: str | None = None
) -> list[sqlite3.Row]:
    if yyyymm and yyyymm != "ALL":
        formatted_month = f"{yyyymm[:4]}-{yyyymm[4:]}"
        cursor = conn.execute(
            """
            SELECT
                return_slip_type,
                COUNT(*) AS case_count,
                SUM(qty) AS total_qty
            FROM defect_records
            WHERE return_slip_type IN ('廠內退料', '託外退料')
              AND SUBSTR(event_date, 1, 7) = ?
            GROUP BY return_slip_type
            ORDER BY total_qty DESC
            """,
            (formatted_month,),
        )
    else:
        cursor = conn.execute(
            """
            SELECT
                return_slip_type,
                COUNT(*) AS case_count,
                SUM(qty) AS total_qty
            FROM defect_records
            WHERE return_slip_type IN ('廠內退料', '託外退料')
            GROUP BY return_slip_type
            ORDER BY total_qty DESC
            """
        )
    return list(cursor.fetchall())



def get_trend_stats(conn: sqlite3.Connection, months: int = 6) -> list[sqlite3.Row]:
    cursor = conn.execute(
        f"""
        SELECT
            SUBSTR(event_date, 1, 7) AS event_month,
            COUNT(*) AS case_count,
            SUM(qty) AS total_qty
        FROM defect_records
        WHERE event_date IS NOT NULL AND event_date <> ''
        GROUP BY SUBSTR(event_date, 1, 7)
        ORDER BY event_month DESC
        LIMIT {months}
        """
    )
    # 按照月份正序回傳 (較早的月份在前，適合畫圖)
    rows = list(cursor.fetchall())
    rows.reverse()
    return rows


def get_supplier_disposition_stats(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    cursor = conn.execute(
        """
        SELECT
            supplier_name,
            disposition,
            SUM(qty) AS total_qty
        FROM defect_records
        WHERE supplier_name IN (
            SELECT supplier_name
            FROM defect_records
            WHERE supplier_name IS NOT NULL AND supplier_name <> '' AND supplier_name <> 'N/A'
            GROUP BY supplier_name
            ORDER BY SUM(qty) DESC
            LIMIT 5
        )
        AND disposition IS NOT NULL AND disposition <> ''
        GROUP BY supplier_name, disposition
        ORDER BY supplier_name, disposition
        """
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


def get_status_preview_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    cursor = conn.execute(
        _build_detail_preview_query("status IS NOT NULL AND status <> ''")
    )
    return list(cursor.fetchall())


def get_status_preview_rows_raw_material(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """原物料狀態總覽（item_no 以 '0' 開頭）"""
    cursor = conn.execute(
        _build_detail_preview_query(
            "status IS NOT NULL AND status <> '' AND item_no LIKE '0%'"
        )
    )
    return list(cursor.fetchall())


def get_status_preview_rows_non_raw_material(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """半成品/成品狀態總覽（item_no 不以 '0' 開頭）"""
    cursor = conn.execute(
        _build_detail_preview_query(
            "status IS NOT NULL AND status <> '' AND item_no NOT LIKE '0%'"
        )
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


_YIMED_SUPPLIER_NAME = "醫電鼎眾"


def get_supplier_processing_preview_rows_exclude_yimed(
    conn: sqlite3.Connection,
) -> list[sqlite3.Row]:
    """一般供應商待追蹤（排除醫電鼎眾製損項目）。"""
    name_field = "supplier_name"
    non_empty_clause = _build_non_empty_name_clause(name_field)
    cursor = conn.execute(
        _build_detail_preview_query(
            f"{non_empty_clause} AND status = '處理中' AND {name_field} <> ?"
        ),
        (_YIMED_SUPPLIER_NAME,),
    )
    return list(cursor.fetchall())


def get_yimed_processing_preview_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """醫電鼎眾待追蹤（製損）。"""
    name_field = "supplier_name"
    non_empty_clause = _build_non_empty_name_clause(name_field)
    cursor = conn.execute(
        _build_detail_preview_query(
            f"{non_empty_clause} AND status = '處理中' AND {name_field} = ?"
        ),
        (_YIMED_SUPPLIER_NAME,),
    )
    return list(cursor.fetchall())


def get_outsource_scrap_preview_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return _get_preview_rows_for_name(
        conn,
        name_field="outsource_supplier_name",
        disposition="報廢",
    )
