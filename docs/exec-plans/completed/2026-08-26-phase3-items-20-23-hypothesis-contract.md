# Phase 3 項目 20–23 對照與 Hypothesis／證據鏈 Schema RFC

Plan status: active — design-derived traceability + schema contract for 48-item rollout Phase 3

## Scope and methodology

- `mapping_type`: **design-derived**
- This document does **not** restore the original user-approved 48-item titles for
  items 20–23; those titles were never committed to the repository.
- Each item below is derived from:
  - [SQE Incident Management UI Design Framework v0.1 §6.3、§1.4](../../SQE_Incident_Management_UI_Design_Framework_v0.1.md) (Investigation / Evidence Before Conclusion)
  - [architecture-workflow-contract.md](../../architecture-workflow-contract.md) (supplier-event sub-tables)
  - [2026-08-24-case-workbench-48-item-rollout.md](2026-08-24-case-workbench-48-item-rollout.md) Phase 3 scope
  - Current implementation inventory (2026-08-26)
- **Phase 3a** (1:1 Root Cause + analysis-note write UI) is inventoried here but
  not re-implemented; **Phase 3b** (this document) owns multi-layer hypothesis
  schema and evidence-chain read-model contract only.

## Current state (Phase 3a inventory)

### Schema (implemented)

| Table / column | Role | Notes |
| --- | --- | --- |
| `anomaly_analysis_notes` | Append-only investigation notes | `evidence_type` ∈ `FACT/INFERENCE/ASSUMPTION/UNKNOWN`; `attachment_count` column exists but is **not** recomputed when `anomaly_attachments.related_note_id` changes |
| `anomaly_root_causes` | 1:1 per `anomaly_id` (`UNIQUE`) | Status ∈ `尚未開始/調查中/提案/已驗證/無法確認`; `not_established_reason` required when `無法確認` |
| `anomaly_attachments.related_note_id` | Note ↔ file link | Phase 2 contract; same-anomaly FK enforced |
| `anomaly_attachments.related_action_id` | Action ↔ file link | Canonical Action lineage (Phase 1) |

### Service boundary (implemented)

- `src/services/event/_anomaly_workbench_service.py`: `create_analysis_note`,
  `list_analysis_notes`, `get_root_cause`, `save_root_cause`, attachment CRUD,
  `list_timeline`, overview delegation.
- Canonical Action writes remain in `_case_action_service` only.

### UI (partial-complete — Phase 3a)

| Surface | Path | Status |
| --- | --- | --- |
| Analysis tab list + actions | `src/ui/widgets/anomaly_management_page.py` (`_build_analysis_tab`) | Read list; buttons「新增分析紀錄」「編輯根本原因」 |
| Add analysis note dialog | `src/ui/widgets/anomaly_note_dialog.py` | Create-only; evidence type combo |
| Edit root cause dialog | `src/ui/widgets/anomaly_root_cause_dialog.py` | Full 1:1 upsert |
| Visual probe | `workbench-page-analysis` | Baseline in `tests/visual_baseline/workbench/` |

**Gaps vs design framework §6.3**

- Analysis list uses plain text rows, not per-note cards with evidence badge styling.
- `attachment_count` on notes may stay `0` after linking files via attachment panel
  (no repository hook to refresh denormalized count).
- No inline「新增紀錄」form on the tab (dialog-only; acceptable for desktop density).
- Root cause card on tab shows subset of fields (no `validation_evidence`,
  `conclusion_note`, `not_established_reason` in read view).

### Read model (partial)

- `get_anomaly_overview_card()` exposes `root_cause_status`, `has_analysis_notes`,
  case-level `attachment_count` — **no** hypothesis summary, **no** per-note
  attachment rollup, **no** unified evidence-chain projection.
- `list_anomaly_timeline()` synthesizes `ROOT_CAUSE_UPDATED` from root-cause row
  when audit log lacks it; analysis-note events depend on audit log entries, not
  a dedicated evidence-chain SSOT.

### Tests (Phase 3a)

| Module | Coverage |
| --- | --- |
| `tests/test_anomaly_workbench_dialogs.py` | `AnomalyNoteDialog`, `AnomalyRootCauseDialog` submit wiring |
| `tests/test_anomaly_workbench_repository.py` | Root cause upsert / `not_established_reason` validation |
| `tests/test_anomaly_model_boundary.py` | Cross-line write guard for `anomaly_analysis_notes` |
| `tests/test_attachments_phase2.py` | `related_note_id` FK and same-anomaly boundary |

