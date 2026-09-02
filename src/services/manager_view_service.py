"""Service façade for manager summary view."""

from __future__ import annotations

from database import connection as _connection
from database import manager_view_repository


def list_manager_summary_rows(
    *,
    status: str = "待處理",
    overdue_only: bool = False,
    responsible_person: str = "",
) -> list[dict]:
    with _connection.get_connection() as conn:
        return manager_view_repository.list_manager_summary_rows(
            conn,
            status=status,
            overdue_only=overdue_only,
            responsible_person=responsible_person,
        )
