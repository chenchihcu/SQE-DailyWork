"""Shared constants, TypedDicts, and helper functions for the repository layer."""

from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import date, datetime, timezone
from typing import Any, TypedDict

from database.product_stage import (
    PRODUCT_STAGE_MASS_PRODUCTION,
    PRODUCT_STAGE_OPTIONS,
)

# ── Metadata / migration keys ──────────────────────────────────────────────
SUPPLIER_CONSOLIDATION_META_KEY = "supplier_consolidation_v1"
PRODUCT_STAGE_SYNC_META_KEY = "product_stage_sync_v1"
DEFAULT_STAGE_CHANGED_BY = "local_user"
STAGE_SYNC_SCOPE_ALL_HISTORY = "all_history_and_future"

# ── Regex helpers ──────────────────────────────────────────────────────────
_SUPPLIER_SUFFIX_PATTERN = re.compile(r"(?:-\d+|-[0-9a-fA-F]{8}(?:-受保護)?)$")
_STRICT_ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# ── Tech-transfer constants ────────────────────────────────────────────────
VISIT_TECH_TRANSFER_ITEM_COLUMNS = (
    "tech_transfer_doc",
    "carrier_requirement",
    "dispensing_process",
    "functional_test",
    "packaging_requirement",
)
TECH_TRANSFER_STATE_YES = "yes"
TECH_TRANSFER_STATE_NO = "no"
TECH_TRANSFER_STATE_NA = "na"
TECH_TRANSFER_STATE_VALUES: tuple[str, ...] = (
    TECH_TRANSFER_STATE_YES,
    TECH_TRANSFER_STATE_NO,
    TECH_TRANSFER_STATE_NA,
)
VISIT_TECH_TRANSFER_STATE_COLUMNS: tuple[str, ...] = tuple(
    f"{col}_state" for col in VISIT_TECH_TRANSFER_ITEM_COLUMNS
)

# ── Event / defect constants ───────────────────────────────────────────────
EVENT_SCOPE_VISIT_ONLY = "VISIT_ONLY"
EVENT_SCOPE_VISIT_WITH_ANOMALY = "VISIT_WITH_ANOMALY"
EVENT_SCOPE_ANOMALY_ONLY = "ANOMALY_ONLY"
EVENT_SCOPE_CLOSED_ONLY = "CLOSED_ONLY"
EVENT_SCOPE_VALUES = {
    EVENT_SCOPE_VISIT_ONLY,
    EVENT_SCOPE_VISIT_WITH_ANOMALY,
    EVENT_SCOPE_ANOMALY_ONLY,
    EVENT_SCOPE_CLOSED_ONLY,
}
DEFECT_NOTE_IMPROVED = "已記錄改善"
DEFECT_NOTE_PENDING_IMPROVEMENT = "待補改善"


# ── TypedDict result types ─────────────────────────────────────────────────
class SupplierDeleteFailure(TypedDict):
    id: str
    reason: str


class SupplierDeleteResult(TypedDict):
    deleted: list[str]
    failed: list[SupplierDeleteFailure]


class ProductStageSyncReport(TypedDict):
    applied: bool
    product_link_updates: int
    anomalies_stage_updates: int
    visits_stage_updates: int
    anomalies_backfilled_by_name: int
    visits_backfilled_by_name: int
    backfill_skipped_ambiguous: int
    backfill_skipped_not_found: int


class ProductStageSyncOnceReport(ProductStageSyncReport):
    skipped: bool
    reason: str


# ── Date / ID / value helpers ──────────────────────────────────────────────
def _today_iso() -> str:
    return date.today().isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat(sep=" ")


def _gen_id() -> str:
    return uuid.uuid4().hex


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_date(value: object, fallback: str | None = None) -> str:
    if isinstance(value, date):
        return value.isoformat()
    if value is None:
        return fallback or _today_iso()
    text = str(value).strip()
    if not text:
        return fallback or _today_iso()
    return text[:10]


def _normalize_strict_iso_date(
    value: object,
    *,
    field_name: str,
    fallback: object | None = None,
) -> str:
    if value is None:
        if fallback is not None:
            return _normalize_strict_iso_date(
                fallback,
                field_name=field_name,
            )
        return _today_iso()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    text = str(value).strip()
    if not text:
        if fallback is not None:
            return _normalize_strict_iso_date(
                fallback,
                field_name=field_name,
            )
        return _today_iso()
    if not _STRICT_ISO_DATE_PATTERN.fullmatch(text):
        raise ValueError(f"{field_name} must be YYYY-MM-DD")
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field_name} must be YYYY-MM-DD") from exc


def _ensure_date_not_in_future(value: str, *, field_name: str) -> None:
    if date.fromisoformat(value) > date.today():
        raise ValueError(f"{field_name} cannot be in the future")


