# SQE DailyWork Harness

This folder is the repo-local system of record for closed-loop Codex work. It keeps agent guidance short while making deeper project context discoverable and verifiable.

## Sources

- Repo instructions: `AGENTS.md`
- Cursor gateway: `.cursor/rules/agents_gateway.mdc`
- Antigravity gateway: `.agents/rules/agents_gateway.md`
- AI rules compatibility register: `docs/harness/ai-rules-compatibility.md`
- Verification gate: `scripts/verify.ps1`
- Harness structure check: `scripts/harness_check.ps1`
- Native Qt visual probe: `scripts/qt_visual_probe.py`
- Native Qt three-DPI belt and target manifest: `scripts/qt_visual_belt.py`,
  `scripts/qt_probe_targets.json`
- Verified SQLite backup CLI: `scripts/sqlite_backup.py`
- Command policy: `.codex/rules/project.rules`
- Product/runtime overview: `README.md`
- Risk ledger: `docs/risk-ledger.md`
- Agent orchestration protocol: `docs/harness/agent-orchestration.md`
- Cross-tool contradiction log: `docs/harness/contradiction-log.md`

## Operating Model

1. Use `AGENTS.md` as the map.
2. Read the narrow source-of-truth doc for the task.
3. Implement the smallest behavior-preserving change.
4. Run the relevant verification gate.
5. Deliver with `Changes`, `Impact`, `Verification`, `Residual risk`, and `Next action`; after debugging or Investigation Path work, record reusable Debug/RCA learning in `closed-loop-log.md`.

## Database Safety

- `scripts/verify.ps1` always creates a disposable SQLite online-backup snapshot
  and enables the formal-path refusal guard before imports or initialization.
- Use `-Profile Focused` for the recurrent safety/contract set and the default
  `-Profile Full` for complete unit, native visual, baseline, and harness gates.
- Never raw-copy an active WAL database. A verified backup must pass read-only
  `integrity_check` and per-table count parity.

## Qt Visual Evidence

- `QT_QPA_PLATFORM=offscreen` is allowed only for structural smoke checks.
- Visual screenshots, Chinese text rendering, and typography judgments must use the native Windows Qt platform.
- Run `scripts\qt_visual_probe.py` when visual evidence is needed; it forces native Windows Qt unless `--allow-offscreen` is explicitly passed.
- `scripts/qt_probe_targets.json` is the single target/DPI manifest.
- `scripts\qt_visual_belt.py` must pass every required target at 100% / 125% /
  150%; `scripts\qt_visual_regress.py` fails when a required baseline is absent
  or its file mapping differs.
- If only offscreen output is available, report it as structural evidence, not as a visual UI finding.

## Qt UI Removal And Compatibility Widgets

- For "remove / do not show" UI requests, verify the element is absent from the visible layout and not only visually obscured.
- Compatibility-only Qt widgets must be explicitly hidden, removed, or inserted into the intended layout; parented-but-unmanaged widgets can float over the page.
- Native visual probes should drive visible routes, controls, and scroll positions, not hidden proxy widgets.

## Repository Hygiene Gates

- `scripts/harness_check.ps1` compares the live tracked plus non-ignored release
  membership to the source-baseline manifest.
- It rejects tracked root-generated quality workbooks and `.playwright-mcp/`
  state, checks active-plan lifecycle markers, and verifies every required visual
  target has a readable baseline manifest and files.

## Non-goals

- This harness does not change schema, migration behavior, UI behavior, export contracts, or SQE workflow.
- This harness does not replace the global Codex baseline.
- This harness does not replace tool-specific safety controls such as Codex rules, Claude hooks, Cursor rules, or Antigravity workspace rules.
