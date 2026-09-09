---
name: sqe-dailywork-change-router
version: 1.2.0
description: "把 SQE DailyWork 變更路由到正確來源檔與驗證 gate（UI、資料契約、services、docs、tests、code-simplifier safe-pass）。Use when 要決定改哪裡、跑什麼驗證、route、change router、驗證 gate 或 code-simplifier。Do NOT use for 實際改 UI 佈局（改用 sqe-dailywork-ui-ux-flow-optimizer）、改 schema（改用 sqe-dailywork-data-contract）或文件盤點（改用 sqe-dailywork-doc-gardening）。"
allowed-tools: Read, Grep, Glob
---

# SQE DailyWork Change Router

Use this skill before implementing SQE DailyWork changes that may touch more than one layer.

## Routing Rules

- UI or visible copy: read `AGENTS.md`, `README.md`, `.cursor/rules/agents_gateway.mdc`, and the relevant `src/ui/` widget or `src/ui/popup_i18n.py`.
- Data contract, migration, visit/anomaly behavior, or storage path: read `README.md`, `docs/risk-ledger.md`, `src/database/repository.py`, and focused tests before changing code.
- Service or export behavior: read the related `src/services/` module plus tests for PDF, Excel, PPTX, or event-service behavior.
- Harness, Codex automation, or repo guidance: read `docs/harness/README.md`, `docs/harness/doc-gardening.md`, `scripts/harness_check.ps1`, and this repo's `AGENTS.md`.

## Verification Selection

- Harness/config/docs-only automation changes: run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/harness_check.ps1`.
- Python behavior changes (no visible UI): prefer `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1`; if impractical, run the closest focused unittest and report the gap under `Residual risk`.
- **UI visual closure gate** (visible `src/ui/` layout, typography, CJK, cards, comparison panels): read `sqe-dailywork-visual-qa`, run the mapped native `scripts\qt_visual_probe.py --target` on Windows, read the PNG, and require probe JSON `visual_trustworthy: true`. Offscreen unittest is structural smoke only. **Do not mark the task done or list skipped probe under `Residual risk`** — use `not verified` instead.
- Global QSS/theme changes: run every touched target or `scripts\qt_visual_belt.py`.

### UI surface → probe target

| Changed surface / file | Probe target |
| --- | --- |
| `repeat_issues_management_page.py` | `repeat-issues-management` |
| `anomaly_management_page.py`, workbench tabs | `workbench` |
| `repeat_issues_panel.py` | `workbench` |
| `stats_view_widget.py` | `stats-stress` |
| `ncr_stats_widget.py` | `ncr-stats` |
| `event_list_widget.py` | `event-list` |
| `supplier_360_page.py` | `supplier-360` |
| `manager_view_page.py` | `manager-view` |
| `theme.py`, global QSS | all touched targets or `qt_visual_belt.py` |

Example (repeat issues page):

```
.venv\Scripts\python.exe scripts\qt_visual_probe.py --target repeat-issues-management --min-width --scale 1.0,1.25,1.5 --output Outputs\visual_qa\repeat-issues-management\probe.png
```

## `/code-simplifier` Safe-Pass Router

Use when the user asks for behavior-preserving simplification (`/code-simplifier`, `safe-pass`, `全 src 簡化`). Read `AGENTS.md` Zero-Noise + workflow split rules and `docs/harness/closed-loop-log.md` **Code-Simplifier Safe-Pass Entry** before editing.

### Scope gate (ask if unclear)

| Depth | Allowed | Forbidden |
| --- | --- | --- |
| **safe-pass** (default) | DRY helpers, rg-proven dead code, remove hide+compute paths, contract-driven UI loops | Split god-files, delete compat shims, merge supplier-event / NCR queries or list contracts |
| **deep-refactor** | Structural splits | Requires explicit user approval + exec plan |

### Pre-edit checklist

```
□ Confirm scope (modified files / all src / report-only) and depth (safe-pass / deep-refactor)
□ git status — single writer; exclude data/*.db, logs, scratch, __pycache__
□ Classify candidates: can change | compat-only keep | do not touch
□ rg symbol before delete — zero callers repo-wide
```

### Layer routing (safe-pass)

| Target | Typical files | Notes |
| --- | --- | --- |
| Service DRY | `src/services/event/_query_service.py`, `src/services/*_codec.py`, `src/services/appearance_preferences_service.py` | Preserve public APIs and mock import paths |
| Confirmed dead code | `src/database/repository.py` private stubs, unused UI helpers | Never delete `event_service.py`, `defect_form_shim.py`, `theme.py` re-exports without migration plan |
| Zero-Noise stats UI | `src/ui/widgets/stats_view_widget.py`, `src/ui/widgets/ncr_stats_widget.py` | Remove insight/info-banner widgets **and** `_set_insights` / `_generate_insights`; do not `.hide()` only |
| List contract render | `src/ui/list_column_contract.py`, event/NCR list widgets | Keep ref_no-first / visit date fallback; do not merge event vs NCR column SSOT |

### Verification gate (safe-pass)

```
□ py_compile on touched modules
□ Focused unittest: stats, appearance, list-column, supplier_event_queues, top_nav_compact_height, shared UI helpers
□ If stats UI changed: native `scripts/qt_visual_probe.py --target stats-stress` and `--target ncr-stats`
□ Background `scripts/verify.ps1` — do not block foreground on full suite
□ Tests after Zero-Noise cleanup: assert EmptyStateWidget / errorText / charts; not hidden insight_label text
```

## Guardrails

- Visual-evidence policy (Playwright / offscreen): authority is `.claude/rules/visual_evidence_rules.md` — do not restate it here.
- Do not run migration, `--apply`, direct `data/*.db` changes, or destructive cleanup without explicit user approval.
- Keep findings and delivery in `Changes / Impact / Verification / Residual risk / Next action` (mirrored mechanically by `.Codex/hooks/sqe-dailywork-stop.ps1` — update both together). `Verification` must cite executed probe commands/JSON/PNG paths for UI work; skipped mandatory checks belong in `not verified`, not `Residual risk`.

## 何時不要觸發

- SQLite schema / migration / 匯出契約的實質規則 → 用 `sqe-dailywork-data-contract`
- UI 視覺 / 截圖 / CJK 證據 → 用 `sqe-dailywork-visual-qa`
- 文件 / harness 漂移盤點 → 用 `sqe-dailywork-doc-gardening`

本技能只回答「改哪裡、跑什麼」的路由問題,不承載領域規則。
