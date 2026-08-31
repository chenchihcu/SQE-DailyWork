"""Service façade for supplier-event operational queue pages."""

from __future__ import annotations

from database import connection as _connection
from database import manager_view_repository


def list_overdue_case_queue_rows() -> list[dict]:
    with _connection.get_connection() as conn:
        return manager_view_repository.list_overdue_case_queue_rows(conn)


def list_root_cause_pending_case_queue_rows() -> list[dict]:
    with _connection.get_connection() as conn:
        return manager_view_repository.list_root_cause_pending_case_queue_rows(conn)


def list_open_action_queue_rows() -> list[dict]:
    with _connection.get_connection() as conn:
        return manager_view_repository.list_operational_action_queue(conn)


def get_supplier_event_queue_counts() -> dict[str, int]:
    with _connection.get_connection() as conn:
        return manager_view_repository.get_supplier_event_queue_counts(conn)
