"""Canonical display order for SQE DailyWork list surfaces.

This module governs presentation only. Database field names and persisted NCR
column-order settings remain owned by their respective workflow modules.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColumnSpec:
    field: str
    label: str


EVENT_LIST_COLUMNS = (
    ColumnSpec("ref_no", "異常單號"),
    ColumnSpec("supplier_name", "供應商"),
    ColumnSpec("product_code", "料號"),
    ColumnSpec("product_name", "品名"),
    ColumnSpec("product_stage", "階段"),
    ColumnSpec("category", "異常類別"),
    ColumnSpec("process_keywords", "SMT 製程關鍵詞"),
    ColumnSpec("responsible_person", "責任人"),
    ColumnSpec("content", "問題/摘要"),
    ColumnSpec("defect_notes", "缺失紀錄"),
    ColumnSpec("quality_report_required", "品質異常單要求"),
    ColumnSpec("status", "狀態"),
    ColumnSpec("closed_at", "結案日期"),
)
EVENT_LIST_FIELDS = tuple(column.field for column in EVENT_LIST_COLUMNS)
EVENT_LIST_HEADERS = tuple(column.label for column in EVENT_LIST_COLUMNS)
EVENT_LIST_COMPACT_FIELDS = frozenset(
    {
        "ref_no",
        "supplier_name",
        "product_code",
        "product_name",
        "category",
        "content",
        "quality_report_required",
        "status",
    }
)

CASE_QUEUE_COLUMNS = (
    ColumnSpec("ref_no", "異常單號"),
    ColumnSpec("supplier_name", "供應商"),
    ColumnSpec("content", "問題/摘要"),
    ColumnSpec("current_action_text", "下一步處置"),
    ColumnSpec("action_due_date", "到期日"),
    ColumnSpec("responsible_person", "異常責任人"),
)

CASE_QUEUE_RCA_COLUMNS = CASE_QUEUE_COLUMNS + (
    ColumnSpec("root_cause_status", "根本原因"),
)

SUPPLIER_OVERVIEW_COLUMNS = (
    ColumnSpec("supplier_name", "供應商"),
    ColumnSpec("open_anomaly_count", "未結異常"),
    ColumnSpec("overdue_anomaly_count", "逾期"),
    ColumnSpec("latest_anomaly_no", "最新異常單號"),
    ColumnSpec("latest_anomaly_date", "異常日期"),
    ColumnSpec("latest_anomaly_category", "異常類別"),
    ColumnSpec("latest_anomaly_desc", "問題摘要"),
    ColumnSpec("latest_anomaly_due_date", "到期日"),
    ColumnSpec("ncr_90d_count", "近 90 日 NCR"),
    ColumnSpec("grade", "評級"),
    ColumnSpec("is_active", "供應商狀態"),
)

SUPPLIER_360_ANOMALY_COLUMNS = (
    ColumnSpec("anomaly_no", "異常單號"),
    ColumnSpec("anomaly_date", "日期"),
    ColumnSpec("category", "異常類別"),
    ColumnSpec("problem_desc", "問題摘要"),
    ColumnSpec("responsible_person", "責任人"),
    ColumnSpec("due_date", "到期日"),
    ColumnSpec("status", "狀態"),
)

MANAGER_SUMMARY_COLUMNS = (
    ColumnSpec("ref_no", "異常單號"),
    ColumnSpec("supplier_name", "供應商"),
    ColumnSpec("content", "問題/摘要"),
    ColumnSpec("status", "狀態"),
    ColumnSpec("current_action_text", "下一步處置"),
    ColumnSpec("action_due_date", "到期日"),
    ColumnSpec("overdue", "逾期"),
    ColumnSpec("root_cause_status", "根本原因"),
    ColumnSpec("corrective_action_status", "改善措施"),
    ColumnSpec("verification_result", "有效性驗證"),
    ColumnSpec("last_updated", "最後更新"),
)

OPERATIONAL_ACTION_QUEUE_COLUMNS = (
    ColumnSpec("ref_no", "異常單號"),
    ColumnSpec("supplier_name", "供應商"),
    ColumnSpec("action_type", "處置類型"),
    ColumnSpec("description", "處置內容"),
    ColumnSpec("owner", "處置負責人"),
    ColumnSpec("due_date", "到期日"),
    ColumnSpec("execution_status", "執行狀態"),
    ColumnSpec("overdue", "逾期"),
)
