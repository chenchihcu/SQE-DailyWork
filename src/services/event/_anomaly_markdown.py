"""Stable YAML-in-Markdown snapshots for supplier anomaly records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from database import connection as _connection
from database import repository
from services import attachment_manager

from ._anomaly_folder import create_anomaly_folder


ANOMALY_FIELDS: tuple[tuple[str, str], ...] = (
    ("id", "異常事件ID"),
    ("anomaly_no", "異常單號"),
    ("anomaly_date", "異常日期"),
    ("supplier_id", "供應商ID"),
    ("supplier_name", "供應商名稱"),
    ("visit_id", "訪廠紀錄ID"),
    ("product_id", "產品ID"),
    ("product_code", "料號"),
    ("product_name", "產品名稱"),
    ("product_stage", "產品階段"),
    ("problem_desc", "異常描述"),
    ("category_raw", "異常類別"),
    ("product_lot_no", "產品批號"),
    ("outsource_work_order", "委外工單"),
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
    ("is_tech_transfer", "是否技術移轉"),
    ("quality_report_required", "是否要求品質異常單"),
    ("created_at", "建立時間"),
    ("updated_at", "更新時間"),
)


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return '""'
    if isinstance(value, bool):
        return '"是"' if value else '"否"'
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def render_anomaly_markdown(detail: dict) -> str:
    """Render a deterministic YAML document using the canonical field order."""
    anomaly_id = str(detail.get("id") or "")
    captions = attachment_manager.get_anomaly_captions(anomaly_id)
    attachments = attachment_manager.list_anomaly_attachments(anomaly_id)

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
