"""Shared display helpers for event and summary tables."""

from __future__ import annotations


def event_type_display(event_type_raw: str) -> str:
    raw = str(event_type_raw or "").strip().upper()
    if raw == "ANOMALY":
        return "異常"
    if raw == "VISIT":
        return "訪廠"
    return "-"
