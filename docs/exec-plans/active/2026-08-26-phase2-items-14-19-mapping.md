# Phase 2 項目 14–19 對照（Design-Derived）

Plan status: active — design-derived traceability for 48-item rollout Phase 2

## Scope and methodology

- `mapping_type`: **design-derived**
- This document does **not** restore the original user-approved 48-item titles for
  items 14–19; those titles were never committed to the repository.
- Each item below is derived from:
  - [SQE Incident Management UI Design Framework v0.1 §6.6](../../SQE_Incident_Management_UI_Design_Framework_v0.1.md) (Attachments / Evidence)
  - [architecture-workflow-contract.md](../../architecture-workflow-contract.md) (`anomaly_attachments` SSOT)
  - [2026-08-24-case-workbench-48-item-rollout.md](2026-08-24-case-workbench-48-item-rollout.md) Phase 2 implementation contract
  - Current implementation and focused verification gates
- Do **not** confuse this numbering with design-framework §7.7 items 14–15
  (screen-fit helper / sidebar IA); those are a separate 15-item borrow list.

## Item map

| # | derived_title | status |
| --- | --- | --- |
| 14 | Attachment metadata contract and formal Promotion | complete |
| 15 | Nine attachment categories with zh-TW labels | complete |
| 16 | Same-anomaly evidence links (analysis note + canonical Action) | complete |
| 17 | Physical storage, suffix allowlist, and legacy projection | complete |
| 18 | Workbench attachments tab write UI | complete |
| 19 | Read-model, export, and audit consumer compatibility | partial-accepted |

---

### 14 — Attachment metadata contract and formal Promotion

| Field | Value |
| --- | --- |
| **design_source** | Architecture workflow contract: `anomaly_attachments` SQLite SSOT; columns `file_type`, `uploaded_by`, `related_note_id`, `related_action_id`; legacy `related_ca_id` retained; exec plan Phase 2 contract bullet 1 |
| **implementation_paths** | `src/database/repository.py` (`preview_anomaly_attachments_contract_v1`, `migrate_anomaly_attachments_contract_v1`); `src/database/connection.py` (read-only fail closed before writable bootstrap); `scripts/migrate_anomaly_attachments_contract_v1.py`; `scripts/apply_anomaly_attachments_promotion.ps1` |
| **verification_gate** | `tests/test_attachments_phase2.py` (`test_fresh_schema_has_phase2_attachment_contract`, `test_legacy_schema_preview_is_read_only_then_upgrade_is_idempotent`); `scripts/verify_attachments_phase2.ps1`; formal Promotion verified 2026-08-26 (`skipped: true`, backup `sqe_v2_backup_anomaly_attachments_v1_20260826_155811.db`) |
| **status** | **complete** |
| **residual_notes** | None blocking Phase 2 |

---

### 15 — Nine attachment categories with zh-TW labels

| Field | Value |
| --- | --- |
| **design_source** | Design framework §6.6 attachment category table (Evidence, NG Photo, FA Report, Supplier 8D, Corrective Action Evidence, Effectiveness Evidence, Specification / Reference, Supplier Audit Evidence, Other) |
| **implementation_paths** | `src/database/repo_helpers.py` (`ANOMALY_ATTACHMENT_CATEGORIES`, `ANOMALY_ATTACHMENT_CATEGORY_LABELS`); `src/ui/widgets/anomaly_attachment_panel.py` (required category on upload and metadata edit) |
| **verification_gate** | `tests/test_attachments_phase2.py` (`test_attachment_can_link_same_anomaly_note_and_canonical_action` asserts `category_label` 證據); `tests/test_anomaly_attachment_panel.py` |
| **status** | **complete** |
| **residual_notes** | Legacy Traditional-Chinese category strings remain readable on read paths per exec plan |

---

### 16 — Same-anomaly evidence links (analysis note + canonical Action)

| Field | Value |
| --- | --- |
| **design_source** | Design framework §6.6 `related_note_id` and corrective-action link; DailyWork maps new writes to canonical `related_action_id` instead of legacy `related_ca_id` |
| **implementation_paths** | `src/database/repository.py` (`create_anomaly_attachment`, cross-anomaly FK validation); `src/ui/widgets/anomaly_attachment_panel.py` (`AttachmentMetadataDialog` note/action combos); `src/services/event/_anomaly_workbench_service.py` (`update_attachment`) |
| **verification_gate** | `tests/test_attachments_phase2.py` (`test_attachment_can_link_same_anomaly_note_and_canonical_action`, `test_attachment_relationship_cannot_cross_anomaly_boundary`) |
| **status** | **complete** |
| **residual_notes** | `related_ca_id` column kept for legacy lineage only; new UI writes `related_action_id` |

