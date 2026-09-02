"""Shared supplier master-data persistence."""

from __future__ import annotations

import logging
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from database.repo_helpers import (
    SUPPLIER_CONSOLIDATION_META_KEY,
    SupplierDeleteFailure,
    SupplierDeleteResult,
    _SUPPLIER_SUFFIX_PATTERN,
    _as_int,
    _gen_id,
    _now_iso,
    _normalized_lookup_text,
    get_migration_meta,
    upsert_migration_meta,
)
from database.repository_schema_helpers import has_column as _has_column
from database.supplier_category import (
    SUPPLIER_CATEGORY_RAW_MATERIAL,
    normalize_supplier_category,
)
from services.path_name_helpers import contains_invalid_path_char

logger = logging.getLogger(__name__)

def canonicalize_supplier_name(supplier_name: str) -> str:
    raw = str(supplier_name or "").strip()
    if not raw:
        return ""
    text = raw
    while True:
        trimmed = _SUPPLIER_SUFFIX_PATTERN.sub("", text).strip()
        if not trimmed:
            return text
        if trimmed == text:
            return trimmed
        text = trimmed

def _normalize_supplier_name_for_storage(supplier_name: str) -> str:
    raw = str(supplier_name or "").strip()
    if not raw:
        return ""
    canonical = canonicalize_supplier_name(raw)
    return canonical or raw

def list_suppliers(
    conn: sqlite3.Connection,
    *,
    include_inactive: bool = True,
    category: str | None = None,
) -> list[dict]:
    sql = """
        SELECT id, supplier_name, contact_name, department, phone, contact_email,
               category, is_active, created_at, updated_at
        FROM suppliers
    """
    conditions: list[str] = []
    params: list[Any] = []
    if not include_inactive:
        conditions.append("is_active = 1")
    if category:
        conditions.append("category = ?")
        params.append(normalize_supplier_category(category))
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY supplier_name COLLATE NOCASE, created_at"
    rows = conn.execute(sql, params).fetchall()
    items: list[dict] = []
    for row in rows:
        item = dict(row)
        item["is_active"] = bool(_as_int(item.get("is_active"), 0))
        items.append(item)
    return items

