"""Derive the primary next-action CTA for event Quick Review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

HANDLER_HANDLE_OVERDUE = "handle_overdue"
HANDLER_ADD_ACTION = "add_action"
HANDLER_ROOT_CAUSE = "root_cause"
HANDLER_VERIFY = "verify"
HANDLER_CLOSE = "close"
HANDLER_OPEN_FULL = "open_full"

_ROOT_CAUSE_PENDING = frozenset({"", "—", "尚未開始", "調查中"})


@dataclass(frozen=True)
class NextActionSpec:
    label: str
    handler_key: str


def _text(value: object) -> str:
    return str(value or "").strip()


def _stages_ready_for_close(detail: Mapping[str, Any], overview: Mapping[str, Any]) -> bool:
    data: Mapping[str, Any] = overview or detail
    root_status = _text(data.get("root_cause_status") or detail.get("root_cause_status"))
    ca_status = _text(
        data.get("corrective_action_status") or detail.get("corrective_action_status")
    )
    verify_result = _text(
        data.get("verification_result") or detail.get("verification_result")
    )
    return (
        root_status not in _ROOT_CAUSE_PENDING
        and ca_status not in {"", "—", "未建立"}
        and verify_result not in {"", "—", "待驗證"}
    )


def resolve_next_action(
    overview: Mapping[str, Any] | None,
    detail: Mapping[str, Any] | None,
) -> NextActionSpec:
    """Return the primary CTA label and handler key for one anomaly row."""
    overview_data: Mapping[str, Any] = overview or {}
    detail_data: Mapping[str, Any] = detail or {}
    status = _text(detail_data.get("status") or overview_data.get("status"))

    if bool(overview_data.get("overdue")) and status == "待處理":
        return NextActionSpec("處理逾期處置", HANDLER_HANDLE_OVERDUE)

    current_action = overview_data.get("current_action") or detail_data.get("current_action")
    open_count = int(overview_data.get("open_action_count") or 0)
    if status == "待處理" and not current_action and open_count <= 0:
        return NextActionSpec("新增處置", HANDLER_ADD_ACTION)

    root_status = _text(
        overview_data.get("root_cause_status") or detail_data.get("root_cause_status")
    )
    if root_status in _ROOT_CAUSE_PENDING and status == "待處理":
        return NextActionSpec("根因調查", HANDLER_ROOT_CAUSE)

    verify_result = _text(
        overview_data.get("verification_result") or detail_data.get("verification_result")
    )
    if verify_result == "待驗證" and status == "待處理":
        return NextActionSpec("記錄驗證", HANDLER_VERIFY)

    if status == "待處理" and _stages_ready_for_close(detail_data, overview_data):
        return NextActionSpec("結案", HANDLER_CLOSE)

    return NextActionSpec("開啟完整案件", HANDLER_OPEN_FULL)