---

### 17 — Physical storage, suffix allowlist, and legacy projection

| Field | Value |
| --- | --- |
| **design_source** | Exec plan Phase 2: writable root `data/attachments/anomaly/{anomaly_id}/`; approved document/image suffixes; path traversal rejection; `storage_state` + `legacy_physical` projection without silent metadata merge |
| **implementation_paths** | `src/services/attachment_manager.py`; `src/services/event/_anomaly_workbench_service.py` (`list_attachments` union projection); `src/database/repository.py` (`get_anomaly_overview_card` attachment count union) |
| **verification_gate** | `tests/test_attachments_phase2.py` (`test_attachment_metadata_rejects_path_components`, `test_overview_counts_unregistered_legacy_physical_file_once`, `test_workbench_service_projects_legacy_file_and_missing_metadata`, `test_service_file_import_registers_metadata_and_compensates_on_failure`); `Phase2AttachmentStorageTests` |
| **status** | **complete** |
| **residual_notes** | **deferred**: bulk reconciliation migration to register unregistered physical-only files as metadata rows (explicitly out of Phase 2; read projection only) |

---

### 18 — Workbench attachments tab write UI

| Field | Value |
| --- | --- |
| **design_source** | Design framework §6.6 upload form (file, category, description, revision, note/action links), list, delete confirmation, empty state |
| **implementation_paths** | `src/ui/widgets/anomaly_attachment_panel.py` (`EvidenceAttachmentPanel`); `src/ui/widgets/anomaly_management_page.py` (附件 tab); `src/services/event/_anomaly_workbench_service.py` (import/update/delete + audit) |
| **verification_gate** | `tests/test_anomaly_attachment_panel.py`; `tests/test_attachments_phase2.py` (`test_service_metadata_update_delete_and_audit_are_transactional`); native `scripts/verify_attachments_phase2_visual.ps1` (`workbench` attachments tab) |
| **status** | **complete** |
| **residual_notes** | None blocking Phase 2 |

---

### 19 — Read-model, export, and audit consumer compatibility

| Field | Value |
| --- | --- |
| **design_source** | Architecture workflow contract “Anomaly Workbench Read Model Parity”; design principle §1.4 Evidence Before Conclusion; exec plan Markdown broad projection / PDF image-only embed |
| **implementation_paths** | `src/database/repository.py` (`get_anomaly_overview_card`); `src/services/event/_anomaly_markdown.py`; `src/services/event_pdf_exporter.py`; `src/services/event/_anomaly_workbench_service.py` (`ATTACHMENT_CREATED/UPDATED/DELETED` audit) |
| **verification_gate** | `tests/test_attachments_phase2.py` (overview count, audit actions); `tests/test_anomaly_folder_creation.py` (markdown attachments); `tests/test_event_pdf_export.py` (PDF attachment HTML); overview parity tests |
| **status** | **partial-accepted** |
| **residual_notes** | `src/ui/widgets/close_anomaly_dialog.py` still uses legacy `AttachmentEditor` (image/captions closure path). Coexists with workbench metadata path; **does not block** Phase 2 completion. Unifying closure attachment UX is a separate follow-up (Phase 4 / closure UX) |

---

## Accepted residuals (cross-item)

| Topic | Disposition | Blocks Phase 2? |
| --- | --- | --- |
| Original 48-item titles 14–19 | Not in repo; this file is design-derived only | No |
| `related_ca_id` legacy column | Retained for rollback/lineage | No |
| Unregistered physical-only bulk register migration | Deferred; projection + union count only | No |
| `CloseAnomalyDialog` legacy `AttachmentEditor` | partial-accepted on item 19 | No |

## Phase boundaries

- **Phase 3a** (Root Cause write UI) and **Phase 3b** (multi-layer hypothesis schema) are outside this mapping.
- **Phase 4** owns remaining workbench header closure/reopen and overview quality-badge closure.

## If original list surfaces later

Run a delta audit against this design-derived map; do not retroactively claim this document matched the original titles without user-provided evidence.
