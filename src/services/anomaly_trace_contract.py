"""Shared anomaly source and ERP trace-number field contract."""

from __future__ import annotations

from typing import Final

ANOMALY_SOURCE_MATERIAL_INCOMING: Final[str] = "原物料進貨（IQC）"
ANOMALY_SOURCE_INTERNAL_MO: Final[str] = "廠內製令"
ANOMALY_SOURCE_OUTSOURCE_PROCESSING: Final[str] = "委外加工"
ANOMALY_SOURCE_OUTSOURCE_RECEIPT: Final[str] = "委外進貨"
ANOMALY_SOURCE_VISIT_AUDIT: Final[str] = "訪廠／稽核"
ANOMALY_SOURCE_OTHER: Final[str] = "其他"

ANOMALY_SOURCE_OPTIONS: Final[tuple[str, ...]] = (
    ANOMALY_SOURCE_MATERIAL_INCOMING,
    ANOMALY_SOURCE_INTERNAL_MO,
    ANOMALY_SOURCE_OUTSOURCE_PROCESSING,
    ANOMALY_SOURCE_OUTSOURCE_RECEIPT,
    ANOMALY_SOURCE_VISIT_AUDIT,
    ANOMALY_SOURCE_OTHER,
)

TRACE_FIELD_MATERIAL_RECEIPT: Final[str] = "material_receipt_no"
TRACE_FIELD_INTERNAL_WORK_ORDER: Final[str] = "internal_work_order_no"
TRACE_FIELD_OUTSOURCE_WORK_ORDER: Final[str] = "outsource_work_order"
TRACE_FIELD_OUTSOURCE_RECEIPT: Final[str] = "outsource_receipt_no"

TRACE_FIELD_LABELS: Final[dict[str, str]] = {
    TRACE_FIELD_MATERIAL_RECEIPT: "原物料進貨單號",
    TRACE_FIELD_INTERNAL_WORK_ORDER: "廠內製令單號",
    TRACE_FIELD_OUTSOURCE_WORK_ORDER: "委外製令單號",
    TRACE_FIELD_OUTSOURCE_RECEIPT: "委外進貨單號",
}

TRACE_FIELD_PATTERN_KEYS: Final[dict[str, str]] = {
    TRACE_FIELD_MATERIAL_RECEIPT: "erp_material_receipt_no_pattern",
    TRACE_FIELD_INTERNAL_WORK_ORDER: "erp_internal_work_order_no_pattern",
    TRACE_FIELD_OUTSOURCE_WORK_ORDER: "erp_outsource_work_order_pattern",
    TRACE_FIELD_OUTSOURCE_RECEIPT: "erp_outsource_receipt_no_pattern",
}

SOURCE_VISIBLE_TRACE_FIELDS: Final[dict[str, frozenset[str]]] = {
    ANOMALY_SOURCE_MATERIAL_INCOMING: frozenset({TRACE_FIELD_MATERIAL_RECEIPT}),
    ANOMALY_SOURCE_INTERNAL_MO: frozenset({TRACE_FIELD_INTERNAL_WORK_ORDER}),
    ANOMALY_SOURCE_OUTSOURCE_PROCESSING: frozenset({TRACE_FIELD_OUTSOURCE_WORK_ORDER}),
    ANOMALY_SOURCE_OUTSOURCE_RECEIPT: frozenset({TRACE_FIELD_OUTSOURCE_RECEIPT}),
    ANOMALY_SOURCE_VISIT_AUDIT: frozenset(),
    ANOMALY_SOURCE_OTHER: frozenset(
        {
            TRACE_FIELD_MATERIAL_RECEIPT,
            TRACE_FIELD_INTERNAL_WORK_ORDER,
            TRACE_FIELD_OUTSOURCE_WORK_ORDER,
            TRACE_FIELD_OUTSOURCE_RECEIPT,
        }
    ),
}

SOURCE_REQUIRED_TRACE_FIELDS: Final[dict[str, frozenset[str]]] = {
    ANOMALY_SOURCE_MATERIAL_INCOMING: frozenset({TRACE_FIELD_MATERIAL_RECEIPT}),
    ANOMALY_SOURCE_INTERNAL_MO: frozenset({TRACE_FIELD_INTERNAL_WORK_ORDER}),
    ANOMALY_SOURCE_OUTSOURCE_PROCESSING: frozenset({TRACE_FIELD_OUTSOURCE_WORK_ORDER}),
    ANOMALY_SOURCE_OUTSOURCE_RECEIPT: frozenset({TRACE_FIELD_OUTSOURCE_RECEIPT}),
    ANOMALY_SOURCE_VISIT_AUDIT: frozenset(),
    ANOMALY_SOURCE_OTHER: frozenset(),
}

LEGACY_ANOMALY_SOURCE_MAP: Final[dict[str, str]] = {
    "進料檢驗 (IQC)": ANOMALY_SOURCE_MATERIAL_INCOMING,
    "製程檢驗 (IPQC)": ANOMALY_SOURCE_INTERNAL_MO,
    "出貨/客戶端 (OQA)": ANOMALY_SOURCE_OTHER,
    "廠內稽核": ANOMALY_SOURCE_VISIT_AUDIT,
    "訪廠發現": ANOMALY_SOURCE_VISIT_AUDIT,
}

PROCESSING_LINE_SOURCE_HINTS: Final[dict[str, str]] = {
    "原物料": ANOMALY_SOURCE_MATERIAL_INCOMING,
    "委外加工": ANOMALY_SOURCE_OUTSOURCE_PROCESSING,
}


def normalize_anomaly_source(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text in ANOMALY_SOURCE_OPTIONS:
        return text
    return LEGACY_ANOMALY_SOURCE_MAP.get(text, "")


def visible_trace_fields_for_source(source: object) -> frozenset[str]:
    normalized = normalize_anomaly_source(source)
    if not normalized:
        return frozenset()
    return SOURCE_VISIBLE_TRACE_FIELDS.get(normalized, frozenset())


def required_trace_fields_for_source(source: object) -> frozenset[str]:
    normalized = normalize_anomaly_source(source)
    if not normalized:
        return frozenset()
    return SOURCE_REQUIRED_TRACE_FIELDS.get(normalized, frozenset())


def hidden_trace_fields_for_source(source: object) -> frozenset[str]:
    visible = visible_trace_fields_for_source(source)
    return frozenset(field for field in TRACE_FIELD_LABELS if field not in visible)


def trace_field_label(field_key: str) -> str:
    return TRACE_FIELD_LABELS.get(field_key, field_key)


def empty_trace_payload() -> dict[str, str]:
    return {field: "" for field in TRACE_FIELD_LABELS}


def extract_trace_values(payload: object) -> dict[str, str]:
    data = payload if isinstance(payload, dict) else {}
    return {
        field: str(data.get(field) or "").strip()
        for field in TRACE_FIELD_LABELS
    }


def processing_line_source_hint(processing_line: object) -> str:
    return PROCESSING_LINE_SOURCE_HINTS.get(str(processing_line or "").strip(), "")
