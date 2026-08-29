"""Stable YAML-in-Markdown snapshots for supplier anomaly records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from database import connection as _connection
from database import repository
from database.repo_helpers import CASE_ACTION_OPEN_STATUSES, format_current_action_text
from services import attachment_manager

from ._anomaly_folder import create_anomaly_folder


ANOMALY_FIELDS: tuple[tuple[str, str], ...] = (
    ("id", "異常事件ID"),
    ("anomaly_no", "異常單號"),
    ("anomaly_date", "異常日期"),
    ("anomaly_source", "異常來源"),
    ("supplier_id", "供應商ID"),
    ("supplier_name", "供應商名稱"),
    ("visit_id", "訪廠紀錄ID"),
    ("product_id", "產品ID"),
    ("product_code", "料號"),
    ("product_name", "產品名稱"),
    ("product_stage", "產品階段"),
    ("problem_desc", "異常描述"),
    ("category_raw", "異常類別"),
    ("process_keywords", "SMT 製程關鍵詞"),
    ("product_lot_no", "產品批號"),
    ("material_receipt_no", "原物料進貨單號"),
    ("internal_work_order_no", "廠內製令單號"),
    ("outsource_work_order", "委外製令單號"),
    ("outsource_receipt_no", "委外進貨單號"),
    ("batch_qty", "批次數量"),
    ("status", "狀態"),
    ("improvement_desc", "改善說明"),
    ("closed_at", "結案日期"),
    ("pending_items", "待辦事項"),
    ("responsible_person", "負責人"),
    ("due_date", "預計完成日期"),
    ("rc_supplier_inventory", "圍堵確認_供應商庫存"),
    ("rc_supplier_wip", "圍堵確認_供應商在製品"),
    ("rc_in_transit", "圍堵確認_運輸途中"),
    ("rc_internal_inventory", "圍堵確認_廠內庫存"),
    ("quality_report_required", "是否要求品質異常單"),
    ("created_at", "建立時間"),
    ("updated_at", "更新時間"),
)

OVERVIEW_FIELDS: tuple[tuple[str, str], ...] = (
    ("overdue", "逾期"),
    ("current_action_text", "目前處置"),
    ("open_action_count", "進行中處置數"),
    ("root_cause_status", "根本原因狀態"),
    ("corrective_action_status", "改善措施狀態"),
    ("verification_result", "有效性驗證"),
    ("hypothesis_count", "原因假設數"),
    ("hypothesis_adopted", "已採納假設"),
    ("attachment_count", "附件數"),
    ("repeat_link_count", "重複警示"),
)


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return '""'
    if isinstance(value, bool):
        return '"是"' if value else '"否"'
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def _overview_snapshot(conn, anomaly_id: str) -> dict[str, Any]:
    overview = repository.get_anomaly_overview_card(conn, anomaly_id)
    return {
        "overdue": bool(overview.get("overdue")),
        "current_action_text": format_current_action_text(
            overview.get("current_action"),
            include_owner_due=True,
        ),
        "open_action_count": int(overview.get("open_action_count") or 0),
        "root_cause_status": overview.get("root_cause_status") or "尚未開始",
        "corrective_action_status": overview.get("corrective_action_status") or "—",
        "verification_result": overview.get("verification_result") or "—",
        "hypothesis_count": int(overview.get("hypothesis_count") or 0),
        "hypothesis_adopted": bool(overview.get("hypothesis_adopted")),
        "attachment_count": int(overview.get("attachment_count") or 0),
        "repeat_link_count": int(overview.get("repeat_link_count") or 0),
    }


def render_anomaly_markdown(detail: dict) -> str:
    """Render a deterministic YAML document using the canonical field order."""
    anomaly_id = str(detail.get("id") or "")
    captions = attachment_manager.get_anomaly_captions(anomaly_id)
    attachments = attachment_manager.list_stored_attachment_files(anomaly_id)

    lines = ["---", "異常事件:"]
    for field, label in ANOMALY_FIELDS:
        lines.append(f"  {label}: {_yaml_scalar(detail.get(field))}")
    if attachments:
        lines.append("  附件:")
        for path in attachments:
            lines.append(f"    - 檔名: {_yaml_scalar(path.name)}")
            lines.append(f"      圖說: {_yaml_scalar(captions.get(path.name, ''))}")
    else:
        lines.append("  附件: []")

    with _connection.get_connection() as conn:
        overview = _overview_snapshot(conn, anomaly_id)
        hypotheses = repository.list_anomaly_hypotheses(conn, anomaly_id)
        actions = repository.list_case_actions(conn, anomaly_id)

    lines.append("案件概況:")
    for field, label in OVERVIEW_FIELDS:
        lines.append(f"  {label}: {_yaml_scalar(overview.get(field))}")

    if hypotheses:
        lines.append("  原因假設:")
        for row in hypotheses:
            level = int(row.get("level") or 1)
            status = str(row.get("status") or "")
            statement = str(row.get("statement") or "").replace("\n", " ").strip()
            lines.append(
                f"    - L{level} [{status}]: {_yaml_scalar(statement)}"
            )
    else:
        lines.append("  原因假設: []")

    open_actions = [
        action
        for action in actions
        if action.get("execution_status") in CASE_ACTION_OPEN_STATUSES
    ]
    if open_actions:
        lines.append("  開啟中處置:")
        for action in open_actions:
            action_type = str(action.get("action_type") or "")
            description = str(action.get("description") or "").replace("\n", " ").strip()
            owner = str(action.get("owner") or "")
            due = str(action.get("due_date") or "")
            lines.append(
                f"    - 類型: {_yaml_scalar(action_type)}"
            )
            lines.append(f"      內容: {_yaml_scalar(description)}")
            lines.append(f"      負責人: {_yaml_scalar(owner)}")
            lines.append(f"      到期日: {_yaml_scalar(due)}")
    else:
        lines.append("  開啟中處置: []")

    lines.append("...")
    return "\n".join(lines) + "\n"


def write_anomaly_markdown(detail: dict) -> Path:
    """Atomically create or overwrite the current anomaly YAML markdown file."""
    supplier_name = str(detail.get("supplier_name") or "")
    anomaly_no = str(detail.get("anomaly_no") or "")
    folder = create_anomaly_folder(
        supplier_name=supplier_name,
        anomaly_no=anomaly_no,
    )
    safe_stem = folder.name
    target = folder / f"{safe_stem}.md"
    temporary = target.with_suffix(".md.tmp")
    temporary.write_text(render_anomaly_markdown(detail), encoding="utf-8")
    temporary.replace(target)
    return target


def sync_anomaly_markdown_by_id(anomaly_id: str) -> Path:
    """Reload the source-of-truth row and synchronize its markdown snapshot."""
    key = str(anomaly_id or "").strip()
    if not key:
        raise ValueError("Anomaly id is required")
    with _connection.get_connection() as conn:
        detail = repository.get_anomaly_detail(conn, key)
    if detail is None:
        raise ValueError("Anomaly not found")
    return write_anomaly_markdown(detail)