### Phase 3a verdict

**partial-complete** — write path for notes + 1:1 root cause exists; evidence-chain
read model and multi-layer hypothesis remain **not started**.

---

## Item map (design-derived 20–23)

| # | derived_title | status |
| --- | --- | --- |
| 20 | Analysis note create + evidence_type workbench closure | partial-complete |
| 21 | Evidence chain: note ↔ attachment same-case links and read model | partial |
| 22 | Multi-layer hypothesis (5-Why / cause tree) data model | **implementation complete** |
| 23 | Hypothesis → Root Cause promotion, validation, and audit semantics | **implementation complete** |

---

### 20 — Analysis note create + evidence_type workbench closure

| Field | Value |
| --- | --- |
| **design_source** | Design framework §6.3 analysis notes: append-only, `content` required, `evidence_type` optional (`FACT/INFERENCE/ASSUMPTION/UNKNOWN`), author + date display |
| **implementation_paths** | `src/database/repository.py` (`create_anomaly_analysis_note`, `list_anomaly_analysis_notes`); `src/ui/widgets/anomaly_note_dialog.py`; `src/ui/widgets/anomaly_management_page.py` (`_build_analysis_tab`, `_open_add_note_dialog`); `src/services/event/_anomaly_workbench_service.py` |
| **verification_gate** | `tests/test_anomaly_workbench_dialogs.py` (`AnomalyNoteDialogTests`); `tests/test_anomaly_model_boundary.py` |
| **status** | **partial-complete** |
| **residual_notes** | No note edit/delete (append-only by design). Per-note `attachment_count` denormalization not kept in sync with `related_note_id` links. Analysis tab lacks design-framework card/badge layout (functional text list only). |

---

### 21 — Evidence chain: note ↔ attachment same-case links and read model

| Field | Value |
| --- | --- |
| **design_source** | Design framework §1.4 Evidence Before Conclusion; §6.3 attachment badge on notes; Phase 2 attachment contract (`related_note_id`) |
| **implementation_paths** | `anomaly_attachments.related_note_id` + repository FK validation; `src/ui/widgets/anomaly_attachment_panel.py` (note link on upload/edit); `get_anomaly_overview_card` case-level attachment count |
| **verification_gate** | `tests/test_attachments_phase2.py` (`test_attachment_can_link_same_anomaly_note_and_canonical_action`, cross-anomaly rejection) |
| **status** | **partial** |
| **residual_notes** | **No SSOT evidence-chain projection** tying note → attachment → (future) hypothesis → root cause. Timeline and overview do not expose chain depth or per-note attachment rollup. Planned: `list_anomaly_evidence_chain(anomaly_id)` read helper (see Schema RFC). |

---

### 22 — Multi-layer hypothesis (5-Why / cause tree) data model

| Field | Value |
| --- | --- |
| **design_source** | Exec plan Phase 3 title「Hypothesis、多層原因」; design framework mentions 5-Why only as `validation_method` placeholder — **insufficient** to infer tree schema; this item is **design-derived extension** |
| **implementation_paths** | `src/database/anomaly_hypothesis_repository.py`; `src/ui/widgets/anomaly_hypothesis_dialog.py`; `src/services/event/_anomaly_workbench_service.py`; `get_anomaly_overview_card()` hypothesis metrics |
| **verification_gate** | `tests/test_hypothesis_phase3.py`; `scripts/verify_hypothesis_phase3.ps1` |
| **status** | **implementation complete** |
| **residual_notes** | Items 20–21 remain partial-complete (analysis note UI / evidence-chain rollup). Hypothesis tree schema, promotion, and audit are verified in Phase 3 harness. |

---

### 23 — Hypothesis → Root Cause promotion, validation, and audit semantics

| Field | Value |
| --- | --- |
| **design_source** | Design framework §6.3 Root Cause status machine; §1.4 separation of conclusion badge vs supporting evidence; exec plan Phase 3 evidence chain |
| **implementation_paths** | **Partial via 3a:** `upsert_anomaly_root_cause` + `AnomalyRootCauseDialog`. **Missing:** promotion from adopted hypothesis, `promoted_from_hypothesis_id` lineage, audit `HYPOTHESIS_*` event kinds |
| **verification_gate** | **Planned:** promotion transaction tests + audit log parity in `tests/test_hypothesis_phase3.py` |
| **status** | **not started** |
| **residual_notes** | Must not auto-set Root Cause to `已驗證` on hypothesis adoption without explicit user action and validation fields. |

