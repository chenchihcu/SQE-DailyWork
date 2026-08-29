"""Service façade for manager summary and operational action queue."""

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


def list_operational_action_queue(
    *,
    responsible_person: str = "",
    overdue_only: bool = False,
) -> list[dict]:
    with _connection.get_connection() as conn:
        return manager_view_repository.list_operational_action_queue(
            conn,
            responsible_person=responsible_person,
            overdue_only=overdue_only,
        )


def get_manager_operational_metrics() -> dict[str, int]:
    with _connection.get_connection() as conn:
        return manager_view_repository.get_manager_operational_metrics(conn)
