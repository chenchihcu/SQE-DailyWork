# Agent Orchestration — Coding Protocol

Version: v2026.07.05-02

This doc defines how coding tasks run across the real agents used in this repo:
**Claude Code, Codex, Cursor, and Gemini/Antigravity**. `AGENTS.md` remains the single source of
truth; this file is referenced from `AGENTS.md` section 8 and does not replace it.

Goal: do coding **correctly**, **efficiently**, with **error-learning**, and **routed to the
best-suited agent**. There is no "Hermes" agent in this repo.

## Role Assignment (RACI)

| Agent | Primary role | Must not do |
|---|---|---|
| Claude | Define the correct problem, spec, architecture judgment, risk review | Mass code changes while requirements are ambiguous |
| Codex | Implement, debug, fix tests, produce a verifiable diff | Widen scope or change the spec on its own |
| Cursor | Light in-editor implementation / quick edits (Local Mode, single writer) | Large cross-stack refactors; parallel writing in a shared checkout |
| Gemini/Antigravity | Process monitoring, verification, evidence preservation | Replace spec decisions or the final code review |

**Antigravity verification is re-scoped for this repo:** SQE DailyWork is a **PySide6 desktop app**,
not a web app. Verification evidence = **native Windows Qt** via `scripts/qt_visual_probe.py`
(plus a walkthrough), not browser / user-journey flows. `QT_QPA_PLATFORM=offscreen` is
structural-only, never visual evidence.

## Task Tiering

Route by risk so small work is not buried in ceremony. Three levels (not five — this is a
single-user repo).

| Level | Scope | Flow |
|---|---|---|
| **L0 (trivial)** | typo, comment, doc micro-edit, pure-text change | Any agent executes directly; short report; no canonical spec |
| **Standard** | normal feature / bug fix / bounded UI within one or two layers | Claude writes the light canonical spec (6 fields) -> execute -> run the relevant gate |
| **Heavy** | anything hitting a Hard Trigger (below) | Full canonical spec -> execute in stages -> verification evidence -> Claude + Codex dual review -> human approval |

**Heavy = the existing Hard Triggers in `AGENTS.md`**: data migration, schema / data-contract
change, export / PDF / Excel / PPTX contract change, destructive data change, public API change,
or a cross-stack "Atomic Path" refactor (data -> service -> UI -> copy). Do not invent a second
risk line.

## Canonical Spec

- **Light default (6 fields):** problem, goal, non-goals, scope (allowed / forbidden changes),
  acceptance criteria, verification method.
- **Full (Heavy only):** add background, FACT / INFERENCE / ASSUMPTION / UNKNOWN, affected areas,
  test requirements, risk assessment, rollback plan, handoff notes, review requirements, final
  status.

Codex implements only what the spec allows. If the spec is insufficient, Codex **stops and
reports** — no guessing.

## Evidence Standard

"Verified" requires evidence, never a self-claim. Evidence is scoped to this desktop app —
**no browser / login / payment flows**.

| Change type | Valid evidence |
|---|---|
| UI text / layout | native Windows Qt **before / after** screenshot (`qt_visual_probe.py`), CJK legible |
| Bug fix | original failing case reproduced + passing evidence after fix + regression test |
| Refactor | existing tests pass + explicit "behavior unchanged" statement |
| Service / logic | focused unittest result (`verify.ps1` or the closest module) |
| Data / schema / export contract | migration dry-run + rollback note + `harness_check` / contract test (Heavy: human approval) |
| Governance / harness | `scripts/harness_check.ps1` prints "Harness check passed." |

Offscreen Qt is structural-only; Playwright is not accepted as visual evidence for this app.

## Stop Conditions

Any agent stops and reports (no guessing) when: acceptance criteria are missing; scope is unclear;
credentials are needed; repo state disagrees with the spec; deletion / migration / deploy is
required; a public API change is not authorized; tests fail for an unknown reason; verification
disagrees with expectation; or the task risks data loss / security / irreversible impact.

**Human approval gate is already enforced by tooling** — do not rebuild it, reference it:
`.claude/hooks/sqe-dailywork-pre-tool-use.ps1` blocks recursive delete, `--apply` without a
`SQE_DAILYWORK_CONFIRM_APPLY=1` marker, and direct `data/*.db` writes; `.codex/rules/project.rules`
prompts on migration and `--apply`. Heavy operations pass through these gates plus explicit user
confirmation.

## Review Severity

Reviews grade findings so results are decidable. Heavy tasks require Claude + Codex dual review.

| Level | Meaning | Handling |
|---|---|---|
| **P0** | data loss, security hole, app cannot run | Stop; must not be accepted |
| **P1** | major logic error, requirement mismatch, test gap | Must fix, then re-review |
| **P2** | edge case, maintainability, weak error handling | Fix advised; state the risk if deferred |
| **P3** | naming, formatting, docs, readability | May defer; non-blocking |

Acceptance requires no open P0 / P1.

## Error Learning

Close the loop so the same mistake is not repeated:

- Deliver with `Changes / Impact / Verification / Residual risk / Next action`; after debugging or
  Investigation-Path work add `Observed / Root cause / Fix / Harness update needed / Destination`.
- If `Harness update needed: yes`, run `/learn` (or the memory-update equivalent) before marking
  complete, and record reusable knowledge in `docs/harness/closed-loop-log.md`.
- **Cross-tool rule conflict:** when two agents give contradictory SOPs, do **not** self-adjudicate.
  Record it in `docs/harness/contradiction-log.md` (Topic / each agent's claim / Risk / Required
  user decision) and ask the user.
- **Task-state conflict routing:** Codex finds the spec infeasible -> stop, return to Claude to
  revise the spec; verification fails -> return to Codex to fix (Claude revises the spec only if
  needed); Claude-review vs Codex-review disagree -> the canonical spec + acceptance criteria are
  the authority.

## Routing Table

| Task type | Primary | Secondary |
|---|---|---|
| Requirement clarification | Claude | Gemini/Antigravity |
| Spec / architecture design | Claude | Codex |
| Implementation coding | Codex | Cursor (light) / Claude |
| Unit tests / CI fix / debug | Codex | Claude |
| Light in-editor edit (L0) | Cursor | Codex |
| Large refactor (Heavy) | Claude plans, Codex executes in stages | Antigravity verifies |
| Qt visual / CJK verification | Gemini/Antigravity (native Qt evidence) | Codex |
| PR / code review | Codex + Claude | Antigravity |
| Final verification record | Gemini/Antigravity | Claude |

## Boundaries

- This file does not replace `AGENTS.md` (single source of truth) and does not weaken global Hard
  Triggers.
- One writer per worktree until a reviewed source baseline commit exists (see
  `docs/harness/ai-rules-compatibility.md`).
- Not adopted, deliberately, for a single-user trunk-based repo: five-level L0-L4 tiering
  (collapsed to three), per-dispatch task-packet YAML (the light canonical spec already carries
  objective / allowed / forbidden / acceptance), and spec-versioning change-log YAML (git history
  is the version record).
- Whether each tool can explicitly select model / effort is **VERIFY** — confirm before relying on
  any automatic escalation / downgrade rule.
