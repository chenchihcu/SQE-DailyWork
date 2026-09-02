"""User-maintainable anomaly source preset library (ui_settings)."""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from typing import Any

from database.connection import get_connection
from services.anomaly_trace_contract import (
    ANOMALY_SOURCE_INTERNAL_MO,
    ANOMALY_SOURCE_MATERIAL_INCOMING,
    ANOMALY_SOURCE_OTHER,
    ANOMALY_SOURCE_OUTSOURCE_PROCESSING,
    ANOMALY_SOURCE_OUTSOURCE_RECEIPT,
    ANOMALY_SOURCE_VISIT_AUDIT,
    SOURCE_REQUIRED_TRACE_FIELDS,
    SOURCE_VISIBLE_TRACE_FIELDS,
    TRACE_FIELD_LABELS,
)

logger = logging.getLogger(__name__)

ANOMALY_SOURCES_SETTINGS_KEY = "supplier_event.anomaly_sources.v1"

_BUILTIN_SOURCE_IDS: dict[str, str] = {
    "material_incoming": ANOMALY_SOURCE_MATERIAL_INCOMING,
    "internal_mo": ANOMALY_SOURCE_INTERNAL_MO,
    "outsource_processing": ANOMALY_SOURCE_OUTSOURCE_PROCESSING,
    "outsource_receipt": ANOMALY_SOURCE_OUTSOURCE_RECEIPT,
    "visit_audit": ANOMALY_SOURCE_VISIT_AUDIT,
    "other": ANOMALY_SOURCE_OTHER,
}

_VALID_TRACE_FIELDS = frozenset(TRACE_FIELD_LABELS)


@dataclass
class AnomalySourceEntry:
    id: str
    label: str
    visible_trace_fields: list[str] = field(default_factory=list)
    required_trace_fields: list[str] = field(default_factory=list)

    def visible_frozenset(self) -> frozenset[str]:
        return frozenset(self.visible_trace_fields)

    def required_frozenset(self) -> frozenset[str]:
        return frozenset(self.required_trace_fields)


@dataclass
class AnomalySourcePresets:
    version: int = 1
    sources: list[AnomalySourceEntry] = field(default_factory=list)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "sources": [
                {
                    "id": entry.id,
                    "label": entry.label,
                    "visible_trace_fields": list(entry.visible_trace_fields),
                    "required_trace_fields": list(entry.required_trace_fields),
                }
                for entry in self.sources
            ],
        }

    @classmethod
    def from_mapping(cls, value: object) -> AnomalySourcePresets | None:
        if not isinstance(value, dict):
            return None
        version = value.get("version")
        sources_raw = value.get("sources")
        if version != 1 or not isinstance(sources_raw, list) or not sources_raw:
            return None
        sources: list[AnomalySourceEntry] = []
        seen_ids: set[str] = set()
        seen_labels: set[str] = set()
        for item in sources_raw:
            if not isinstance(item, dict):
                return None
            entry_id = str(item.get("id") or "").strip()
            label = str(item.get("label") or "").strip()
            if not entry_id or not label:
                return None
            label_key = label.casefold()
            if entry_id in seen_ids or label_key in seen_labels:
                return None
            visible_raw = item.get("visible_trace_fields")
            required_raw = item.get("required_trace_fields")
            if not isinstance(visible_raw, list) or not isinstance(required_raw, list):
                return None
            visible = _normalize_trace_field_list(visible_raw)
            required = _normalize_trace_field_list(required_raw)
            if not required.issubset(visible):
                return None
            seen_ids.add(entry_id)
            seen_labels.add(label_key)
            sources.append(
                AnomalySourceEntry(
                    id=entry_id,
                    label=label,
                    visible_trace_fields=sorted(visible),
                    required_trace_fields=sorted(required),
                )
            )
        return cls(version=1, sources=sources)


def _normalize_trace_field_list(values: list[object]) -> frozenset[str]:
    normalized: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text in _VALID_TRACE_FIELDS:
            normalized.add(text)
    return frozenset(normalized)


def _trace_lists_for_label(label: str) -> tuple[list[str], list[str]]:
    visible = sorted(SOURCE_VISIBLE_TRACE_FIELDS.get(label, frozenset()))
    required = sorted(SOURCE_REQUIRED_TRACE_FIELDS.get(label, frozenset()))
    return visible, required


def default_sources() -> AnomalySourcePresets:
    sources: list[AnomalySourceEntry] = []
    for entry_id, label in _BUILTIN_SOURCE_IDS.items():
        visible, required = _trace_lists_for_label(label)
        sources.append(
            AnomalySourceEntry(
                id=entry_id,
                label=label,
                visible_trace_fields=visible,
                required_trace_fields=required,
            )
        )
    return AnomalySourcePresets(version=1, sources=sources)


def _load_raw(conn: sqlite3.Connection) -> tuple[bool, object | None]:
    row = conn.execute(
        "SELECT setting_value FROM ui_settings WHERE setting_key = ?",
        (ANOMALY_SOURCES_SETTINGS_KEY,),
    ).fetchone()
    if row is None:
        return False, None
    try:
        return True, json.loads(row[0])
    except (json.JSONDecodeError, TypeError, ValueError):
        return True, None


