# SQE DailyWork 全量 48 項七階段導入

Plan status: active — Phase 2 completed; Phase 3/4 pending

## Goal

依使用者核准的七階段計畫導入案件工作台、證據鏈、供應商視角、
Repeat Issue、營運分析與報告能力。每一階段必須完成實作、文件同步與
必要驗證後停止；只有使用者回覆精確的 `繼續` 才可執行上一階段的正式
資料 Promotion Gate（如適用）並進入下一階段。

## Fixed boundaries

- 應用維持單機 PySide6 + SQLite；不導入 Web、ORM 或多人雲端架構。
- `anomalies.status` 維持 `待處理 / 已結案`；工作階段由 canonical read model 推導。
- 正式 `data/sqe_v2.db` 與正式附件目錄不供測試、visual probe 或 fixture 使用。
- 既有未提交差異全部視為使用者所有；不 reset、不還原、不清理。
- 以單一 writer 執行；不啟動平行寫入。
- schema promotion 使用已驗證備份、transactional/idempotent migration、
  integrity/FK/reconciliation、focused smoke 與整體 rollback unit。
- 舊 action tables 在本計畫內保留為 rollback snapshot，不 DROP。

## Baseline and rollback point

- Baseline captured: 2026-08-24（Phase 1 開始前）。
- 使用者既有 dirty paths：`.gitignore`、`.opencode/`、`brain/`、
  `docs/harness/ai-rules-compatibility.md`、
  `docs/harness/source-baseline-manifest.md`、
  `scripts/button_audit_report.py`、`scripts/harness_check.ps1`。
- Phase 1 的 canonical implementation paths 在開始前沒有既有差異。
- 正式 promotion rollback：還原 promotion 前 SQLite online backup，並啟動前一可用版本；
  不使用不完整 reverse SQL 修補正式資料。
- Phase 1 完成前不修改正式 DB；本階段所有 migration/backfill/reconciliation
  僅在 in-memory、temporary disposable DB 與正式 DB 的唯讀複本驗證。

## RCA

目前 next action 與 corrective action 分別由 `anomaly_actions`、
`corrective_actions` 及兩套 service/API 管理，狀態語意也把「執行」與
「有效性」混在一起；`effectiveness_verifications` 與附件關聯又直接依賴
舊 corrective-action ID。若先擴充 UI，會固化雙模型並使 Overview、清單、
Timeline 與後續 exporters 各自重算。Phase 1 因此先建立 canonical
`case_actions` + append-only `action_verifications`，完成 deterministic lineage
與單一 transactional service，再接 UI。

### Phase 1 premature-promotion incident and containment

- Observed: 2026-08-24 15:32，正式 DB 出現
  `sqe_v2_backup_case_actions_v1_20260824_153227.db`；此命名只由明示
  Promotion CLI 的 apply path 產生。正式 DB 當時為 25 tables／317 rows，
  其中 canonical Action tables 為 14／0／14 rows；遷移前備份為
  22 tables／288 rows。現有紀錄不足以唯一識別發出命令的 caller，維持
  `UNKNOWN`，不猜測。
- Data RCA: 唯讀逐表 hash 證明所有既有業務欄位一致；唯一額外差異是
  `monthly_stats_cache.updated_at`，其月份、visit count 與 closed-anomaly count
  完全一致。沒有 migration 後新 Action、附件關聯錯配或 FK violation。
- Harness RCA: 原 verification 沒有在 command 前後鎖定正式 DB 的完整邏輯
  fingerprint；原 Phase 1 focused wrapper 也未建立 `SQE_DB_PATH` disposable
  copy，因此無法 fail closed 證明正式 DB 完全未被觸及。
- Fix: repository 依 `PRAGMA database_list` main path 阻擋正式 migration；
  Promotion 同時要求兩個 marker；正式 DB 缺 schema 時在 writable bootstrap
  前先 read-only fail closed。Focused／Full／native visual／baseline refresh 全部
  使用 disposable copy 並驗證正式 schema + 全表資料 fingerprint 前後相同。
