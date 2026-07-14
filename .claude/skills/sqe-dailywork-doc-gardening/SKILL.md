---
name: sqe-dailywork-doc-gardening
version: 1.0.0
description: 唯讀(report-only)檢查 SQE DailyWork 的文件與 harness 漂移,範圍涵蓋 README、AGENTS、.cursor/rules、docs/harness、risk ledger 與驗證腳本。Use this skill 當要盤點文件是否與實作脫節時。觸發詞包含「文件漂移」「doc gardening」「harness drift」「README」「AGENTS」「risk ledger」「report-only」。
allowed-tools: Read, Grep, Glob
---

# SQE DailyWork Doc Gardening

Use this skill for SQE DailyWork documentation drift, harness consistency, and repo guidance checks.

## Report-Only Default

- Inspect and report drift; do not edit files unless the user explicitly asks for remediation.
- Check `AGENTS.md`, `.cursor/rules/agents_gateway.mdc`, `.codex/rules/project.rules`, `scripts/verify.ps1`, `scripts/harness_check.ps1`, `docs/harness/`, `docs/exec-plans/`, `docs/risk-ledger.md`, and `README.md`.
- Treat current code and tests as stronger evidence than older docs.

## Output Shape

Use:

- Changes observed
- Impact
- Verification status
- Residual risk
- Evidence paths
- Recommended next action
- Verification command to rerun after remediation

## Promotion Rule

Repeated issues should move first into tests or verification scripts, then source-of-truth docs, then repo `AGENTS.md`, and only then broader command rules or global guidance.

## 何時不要觸發

- 程式行為變更與驗證選擇 → 用 `sqe-dailywork-change-router`(路由)與 `scripts/verify.ps1`
- 單檔文件小修(直接改即可)不需啟動盤點
