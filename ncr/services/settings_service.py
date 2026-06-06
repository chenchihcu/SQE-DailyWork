from __future__ import annotations

import json
import sqlite3


def get_setting(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    """獲取 UI 設定。"""
    row = conn.execute(
        "SELECT setting_value FROM ui_settings WHERE setting_key = ?", (key,)
    ).fetchone()
    return row[0] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    """儲存 UI 設定。"""
    conn.execute(
        "INSERT OR REPLACE INTO ui_settings (setting_key, setting_value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()


def get_column_order(conn: sqlite3.Connection, key: str) -> list[str] | None:
    """獲取欄位順序列表。"""
    value = get_setting(conn, key)
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def set_column_order(conn: sqlite3.Connection, key: str, field_names: list[str]) -> None:
    """儲存欄位順序列表。"""
    set_setting(conn, key, json.dumps(field_names))