- Recovery evidence: 無 SQE/Python process 後，先建立 verified incident snapshot，
  再以 online backup 回復。正式 DB 與遷移前備份的 logical state SHA-256 均為
  `8089f1248094be31e2f301677aee0bbad40d274506c624e043f221758a461db1`；
  `integrity_check=ok`、`foreign_key_check=[]`、canonical schema 不存在。
- Destination: guards/tests → repository、connection、backup/fingerprint helpers；
  operational record → 本 exec plan 與 `docs/risk-ledger.md`。

## Phase map

| Phase | Scope | Schema | Status |
| --- | --- | --- | --- |
| 1 | 統一 Action 模型與執行閉環（02、03、07、08、09） | yes | completed — formal Promotion verified |
| 2 | 附件與 Evidence 基礎契約（14–19） | yes | completed — formal Promotion verified; items 14–19 design-derived mapping documented |
| 3 | Hypothesis、多層原因與證據鏈（20–23） | yes | pending |
| 4 | 案件工作台完整 UI 閉環（01、04–06、10–13、24） | no | pending |
| 5 | Supplier 360 與 Repeat Issue（25–30） | yes | pending |
| 6 | 作業清單、Manager View 與分析（31–36） | no | pending |
| 7 | 匯出、報告、全系統驗收與發布（37–48） | no | pending |

## Phase 1 implementation contract

- 新增 canonical `case_actions`、`action_verifications` 與 legacy mapping。
- deterministic migration：保留不碰撞 ID；碰撞時 anomaly action 保留原 ID，
  corrective action 使用固定 namespace UUIDv5。
- 遷移舊 verification 與 `anomaly_attachments.related_ca_id` 關聯；legacy 狀態
  缺少驗證 row 時建立明確的 `LEGACY_STATUS` incomplete record，不偽造證據。
- 新程式只使用 `create/list/get/update/complete/cancel_case_action` 與
  `record/list_action_verifications`。
- Action execution status 固定為 `已規劃 / 執行中 / 已完成 / 已取消`；
  verification status 由類型、required flag 與最新 verification 推導。
- 所有 Action 狀態變更與 audit log 在單一 transaction 中完成。
- `get_anomaly_overview_card()` 維持 read-model SSOT，改讀 canonical tables。
- 既有正式 DB 未升級時 fail closed 並顯示「需要完成資料升級」，不得自動 migration。

## Phase 1 gates

- Legacy mapping、ID preservation/collision、mapping reference、attachment/verification migration。
- Migration idempotency、integrity、foreign keys、row/relation reconciliation。
- Action type/verification constraints、complete/cancel/update/overdue/current ordering。
- Overview/service/UI parity 與完整 disposable DB lifecycle fixture。
- Focused tests、Full verify、harness check。
- Native Windows Qt `workbench`、`dialog-density` at 100% / 125% / 150% DPI。

## Phase 2 implementation contract — foundation + workbench attachment UI

Item-level mapping for 14–19 is documented in
[2026-08-26-phase2-items-14-19-mapping.md](2026-08-26-phase2-items-14-19-mapping.md)
(`mapping_type: design-derived`; not a restoration of the original 48-item titles).
The contract below records only repo-confirmed foundation behavior.

- `anomaly_attachments` is the SQLite metadata contract. Existing
  `related_ca_id` remains a legacy compatibility column; new relationships use
  canonical `related_action_id` and optional `related_note_id`. System metadata
  includes `file_type` and `uploaded_by`; attachment categories retain the nine
  design-framework values, while legacy Traditional-Chinese labels remain
  readable.
