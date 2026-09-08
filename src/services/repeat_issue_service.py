"""Repeat-issue similarity scoring and read-model helpers."""

from __future__ import annotations

from typing import Any

from database import connection as _connection
from database import repository

DISPOSITION_PENDING = "待確認"
DISPOSITION_CONFIRMED = "已確認重複"
DISPOSITION_DISMISSED = "已排除"

__all__ = [
    "DISPOSITION_PENDING",
    "DISPOSITION_CONFIRMED",
    "DISPOSITION_DISMISSED",
    "get_repeat_link_disposition",
    "set_repeat_link_disposition",
    "list_repeat_issues",
    "query_all_repeat_issues",
    "refresh_repeat_links_for_suppliers",
]


def _disposition_setting_key(anomaly_id: str, peer_id: str) -> str:
    a, b = sorted([str(anomaly_id).strip(), str(peer_id).strip()])
    return f"repeat_disposition:{a}:{b}"


def get_repeat_link_disposition(anomaly_id: str, peer_id: str) -> str:
    aid = str(anomaly_id or "").strip()
    pid = str(peer_id or "").strip()
    if not aid or not pid:
        return DISPOSITION_PENDING
    key = _disposition_setting_key(aid, pid)
    try:
        with _connection.get_connection() as conn:
            row = conn.execute(
                "SELECT setting_value FROM ui_settings WHERE setting_key = ?",
                (key,),
            ).fetchone()
            if row and row["setting_value"]:
                return str(row["setting_value"])
    except Exception:
        pass
    return DISPOSITION_PENDING


def set_repeat_link_disposition(
    anomaly_id: str,
    peer_id: str,
    disposition: str,
) -> None:
    aid = str(anomaly_id or "").strip()
    pid = str(peer_id or "").strip()
    if not aid or not pid:
        return
    key = _disposition_setting_key(aid, pid)
    val = str(disposition or "").strip() or DISPOSITION_PENDING
    with _connection.get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ui_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO ui_settings (setting_key, setting_value)
            VALUES (?, ?)
            ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value
            """,
            (key, val),
        )
        conn.commit()


def list_repeat_issues(anomaly_id: str, *, limit: int = 20) -> list[dict]:
    with _connection.get_connection() as conn:
        repository.require_repeat_links_schema(conn)
        rows = repository.list_repeat_links_for_anomaly(
            conn,
            anomaly_id,
            limit=limit,
        )
    for row in rows:
        peer_id = row.get("peer_anomaly_id")
        if "disposition" not in row or not row["disposition"]:
            row["disposition"] = get_repeat_link_disposition(anomaly_id, str(peer_id or ""))
    return rows


def query_all_repeat_issues(
    supplier_id: str = "",
    min_score: int = 0,
    disposition: str = "",
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Query potential repeat issue pairs across suppliers or for a specific supplier."""
    with _connection.get_connection() as conn:
        repository.require_repeat_links_schema(conn)
        query = """
            SELECT
                l.anomaly_id,
                l.peer_anomaly_id,
                l.similarity_score,
                l.match_reasons,
                a1.anomaly_no AS source_anomaly_no,
                a1.anomaly_date AS source_anomaly_date,
                a1.category AS source_category,
                a1.status AS source_status,
                a1.problem_desc AS source_problem_desc,
                a1.product_name AS source_product_name,
                a1.supplier_id,
                COALESCE(s.name, '') AS supplier_name,
                a2.anomaly_no,
                a2.anomaly_date,
                a2.category,
                a2.status,
                a2.problem_desc,
                a2.product_name
            FROM anomaly_repeat_links AS l
            JOIN anomalies AS a1 ON a1.id = l.anomaly_id
            JOIN anomalies AS a2 ON a2.id = l.peer_anomaly_id
            LEFT JOIN suppliers AS s ON s.id = a1.supplier_id
            WHERE 1=1
        """
        params: list[Any] = []
        if supplier_id:
            query += " AND a1.supplier_id = ?"
            params.append(supplier_id)
        if min_score > 0:
            query += " AND l.similarity_score >= ?"
            params.append(min_score)

        query += " ORDER BY l.similarity_score DESC, a1.anomaly_date DESC LIMIT ?"
        params.append(max(1, int(limit)))

        raw_rows = [dict(r) for r in conn.execute(query, params).fetchall()]

    results: list[dict[str, Any]] = []
    for r in raw_rows:
        disp = get_repeat_link_disposition(r["anomaly_id"], r["peer_anomaly_id"])
        if disposition and disp != disposition:
            continue
        r["disposition"] = disp
        results.append(r)
    return results


def refresh_repeat_links_for_suppliers(
    conn,
    *supplier_ids: str,
) -> None:
    repository.require_repeat_links_schema(conn)
    seen: set[str] = set()
    for supplier_id in supplier_ids:
        sid = str(supplier_id or "").strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        repository.refresh_supplier_repeat_links(conn, sid)
