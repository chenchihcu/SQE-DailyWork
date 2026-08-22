"""Shared constants, TypedDicts, and helper functions for the repository layer."""

from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import date, datetime
from typing import TypedDict

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

# ── Anomaly action (Next Action) constants ──────────────────────────────────
ANOMALY_ACTION_STATUS_OPEN = "進行中"
ANOMALY_ACTION_STATUS_COMPLETED = "已完成"
ANOMALY_ACTION_STATUS_CANCELLED = "已取消"
ANOMALY_ACTION_STATUSES: tuple[str, ...] = (
    ANOMALY_ACTION_STATUS_OPEN,
    ANOMALY_ACTION_STATUS_COMPLETED,
    ANOMALY_ACTION_STATUS_CANCELLED,
)
ANOMALY_ACTIONS_MIGRATION_META_KEY = "anomaly_actions_v1"
ANOMALY_ACTIONS_BACKFILL_META_KEY = "anomaly_actions_backfill_v1"

# ── Anomaly analysis / root cause / CA / verification constants ─────────────
ANOMALY_EVIDENCE_FACT = "FACT"
ANOMALY_EVIDENCE_INFERENCE = "INFERENCE"
ANOMALY_EVIDENCE_ASSUMPTION = "ASSUMPTION"
ANOMALY_EVIDENCE_UNKNOWN = "UNKNOWN"
ANOMALY_EVIDENCE_TYPES: tuple[str, ...] = (
    ANOMALY_EVIDENCE_FACT,
    ANOMALY_EVIDENCE_INFERENCE,
    ANOMALY_EVIDENCE_ASSUMPTION,
    ANOMALY_EVIDENCE_UNKNOWN,
)
ANOMALY_EVIDENCE_LABELS: dict[str, str] = {
    ANOMALY_EVIDENCE_FACT: "已確認事實",
    ANOMALY_EVIDENCE_INFERENCE: "推論",
    ANOMALY_EVIDENCE_ASSUMPTION: "假設",
    ANOMALY_EVIDENCE_UNKNOWN: "待確認",
}

ANOMALY_ROOT_CAUSE_NOT_STARTED = "尚未開始"
ANOMALY_ROOT_CAUSE_UNDER_INVESTIGATION = "調查中"
ANOMALY_ROOT_CAUSE_PROPOSED = "提案"
ANOMALY_ROOT_CAUSE_VERIFIED = "已驗證"
ANOMALY_ROOT_CAUSE_NOT_ESTABLISHED = "無法確認"
ANOMALY_ROOT_CAUSE_STATUSES: tuple[str, ...] = (
    ANOMALY_ROOT_CAUSE_NOT_STARTED,
    ANOMALY_ROOT_CAUSE_UNDER_INVESTIGATION,
    ANOMALY_ROOT_CAUSE_PROPOSED,
    ANOMALY_ROOT_CAUSE_VERIFIED,
    ANOMALY_ROOT_CAUSE_NOT_ESTABLISHED,
)

CORRECTIVE_ACTION_STATUS_PLANNED = "已規劃"
CORRECTIVE_ACTION_STATUS_IN_PROGRESS = "執行中"
CORRECTIVE_ACTION_STATUS_IMPLEMENTED = "已實施"
CORRECTIVE_ACTION_STATUS_VERIFICATION_PENDING = "待有效性驗證"
CORRECTIVE_ACTION_STATUS_EFFECTIVE = "有效"
CORRECTIVE_ACTION_STATUS_INEFFECTIVE = "無效"
CORRECTIVE_ACTION_STATUS_CANCELLED = "已取消"
CORRECTIVE_ACTION_STATUSES: tuple[str, ...] = (
    CORRECTIVE_ACTION_STATUS_PLANNED,
    CORRECTIVE_ACTION_STATUS_IN_PROGRESS,
    CORRECTIVE_ACTION_STATUS_IMPLEMENTED,
    CORRECTIVE_ACTION_STATUS_VERIFICATION_PENDING,
    CORRECTIVE_ACTION_STATUS_EFFECTIVE,
    CORRECTIVE_ACTION_STATUS_INEFFECTIVE,
    CORRECTIVE_ACTION_STATUS_CANCELLED,
)

EFFECTIVENESS_VERIFICATION_RESULT_PENDING = "待驗證"
EFFECTIVENESS_VERIFICATION_RESULT_EFFECTIVE = "有效"
EFFECTIVENESS_VERIFICATION_RESULT_INEFFECTIVE = "無效"
EFFECTIVENESS_VERIFICATION_RESULT_INCONCLUSIVE = "無法判定"
EFFECTIVENESS_VERIFICATION_RESULTS: tuple[str, ...] = (
    EFFECTIVENESS_VERIFICATION_RESULT_PENDING,
    EFFECTIVENESS_VERIFICATION_RESULT_EFFECTIVE,
    EFFECTIVENESS_VERIFICATION_RESULT_INEFFECTIVE,
    EFFECTIVENESS_VERIFICATION_RESULT_INCONCLUSIVE,
)

ANOMALY_ANALYSIS_NOTES_MIGRATION_META_KEY = "anomaly_analysis_notes_v1"
ANOMALY_ROOT_CAUSES_MIGRATION_META_KEY = "anomaly_root_causes_v1"
CORRECTIVE_ACTIONS_MIGRATION_META_KEY = "corrective_actions_v1"
EFFECTIVENESS_VERIFICATIONS_MIGRATION_META_KEY = "effectiveness_verifications_v1"
ANOMALY_ATTACHMENTS_MIGRATION_META_KEY = "anomaly_attachments_v1"
ANOMALY_EIGHT_D_REVIEWS_MIGRATION_META_KEY = "anomaly_eight_d_reviews_v1"
ANOMALY_AUDIT_LOGS_MIGRATION_META_KEY = "anomaly_audit_logs_v1"


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
    # Local wall-clock time (tz-aware) so created_at/updated_at match the user's
    # calendar day and the schema triggers' datetime('now', 'localtime'). Using
    # UTC here made audit timestamps show the previous day for UTC+8 users near
    # midnight. Date-range statistics are unaffected (they key off the date-only
    # anomaly_date / closed_at values, not these timestamps).
    return datetime.now().astimezone().replace(microsecond=0).isoformat(sep=" ")


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


def _normalize_loose_iso_date(
    value: object,
    *,
    field_name: str,
) -> str:
    """Accept ``YYYY-MM-DD`` or ``YYYY/MM/DD`` and return the ISO form.

    Strict ISO date validation is used everywhere else; this helper exists for
    action due dates so simple UI shortcuts like ``2026/07/01`` are accepted
    without forcing the caller to pre-format. The result is always at the
    YYYY-MM-DD resolution.
    """
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    text = text.replace("/", "-")
    return _normalize_strict_iso_date(text, field_name=field_name)


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
