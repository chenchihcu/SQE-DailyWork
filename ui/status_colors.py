from __future__ import annotations

from dataclasses import dataclass

from ui.theme import TOKENS


@dataclass(frozen=True)
class StatusPalette:
    foreground: str
    background: str
    border: str
    chart: str


STATUS_PALETTES: dict[str, StatusPalette] = {
    "pending": StatusPalette(
        TOKENS["status_pending_fg"],
        TOKENS["status_pending_bg"],
        TOKENS["status_pending_border"],
        TOKENS["status_pending_chart"],
    ),
    "success": StatusPalette(
        TOKENS["status_success_fg"],
        TOKENS["status_success_bg"],
        TOKENS["status_success_border"],
        TOKENS["status_success_chart"],
    ),
    "danger": StatusPalette(
        TOKENS["status_danger_fg"],
        TOKENS["status_danger_bg"],
        TOKENS["status_danger_border"],
        TOKENS["status_danger_chart"],
    ),
    "info": StatusPalette(
        TOKENS["status_info_fg"],
        TOKENS["status_info_bg"],
        TOKENS["status_info_border"],
        TOKENS["status_info_chart"],
    ),
    "unknown": StatusPalette(
        TOKENS["status_unknown_fg"],
        TOKENS["status_unknown_bg"],
        TOKENS["status_unknown_border"],
        TOKENS["status_unknown_chart"],
    ),
    "na": StatusPalette(
        TOKENS["status_na_fg"],
        TOKENS["status_na_bg"],
        TOKENS["status_na_border"],
        TOKENS["status_na_chart"],
    ),
}

DEFAULT_STATUS_COLOR_HEX = STATUS_PALETTES["unknown"].foreground

_STATUS_TONE_MAP = {
    "啟用": "success",
    "ACTIVE": "success",
    "停用": "danger",
    "INACTIVE": "danger",
    "待處理": "pending",
    "OPEN": "pending",
    "已結案": "success",
    "已完成": "success",
    "CLOSED": "success",
    "COMPLETED": "success",
    "異常": "danger",
    "ANOMALY": "danger",
    "訪廠": "info",
    "VISIT": "info",
    "不適用": "na",
    "N/A": "na",
    "NA": "na",
    "逾期未結": "danger",
    "單獨異常": "pending",
    "訪廠發現異常": "info",
}


def get_status_tone(status: str | None) -> str:
    normalized = str(status or "").strip().upper()
    if not normalized:
        return "unknown"
    return _STATUS_TONE_MAP.get(normalized, "unknown")


def get_status_palette(status: str | None) -> StatusPalette:
    return STATUS_PALETTES[get_status_tone(status)]


def get_status_color_hex(status: str | None) -> str:
    return get_status_palette(status).foreground
