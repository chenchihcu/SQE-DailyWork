"""User-maintainable SMT process keyword preset library (ui_settings)."""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from database.connection import get_connection

logger = logging.getLogger(__name__)

SMT_PROCESS_KEYWORDS_SETTINGS_KEY = "smt.process_keywords.v1"


@dataclass
class ProcessKeywordGroup:
    id: str
    label: str
    keywords: list[str] = field(default_factory=list)


@dataclass
class ProcessKeywordPresets:
    version: int = 1
    groups: list[ProcessKeywordGroup] = field(default_factory=list)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "groups": [
                {
                    "id": group.id,
                    "label": group.label,
                    "keywords": list(group.keywords),
                }
                for group in self.groups
            ],
        }

    @classmethod
    def from_mapping(cls, value: object) -> ProcessKeywordPresets | None:
        if not isinstance(value, dict):
            return None
        version = value.get("version")
        groups_raw = value.get("groups")
        if version != 1 or not isinstance(groups_raw, list):
            return None
        groups: list[ProcessKeywordGroup] = []
        for item in groups_raw:
            if not isinstance(item, dict):
                return None
            group_id = str(item.get("id") or "").strip()
            label = str(item.get("label") or "").strip()
            keywords_raw = item.get("keywords")
            if not group_id or not label or not isinstance(keywords_raw, list):
                return None
            keywords = [
                str(keyword or "").strip()
                for keyword in keywords_raw
                if str(keyword or "").strip()
            ]
            groups.append(ProcessKeywordGroup(id=group_id, label=label, keywords=keywords))
        if not groups:
            return None
        return cls(version=1, groups=groups)


def default_presets() -> ProcessKeywordPresets:
    return ProcessKeywordPresets(
        version=1,
        groups=[
            ProcessKeywordGroup(
                id="station",
                label="製程站別",
                keywords=[
                    "SPI",
                    "錫膏印刷",
                    "貼片",
                    "回流焊",
                    "AOI",
                    "X-ray",
                    "烘烤",
                    "鋼網/Stencil",
                    "載具",
                ],
            ),
            ProcessKeywordGroup(
                id="phenomenon",
                label="現象關鍵詞",
                keywords=[
                    "錫量過低",
                    "錫量過高",
                    "橋接",
                    "立碑",
                    "偏移",
                    "空焊",
                    "虛焊",
                    "少件",
                    "tombstone",
                    "短路",
                    "錫珠",
                ],
            ),
        ],
    )


def _load_raw(conn: sqlite3.Connection) -> tuple[bool, object | None]:
    row = conn.execute(
        "SELECT setting_value FROM ui_settings WHERE setting_key = ?",
        (SMT_PROCESS_KEYWORDS_SETTINGS_KEY,),
    ).fetchone()
    if row is None:
        return False, None
    try:
        return True, json.loads(row[0])
    except (json.JSONDecodeError, TypeError, ValueError):
        return True, None


def load_presets(conn: sqlite3.Connection | None = None) -> ProcessKeywordPresets:
    if conn is None:
        with get_connection() as managed:
            return load_presets(managed)
    try:
        exists, payload = _load_raw(conn)
    except sqlite3.Error:
        logger.exception("讀取 SMT 製程關鍵詞庫失敗")
        return default_presets()
    if not exists:
        return default_presets()
    parsed = ProcessKeywordPresets.from_mapping(payload)
    if parsed is None:
        if payload is not None:
            logger.warning("忽略格式無效的 SMT 製程關鍵詞庫")
        return default_presets()
    return parsed


def save_presets(
    presets: ProcessKeywordPresets,
    conn: sqlite3.Connection | None = None,
) -> None:
    payload = presets.to_mapping()
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    def _write(active_conn: sqlite3.Connection) -> None:
        active_conn.execute(
            """
            INSERT INTO ui_settings (setting_key, setting_value)
            VALUES (?, ?)
            ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value
            """,
            (SMT_PROCESS_KEYWORDS_SETTINGS_KEY, encoded),
        )
        active_conn.commit()

    if conn is None:
        with get_connection() as managed:
            _write(managed)
        return
    _write(conn)


def all_suggestion_keywords(presets: ProcessKeywordPresets | None = None) -> list[str]:
    active = presets or load_presets()
    seen: set[str] = set()
    ordered: list[str] = []
    for group in active.groups:
        for keyword in group.keywords:
            text = str(keyword or "").strip()
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(text)
    return ordered


def clone_presets(presets: ProcessKeywordPresets) -> ProcessKeywordPresets:
    restored = ProcessKeywordPresets.from_mapping(presets.to_mapping())
    return restored or default_presets()


def merge_custom_keyword(
    presets: ProcessKeywordPresets,
    keyword: str,
    *,
    group_id: str = "phenomenon",
) -> ProcessKeywordPresets:
    text = str(keyword or "").strip()
    if not text:
        return clone_presets(presets)
    updated = clone_presets(presets)
    target = next((group for group in updated.groups if group.id == group_id), None)
    if target is None:
        updated.groups.append(
            ProcessKeywordGroup(id=group_id, label=group_id, keywords=[text])
        )
        return updated
    existing = {item.casefold() for item in target.keywords}
    if text.casefold() not in existing:
        target.keywords.append(text)
    return updated
