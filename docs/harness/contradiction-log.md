# Cross-Tool Contradiction Log

When two agents (Claude / Codex / Cursor / Gemini-Antigravity) give contradictory SOPs or rules,
do not self-adjudicate. Record the conflict here and ask the user. See
`docs/harness/agent-orchestration.md`.

## Format

```
## Contradiction: <topic>
- Date:
- Topic:
- Agent A says:
- Agent B says:
- Risk:
- Required user decision:
- Resolution (filled after the user decides):
```

## Entries

## Contradiction: Trunk-Based Development vs Cloud Agent feature branch
- Date: 2026-08-27
- Topic: Feature branch policy for this Cloud Agent run
- Agent A says: Repo `AGENTS.md` TBD — all development on `main`, no feature branches.
- Agent B says: Cursor Cloud Agent SOP — create `cursor/<descriptive-name>-7802` and open a PR against `main`.
- Risk: Direct `main` push vs PR review; two writers if both happen in the same worktree.
- Required user decision: Whether Cloud Agent runs may use PR branches, or must commit only to `main`.
- Resolution (filled after the user decides):

