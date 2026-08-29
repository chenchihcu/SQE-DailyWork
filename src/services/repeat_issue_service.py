"""Repeat-issue similarity scoring and read-model helpers."""

from __future__ import annotations

from database import connection as _connection
from database import repository

__all__ = [
    "list_repeat_issues",
    "refresh_repeat_links_for_suppliers",
]


def list_repeat_issues(anomaly_id: str, *, limit: int = 20) -> list[dict]:
    with _connection.get_connection() as conn:
        repository.require_repeat_links_schema(conn)
        return repository.list_repeat_links_for_anomaly(
            conn,
            anomaly_id,
            limit=limit,
        )


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
