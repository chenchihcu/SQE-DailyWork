"""Shared overview-card text formatting for exports and derived outputs."""

from __future__ import annotations


def format_current_action_text(current: object) -> str:
    """Owner/due parenthetical format; empty string when description is absent."""
    if not isinstance(current, dict):
        return ""
    description = str(current.get("description") or "").strip()
    if not description:
        return ""
    owner = str(current.get("owner") or "").strip() or "—"
    due = str(current.get("due_date") or "").strip()
    if due:
        return f"{description}（{owner} / {due}）"
    return f"{description}（{owner}）"
