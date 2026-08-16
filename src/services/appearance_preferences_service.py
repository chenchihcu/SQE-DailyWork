"""Persistence boundary for application-wide display and system preferences."""

from __future__ import annotations

import json
import logging
import sqlite3

from database.connection import get_connection
from ui.appearance_preferences import AppearancePreferences


logger = logging.getLogger(__name__)

APPEARANCE_PREFERENCES_V1_KEY = "appearance.preferences.v1"
APPEARANCE_PREFERENCES_V2_KEY = "appearance.preferences.v2"
APPEARANCE_PREFERENCES_V3_KEY = "appearance.preferences.v3"
APPEARANCE_PREFERENCES_V4_KEY = "appearance.preferences.v4"
APPEARANCE_PREFERENCES_V5_KEY = "appearance.preferences.v5"
APPEARANCE_PREFERENCES_KEY = APPEARANCE_PREFERENCES_V5_KEY


def _load_raw_preferences(conn: sqlite3.Connection, key: str) -> tuple[bool, object | None]:
    """Return presence plus decoded payload; malformed JSON remains invalid data."""
    row = conn.execute(
        "SELECT setting_value FROM ui_settings WHERE setting_key = ?",
        (key,),
    ).fetchone()
    if row is None:
        return False, None
    try:
        return True, json.loads(row[0])
    except (json.JSONDecodeError, TypeError, ValueError):
        return True, None


def load_preferences(conn: sqlite3.Connection) -> AppearancePreferences:
    """Load strict v5 preferences, with read-only v4, v3, v2 and v1 compatibility fallbacks."""
    try:
        v5_exists, v5_payload = _load_raw_preferences(conn, APPEARANCE_PREFERENCES_V5_KEY)
    except sqlite3.Error:
        logger.exception("讀取介面與系統 v5 偏好失敗")
        return AppearancePreferences.default()

    if v5_exists:
        preferences = AppearancePreferences.from_mapping(v5_payload)
        if preferences == AppearancePreferences.default() and v5_payload != preferences.to_mapping():
            logger.warning("忽略格式無效的介面與系統 v5 偏好")
        return preferences

    try:
        v4_exists, v4_payload = _load_raw_preferences(conn, APPEARANCE_PREFERENCES_V4_KEY)
    except sqlite3.Error:
        logger.exception("讀取介面與系統 v4 偏好失敗")
        return AppearancePreferences.default()

    if v4_exists:
        preferences = AppearancePreferences.from_mapping(v4_payload)
        if preferences == AppearancePreferences.default() and v4_payload != preferences.to_mapping():
            logger.warning("忽略格式無效的介面與系統 v4 偏好")
        return preferences

    try:
        v3_exists, v3_payload = _load_raw_preferences(conn, APPEARANCE_PREFERENCES_V3_KEY)
    except sqlite3.Error:
        logger.exception("讀取介面與系統 v3 偏好失敗")
        return AppearancePreferences.default()

    if v3_exists:
        preferences = AppearancePreferences.from_mapping(v3_payload)
        if preferences == AppearancePreferences.default() and v3_payload != preferences.to_mapping():
            logger.warning("忽略格式無效的介面與系統 v3 偏好")
        return preferences

    try:
        v2_exists, v2_payload = _load_raw_preferences(conn, APPEARANCE_PREFERENCES_V2_KEY)
    except sqlite3.Error:
        logger.exception("讀取介面設計 v2 偏好失敗")
        return AppearancePreferences.default()

    if v2_exists:
        preferences = AppearancePreferences.from_v2_mapping(v2_payload)
        if preferences == AppearancePreferences.default() and v2_payload != preferences.to_mapping():
            logger.warning("忽略格式無效的介面設計 v2 偏好")
        return preferences

    try:
        v1_exists, v1_payload = _load_raw_preferences(conn, APPEARANCE_PREFERENCES_V1_KEY)
    except sqlite3.Error:
        logger.exception("讀取舊版介面設計偏好失敗")
        return AppearancePreferences.default()
    if not v1_exists:
        return AppearancePreferences.default()
    preferences = AppearancePreferences.from_v1_mapping(v1_payload)
    if preferences == AppearancePreferences.default() and v1_payload != {"density": "standard", "text_scale": "standard"}:
        logger.warning("忽略格式無效的舊版介面設計偏好")
    return preferences


def save_preferences(conn: sqlite3.Connection, preferences: AppearancePreferences) -> None:
    """Atomically save only the namespaced v4 appearance key."""
    normalized = AppearancePreferences.from_mapping(preferences.to_mapping())
    if normalized != preferences:
        raise ValueError("介面偏好包含不支援的值")
    payload = json.dumps(preferences.to_mapping(), ensure_ascii=False, separators=(",", ":"))
    conn.execute(
        """
        INSERT INTO ui_settings (setting_key, setting_value)
        VALUES (?, ?)
        ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value
        """,
        (APPEARANCE_PREFERENCES_KEY, payload),
    )
    conn.commit()


def load_application_preferences() -> AppearancePreferences:
    """Best-effort runtime load; a display preference must never block startup."""
    try:
        with get_connection() as conn:
            return load_preferences(conn)
    except sqlite3.Error:
        logger.exception("無法開啟介面偏好，改用預設值")
        return AppearancePreferences.default()


def save_application_preferences(preferences: AppearancePreferences) -> None:
    with get_connection() as conn:
        save_preferences(conn, preferences)


