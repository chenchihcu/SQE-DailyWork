"""Validate anomaly ERP trace numbers against source matrix and preferences."""

from __future__ import annotations

import re
from typing import Any

from services.anomaly_trace_contract import (
    TRACE_FIELD_LABELS,
    TRACE_FIELD_PATTERN_KEYS,
    empty_trace_payload,
    extract_trace_values,
    hidden_trace_fields_for_source,
    normalize_anomaly_source,
    required_trace_fields_for_source,
)


def compile_trace_pattern(pattern: object) -> re.Pattern[str] | None:
    text = str(pattern or "").strip()
    if not text:
        return None
    return re.compile(text)


def validate_trace_pattern_text(pattern: object) -> str:
    text = str(pattern or "").strip()
    if not text:
        return ""
    try:
        re.compile(text)
    except re.error as exc:
        raise ValueError(f"ERP 格式規則無效：{exc}") from exc
    return text


def build_trace_patterns(preferences: object) -> dict[str, str]:
    return {
        field: validate_trace_pattern_text(getattr(preferences, pattern_key, ""))
        for field, pattern_key in TRACE_FIELD_PATTERN_KEYS.items()
    }


def _pattern_for_field(patterns: dict[str, str], field: str) -> re.Pattern[str] | None:
    return compile_trace_pattern(patterns.get(field, ""))


def _assert_trace_field_pattern(
    field: str,
    value: str,
    patterns: dict[str, str],
) -> None:
    pattern = _pattern_for_field(patterns, field)
    if pattern is None:
        raise ValueError(
            f"請先在顯示設定中設定{TRACE_FIELD_LABELS[field]}的 ERP 格式規則"
        )
    if not pattern.fullmatch(value):
        raise ValueError(f"{TRACE_FIELD_LABELS[field]}格式不符合 ERP 規則")


def validate_anomaly_trace_payload(
    *,
    anomaly_source: object,
    supplier_id: object,
    payload: object,
    patterns: dict[str, str],
    allow_legacy_blank_source: bool = False,
) -> dict[str, str]:
    """Normalize and validate trace fields; raise ValueError on contract violations."""
    normalized_source = normalize_anomaly_source(anomaly_source)
    values = extract_trace_values(payload)
    if not normalized_source:
        if allow_legacy_blank_source:
            for field, value in values.items():
                if not value:
                    continue
                _assert_trace_field_pattern(field, value, patterns)
            return values
        raise ValueError("請選擇異常來源")

    required_fields = required_trace_fields_for_source(normalized_source)
    hidden_fields = hidden_trace_fields_for_source(normalized_source)

    for field in hidden_fields:
        if values[field]:
            raise ValueError(
                f"異常來源「{normalized_source}」不可填寫{TRACE_FIELD_LABELS[field]}"
            )

    for field in required_fields:
        if not values[field]:
            raise ValueError(f"{TRACE_FIELD_LABELS[field]}為必填")
        _assert_trace_field_pattern(field, values[field], patterns)

    for field, value in values.items():
        if field in required_fields or not value:
            continue
        _assert_trace_field_pattern(field, value, patterns)

    return values


def sanitize_trace_payload_for_source(
    anomaly_source: object,
    payload: object,
) -> dict[str, str]:
    """Drop hidden-field values while preserving visible non-empty entries."""
    values = extract_trace_values(payload)
    hidden_fields = hidden_trace_fields_for_source(anomaly_source)
    for field in hidden_fields:
        values[field] = ""
    return values


def merge_trace_payload(base: dict[str, Any] | None, extra: dict[str, Any] | None) -> dict[str, str]:
    merged = empty_trace_payload()
    for source in (base, extra):
        if not isinstance(source, dict):
            continue
        for field in merged:
            text = str(source.get(field) or "").strip()
            if text:
                merged[field] = text
    return merged