def _normalize_non_negative_int(value: object, *, field_name: str) -> int:
    result = _as_int(value, 0)
    if result < 0:
        raise ValueError(f"{field_name} cannot be negative")
    return result


def _normalize_month(yyyymm: str) -> str:
    text = (yyyymm or "").strip()
    if len(text) == 7 and "-" in text:
        return text.replace("-", "")
    if len(text) != 6 or not text.isdigit():
        raise ValueError("Month must be YYYYMM or YYYY-MM")
    return text


def _month_from_date_value(value: object | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return _normalize_date(text)[:7].replace("-", "")


def _normalize_product_stage(value: object, fallback: str | None = None) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback or PRODUCT_STAGE_MASS_PRODUCTION
    if text not in PRODUCT_STAGE_OPTIONS:
        raise ValueError("Product stage must be 量產 or 試產")
    return text


def _normalize_product_stage_for_read(value: object) -> str:
    try:
        return _normalize_product_stage(
            value,
            fallback=PRODUCT_STAGE_MASS_PRODUCTION,
        )
    except ValueError:
        return PRODUCT_STAGE_MASS_PRODUCTION


# ── Tech-transfer helpers ──────────────────────────────────────────────────
def _normalize_tech_transfer_state(value: object) -> str:
    text = str(value or "").strip().lower()
    if text in TECH_TRANSFER_STATE_VALUES:
        return text
    return TECH_TRANSFER_STATE_NO


def _resolve_tech_transfer_states(
    *,
    states: dict | None,
    booleans: dict[str, bool],
) -> dict[str, str]:
    """Compute final state-strings per item.

    `states` (if a dict) is canonical and may carry 'yes' / 'no' / 'na'. Missing
    keys (or invalid values) fall back to the matching boolean: True → 'yes',
    False → 'no'. This lets older callers that only pass booleans keep working.
    """
    result: dict[str, str] = {}
    for key in VISIT_TECH_TRANSFER_ITEM_COLUMNS:
        explicit: str | None = None
        if isinstance(states, dict) and key in states:
            candidate = str(states[key] or "").strip().lower()
            if candidate in TECH_TRANSFER_STATE_VALUES:
                explicit = candidate
        if explicit is not None:
            result[key] = explicit
        else:
            result[key] = (
                TECH_TRANSFER_STATE_YES
                if booleans.get(key)
                else TECH_TRANSFER_STATE_NO
            )
    return result


# ── Migration meta helpers ─────────────────────────────────────────────────
def upsert_migration_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO migration_meta(key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = CURRENT_TIMESTAMP
        """,
        (key, value),
    )
    conn.commit()


def get_migration_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute(
        "SELECT value FROM migration_meta WHERE key = ?",
        (key,),
    ).fetchone()
    if row is None:
        return None
    return str(row["value"])


# ── Product lookup helpers ─────────────────────────────────────────────────
def _normalized_lookup_text(value: object) -> str:
    return str(value or "").strip()


def _register_unique_lookup_key(
    lookup: dict[tuple[str, str], str | None],
    key: tuple[str, str],
    product_id: str,
) -> None:
    if not key[0] or not key[1]:
        return
    existing = lookup.get(key)
    if existing is None and key not in lookup:
        lookup[key] = product_id
        return
    if existing == product_id:
        return
    lookup[key] = None


def _build_product_lookup_by_supplier_and_name(
    conn: sqlite3.Connection,
) -> dict[tuple[str, str], str | None]:
    rows = conn.execute(
        """
        SELECT
            id,
            supplier_id,
            secondary_supplier_id,
            trim(product_name) AS product_name
        FROM products
        WHERE trim(product_name) <> '' AND is_active = 1
        """
    ).fetchall()
    lookup: dict[tuple[str, str], str | None] = {}
    for row in rows:
        product_id = _normalized_lookup_text(row["id"])
        product_name = _normalized_lookup_text(row["product_name"])
        supplier_id = _normalized_lookup_text(row["supplier_id"])
        secondary_supplier_id = _normalized_lookup_text(row["secondary_supplier_id"])
        _register_unique_lookup_key(lookup, (supplier_id, product_name), product_id)
        _register_unique_lookup_key(lookup, (secondary_supplier_id, product_name), product_id)
    return lookup


# ── Schema helpers ─────────────────────────────────────────────────────────
def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        LIMIT 1
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    if not _table_exists(conn, table_name):
        return set()
    rows = conn.execute(
        f"PRAGMA table_info({_quote_identifier(table_name)})"
    ).fetchall()
    return {str(row["name"]) for row in rows}


def _quote_identifier(identifier: str) -> str:
    if not identifier:
        raise ValueError("Identifier must not be empty")
    return '"' + str(identifier).replace('"', '""') + '"'
