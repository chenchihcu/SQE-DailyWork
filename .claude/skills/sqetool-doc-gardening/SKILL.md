---
name: sqetool-doc-gardening
description: Report-only SQETOOL documentation and harness drift check across README, AGENTS, .cursorrules, docs/harness, risk ledger, and verification scripts.
allowed-tools: Read, Grep, Glob
---

# SQETOOL Doc Gardening

Use this skill for SQETOOL documentation drift, harness consistency, and repo guidance checks.

## Report-Only Default

- Inspect and report drift; do not edit files unless the user explicitly asks for remediation.
- Check `AGENTS.md`, `.cursorrules`, `.codex/rules/project.rules`, `scripts/verify.ps1`, `scripts/harness_check.ps1`, `docs/harness/`, `docs/exec-plans/`, `docs/risk-ledger.md`, and `README.md`.
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