---

## Schema RFC

### Problem statement

DailyWork can record unstructured analysis notes and a single Root Cause per
anomaly, but cannot represent a **structured multi-layer Why tree** or a **single
read model** for evidence chain navigation. Implementing UI first would fork
overview, timeline, Markdown, and export consumers.

### Recommendation

**Adopt Option A** — dedicated `anomaly_hypotheses` table. Defer Option B unless
a future session explicitly accepts note/hypothesis semantic mixing.

### Option A — `anomaly_hypotheses` (recommended)

```sql
CREATE TABLE anomaly_hypotheses (
    id TEXT PRIMARY KEY,
    anomaly_id TEXT NOT NULL,
    parent_hypothesis_id TEXT REFERENCES anomaly_hypotheses(id),
    level INTEGER NOT NULL DEFAULT 1 CHECK (level BETWEEN 1 AND 5),
    sort_order INTEGER NOT NULL DEFAULT 0,
    statement TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '提案'
        CHECK (status IN ('提案','調查中','支持','反證','採納','淘汰')),
    evidence_type TEXT NOT NULL DEFAULT 'UNKNOWN'
        CHECK (evidence_type IN ('FACT','INFERENCE','ASSUMPTION','UNKNOWN')),
    linked_note_id TEXT REFERENCES anomaly_analysis_notes(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (anomaly_id) REFERENCES anomalies(id) ON DELETE CASCADE
);
CREATE INDEX idx_anomaly_hypotheses_anomaly
    ON anomaly_hypotheses(anomaly_id, level, sort_order);
CREATE INDEX idx_anomaly_hypotheses_parent
    ON anomaly_hypotheses(parent_hypothesis_id);
```

**Root Cause relationship (preserve 1:1)**

- Keep `anomaly_root_causes` as the **single conclusion record** per anomaly.
- Add optional column on root cause (implementation session):
  `promoted_from_hypothesis_id TEXT REFERENCES anomaly_hypotheses(id)`.
- **Promotion flow (spec):** user selects one `採納` hypothesis → service copies
  `statement` into root cause, sets root-cause status to `提案` or `調查中`
  (never auto-`已驗證`), copies `evidence_type` into validation narrative only
  as helper text — user must still fill `validation_method` / `validation_evidence`
  before `已驗證`.
- Hypothesis row remains; status stays `採納` with audit `HYPOTHESIS_PROMOTED`.

**Attachment contract (Phase 2 extension — separate migration meta)**

- Phase 2 keeps `related_note_id` / `related_action_id` only.
- Phase 3 implementation may add `related_hypothesis_id` on `anomaly_attachments`
  with same-anomaly FK guard (mirror note/action pattern).
- Files may link to note **or** hypothesis, not both (CHECK or service validation).

**Migration meta**

- Key: `anomaly_hypotheses_v1` (schema version `1`).
- Pattern: read-only preview, disposable/fresh auto-install, formal DB
  fail-closed until Promotion CLI (mirror `anomaly_attachments_contract_v1`).

### Option B — extend `anomaly_analysis_notes` (not recommended)

Add `parent_note_id`, `hypothesis_role` (`WHY_LAYER` vs `FREE_NOTE`), `why_level`.

| Pros | Cons |
| --- | --- |
| No new table | Mixes free-form investigation log with structured Why tree |
| Reuses note UI patterns | Timeline/export cannot distinguish roles without fragile heuristics |
| | Harder to enforce tree depth (5-Why) and status machine on notes |
| | Promotion to Root Cause requires parsing note graph |

**Verdict:** reject for default path; document only as fallback if schema
surface area must be minimized.

### Invariants (all options)

1. **Same-anomaly FK:** `anomaly_hypotheses`, `linked_note_id`, and
   `related_hypothesis_id` must reference rows with matching `anomaly_id`.
2. **No cross-case links:** service layer rejects cross-anomaly note/hypothesis/
   attachment/action pairing (existing Phase 2 pattern).
3. **Append-only audit:** hypothesis create/update/status change and promotion
   write `anomaly_audit_logs`; timeline consumes audit SSOT (no double count).
