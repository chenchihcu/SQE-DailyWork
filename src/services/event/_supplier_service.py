"""Supplier CRUD and contact management."""

from __future__ import annotations

from database import connection as _connection
from database import repository


def list_suppliers(*, include_inactive: bool = True) -> list[dict]:
    with _connection.get_connection() as conn:
        return repository.list_suppliers(conn, include_inactive=include_inactive)


def create_supplier(payload: dict) -> str:
    with _connection.get_connection() as conn:
        return repository.create_supplier_record(
            conn,
            supplier_name=payload.get("supplier_name", ""),
            contact_name=payload.get("contact_name", ""),
            department=payload.get("department", ""),
            phone=payload.get("phone", ""),
            contact_email=payload.get("contact_email", ""),
        )


def update_supplier(supplier_id: str, payload: dict) -> None:
    with _connection.get_connection() as conn:
        repository.update_supplier_record(
            conn,
            supplier_id=supplier_id,
            supplier_name=payload.get("supplier_name", ""),
            contact_name=payload.get("contact_name", ""),
            department=payload.get("department", ""),
            phone=payload.get("phone", ""),
            contact_email=payload.get("contact_email", ""),
        )


def set_supplier_active(supplier_id: str, is_active: bool) -> None:
    with _connection.get_connection() as conn:
        repository.set_supplier_active(conn, supplier_id, is_active)


def delete_supplier(supplier_id: str) -> None:
    with _connection.get_connection() as conn:
        repository.delete_supplier_record(conn, supplier_id)


def list_supplier_contacts(supplier_id: str) -> list[dict]:
    with _connection.get_connection() as conn:
        return repository.list_supplier_contacts(conn, supplier_id)


def add_supplier_contact(supplier_id: str, payload: dict) -> str:
    with _connection.get_connection() as conn:
        return repository.add_supplier_contact(
            conn,
            supplier_id=supplier_id,
            contact_name=payload.get("contact_name", ""),
            department=payload.get("department", ""),
            phone=payload.get("phone", ""),
            email=payload.get("email", ""),
            is_primary=bool(payload.get("is_primary", False)),
        )


def delete_supplier_contact(contact_id: str) -> None:
    with _connection.get_connection() as conn:
        repository.delete_supplier_contact(conn, contact_id)


def set_primary_contact(supplier_id: str, contact_id: str) -> None:
    with _connection.get_connection() as conn:
        repository.set_primary_contact(conn, supplier_id, contact_id)


def delete_suppliers(
    supplier_ids: list[str],
) -> repository.SupplierDeleteResult:
    with _connection.get_connection() as conn:
        return repository.delete_supplier_records(conn, supplier_ids)


def list_active_suppliers() -> list[dict]:
    with _connection.get_connection() as conn:
        return repository.list_active_suppliers(conn)
