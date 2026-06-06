# Doc Gardening

Doc gardening keeps SQE DailyWork's repo knowledge useful for agent work without turning docs into a large manual.

## Weekly Report-first Check

Inspect:

- `AGENTS.md`
- `CLAUDE.md`
- `.agents/rules/agents_gateway.md`
- `.cursor/rules/agents_gateway.mdc`
- `.codex/rules/project.rules`
- `scripts/verify.ps1`
- `scripts/harness_check.ps1`
- `docs/harness/`
- `docs/harness/ai-rules-compatibility.md`
- `docs/harness/source-baseline-manifest.md`
- `docs/exec-plans/`
- `docs/risk-ledger.md`
- `README.md`

Also check:

- Source-control boundary: repo root, tracked-file baseline, `git status --short`, and `.gitignore` coverage for generated data/output/local tool state.
- Source baseline manifest: check `source_baseline_status`, `recommended-track-list`, `recommended-ignore-list`, `needs-user-decision-list`, `do-not-track-list`, and role review results.
- AI rules size budget: Codex `AGENTS.md` under 32 KiB default project-doc budget, Claude `CLAUDE.md` under 200 lines, Cursor rules under 500 lines, and Antigravity rules under 12,000 characters.
- SQE DailyWork Claude automation: `.claude/settings.json`, `.claude/hooks/`, `.claude/skills/`, `.claude/agents/`, and `docs/harness/claude-code-automation.md`.
- Windows command reliability: prefer `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe` in verification notes when short `powershell` is not available through PATH.
- One-writer safety: report if automation would run in a noisy checkout or before a reviewed source baseline commit exists.
- Automation self-check: confirm the active TOML is one-project scoped, `ACTIVE`, `local`, report-only, and not a duplicate automation.

Report only:

- Drift findings or no-drift summary
- Changes observed
- Impact
- Verification status
- Residual risk
- Evidence paths
- Recommended next action
- Verification command to rerun after remediation

Verification command:

```powershell
C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\harness_check.ps1
```

Do not edit files from automation unless the user explicitly asks for remediation.

## Promotion Rule

When the same issue appears repeatedly, promote the learning in this order:

1. Focused test or verification script.
2. Repo source-of-truth doc.
3. Repo `AGENTS.md` pointer or guardrail.
4. Project rules if command behavior is involved.
5. Global Codex baseline only when the rule is cross-project.
