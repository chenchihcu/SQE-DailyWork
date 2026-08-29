"""Read-only supplier-centric projections over the three workflow sources."""

from __future__ import annotations

from database import connection as _connection
from database import repository


SCORECARD_GRADE_A_ON_TIME_RATE = 0.9
SCORECARD_GRADE_A_NCR_MAX = 2
SCORECARD_GRADE_B_ON_TIME_RATE = 0.75
SCORECARD_GRADE_B_NCR_MAX = 5


def _grade_from_metrics(on_time_rate: float, ncr_count: int) -> str:
    if on_time_rate >= SCORECARD_GRADE_A_ON_TIME_RATE and ncr_count <= SCORECARD_GRADE_A_NCR_MAX:
        return "A"
    if on_time_rate >= SCORECARD_GRADE_B_ON_TIME_RATE and ncr_count <= SCORECARD_GRADE_B_NCR_MAX:
        return "B"
    return "C"


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
                COUNT(CASE WHEN status = '待處理' THEN 1 END) AS open_count
            FROM anomalies
            WHERE supplier_id = ?
            """,
            (sid,),
        ).fetchone()
        overdue_count = repository.count_overdue_open_anomalies(conn, supplier_id=sid)
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
            "overdue_anomaly_count": overdue_count,
            "ncr_90d_count": int(ncr["count"] or 0),
            "latest_visit_date": visit["latest"] if visit else "",
            "repeat_flagged_anomaly_count": repository.count_supplier_repeat_flagged_anomalies(
                conn, sid
            ),
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


def list_supplier_rows(*, view_scope: str = "open_anomaly") -> list[dict]:
    """Return active suppliers with one batched quality summary per row.

    ``open_anomaly`` is the operational default because this page is an
    anomaly-work view.  The other scopes are available for explicit
    classification in the page filter.
    """
    scope_filters = {
        "open_anomaly": "COALESCE(a.open_anomaly_count, 0) > 0",
        "any_anomaly": "COALESCE(a.anomaly_count, 0) > 0",
        "all": "1 = 1",
    }
    try:
        scope_filter = scope_filters[view_scope]
    except KeyError as exc:
        raise ValueError(f"Unsupported supplier overview scope: {view_scope}") from exc

    with _connection.get_connection() as conn:
        overdue_by_supplier = repository.count_overdue_open_anomalies_by_supplier(conn)
        defect_columns = {
            str(item["name"])
            for item in conn.execute("PRAGMA table_info(defect_records)").fetchall()
        }
        has_supplier_id = "supplier_id" in defect_columns
        defect_key = "d.supplier_id" if has_supplier_id else "d.supplier_name"
        defect_join_key = "s.id" if has_supplier_id else "s.supplier_name"
        row = conn.execute(
            f"""
            WITH latest_open_anomaly AS (
                SELECT
                    supplier_id,
                    anomaly_no AS latest_anomaly_no,
                    anomaly_date AS latest_anomaly_date,
                    category AS latest_anomaly_category,
                    problem_desc AS latest_anomaly_desc,
                    due_date AS latest_anomaly_due_date,
                    ROW_NUMBER() OVER (
                        PARTITION BY supplier_id
                        ORDER BY anomaly_date DESC, created_at DESC, id DESC
                    ) AS row_number
                FROM anomalies
                WHERE status = '待處理'
            )
            SELECT
                s.*,
                COALESCE(a.anomaly_count, 0) AS anomaly_count,
                COALESCE(a.open_anomaly_count, 0) AS open_anomaly_count,
                COALESCE(a.overdue_anomaly_count, 0) AS overdue_anomaly_count,
                COALESCE(d.ncr_90d_count, 0) AS ncr_90d_count,
                v.latest_visit_date,
                la.latest_anomaly_no,
                la.latest_anomaly_date,
                la.latest_anomaly_category,
                la.latest_anomaly_desc,
                la.latest_anomaly_due_date
            FROM suppliers AS s
            LEFT JOIN (
                SELECT
                    supplier_id,
                    COUNT(*) AS anomaly_count,
                    SUM(CASE WHEN status = '待處理' THEN 1 ELSE 0 END)
                        AS open_anomaly_count,
                    0 AS overdue_anomaly_count
                FROM anomalies
                GROUP BY supplier_id
            ) AS a ON a.supplier_id = s.id
            LEFT JOIN (
                SELECT
                    {defect_key} AS supplier_key,
                    SUM(
                        CASE
                            WHEN event_date >= date('now', 'localtime', '-90 day')
                            THEN 1 ELSE 0
                        END
                    ) AS ncr_90d_count
                FROM defect_records AS d
                GROUP BY {defect_key}
            ) AS d ON d.supplier_key = {defect_join_key}
            LEFT JOIN (
                SELECT supplier_id, MAX(visit_date) AS latest_visit_date
                FROM visits
                GROUP BY supplier_id
            ) AS v ON v.supplier_id = s.id
            LEFT JOIN latest_open_anomaly AS la
                ON la.supplier_id = s.id AND la.row_number = 1
            WHERE s.is_active = 1
              AND {scope_filter}
            ORDER BY s.supplier_name COLLATE NOCASE
            """
        ).fetchall()
        rows: list[dict] = []
        for item in row:
            entry = dict(item)
            entry["overdue_anomaly_count"] = overdue_by_supplier.get(
                str(entry.get("id") or ""),
                0,
            )
            rows.append(entry)
        return rows


def list_supplier_anomalies(supplier_id: str) -> list[dict]:
    with _connection.get_connection() as conn:
        return [
            dict(row)
            for row in conn.execute(
                f"""
                SELECT anomaly_no, anomaly_date, category, problem_desc, status,
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
    grade = _grade_from_metrics(on_time_rate, ncr_count)
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


def list_supplier_contacts(supplier_id: str) -> list[dict]:
    sid = str(supplier_id or "").strip()
    if not sid:
        return []
    with _connection.get_connection() as conn:
        return repository.list_supplier_contacts(conn, sid)


def list_supplier_scorecards(start_date: str, end_date: str) -> dict[str, str]:
    with _connection.get_connection() as conn:
        supplier_ids = [
            str(row["id"])
            for row in conn.execute(
                "SELECT id FROM suppliers WHERE is_active = 1"
            ).fetchall()
        ]
    grades: dict[str, str] = {}
    for supplier_id in supplier_ids:
        scorecard = get_supplier_scorecard(supplier_id, start_date, end_date)
        grades[supplier_id] = str(scorecard.get("grade") or "—")
    return grades
