"""User-maintainable anomaly category preset library (ui_settings)."""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from database.connection import get_connection

logger = logging.getLogger(__name__)

_DEFAULT_CATEGORY_LABELS: tuple[str, ...] = (
    "製程參數失控",
    "規範文件缺漏",
    "檢驗把關失靈",
    "設計匹配不良",
    "設備能力不符",
    "包裝防護不足",
    "來料品質不良",
    "標準作業不落實",
    "供應商改善不力",
    "其他",
)

ANOMALY_CATEGORIES_SETTINGS_KEY = "supplier_event.anomaly_categories.v1"


@dataclass
class AnomalyCategoryPresets:
    version: int = 1
    categories: list[str] = field(default_factory=list)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "categories": list(self.categories),
        }

    @classmethod
    def from_mapping(cls, value: object) -> AnomalyCategoryPresets | None:
        if not isinstance(value, dict):
            return None
        version = value.get("version")
        categories_raw = value.get("categories")
        if version != 1 or not isinstance(categories_raw, list) or not categories_raw:
            return None
        categories: list[str] = []
        seen: set[str] = set()
        for item in categories_raw:
            text = str(item or "").strip()
            if not text:
                return None
            key = text.casefold()
            if key in seen:
                return None
            seen.add(key)
            categories.append(text)
        return cls(version=1, categories=categories)


def default_categories() -> AnomalyCategoryPresets:
    return AnomalyCategoryPresets(
        version=1,
        categories=list(_DEFAULT_CATEGORY_LABELS),
    )


def _load_raw(conn: sqlite3.Connection) -> tuple[bool, object | None]:
    row = conn.execute(
        "SELECT setting_value FROM ui_settings WHERE setting_key = ?",
        (ANOMALY_CATEGORIES_SETTINGS_KEY,),
    ).fetchone()
    if row is None:
        return False, None
    try:
        return True, json.loads(row[0])
    except (json.JSONDecodeError, TypeError, ValueError):
        return True, None


_cache: AnomalyCategoryPresets | None = None


def invalidate_cache() -> None:
    global _cache
    _cache = None


def load_categories(conn: sqlite3.Connection | None = None) -> AnomalyCategoryPresets:
    global _cache
    if conn is None and _cache is not None:
        return clone_categories(_cache)

    def _resolve(active_conn: sqlite3.Connection) -> AnomalyCategoryPresets:
        try:
            exists, payload = _load_raw(active_conn)
        except sqlite3.Error:
            logger.exception("讀取異常類別辭庫失敗")
            return default_categories()
        if not exists:
            return default_categories()
        parsed = AnomalyCategoryPresets.from_mapping(payload)
        if parsed is None:
            if payload is not None:
                logger.warning("忽略格式無效的異常類別辭庫")
            return default_categories()
        return parsed

    if conn is None:
        with get_connection() as managed:
            result = _resolve(managed)
    else:
        result = _resolve(conn)
    if conn is None:
        _cache = clone_categories(result)
    return result


def save_categories(
    presets: AnomalyCategoryPresets,
    conn: sqlite3.Connection | None = None,
) -> None:
    validation_error = validate_categories(presets)
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
            (ANOMALY_CATEGORIES_SETTINGS_KEY, encoded),
        )
        active_conn.commit()

    if conn is None:
        with get_connection() as managed:
            _write(managed)
    else:
        _write(conn)
    invalidate_cache()


def validate_categories(presets: AnomalyCategoryPresets) -> str:
    if not presets.categories:
        return "至少保留一個異常類別。"
    seen: set[str] = set()
    for category in presets.categories:
        text = str(category or "").strip()
        if not text:
            return "異常類別名稱不可為空。"
        key = text.casefold()
        if key in seen:
            return f"異常類別名稱重複：{text}"
        seen.add(key)
    return ""


def clone_categories(presets: AnomalyCategoryPresets) -> AnomalyCategoryPresets:
    restored = AnomalyCategoryPresets.from_mapping(presets.to_mapping())
    return restored or default_categories()


def all_category_labels(presets: AnomalyCategoryPresets | None = None) -> list[str]:
    active = presets or load_categories()
    return list(active.categories)


def is_valid_category(value: object, presets: AnomalyCategoryPresets | None = None) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    labels = {label.casefold() for label in all_category_labels(presets)}
    return text.casefold() in labels


def count_anomalies_using_category(label: str, conn: sqlite3.Connection | None = None) -> int:
    text = str(label or "").strip()
    if not text:
        return 0

    def _count(active_conn: sqlite3.Connection) -> int:
        row = active_conn.execute(
            "SELECT COUNT(*) FROM anomalies WHERE TRIM(category) = ?",
            (text,),
        ).fetchone()
        return int(row[0]) if row else 0

    if conn is None:
        with get_connection() as managed:
            return _count(managed)
    return _count(conn)
