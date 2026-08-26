"""Shared overview / export display helpers for supplier anomaly read models."""

from __future__ import annotations

from typing import Any


def format_current_action_text(action: dict | None) -> str:
    """Format current action as description（owner / due）for exports and snapshots."""
    current = action or {}
    current_desc = str(current.get("description") or "").strip()
    if not current_desc:
        return ""
    current_owner = str(current.get("owner") or "").strip()
    current_due = str(current.get("due_date") or "").strip()
    owner_label = current_owner or "—"
    if current_due:
        return f"{current_desc}（{owner_label} / {current_due}）"
    return f"{current_desc}（{owner_label}）"


def format_quality_report_required_for_export(value: Any) -> str:
    """Return 是/否/未設定 for anomaly Excel export rows."""
    if value is None:
        return "未設定"
    if isinstance(value, str):
        normalized = value.strip().lower()
        if not normalized:
            return "未設定"
        if normalized in {"1", "true", "yes", "是"}:
            return "是"
        if normalized in {"0", "false", "no", "否"}:
            return "否"
    return "是" if bool(value) else "否"