4. **No fabricated verification:** adopting a hypothesis must not auto-create
   `action_verifications` or set root cause to `已驗證`.
5. **Tree integrity:** `parent_hypothesis_id` must not introduce cycles; max depth
   5 (enforced in service on insert/move).
6. **Soft-delete:** if hypotheses support deactivation later, use `is_active`
   pattern consistent with AGENTS.md (not in v1 unless required).

### Read model SSOT (planned API)

New repository helper (name fixed for implementation session):

`list_anomaly_evidence_chain(conn, anomaly_id) -> list[dict]`

Ordered nodes, each:

| Field | Source |
| --- | --- |
| `node_type` | `analysis_note` \| `attachment` \| `hypothesis` \| `root_cause` |
| `node_id` | primary key |
| `ts` | `created_at` or attachment `uploaded_at` |
| `summary` | truncated statement/content/file_name |
| `evidence_type` | note/hypothesis when applicable |
| `status` | hypothesis or root-cause status when applicable |
| `parent_id` | for hypothesis tree only |
| `attachment_count` | **computed** from `COUNT(*)` on `anomaly_attachments` where `related_note_id` or `related_hypothesis_id` matches |

**Overview card extensions (planned fields)**

- `hypothesis_count`: active hypotheses for anomaly
- `hypothesis_deepest_level`: max `level` among non-`淘汰` rows
- `hypothesis_adopted`: exists row with `status = '採納'`
- `root_cause_status`: unchanged (existing SSOT)
- Fallback: when no hypotheses table / empty, fields default to `0` / `false` /
  existing root-cause behavior (backward compatible)

**Timeline**

- New audit kinds: `HYPOTHESIS_CREATED`, `HYPOTHESIS_STATUS_CHANGED`,
  `HYPOTHESIS_PROMOTED` (enum in repo_helpers; UI shows zh-TW labels).
- Do not synthesize hypothesis events from row snapshots unless audit missing
  (mirror current `ROOT_CAUSE_UPDATED` fallback pattern).

### Out of scope (Phase 3 RFC)

- Repeat Issue similarity (Phase 5)
- Manager View / operational queues (Phase 6)
- Excel/PDF embedded hypothesis tree PNG (Phase 7)
- Dropping `anomaly_actions` / `corrective_actions` legacy tables

---

## Implementation gate outline (next coding session — not this spec session)

| Gate | Planned artifact |
| --- | --- |
| Schema migration | `preview_anomaly_hypotheses_v1` / `migrate_anomaly_hypotheses_v1` in `repository.py`; optional `related_hypothesis_id` attachment column migration |
| Disposable tests | `tests/test_hypothesis_phase3.py` — preview/apply/idempotency, tree FK, cycle rejection, promotion transaction, audit emission |
| Repository/service | `list/create/update_hypothesis`, `promote_hypothesis_to_root_cause`, `list_anomaly_evidence_chain`; `_anomaly_workbench_service` wrappers |
| Focused wrapper | `scripts/verify_hypothesis_phase3.ps1` — formal fingerprint before/after on disposable copy |
| Promotion CLI | `scripts/migrate_anomaly_hypotheses_v1.py`, `scripts/apply_anomaly_hypotheses_promotion.ps1` (dry-run default; `-Apply` requires exact user `繼續` + dual markers) |
| UI | Analysis tab hypothesis tree + promote action (**Phase 3 implementation**, not 3b spec) |
| Docs sync | `architecture-workflow-contract.md`, exec plan Phase 3 status → implementation |
| Native visual | Extend `workbench-page-analysis` baseline after UI lands |

**Stop rule after implementation:** report `Changes / Impact / Verification /
Residual risk / Next action`; do not run formal Promotion without user `繼續`.

---

## Accepted residuals

| Topic | Disposition |
| --- | --- |
| Original 48-item titles 20–23 | Not in repo; this file is design-derived only |
| Option B (note-as-hypothesis-node) | Documented, not recommended |
| Phase 3a UI polish (badges, inline form) | May be picked up in Phase 4 workbench closure or Phase 3 implementation |
| Per-note `attachment_count` denormalization | Fix in implementation session via computed read model (preferred) or trigger |

## If original list surfaces later

Run delta audit against this design-derived map; do not retroactively claim this
document matched the original titles without user-provided evidence.
