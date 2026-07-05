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

## Qt Visual Evidence

- `QT_QPA_PLATFORM=offscreen` is allowed only for structural smoke checks.
- Visual screenshots, Chinese text rendering, and typography judgments must use the native Windows Qt platform.
- Run `scripts\qt_visual_probe.py` when visual evidence is needed; it forces native Windows Qt unless `--allow-offscreen` is explicitly passed.
- If only offscreen output is available, report it as structural evidence, not as a visual UI finding.

## Qt UI Removal And Compatibility Widgets

- For "remove / do not show" UI requests, verify the element is absent from the visible layout and not only visually obscured.
- Compatibility-only Qt widgets must be explicitly hidden, removed, or inserted into the intended layout; parented-but-unmanaged widgets can float over the page.
- Native visual probes should drive visible routes, controls, and scroll positions, not hidden proxy widgets.

## Non-goals

- This harness does not change schema, migration behavior, UI behavior, export contracts, or SQE workflow.
- This harness does not replace the global Codex baseline.
- This harness does not replace tool-specific safety controls such as Codex rules, Claude hooks, Cursor rules, or Antigravity workspace rules.