- The writable file root remains
  `data/attachments/anomaly/{anomaly_id}/`, resolved through the existing
  `SQE_DB_PATH` data directory. `captions.json` and legacy image-only APIs stay
  readable. New evidence storage accepts the approved document/image suffixes,
  rejects path traversal, and exposes legacy physical-only files as an
  explicit read projection until a separately approved reconciliation migration
  registers them.
- Workbench metadata and physical storage are not silently merged into a new
  guessed row: DB rows preserve `storage_state=present/missing`, while
  unregistered physical files are marked `legacy_physical=true`. Overview
  attachment counts use the union by stored filename so one file is counted
  once. Markdown snapshots use the broad stored-file projection; PDF continues
  to embed image attachments only.
- The workbench **附件** tab uses `EvidenceAttachmentPanel` for upload,
  metadata edit, note/action linking, and legacy physical projection. Phase 4
  still owns remaining header closure/reopen and overview quality-badge
  closure; it does not re-implement the attachment upload panel.
- The new contract migration has a read-only preview and an atomic apply
  helper (`scripts/migrate_anomaly_attachments_contract_v1.py`,
  `scripts/apply_anomaly_attachments_promotion.ps1`). Fresh/disposable databases
  may install it automatically; an existing formal database must remain untouched
  until a separate approved Promotion Gate supplies backup, rollback,
  reconciliation and focused/full evidence.

## Phase 2 evidence gates

- In-memory schema preview/apply/idempotency, note/action same-anomaly FK
  validation, legacy physical-file union count, and path traversal regression:
  `tests/test_attachments_phase2.py`.
- Workbench attachment panel, action/overview regression and source compile
  checks must remain green. Attachment manager, editor, Markdown and PDF
  consumers are focused compatibility gates; scratch `SQE_DB_PATH` is required
  for file tests.
- Disposable formal-fingerprint wrappers:
  `scripts/verify_attachments_phase2.ps1`,
  `scripts/verify_attachments_phase2_full.ps1`,
  `scripts/verify_attachments_phase2_visual.ps1`.
- Full `scripts/verify.ps1` is green for the current source snapshot, including
  the native belt and required pixel baselines. Native visual evidence includes
  `workbench` (attachments tab) and `dialog-density` at 100% / 125% / 150% DPI.

## Phase 2 completion evidence

- Date: 2026-08-26
- Formal DB preview: `anomaly_attachments_contract_v1` `ready: true` before apply
- Formal Promotion apply: `skipped: true` (idempotent no-op; schema/meta already present)
- Verified backup:
  `data/sqe_v2_backup_anomaly_attachments_v1_20260826_155811.db`
- Formal logical fingerprint (before == after):
  `c44e5c20c75a3fbabbf0c95c56b2328a8b36e76eb65fc549521a6c3a68257aa3`
- Focused gate: `scripts/verify_attachments_phase2.ps1` PASS (53 tests)
- Native visual gate: `scripts/verify_attachments_phase2_visual.ps1` PASS
  (`workbench` + `dialog-density` @ 1.0 / 1.25 / 1.5)
- Full gate: `scripts/verify_attachments_phase2_full.ps1` PASS
  (`scratch/verify-full-log-final.txt`)
- Harness: `scripts/harness_check.ps1` PASS (live membership `625`)
- Audit report: `scratch/phase2r-attachment-audit.json`
- Items 14–19 mapping:
  `docs/exec-plans/active/2026-08-26-phase2-items-14-19-mapping.md`
  (design-derived; item 19 partial-accepted for legacy closure attachment path)

## Stop rule

Phase 2 Promotion gate 已完成（2026-08-26）。下一停點由使用者選擇：

- **Phase 3**：Hypothesis／多層原因／證據鏈（需先寫契約；3a Root Cause 1:1 寫入 UI 已部分落地）
- **Phase 4**：案件工作台完整 UI 閉環（header 結案／重開、概況品質結論徽章；無新 schema）

不得在未另開核准的情況下 DROP 舊 action tables 或發明 14–19／20–23 逐項對照。
