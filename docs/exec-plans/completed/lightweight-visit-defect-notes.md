# Lightweight Visit Defect Notes

## Contract

- One visit records one supplier/date/person activity.
- A visit can contain multiple product sections.
- Each visit or product section can contain lightweight defect notes.
- Defect notes are simple record/improvement pairs, not formal anomaly tickets.

## Scope

- Added visit product-section and defect-note storage.
- Kept legacy `visits.product_id` fields as compatibility snapshots.
- Routed home quick actions for visit/anomaly registration to one visit-record form.
- Updated list/PDF/docs/tests for lightweight notes.

## Non-goals

- Formal anomaly flow remains available.
- No 8D/CAPA/audit severity, owner approval, or formal closure workflow was added.
- Defect notes do not create one anomaly ticket per row.

## Verification

- `.\scripts\verify.ps1` passed.
- Focused repository, service, PDF, UI structural, home quick-action, and visit-detail tests passed.
- Native Qt visual probe passed through `scripts\verify.ps1`.

## Completion Notes

- `visit_product_sections` stores product/time/work-order/qty/summary rows per visit.
- `visit_defect_notes` stores visit-level or product-section `缺失 / 改善 / 備註` rows.
- Home `登錄異常事件` routes to the lightweight visit-defect form; formal `新增異常` still opens the anomaly form.
- List rollups show aggregated products plus defect and pending-improvement counts.
- Visit PDF export prints simple defect/improvement tables without formal anomaly-report fields.
