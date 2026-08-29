# Phase 4 項目 01、04–06、10–13、24 對照（Design-Derived）

Plan status: completed — design-derived traceability + UI closure for 48-item rollout Phase 4

## Scope and methodology

- `mapping_type`: **design-derived**
- This document does **not** restore the original user-approved 48-item titles for
  items 01、04–06、10–13、24; those titles were never committed to the repository.
- Each item below is derived from:
  - [SQE Incident Management UI Design Framework v0.1 §6.1–6.7](../../SQE_Incident_Management_UI_Design_Framework_v0.1.md)
  - [architecture-workflow-contract.md](../../architecture-workflow-contract.md)
  - [2026-08-24-case-workbench-48-item-rollout.md](../active/2026-08-24-case-workbench-48-item-rollout.md) Phase 4 scope
- **No schema / Promotion** in Phase 4. `anomalies.status` remains `待處理` / `已結案`.

## Item map

| # | derived_title | status |
| --- | --- | --- |
| 01 | Workbench header closure/reopen + overdue hint | complete |
| 04 | Overview「案件資料」card (DailyWork fields) | complete |
| 05 | Overview「品質結論」badges from overview SSOT | complete |
| 06 | Overview「目前處置」card + action complete/cancel | complete |
| 10 | Timeline shows CASE_CLOSED / CASE_REOPENED audit events | complete |
| 11 | Supplier 8D tab status presentation | complete |
| 12 | Corrective Actions tab execution/verification presentation | complete |
| 13 | History tab read model + manual audit entry (DailyWork residual) | complete |
| 24 | CaseStageStepper refresh on close/reopen/action change | complete |

---

### 01 — Workbench header closure/reopen

| Field | Value |
| --- | --- |
| **design_source** | Design framework §6 header: CloseCaseDialog / ReopenCaseDialog; DailyWork binary `待處理`/`已結案` |
| **implementation_paths** | `src/ui/widgets/anomaly_management_page.py` (header buttons); `src/ui/widgets/close_anomaly_dialog.py`; `src/ui/widgets/reopen_anomaly_dialog.py`; `src/ui/widgets/event_actions.py` |
| **verification_gate** | `tests/test_anomaly_management_page.py`; `tests/test_workbench_phase4.py` |
| **status** | **complete** |
| **residual_notes** | No Web multi-state CaseStatusSelect; overdue badge in header when `overview.overdue` |

---

### 04 — Overview case data card

| Field | Value |
| --- | --- |
| **design_source** | Design framework §6.1 card one; mapped to DailyWork anomaly fields |
| **implementation_paths** | `anomaly_management_page._build_overview_tab` |
| **verification_gate** | `tests/test_anomaly_management_page.py` |
| **status** | **complete** |

---

### 05 — Overview quality conclusion badges

| Field | Value |
| --- | --- |
| **design_source** | Design framework §6.1 card two; `get_anomaly_overview_card()` SSOT |
| **implementation_paths** | `repository.get_anomaly_overview_card`; overview tab badges |
| **verification_gate** | `tests/test_workbench_phase4.py` |
| **status** | **complete** |
| **residual_notes** | `hypothesis_count` shown as supplemental text when > 0 |

---

### 06 — Overview current action card

| Field | Value |
| --- | --- |
| **design_source** | Design framework §6.1 card three + action dialogs |
| **implementation_paths** | `anomaly_management_page` overview action card; existing complete/cancel dialogs |
| **verification_gate** | `tests/test_anomaly_management_page.py` |
| **status** | **complete** |

---

### 10 — Timeline close/reopen visibility

| Field | Value |
| --- | --- |
| **design_source** | Design framework §6.2 CASE_CLOSED / CASE_REOPENED |
| **implementation_paths** | `_anomaly_service.close_anomaly` / `reopen_anomaly` audit writes; `list_anomaly_timeline` |
| **verification_gate** | `tests/test_workbench_phase4.py` |
| **status** | **complete** |

---

### 11 — Supplier 8D presentation

| Field | Value |
| --- | --- |
| **design_source** | Design framework §6.4 review status badges |
| **implementation_paths** | `anomaly_management_page._build_eight_d_tab` |
| **verification_gate** | visual `workbench-page-eight-d` |
| **status** | **complete** |

---

### 12 — Corrective actions presentation

| Field | Value |
| --- | --- |
| **design_source** | Design framework §6.5 CA status badges |
| **implementation_paths** | `anomaly_management_page._build_corrective_tab` / `_add_case_action_rows` |
| **verification_gate** | visual `workbench-page-corrective` |
| **status** | **complete** |

---

### 13 — History tab

| Field | Value |
| --- | --- |
| **design_source** | Design framework §6.7 audit table (read-only in Web) |
| **implementation_paths** | `anomaly_management_page._build_history_tab`; `AddAuditLogDialog` retained |
| **verification_gate** | `tests/test_anomaly_management_page.py` |
| **status** | **complete** |
| **residual_notes** | DailyWork keeps manual「新增處理紀錄」— not Web parity |

---

### 24 — CaseStageStepper lifecycle refresh

| Field | Value |
| --- | --- |
| **design_source** | Exec plan Phase 4 item 24; AGENTS.md CaseStageStepper explicit status checks |
| **implementation_paths** | `common_widgets.CaseStageStepper`; `load_anomaly` / `refresh_data` |
| **verification_gate** | `tests/test_anomaly_management_page.py` |
| **status** | **complete** |

---

## Closure attachment contract (Phase 4)

- `CloseAnomalyDialog` embeds `EvidenceAttachmentPanel` (Phase 2 metadata path).
- Uploads persist immediately; canceling close does not roll back uploaded files.
- `date_adjustment_only` mode disables the evidence panel.
- `NewAnomalyDialog` **retains** legacy `AttachmentEditor` for create-time photos.

## Reopen contract (Phase 4)

- `reopen_anomaly(anomaly_id, reopen_reason=...)` requires non-empty reason.
- Same transaction: clear closure fields + `CASE_REOPENED` audit (`before_value` = prior close summary, `after_value` = reason).
- No mandatory next Action; no `reopened_at` / `reopened_reason` columns.

## Accepted residuals

| Topic | Disposition |
| --- | --- |
| Original 48-item titles 01–24 | Not in repo; design-derived only |
| Web CaseStatusSelect multi-state | Out of scope; binary status preserved |
| Analysis tab card/badge polish | Phase 3 residual; not blocking Phase 4 |
| History manual audit entry | DailyWork intentional residual |

## Completion evidence

- Date: 2026-08-26
- Focused gate: `scripts/verify_workbench_phase4.ps1` PASS (47 tests)
- Native visual: `dialog-density` close/reopen baselines @ 1.0 / 1.25 / 1.5
- Formal DB fingerprint: unchanged during focused gate
