"""Product CRUD and stage change log."""

from __future__ import annotations

from database import connection as _connection
from database import repository


def list_products(*, include_inactive: bool = True) -> list[dict]:
    with _connection.get_connection() as conn:
        return repository.list_products(conn, include_inactive=include_inactive)


def create_product(payload: dict) -> str:
    with _connection.get_connection() as conn:
        return repository.create_product_record(
            conn,
            product_code=payload.get("product_code", ""),
            product_name=payload.get("product_name", ""),
            product_stage=payload.get("product_stage", "量產"),
            supplier_id=(payload.get("supplier_id") or "").strip(),
            secondary_supplier_id=(
                payload.get("secondary_supplier_id") or ""
            ).strip()
            or None,
        )


def update_product(product_id: str, payload: dict) -> None:
    with _connection.get_connection() as conn:
        repository.update_product_record(
            conn,
            product_id=product_id,
            product_code=payload.get("product_code", ""),
            product_name=payload.get("product_name", ""),
            product_stage=payload.get("product_stage", "量產"),
            supplier_id=(payload.get("supplier_id") or "").strip(),
            secondary_supplier_id=(
                payload.get("secondary_supplier_id") or ""
            ).strip()
            or None,
            stage_change_reason=(payload.get("stage_change_reason") or "").strip(),
        )


def set_product_active(product_id: str, is_active: bool) -> None:
    with _connection.get_connection() as conn:
        repository.set_product_active(conn, product_id, is_active)


def delete_product(product_id: str) -> None:
    with _connection.get_connection() as conn:
        repository.delete_product_record(conn, product_id)


def list_active_products_for_supplier(supplier_id: str | None) -> list[dict]:
    with _connection.get_connection() as conn:
        return repository.list_active_products_for_supplier(conn, supplier_id)


def has_active_suppliers() -> bool:
    from ._supplier_service import list_active_suppliers

    return bool(list_active_suppliers())


def list_product_stage_change_logs(
    *, product_id: str | None = None, limit: int = 200
) -> list[dict]:
    with _connection.get_connection() as conn:
        return repository.list_product_stage_change_logs(
            conn,
            product_id=(product_id or "").strip() or None,
            limit=limit,
        )
