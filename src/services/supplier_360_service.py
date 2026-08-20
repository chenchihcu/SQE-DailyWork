"""Read-only supplier-centric projections over the three workflow sources."""

from __future__ import annotations

from database import connection as _connection


def _supplier(conn, supplier_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM suppliers WHERE id = ? AND is_active = 1",
        (str(supplier_id or "").strip(),),
    ).fetchone()
    return dict(row) if row is not None else None


def _defect_supplier_key(conn, supplier: dict) -> tuple[str, str]:
    columns = {
        str(row["name"])
        for row in conn.execute("PRAGMA table_info(defect_records)").fetchall()
    }
    if "supplier_id" in columns:
        return "supplier_id", str(supplier["id"])
    return "supplier_name", str(supplier.get("supplier_name") or "")


def get_supplier_summary(supplier_id: str) -> dict:
    with _connection.get_connection() as conn:
        supplier = _supplier(conn, supplier_id)
        if supplier is None:
            return {}
        sid = str(supplier["id"])
        defect_column, defect_value = _defect_supplier_key(conn, supplier)
        anomaly = conn.execute(
            """
            SELECT
                COUNT(CASE WHEN status = '待處理' THEN 1 END) AS open_count,
                COUNT(CASE WHEN status = '待處理'
                            AND due_date <> ''
                            AND due_date < date('now', 'localtime')
                           THEN 1 END) AS overdue_count
            FROM anomalies
            WHERE supplier_id = ?
            """,
            (sid,),
        ).fetchone()
        ncr = conn.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM defect_records
            WHERE {defect_column} = ?
              AND event_date >= date('now', 'localtime', '-90 day')
            """,
            (defect_value,),
        ).fetchone()
        visit = conn.execute(
            "SELECT MAX(visit_date) AS latest FROM visits WHERE supplier_id = ?",
            (sid,),
        ).fetchone()
        return {
            "supplier": supplier,
            "open_anomaly_count": int(anomaly["open_count"] or 0),
            "overdue_anomaly_count": int(anomaly["overdue_count"] or 0),
            "ncr_90d_count": int(ncr["count"] or 0),
            "latest_visit_date": visit["latest"] if visit else "",
        }


def list_supplier_timeline(supplier_id: str, *, limit: int = 50) -> list[dict]:
    sid = str(supplier_id or "").strip()
    if not sid:
        return []
    with _connection.get_connection() as conn:
        supplier = _supplier(conn, sid)
        if supplier is None:
            return []
        defect_column, defect_value = _defect_supplier_key(conn, supplier)
        rows: list[dict] = []
        for row in conn.execute(
            """
            SELECT id AS record_id, anomaly_no AS ref_no, anomaly_date AS event_date,
                   problem_desc AS title, status, '異常' AS source
            FROM anomalies
            WHERE supplier_id = ?
            """,
            (sid,),
        ).fetchall():
            rows.append(dict(row))
        for row in conn.execute(
            """
            SELECT id AS record_id, '' AS ref_no, visit_date AS event_date,
                   summary AS title, status, '訪廠' AS source
            FROM visits
            WHERE supplier_id = ?
            """,
            (sid,),
        ).fetchall():
            rows.append(dict(row))
        for row in conn.execute(
            f"""
            SELECT id AS record_id, defect_no AS ref_no, event_date,
                   defect_desc AS title, status, '不合格品' AS source
            FROM defect_records
            WHERE {defect_column} = ?
            """,
            (defect_value,),
        ).fetchall():
            rows.append(dict(row))
        rows.sort(key=lambda item: str(item.get("event_date") or ""), reverse=True)
        return rows[: max(1, int(limit))]


def list_supplier_rows() -> list[dict]:
    with _connection.get_connection() as conn:
        suppliers = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM suppliers WHERE is_active = 1 ORDER BY supplier_name"
            ).fetchall()
        ]
    return [
        {
            **supplier,
            **{
                key: value
                for key, value in get_supplier_summary(str(supplier["id"])).items()
                if key != "supplier"
            },
        }
        for supplier in suppliers
    ]


def list_supplier_anomalies(supplier_id: str) -> list[dict]:
    with _connection.get_connection() as conn:
        return [
            dict(row)
            for row in conn.execute(
                f"""
                SELECT anomaly_no, anomaly_date, problem_desc, status,
                       responsible_person, due_date, closed_at
                FROM anomalies
                WHERE supplier_id = ?
                ORDER BY anomaly_date DESC
                """,
                (str(supplier_id),),
            ).fetchall()
        ]


def list_supplier_visits(supplier_id: str) -> list[dict]:
    with _connection.get_connection() as conn:
        return [
            dict(row)
            for row in conn.execute(
                f"""
                SELECT visit_date, summary, visitor_name, status, work_order_no
                FROM visits
                WHERE supplier_id = ?
                ORDER BY visit_date DESC
                """,
                (str(supplier_id),),
            ).fetchall()
        ]


def list_supplier_defects(supplier_id: str) -> list[dict]:
    with _connection.get_connection() as conn:
        supplier = _supplier(conn, supplier_id)
        if supplier is None:
            return []
        defect_column, defect_value = _defect_supplier_key(conn, supplier)
        return [
            dict(row)
            for row in conn.execute(
                f"""
                SELECT defect_no, event_date, item_no, product_name,
                       defect_desc, status, disposition, responsibility
                FROM defect_records
                WHERE {defect_column} = ?
                ORDER BY event_date DESC
                """,
                (defect_value,),
            ).fetchall()
        ]


def get_supplier_scorecard(
    supplier_id: str,
    start_date: str,
    end_date: str,
) -> dict:
    with _connection.get_connection() as conn:
        sid = str(supplier_id or "")
        supplier = _supplier(conn, sid) or {"id": sid, "supplier_name": ""}
        defect_column, defect_value = _defect_supplier_key(conn, supplier)
        anomaly = conn.execute(
            f"""
            SELECT
                COUNT(*) AS count,
                COUNT(CASE WHEN status = '已結案' AND due_date <> ''
                                AND closed_at <> '' AND closed_at <= due_date
                           THEN 1 END) AS on_time,
                COUNT(CASE WHEN status = '已結案' THEN 1 END) AS closed
            FROM anomalies
            WHERE supplier_id = ? AND anomaly_date BETWEEN ? AND ?
            """,
            (sid, start_date, end_date),
        ).fetchone()
        ncr = conn.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM defect_records
            WHERE {defect_column} = ? AND event_date BETWEEN ? AND ?
            """,
            (defect_value, start_date, end_date),
        ).fetchone()
        visits = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM visits
            WHERE supplier_id = ? AND visit_date BETWEEN ? AND ?
            """,
            (sid, start_date, end_date),
        ).fetchone()
    closed = int(anomaly["closed"] or 0)
    on_time_rate = (int(anomaly["on_time"] or 0) / closed) if closed else 1.0
    anomaly_count = int(anomaly["count"] or 0)
    ncr_count = int(ncr["count"] or 0)
    if on_time_rate >= 0.9 and ncr_count <= 2:
        grade = "A"
    elif on_time_rate >= 0.75 and ncr_count <= 5:
        grade = "B"
    else:
        grade = "C"
    return {
        "grade": grade,
        "anomaly_count": anomaly_count,
        "ncr_count": ncr_count,
        "visit_count": int(visits["count"] or 0),
        "closed_anomaly_count": closed,
        "on_time_rate": on_time_rate,
        "start_date": start_date,
        "end_date": end_date,
    }