_cache: AnomalySourcePresets | None = None


def invalidate_cache() -> None:
    global _cache
    _cache = None


def load_sources(conn: sqlite3.Connection | None = None) -> AnomalySourcePresets:
    global _cache
    if conn is None and _cache is not None:
        return clone_sources(_cache)

    def _resolve(active_conn: sqlite3.Connection) -> AnomalySourcePresets:
        try:
            exists, payload = _load_raw(active_conn)
        except sqlite3.Error:
            logger.exception("讀取異常來源辭庫失敗")
            return default_sources()
        if not exists:
            return default_sources()
        parsed = AnomalySourcePresets.from_mapping(payload)
        if parsed is None:
            if payload is not None:
                logger.warning("忽略格式無效的異常來源辭庫")
            return default_sources()
        return parsed

    if conn is None:
        with get_connection() as managed:
            result = _resolve(managed)
    else:
        result = _resolve(conn)
    if conn is None:
        _cache = clone_sources(result)
    return result


def save_sources(
    presets: AnomalySourcePresets,
    conn: sqlite3.Connection | None = None,
) -> None:
    validation_error = validate_sources(presets)
    if validation_error:
        raise ValueError(validation_error)
    payload = presets.to_mapping()
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    def _write(active_conn: sqlite3.Connection) -> None:
        active_conn.execute(
            """
            INSERT INTO ui_settings (setting_key, setting_value)
            VALUES (?, ?)
            ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value
            """,
            (ANOMALY_SOURCES_SETTINGS_KEY, encoded),
        )
        active_conn.commit()

    if conn is None:
        with get_connection() as managed:
            _write(managed)
    else:
        _write(conn)
    invalidate_cache()


def validate_sources(presets: AnomalySourcePresets) -> str:
    if not presets.sources:
        return "至少保留一個異常來源。"
    seen_ids: set[str] = set()
    seen_labels: set[str] = set()
    for entry in presets.sources:
        entry_id = str(entry.id or "").strip()
        label = str(entry.label or "").strip()
        if not entry_id:
            return "異常來源識別碼不可為空。"
        if not label:
            return "異常來源名稱不可為空。"
        if entry_id in seen_ids:
            return f"異常來源識別碼重複：{entry_id}"
        label_key = label.casefold()
        if label_key in seen_labels:
            return f"異常來源名稱重複：{label}"
        visible = _normalize_trace_field_list(entry.visible_trace_fields)
        required = _normalize_trace_field_list(entry.required_trace_fields)
        if not required.issubset(visible):
            return f"異常來源「{label}」的必填追溯欄位必須包含於顯示欄位。"
        seen_ids.add(entry_id)
        seen_labels.add(label_key)
    return ""


def clone_sources(presets: AnomalySourcePresets) -> AnomalySourcePresets:
    restored = AnomalySourcePresets.from_mapping(presets.to_mapping())
    return restored or default_sources()


def all_source_labels(presets: AnomalySourcePresets | None = None) -> list[str]:
    active = presets or load_sources()
    return [entry.label for entry in active.sources]


def find_source_by_label(
    label: object,
    presets: AnomalySourcePresets | None = None,
) -> AnomalySourceEntry | None:
    text = str(label or "").strip()
    if not text:
        return None
    active = presets or load_sources()
    for entry in active.sources:
        if entry.label == text:
            return entry
    return None


def find_source_by_id(
    entry_id: object,
    presets: AnomalySourcePresets | None = None,
) -> AnomalySourceEntry | None:
    text = str(entry_id or "").strip()
    if not text:
        return None
    active = presets or load_sources()
    for entry in active.sources:
        if entry.id == text:
            return entry
    return None


def label_for_source_id(
    entry_id: object,
    presets: AnomalySourcePresets | None = None,
) -> str:
    entry = find_source_by_id(entry_id, presets)
    return entry.label if entry else ""


def visible_trace_fields(label: object, presets: AnomalySourcePresets | None = None) -> frozenset[str]:
    entry = find_source_by_label(label, presets)
    if entry is None:
        return frozenset()
    return entry.visible_frozenset()


def required_trace_fields(label: object, presets: AnomalySourcePresets | None = None) -> frozenset[str]:
    entry = find_source_by_label(label, presets)
    if entry is None:
        return frozenset()
    return entry.required_frozenset()


def count_anomalies_using_source(label: str, conn: sqlite3.Connection | None = None) -> int:
    text = str(label or "").strip()
    if not text:
        return 0

    def _count(active_conn: sqlite3.Connection) -> int:
        row = active_conn.execute(
            "SELECT COUNT(*) FROM anomalies WHERE TRIM(anomaly_source) = ?",
            (text,),
        ).fetchone()
        return int(row[0]) if row else 0

    if conn is None:
        with get_connection() as managed:
            return _count(managed)
    return _count(conn)


def new_custom_source_id() -> str:
    return f"custom_{uuid.uuid4().hex[:8]}"