def get_supplier(conn: sqlite3.Connection, supplier_id: str) -> dict | None:
    supplier_key = (supplier_id or "").strip()
    if not supplier_key:
        return None
    row = conn.execute(
        """
        SELECT id, supplier_name, contact_name, department, phone, contact_email,
               category, is_active, created_at, updated_at
        FROM suppliers
        WHERE id = ?
        LIMIT 1
        """,
        (supplier_key,),
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["is_active"] = bool(_as_int(result.get("is_active"), 0))
    return result

def create_supplier_record(
    conn: sqlite3.Connection,
    *,
    supplier_name: str,
    contact_name: str = "",
    department: str = "",
    phone: str = "",
    contact_email: str = "",
    category: str = SUPPLIER_CATEGORY_RAW_MATERIAL,
) -> str:
    normalized_name = _normalize_supplier_name_for_storage(supplier_name)
    if not normalized_name:
        raise ValueError("Supplier name is required")
    normalized_category = normalize_supplier_category(category)
    supplier_id = _gen_id()
    try:
        conn.execute(
            """
            INSERT INTO suppliers(
                id, supplier_name, contact_name, department, phone, contact_email,
                category, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                supplier_id,
                normalized_name,
                (contact_name or "").strip(),
                (department or "").strip(),
                (phone or "").strip(),
                (contact_email or "").strip(),
                normalized_category,
                _now_iso(),
                _now_iso(),
            ),
        )
        # Automatically create the primary contact record
        conn.execute(
            """
            INSERT INTO supplier_contacts(
                id, supplier_id, contact_name, department, phone, email, is_primary, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                _gen_id(),
                supplier_id,
                (contact_name or "").strip(),
                (department or "").strip(),
                (phone or "").strip(),
                (contact_email or "").strip(),
                _now_iso(),
                _now_iso(),
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError("Supplier name already exists") from exc
    conn.commit()
    return supplier_id

def update_supplier_record(
    conn: sqlite3.Connection,
    *,
    supplier_id: str,
    supplier_name: str,
    contact_name: str = "",
    department: str = "",
    phone: str = "",
    contact_email: str = "",
    category: str | None = None,
) -> None:
    supplier_key = (supplier_id or "").strip()
    if not supplier_key:
        raise ValueError("Supplier id is required")
    normalized_name = _normalize_supplier_name_for_storage(supplier_name)
    if not normalized_name:
        raise ValueError("Supplier name is required")
    normalized_category: str | None = None
    if category is not None:
        normalized_category = normalize_supplier_category(category)
    try:
        if normalized_category is not None:
            cur = conn.execute(
                """
                UPDATE suppliers
                SET supplier_name = ?, contact_name = ?, department = ?, phone = ?,
                    contact_email = ?, category = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    normalized_name,
                    (contact_name or "").strip(),
                    (department or "").strip(),
                    (phone or "").strip(),
                    (contact_email or "").strip(),
                    normalized_category,
                    _now_iso(),
                    supplier_key,
                ),
            )
        else:
            cur = conn.execute(
                """
                UPDATE suppliers
                SET supplier_name = ?, contact_name = ?, department = ?, phone = ?,
                    contact_email = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    normalized_name,
                    (contact_name or "").strip(),
                    (department or "").strip(),
                    (phone or "").strip(),
                    (contact_email or "").strip(),
                    _now_iso(),
                    supplier_key,
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise ValueError("Supplier name already exists") from exc
    if cur.rowcount == 0:
        raise ValueError("Supplier not found")
    conn.commit()

def set_supplier_active(
    conn: sqlite3.Connection,
    supplier_id: str,
    is_active: bool,
) -> None:
    supplier_key = (supplier_id or "").strip()
    if not supplier_key:
        raise ValueError("Supplier id is required")
    cur = conn.execute(
        """
        UPDATE suppliers
        SET is_active = ?, updated_at = ?
        WHERE id = ?
        """,
        (1 if is_active else 0, _now_iso(), supplier_key),
    )
    if cur.rowcount == 0:
        raise ValueError("Supplier not found")
    conn.commit()

def delete_supplier_record(
    conn: sqlite3.Connection,
    supplier_id: str,
    *,
    commit: bool = True,
) -> None:
    supplier_key = (supplier_id or "").strip()
    if not supplier_key:
        raise ValueError("Supplier id is required")
    if get_supplier(conn, supplier_key) is None:
        raise ValueError("Supplier not found")

    referenced_by: list[str] = []
    products_where = (
        "supplier_id = ? OR secondary_supplier_id = ?"
        if _has_column(conn, "products", "secondary_supplier_id")
        else "supplier_id = ?"
    )
    products_params: tuple[str, ...] = (
        (supplier_key, supplier_key)
        if _has_column(conn, "products", "secondary_supplier_id")
        else (supplier_key,)
    )
    for table_name in ("products", "anomalies", "visits"):
        where_clause = "supplier_id = ?"
        params: tuple[str, ...] = (supplier_key,)
        if table_name == "products":
            where_clause = products_where
            params = products_params
        row = conn.execute(
            f"SELECT COUNT(*) AS c FROM {table_name} WHERE {where_clause}",
            params,
        ).fetchone()
        if row is not None and _as_int(row["c"], 0) > 0:
            referenced_by.append(table_name)
    if referenced_by:
        raise ValueError(f"Supplier is referenced by {', '.join(referenced_by)}")

    conn.execute("DELETE FROM supplier_contacts WHERE supplier_id = ?", (supplier_key,))
    conn.execute("DELETE FROM suppliers WHERE id = ?", (supplier_key,))
    if commit:
        conn.commit()

def list_supplier_contacts(conn: sqlite3.Connection, supplier_id: str) -> list[dict]:
    supplier_key = (supplier_id or "").strip()
    if not supplier_key:
        return []
    rows = conn.execute(
        """
        SELECT id, supplier_id, contact_name, department, phone, email, is_primary, created_at, updated_at
        FROM supplier_contacts
        WHERE supplier_id = ?
        ORDER BY is_primary DESC, contact_name COLLATE NOCASE
        """,
        (supplier_key,),
    ).fetchall()
    items: list[dict] = []
    for row in rows:
        item = dict(row)
        item["is_primary"] = bool(_as_int(item.get("is_primary"), 0))
        items.append(item)
    return items

def add_supplier_contact(
    conn: sqlite3.Connection,
    *,
    supplier_id: str,
    contact_name: str,
    department: str = "",
    phone: str = "",
    email: str = "",
    is_primary: bool = False,
) -> str:
    supplier_key = (supplier_id or "").strip()
    if not supplier_key:
        raise ValueError("Supplier id is required")
    contact_id = _gen_id()
    conn.execute(
        """
        INSERT INTO supplier_contacts(
            id, supplier_id, contact_name, department, phone, email, is_primary, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            contact_id,
            supplier_key,
            (contact_name or "").strip(),
            (department or "").strip(),
            (phone or "").strip(),
            (email or "").strip(),
            1 if is_primary else 0,
            _now_iso(),
            _now_iso(),
        ),
    )
    if is_primary:
        # Update other contacts to not be primary
        conn.execute(
            "UPDATE supplier_contacts SET is_primary = 0 WHERE supplier_id = ? AND id <> ?",
            (supplier_key, contact_id),
        )
        # Also update the main suppliers table with this primary contact info
        conn.execute(
            """
            UPDATE suppliers
            SET contact_name = ?, department = ?, phone = ?, contact_email = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                (contact_name or "").strip(),
                (department or "").strip(),
                (phone or "").strip(),
                (email or "").strip(),
                _now_iso(),
                supplier_key,
            ),
        )
    conn.commit()
    return contact_id

def delete_supplier_contact(conn: sqlite3.Connection, contact_id: str) -> None:
    contact_key = (contact_id or "").strip()
    if not contact_key:
        raise ValueError("Contact id is required")
    conn.execute("DELETE FROM supplier_contacts WHERE id = ?", (contact_key,))
    conn.commit()

def set_primary_contact(
    conn: sqlite3.Connection, supplier_id: str, contact_id: str
) -> None:
    supplier_key = (supplier_id or "").strip()
    contact_key = (contact_id or "").strip()
    if not supplier_key or not contact_key:
        raise ValueError("Supplier id and contact id are required")

    contact = conn.execute(
        "SELECT * FROM supplier_contacts WHERE id = ?", (contact_key,)
    ).fetchone()
    if not contact:
        raise ValueError("Contact not found")

    conn.execute(
        "UPDATE supplier_contacts SET is_primary = 0 WHERE supplier_id = ?",
        (supplier_key,),
    )
    conn.execute(
        "UPDATE supplier_contacts SET is_primary = 1 WHERE id = ?", (contact_key,)
    )

    # Sync to main suppliers table
    conn.execute(
        """
        UPDATE suppliers
        SET contact_name = ?, department = ?, phone = ?, contact_email = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            contact["contact_name"],
            contact["department"],
            contact["phone"],
            contact["email"],
            _now_iso(),
            supplier_key,
        ),
    )
    conn.commit()

def delete_supplier_records(
    conn: sqlite3.Connection,
    supplier_ids: list[str],
) -> SupplierDeleteResult:
    deleted_ids: list[str] = []
    failed: list[SupplierDeleteFailure] = []
    seen: set[str] = set()

    for supplier_id in supplier_ids or []:
        supplier_key = (supplier_id or "").strip()
        if supplier_key in seen:
            continue
        seen.add(supplier_key)
        try:
            delete_supplier_record(conn, supplier_key, commit=False)
            deleted_ids.append(supplier_key)
        except (ValueError, sqlite3.IntegrityError) as exc:
            failed.append({"id": supplier_key, "reason": str(exc)})

    conn.commit()
    return {"deleted": deleted_ids, "failed": failed}

def _supplier_recency_sort_key(item: dict) -> tuple[str, str, str]:
    return (
        str(item.get("updated_at") or ""),
        str(item.get("created_at") or ""),
        str(item.get("id") or ""),
    )

def _pick_latest_non_empty_supplier_field(rows: list[dict], field: str) -> str:
    for item in sorted(rows, key=_supplier_recency_sort_key, reverse=True):
        value = str(item.get(field) or "").strip()
        if value:
            return value
    return ""

def _pick_supplier_keeper(canonical_name: str, rows: list[dict]) -> dict:
    return sorted(
        rows,
        key=lambda item: (
            0
            if str(item.get("supplier_name") or "").strip() == canonical_name
            else 1,
            0 if bool(item.get("is_active")) else 1,
            str(item.get("created_at") or ""),
            str(item.get("id") or ""),
        ),
    )[0]

def _merge_supplier_products(
    conn: sqlite3.Connection,
    *,
    from_supplier_id: str,
    to_supplier_id: str,
    now_iso: str,
) -> dict[str, int]:
    from database.product_repository import _pick_latest_product_name

    stats = {
        "products_supplier_relinked": 0,
        "products_secondary_supplier_relinked": 0,
        "product_conflicts_resolved": 0,
        "products_updated": 0,
        "products_deleted": 0,
        "anomalies_product_relinked": 0,
        "visits_product_relinked": 0,
        "visit_sections_product_relinked": 0,
    }
    has_secondary_supplier_id = _has_column(conn, "products", "secondary_supplier_id")
    source_rows = conn.execute(
        (
            """
            SELECT id, product_code, product_name, secondary_supplier_id, is_active, created_at, updated_at
            FROM products
            WHERE supplier_id = ?
            ORDER BY created_at ASC, id ASC
            """
            if has_secondary_supplier_id
            else """
            SELECT id, product_code, product_name, is_active, created_at, updated_at
            FROM products
            WHERE supplier_id = ?
            ORDER BY created_at ASC, id ASC
            """
        ),
        (from_supplier_id,),
    ).fetchall()
    for row in source_rows:
        source_item = dict(row)
        source_product_id = str(source_item["id"])
        source_product_code = str(source_item["product_code"] or "").strip()
        target = conn.execute(
            (
                """
                SELECT id, product_name, secondary_supplier_id, is_active, created_at, updated_at
                FROM products
                WHERE supplier_id = ? AND product_code = ?
                LIMIT 1
                """
                if has_secondary_supplier_id
                else """
                SELECT id, product_name, is_active, created_at, updated_at
                FROM products
                WHERE supplier_id = ? AND product_code = ?
                LIMIT 1
                """
            ),
            (to_supplier_id, source_product_code),
        ).fetchone()
        if target is None:
            if has_secondary_supplier_id:
                merged_secondary_supplier_id = str(
                    source_item.get("secondary_supplier_id") or ""
                ).strip()
                if merged_secondary_supplier_id == to_supplier_id:
                    merged_secondary_supplier_id = ""
                cur = conn.execute(
                    """
                    UPDATE products
                    SET supplier_id = ?,
                        secondary_supplier_id = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        to_supplier_id,
                        merged_secondary_supplier_id or None,
                        now_iso,
                        source_product_id,
                    ),
                )
            else:
                cur = conn.execute(
                    """
                    UPDATE products
                    SET supplier_id = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (to_supplier_id, now_iso, source_product_id),
                )
            stats["products_supplier_relinked"] += int(cur.rowcount)
            continue

        target_item = dict(target)
        target_product_id = str(target_item["id"])
        if target_product_id == source_product_id:
            continue

        merged_product_name = _pick_latest_product_name([target_item, source_item])
        target_product_name = str(target_item.get("product_name") or "").strip()
        target_is_active = bool(_as_int(target_item.get("is_active"), 0))
        source_is_active = bool(_as_int(source_item.get("is_active"), 0))
        merged_is_active = target_is_active or source_is_active
        final_product_name = merged_product_name or target_product_name
        final_secondary_supplier_id: str | None = None
        if has_secondary_supplier_id:
            target_secondary_supplier_id = str(
                target_item.get("secondary_supplier_id") or ""
            ).strip()
            source_secondary_supplier_id = str(
                source_item.get("secondary_supplier_id") or ""
            ).strip()
            merged_secondary_supplier_id = (
                target_secondary_supplier_id or source_secondary_supplier_id
            )
            if merged_secondary_supplier_id == to_supplier_id:
                merged_secondary_supplier_id = ""
            final_secondary_supplier_id = merged_secondary_supplier_id or None

        if has_secondary_supplier_id:
            current_secondary_supplier_id = str(
                target_item.get("secondary_supplier_id") or ""
            ).strip() or None
            if (
                final_product_name != target_product_name
                or merged_is_active != target_is_active
                or final_secondary_supplier_id != current_secondary_supplier_id
            ):
                conn.execute(
                    """
                    UPDATE products
                    SET product_name = ?,
                        secondary_supplier_id = ?,
                        is_active = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        final_product_name,
                        final_secondary_supplier_id,
                        1 if merged_is_active else 0,
                        now_iso,
                        target_product_id,
                    ),
                )
                stats["products_updated"] += 1
        elif (
            final_product_name != target_product_name
            or merged_is_active != target_is_active
        ):
            conn.execute(
                """
                UPDATE products
                SET product_name = ?, is_active = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    final_product_name,
                    1 if merged_is_active else 0,
                    now_iso,
                    target_product_id,
                ),
            )
            stats["products_updated"] += 1

        anomaly_cur = conn.execute(
            """
            UPDATE anomalies
            SET product_id = ?, product_name = ?, updated_at = ?
            WHERE product_id = ?
            """,
            (
                target_product_id,
                final_product_name,
                now_iso,
                source_product_id,
            ),
        )
        visit_cur = conn.execute(
            """
            UPDATE visits
            SET product_id = ?, product_name = ?, updated_at = ?
            WHERE product_id = ?
            """,
            (
                target_product_id,
                final_product_name,
                now_iso,
                source_product_id,
            ),
        )
        visit_section_cur = conn.execute(
            """
            UPDATE visit_product_sections
            SET product_id = ?, product_name = ?, updated_at = ?
            WHERE product_id = ?
            """,
            (
                target_product_id,
                final_product_name,
                now_iso,
                source_product_id,
            ),
        )
        delete_cur = conn.execute(
            "DELETE FROM products WHERE id = ?",
            (source_product_id,),
        )
        stats["product_conflicts_resolved"] += 1
        stats["anomalies_product_relinked"] += int(anomaly_cur.rowcount)
        stats["visits_product_relinked"] += int(visit_cur.rowcount)
        stats["visit_sections_product_relinked"] += int(visit_section_cur.rowcount)
        stats["products_deleted"] += int(delete_cur.rowcount)
    return stats

def _consolidate_suppliers_inner(conn: sqlite3.Connection) -> dict[str, Any]:
    suppliers_raw = conn.execute(
        """
        SELECT id, supplier_name, contact_name, phone, is_active, created_at, updated_at
        FROM suppliers
        ORDER BY created_at ASC, id ASC
        """
    ).fetchall()
    suppliers: list[dict[str, Any]] = []
    for row in suppliers_raw:
        item = dict(row)
        item["is_active"] = bool(_as_int(item.get("is_active"), 0))
        suppliers.append(item)

    report: dict[str, Any] = {
        "suppliers_before": len(suppliers),
        "suppliers_after": len(suppliers),
        "groups_total": 0,
        "groups_merged": 0,
        "groups_renamed": 0,
        "suppliers_deleted": 0,
        "suppliers_updated": 0,
        "anomalies_supplier_relinked": 0,
        "visits_supplier_relinked": 0,
        "products_supplier_relinked": 0,
        "products_secondary_supplier_relinked": 0,
        "product_conflicts_resolved": 0,
        "products_updated": 0,
        "products_deleted": 0,
        "anomalies_product_relinked": 0,
        "visits_product_relinked": 0,
        "groups": [],
    }
    if not suppliers:
        return report

    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in suppliers:
        current_name = str(item.get("supplier_name") or "").strip()
        canonical_name = canonicalize_supplier_name(current_name) or current_name
        grouped.setdefault(canonical_name, []).append(item)

    report["groups_total"] = len(grouped)
    now_iso = _now_iso()
    for canonical_name in sorted(grouped.keys(), key=str.lower):
        group_rows = grouped[canonical_name]
        keeper = _pick_supplier_keeper(canonical_name, group_rows)
        keeper_id = str(keeper["id"])
        merged_rows = [item for item in group_rows if str(item["id"]) != keeper_id]
        merged_supplier_ids = [str(item["id"]) for item in merged_rows]
        if merged_rows:
            report["groups_merged"] += 1

        merged_is_active = any(bool(item.get("is_active")) for item in group_rows)
        merged_contact_name = _pick_latest_non_empty_supplier_field(
            group_rows, "contact_name"
        )
        merged_phone = _pick_latest_non_empty_supplier_field(group_rows, "phone")

        for merged_item in merged_rows:
            merged_supplier_id = str(merged_item["id"])
            anomaly_cur = conn.execute(
                """
                UPDATE anomalies
                SET supplier_id = ?, updated_at = ?
                WHERE supplier_id = ?
                """,
                (keeper_id, now_iso, merged_supplier_id),
            )
            visit_cur = conn.execute(
                """
                UPDATE visits
                SET supplier_id = ?, updated_at = ?
                WHERE supplier_id = ?
                """,
                (keeper_id, now_iso, merged_supplier_id),
            )
            product_stats = _merge_supplier_products(
                conn,
                from_supplier_id=merged_supplier_id,
                to_supplier_id=keeper_id,
                now_iso=now_iso,
            )
            secondary_relinked = 0
            if _has_column(conn, "products", "secondary_supplier_id"):
                secondary_relinked_cur = conn.execute(
                    """
                    UPDATE products
                    SET secondary_supplier_id = ?, updated_at = ?
                    WHERE secondary_supplier_id = ?
                    """,
                    (keeper_id, now_iso, merged_supplier_id),
                )
                secondary_relinked += int(secondary_relinked_cur.rowcount)
                conn.execute(
                    """
                    UPDATE products
                    SET secondary_supplier_id = NULL, updated_at = ?
                    WHERE supplier_id = ? AND secondary_supplier_id = ?
                    """,
                    (now_iso, keeper_id, keeper_id),
                )
            delete_cur = conn.execute(
                "DELETE FROM suppliers WHERE id = ?",
                (merged_supplier_id,),
            )
            report["anomalies_supplier_relinked"] += int(anomaly_cur.rowcount)
            report["visits_supplier_relinked"] += int(visit_cur.rowcount)
            report["products_supplier_relinked"] += int(
                product_stats["products_supplier_relinked"]
            )
            report["products_secondary_supplier_relinked"] += int(secondary_relinked)
            report["product_conflicts_resolved"] += int(
                product_stats["product_conflicts_resolved"]
            )
            report["products_updated"] += int(product_stats["products_updated"])
            report["products_deleted"] += int(product_stats["products_deleted"])
            report["anomalies_product_relinked"] += int(
                product_stats["anomalies_product_relinked"]
            )
            report["visits_product_relinked"] += int(
                product_stats["visits_product_relinked"]
            )
            report["suppliers_deleted"] += int(delete_cur.rowcount)

        keeper_row = conn.execute(
            """
            SELECT id, supplier_name, contact_name, phone, is_active
            FROM suppliers
            WHERE id = ?
            LIMIT 1
            """,
            (keeper_id,),
        ).fetchone()
        if keeper_row is None:
            continue

        keeper_item = dict(keeper_row)
        current_name = str(keeper_item.get("supplier_name") or "").strip()
        current_contact = str(keeper_item.get("contact_name") or "").strip()
        current_phone = str(keeper_item.get("phone") or "").strip()
        current_is_active = bool(_as_int(keeper_item.get("is_active"), 0))
        final_name = canonical_name or current_name
        final_contact = merged_contact_name
        final_phone = merged_phone
        final_is_active = merged_is_active
        renamed = final_name != current_name

        if (
            renamed
            or final_contact != current_contact
            or final_phone != current_phone
            or final_is_active != current_is_active
        ):
            conn.execute(
                """
                UPDATE suppliers
                SET supplier_name = ?,
                    contact_name = ?,
                    phone = ?,
                    is_active = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    final_name,
                    final_contact,
                    final_phone,
                    1 if final_is_active else 0,
                    now_iso,
                    keeper_id,
                ),
            )
            report["suppliers_updated"] += 1
            if renamed:
                report["groups_renamed"] += 1

        if merged_rows or renamed:
            report["groups"].append(
                {
                    "canonical_name": canonical_name,
                    "keeper_supplier_id": keeper_id,
                    "merged_supplier_ids": merged_supplier_ids,
                    "renamed": renamed,
                }
            )

    report["suppliers_after"] = int(
        conn.execute("SELECT COUNT(*) AS c FROM suppliers").fetchone()["c"]
    )
    return report

