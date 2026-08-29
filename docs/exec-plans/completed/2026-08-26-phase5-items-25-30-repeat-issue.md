# Phase 5 項目 25–30 對照（Design-Derived）

Plan status: completed — design-derived traceability + repeat-issue schema/UI for 48-item rollout Phase 5

## Scope and methodology

- `mapping_type`: **design-derived**
- This document does **not** restore the original user-approved 48-item titles for
  items 25–30; those titles were never committed to the repository.
- Each item below is derived from:
  - [SQE Incident Management UI Design Framework v0.1 §6 header RepeatIssuesPanel](../../SQE_Incident_Management_UI_Design_Framework_v0.1.md)
  - [architecture-workflow-contract.md](../../architecture-workflow-contract.md) §8 Supplier 360
  - [2026-08-24-case-workbench-48-item-rollout.md](../active/2026-08-24-case-workbench-48-item-rollout.md) Phase 5 scope
- **Schema + Promotion** required for `anomaly_repeat_links_v1` on formal DB.

## Item map

| # | derived_title | status |
| --- | --- | --- |
| 25 | Repeat-issue similarity schema (`anomaly_repeat_links`) | complete |
| 26 | Deterministic same-supplier scoring service | complete |
| 27 | Supplier-scoped index refresh on anomaly create/update | complete |
| 28 | Workbench `RepeatIssuesPanel` between stepper and tabs | complete |
| 29 | Supplier 360 summary「重複警示」read model | complete |
| 30 | Focused tests + verify/promotion gates | complete |

---

### 25 — Repeat-issue similarity schema

| Field | Value |
| --- | --- |
| **design_source** | Design framework §6 RepeatIssuesPanel; supplier-event line only |
| **implementation_paths** | `src/database/anomaly_repeat_repository.py`; `migration_meta` key `anomaly_repeat_links_v1` |
| **verification_gate** | `tests/test_repeat_issue_phase5.py` |
| **status** | **complete** |

---

### 26 — Deterministic scoring

| Field | Value |
| --- | --- |
| **design_source** | Same-supplier historical cases; category/product/keywords/problem tokens |
| **implementation_paths** | `src/services/repeat_issue_scoring.py` |
| **verification_gate** | `tests/test_repeat_issue_phase5.py` |
| **status** | **complete** |
| **residual_notes** | Minimum score = category match (40); no fuzzy ML / FTS |

---

### 27 — Index refresh hooks

| Field | Value |
| --- | --- |
| **design_source** | Index must stay current when anomalies change |
| **implementation_paths** | `refresh_supplier_repeat_links`; `_anomaly_service` create/update hooks |
| **verification_gate** | `tests/test_repeat_issue_phase5.py` |
| **status** | **complete** |

---

### 28 — Workbench RepeatIssuesPanel

| Field | Value |
| --- | --- |
| **design_source** | Design framework §6 header↔tabs「潛在重複異常」; empty state「無相似案件」 |
| **implementation_paths** | `src/ui/widgets/repeat_issues_panel.py`; `anomaly_management_page.py` |
| **verification_gate** | `tests/test_anomaly_management_page.py` |
| **status** | **complete** |
| **residual_notes** | Double-click opens peer anomaly in workbench |

---

### 29 — Supplier 360 repeat summary

| Field | Value |
| --- | --- |
| **design_source** | Supplier 360 read-only aggregation; separate source labels preserved |
| **implementation_paths** | `supplier_360_service.get_supplier_summary`; `supplier_360_page.py` header |
| **verification_gate** | `tests/test_repeat_issue_phase5.py`; `tests/test_supplier_360_service.py` |
| **status** | **complete** |

---

### 30 — Verification and Promotion gates

| Field | Value |
| --- | --- |
| **implementation_paths** | `scripts/verify_workbench_phase5.ps1`; `scripts/migrate_anomaly_repeat_links_v1.py`; `scripts/apply_anomaly_repeat_links_promotion.ps1` |
| **verification_gate** | disposable DB + formal fingerprint unchanged |
| **status** | **complete** |
| **residual_notes** | Formal Promotion requires user `繼續` + env markers |

## Phase 5 evidence

- Date: 2026-08-26
- Focused: `scripts/verify_workbench_phase5.ps1`
- Promotion dry-run: `scripts/migrate_anomaly_repeat_links_v1.py` (preview only until `繼續`)
- Formal Promotion: 2026-08-26 verified — backup `data/sqe_v2_backup_anomaly_repeat_links_v1_20260826_223506.db`; 22 links across 19 suppliers
