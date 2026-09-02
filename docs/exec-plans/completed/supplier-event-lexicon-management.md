# Supplier Event Lexicon Management

Plan status: completed

## Summary

Added user-maintainable anomaly source and anomaly category lexicons stored in
`ui_settings`, managed from **顯示設定 → 表單與業務**, and consumed by anomaly
forms, trace validation, appearance defaults, and NCR handoff.

## Keys

- `supplier_event.anomaly_sources.v1`
- `supplier_event.anomaly_categories.v1`

## Verification

- `tests.test_anomaly_source_preset_service`
- `tests.test_anomaly_category_preset_service`
- `tests.test_anomaly_trace_fields`
