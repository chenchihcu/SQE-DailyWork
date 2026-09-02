"""Persistence boundary for application-wide display and system preferences."""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable

from database.connection import get_connection
from ui.appearance_preferences import AppearancePreferences, _canonicalize_stored_mapping


logger = logging.getLogger(__name__)

APPEARANCE_PREFERENCES_V1_KEY = "appearance.preferences.v1"
APPEARANCE_PREFERENCES_V2_KEY = "appearance.preferences.v2"
APPEARANCE_PREFERENCES_V3_KEY = "appearance.preferences.v3"
APPEARANCE_PREFERENCES_V4_KEY = "appearance.preferences.v4"
APPEARANCE_PREFERENCES_V5_KEY = "appearance.preferences.v5"
APPEARANCE_PREFERENCES_V6_KEY = "appearance.preferences.v6"
APPEARANCE_PREFERENCES_V7_KEY = "appearance.preferences.v7"
APPEARANCE_PREFERENCES_V8_KEY = "appearance.preferences.v8"
APPEARANCE_PREFERENCES_V9_KEY = "appearance.preferences.v9"
APPEARANCE_PREFERENCES_V10_KEY = "appearance.preferences.v10"
APPEARANCE_PREFERENCES_KEY = APPEARANCE_PREFERENCES_V10_KEY

_V1_INVALID_BASELINE = {"density": "standard", "text_scale": "standard"}


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


def _load_version_preferences(
    conn: sqlite3.Connection,
    *,
    key: str,
    log_label: str,
    parser: Callable[[object | None], AppearancePreferences],
    invalid_baseline: dict[str, str] | None = None,
) -> AppearancePreferences | None:
    try:
        exists, payload = _load_raw_preferences(conn, key)
    except sqlite3.Error:
        logger.exception("讀取%s失敗", log_label)
        return AppearancePreferences.default()

    if not exists:
        return None

    preferences = parser(payload)
    if invalid_baseline is not None:
        if (
            preferences == AppearancePreferences.default()
            and payload != invalid_baseline
        ):
            logger.warning("忽略格式無效的%s", log_label)
    elif (
        preferences == AppearancePreferences.default()
        and _canonicalize_stored_mapping(payload) != preferences.to_mapping()
    ):
        logger.warning("忽略格式無效的%s", log_label)
    return preferences


def load_preferences(conn: sqlite3.Connection) -> AppearancePreferences:
    """Load strict v10 preferences, with read-only v9-v1 compatibility fallbacks."""
    fallback_chain: tuple[tuple[str, str, Callable[[object | None], AppearancePreferences], dict[str, str] | None], ...] = (
        (APPEARANCE_PREFERENCES_V10_KEY, "介面與系統 v10 偏好", AppearancePreferences.from_mapping, None),
        (APPEARANCE_PREFERENCES_V9_KEY, "介面與系統 v9 偏好", AppearancePreferences.from_mapping, None),
        (APPEARANCE_PREFERENCES_V8_KEY, "介面與系統 v8 偏好", AppearancePreferences.from_mapping, None),
        (APPEARANCE_PREFERENCES_V7_KEY, "介面與系統 v7 偏好", AppearancePreferences.from_mapping, None),
        (APPEARANCE_PREFERENCES_V6_KEY, "介面與系統 v6 偏好", AppearancePreferences.from_mapping, None),
        (APPEARANCE_PREFERENCES_V5_KEY, "介面與系統 v5 偏好", AppearancePreferences.from_mapping, None),
        (APPEARANCE_PREFERENCES_V4_KEY, "介面與系統 v4 偏好", AppearancePreferences.from_mapping, None),
        (APPEARANCE_PREFERENCES_V3_KEY, "介面與系統 v3 偏好", AppearancePreferences.from_mapping, None),
        (APPEARANCE_PREFERENCES_V2_KEY, "介面設計 v2 偏好", AppearancePreferences.from_v2_mapping, None),
        (APPEARANCE_PREFERENCES_V1_KEY, "舊版介面設計偏好", AppearancePreferences.from_v1_mapping, _V1_INVALID_BASELINE),
    )

    for key, log_label, parser, invalid_baseline in fallback_chain:
        preferences = _load_version_preferences(
            conn,
            key=key,
            log_label=log_label,
            parser=parser,
            invalid_baseline=invalid_baseline,
        )
        if preferences is not None:
            return preferences
    return AppearancePreferences.default()


def save_preferences(conn: sqlite3.Connection, preferences: AppearancePreferences) -> None:
    """Atomically save only the namespaced v9 appearance key."""
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
