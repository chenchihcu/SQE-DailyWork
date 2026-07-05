"""Shared private helpers for event service sub-modules."""

from __future__ import annotations

import logging
from datetime import date

logger = logging.getLogger(__name__)

from database import repository


def _month_now() -> str:
    return date.today().strftime("%Y%m")


def _require_supplier_record(
    conn,
    supplier_id: str,
    *,
    require_active: bool,
) -> dict:
    supplier_key = (supplier_id or "").strip()
    if not supplier_key:
        raise ValueError("Supplier is required")
    supplier = repository.get_supplier(conn, supplier_key)
    if supplier is None:
        raise ValueError("Supplier not found")
    if require_active and not bool(supplier.get("is_active")):
        raise ValueError("Supplier is inactive")
    return supplier


def _product_matches_supplier_scope(product: dict, supplier_id: str) -> bool:
    primary = str(product.get("supplier_id") or "").strip()
    secondary = str(product.get("secondary_supplier_id") or "").strip()
    if primary == supplier_id or secondary == supplier_id:
        return True
    if not primary and not secondary:
        return True
    return False


def _resolve_product_name(
    conn,
    *,
    supplier_id: str,
    product_id: str | None,
    require_active: bool = False,
) -> str:
    product_key = (product_id or "").strip()
    if not product_key:
        return ""
    product = repository.get_product(conn, product_key)
    if product is None:
        raise ValueError("Product not found")
    if require_active and not bool(product.get("is_active")):
        raise ValueError("Product is inactive")
    if not _product_matches_supplier_scope(product, supplier_id):
        raise ValueError("Product does not belong to selected supplier")
    return str(product.get("product_name") or "").strip()


def _require_product_id(payload: dict) -> str:
    product_id = (payload.get("product_id") or "").strip()
    if not product_id:
        raise ValueError("Product is required")
    return product_id