def consolidate_suppliers(
    conn: sqlite3.Connection,
    *,
    apply: bool = True,
) -> dict[str, Any]:
    savepoint_name = f"supplier_consolidation_{uuid.uuid4().hex}"
    conn.execute(f"SAVEPOINT {savepoint_name}")
    try:
        report = _consolidate_suppliers_inner(conn)
        report["applied"] = bool(apply)
        report["changed"] = bool(
            report.get("groups_merged")
            or report.get("groups_renamed")
            or report.get("product_conflicts_resolved")
        )
        if apply:
            conn.execute(f"RELEASE SAVEPOINT {savepoint_name}")
            conn.commit()
        else:
            conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
            conn.execute(f"RELEASE SAVEPOINT {savepoint_name}")
        return report
    except Exception:
        logger.exception("consolidate_suppliers failed")
        try:
            conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
            conn.execute(f"RELEASE SAVEPOINT {savepoint_name}")
        except sqlite3.Error:
            logger.warning("supplier consolidation rollback cleanup failed", exc_info=True)
        raise

def ensure_supplier(
    conn: sqlite3.Connection,
    supplier_name: str,
    *,
    supplier_id: str | None = None,
    contact_name: str = "",
    department: str = "",
    phone: str = "",
    contact_email: str = "",
) -> str:
    normalized_name = _normalize_supplier_name_for_storage(supplier_name)
    if not normalized_name:
        normalized_name = "Unknown Supplier"

    row = conn.execute(
        "SELECT id FROM suppliers WHERE supplier_name = ?",
        (normalized_name,),
    ).fetchone()
    if row:
        return str(row["id"])

    generated_id = supplier_id or _gen_id()
    conn.execute(
        """
        INSERT INTO suppliers(
            id, supplier_name, contact_name, department, phone, contact_email,
            is_active, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
        """,
        (
            generated_id,
            normalized_name,
            (contact_name or "").strip(),
            (department or "").strip(),
            (phone or "").strip(),
            (contact_email or "").strip(),
            _now_iso(),
            _now_iso(),
        ),
    )
    return generated_id
