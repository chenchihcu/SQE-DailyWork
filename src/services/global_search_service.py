"""Read-only cross-domain search for the main-window command surface."""

from __future__ import annotations

from database import connection as _connection
from database import repository


def search_global(keyword: str, *, limit: int = 30) -> list[dict]:
    with _connection.get_connection() as conn:
        return repository.search_global(conn, keyword, limit=limit)
