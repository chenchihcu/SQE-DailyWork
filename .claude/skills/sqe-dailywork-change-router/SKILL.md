---
name: sqe-dailywork-change-router
version: 1.1.0
description: 把 SQE DailyWork 的變更路由到正確的來源檔案與驗證 gate,在動 UI、資料契約、services、匯出、docs 或 tests 之前先分類。Use this skill 當要決定改哪裡、跑什麼驗證時。觸發詞包含「route」「change router」「驗證 gate」「該改哪」「該跑什麼檢查」「先分類」「services」「code-simplifier」「簡化」「safe-pass」。
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
- Python behavior changes: prefer `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1`.
- UI visual/CJK/font/screenshot work: use `scripts\qt_visual_probe.py` on native Windows Qt; offscreen is structural smoke only.
- If full verification is impractical, run the closest focused unittest and report the residual risk.

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
| List contract render | `src/ui/list_column_contract.py`, `src/ui/widgets/home_widget.py`, event/NCR list widgets | Keep ref_no-first / visit date fallback; do not merge event vs NCR column SSOT |

### Verification gate (safe-pass)

```
□ py_compile on touched modules
□ Focused unittest: stats, appearance, list-column, home-backlog, shared UI helpers
□ If stats UI changed: native `scripts/qt_visual_probe.py --target stats-stress` and `--target ncr-stats`
□ Background `scripts/verify.ps1` — do not block foreground on full suite
□ Tests after Zero-Noise cleanup: assert EmptyStateWidget / errorText / charts; not hidden insight_label text
```

## Guardrails

- Visual-evidence policy (Playwright / offscreen): authority is `.claude/rules/visual_evidence_rules.md` — do not restate it here.
- Do not run migration, `--apply`, direct `data/*.db` changes, or destructive cleanup without explicit user approval.
- Keep findings and delivery in `Changes / Impact / Verification / Residual risk / Next action` (mirrored mechanically by `.Codex/hooks/sqe-dailywork-stop.ps1` — update both together).

## 何時不要觸發

- SQLite schema / migration / 匯出契約的實質規則 → 用 `sqe-dailywork-data-contract`
- UI 視覺 / 截圖 / CJK 證據 → 用 `sqe-dailywork-visual-qa`
- 文件 / harness 漂移盤點 → 用 `sqe-dailywork-doc-gardening`

本技能只回答「改哪裡、跑什麼」的路由問題,不承載領域規則。
