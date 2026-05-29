# AI Rules Compatibility Overview - SQETOOL

Last verified: 2026-05-25

This file is the repo-local compatibility register for Codex, Claude Code, Cursor, and Google Antigravity. It is a control document for AI-agent operation, not a SQE workflow specification.

## Claim Type

- `official`: confirmed from vendor documentation linked in Source Register.
- `local-observed`: confirmed from files or commands in this checkout.
- `audit-inference`: risk-audit conclusion derived from official and local evidence.
- `assumption`: chosen operating default that requires future revalidation.
- `not verified`: not directly verified in the current local tool UI/session.

## Source Register

| Claim | Type | Source |
| --- | --- | --- |
| Codex uses `AGENTS.md` guidance discovery and project-scoped instructions. | `official` | https://developers.openai.com/codex/guides/agents-md |
| Codex command policy belongs in `.codex/rules/*.rules` with `prefix_rule`. | `official` | https://developers.openai.com/codex/rules |
| Codex sandbox and approval defaults belong in `config.toml`. | `official` | https://developers.openai.com/codex/config-reference |
| Claude reads `CLAUDE.md`; importing `@AGENTS.md` is the Windows-friendly adapter. | `official` | https://code.claude.com/docs/en/memory |
| Claude permissions and hooks are enforceable controls separate from `CLAUDE.md` context. | `official` | https://code.claude.com/docs/en/permissions and https://code.claude.com/docs/en/hooks |
| Cursor Project Rules live in `.cursor/rules`; `AGENTS.md` is a plain markdown alternative. | `official` | https://docs.cursor.com/en/context |
| Antigravity workspace rules live in `.agents/rules`; New Worktree Mode isolates concurrent agents. | `official` | https://antigravity.google/docs/rules-workflows and https://www.antigravity.google/docs/projects |
| Codex stops adding guidance when combined project instructions reach `project_doc_max_bytes`; the documented default is 32 KiB. | `official` | https://developers.openai.com/codex/guides/agents-md |
| Claude recommends targeting under 200 lines per `CLAUDE.md` file because longer files consume context and reduce adherence. | `official` | https://code.claude.com/docs/en/memory |
| Cursor recommends keeping rules under 500 lines. | `official` | https://docs.cursor.com/en/context |
| Antigravity limits each rule file to 12,000 characters. | `official` | https://antigravity.google/docs/rules-workflows |
| Local file inventory for this register. | `local-observed` | `Get-ChildItem` over `AGENTS.md`, `CLAUDE.md`, `.codex/rules`, `.cursor/rules`, `.agents/rules`, `.claude`, and `scripts/harness_check.ps1` |
| Source-control boundary check. | `local-observed` | `git rev-parse --show-toplevel`, `git status --short`, `git ls-files` |
| Source baseline manifest and candidate tracking lists. | `local-observed` | `docs/harness/source-baseline-manifest.md` |
| On this Windows host, `powershell` was not available through PATH during verification; the full Windows PowerShell path was available. | `local-observed` | `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe` |

## Instruction Size Budget

| Surface | Type | Budget | Control |
| --- | --- | --- | --- |
| `AGENTS.md` | `official` | Codex combined project instructions stop at `project_doc_max_bytes`, 32 KiB default. | Keep repo `AGENTS.md` under 32 KiB and move detailed material into docs. |
| `CLAUDE.md` | `official` | Target under 200 lines. | Keep `CLAUDE.md` as `@AGENTS.md` plus Claude-only notes. |
| `.cursor/rules/*.mdc` | `official` | Keep each rule under 500 lines. | Keep only `agents_gateway.mdc` always-on; split or scope large rules. |
| `.agents/rules/*.md` | `official` | 12,000 characters per Antigravity rule file. | Keep Antigravity gateway short; put details in this file. |
| Always-on gateway files | `audit-inference` | Local operating budget: short enough to scan before every task. | Gateway files route to `AGENTS.md`; they do not duplicate full policy. |

## Compatibility Overview

| Surface | Local file | Type | Control strength | Required behavior |
| --- | --- | --- | --- | --- |
| Shared policy | `AGENTS.md` | `local-observed` | Context policy | Treat as the single repo policy source. |
| Codex command policy | `.codex/rules/project.rules` | `local-observed` | Command approval control | Keep only allow/prompt/forbid command rules here. |
| Claude adapter | `CLAUDE.md` | `local-observed` | Context adapter | Import `@AGENTS.md`; keep only Claude-specific notes. |
| Claude automation | `.claude/settings.json`, `.claude/hooks/`, `.claude/skills/`, `.claude/agents/` | `local-observed` | Tool and workflow control | Keep SQETOOL-specific automation here and verify through harness check. |
| Cursor adapter | `.cursor/rules/agents_gateway.mdc` | `local-observed` | Prompt context | Always-on gateway pointing to `AGENTS.md`. |
| Antigravity adapter | `.agents/rules/agents_gateway.md` | `local-observed` | Prompt context | Workspace gateway pointing to `AGENTS.md`; prefer New Worktree Mode. |
| Harness check | `scripts/harness_check.ps1` | `local-observed` | Deterministic local check | Verify gateway presence, source register, claim types, and completion format. |
| Source baseline manifest | `docs/harness/source-baseline-manifest.md` | `local-observed` | Source-control audit register | Record Git root, tracked/untracked/ignored status, baseline readiness, candidate lists, and role review. |

## Source Control Boundary

| Control | Type | Required behavior |
| --- | --- | --- |
| Baseline source of truth | `local-observed` | Read `docs/harness/source-baseline-manifest.md` before staging, committing, switching AI tools, or changing automation execution mode. |
| Staging guardrail | `audit-inference` | Do not use `git add .`; use an explicit reviewed path list after the baseline candidate lists are approved. |
| Parallel writing guardrail | `audit-inference` | Keep one writer per worktree until the source baseline manifest reports a reviewed baseline commit. |
| Generated data guardrail | `audit-inference` | Runtime DBs, outputs, scratch folders, build artifacts, caches, and local tool state remain excluded from baseline tracking. |

## Source-Control RCA And Extended Risks

| Finding | Type | Root cause | Extended risk | Control |
| --- | --- | --- | --- | --- |
| Git root exists, but tracked count was 0 before this pass. | `local-observed` | Repository was initialized without a committed source baseline. | AI handoff cannot rely on `git diff`, and untracked source changes can be missed. | Keep one writer per worktree until a reviewed source baseline commit exists. |
| `.gitignore` ignored the whole `.cursor/` directory before this pass. | `local-observed` | Local/editor noise rule was too broad for shared Cursor rules. | Cursor gateway could remain local-only and drift from `AGENTS.md`. | Ignore Cursor local state but unignore `.cursor/rules/**`. |
| Runtime/generated directories are ignored. | `local-observed` | `data/`, `Outputs/`, `scratch/`, runtime caches, and local Claude state are not shared policy. | Blind add can still capture unexpected generated files outside ignore coverage. | Review `git status --short --ignored` before any baseline commit. |
| Initial source baseline is not committed. | `local-observed` | This pass did not create a broad baseline commit. | Parallel agents still lack a clean handoff point. | Create a reviewed source baseline commit after generated paths are ignored. |
| Baseline candidate lists are not yet approved. | `local-observed` | `docs/harness/source-baseline-manifest.md` now classifies files, but no human approval has converted the list into a commit. | Automation or another AI could treat untracked source as disposable or accidentally omit governance files. | Treat the manifest as an audit register, not approval to stage. |
| Scratch/generated state is excluded from baseline tracking. | `local-observed` | `scratch/`, runtime outputs, and local generated artifacts are ignored. | Blind staging outside the reviewed candidate list can still capture unexpected generated files. | Keep scratch ignored and do not delete without explicit approval. |
| Native Qt visual evidence is project-critical. | `audit-inference` | SQETOOL requires Windows CJK rendering checks for visual UI claims. | A non-native or offscreen-only agent can approve broken typography/layout. | Keep `scripts/qt_visual_probe.py` as the visual-evidence control. |
| Oversized always-on rules reduce instruction efficiency. | `audit-inference` | Long rules consume context and make high-priority instructions harder to isolate. | Optional workflow details can crowd out SQETOOL business rules. | Enforce the Instruction Size Budget in `scripts/harness_check.ps1`. |

## Multi-AI Switching Protocol

1. Confirm repo path, branch, worktree, and `git status --short`.
2. Read `AGENTS.md` and the active tool gateway before edits.
3. Confirm the previous agent handoff has `Changes`, `Verification`, and `Residual risk`.
4. Keep one writer per worktree. Do not run two writing AI tools in the same checkout.
5. Use Antigravity New Worktree Mode for complex or parallel work. Use Local Mode only for small interactive tasks.
6. If git status is noisy or the baseline commit is absent, stay in single-writer mode.

## One Writer Protocol

| Condition | Type | Mode |
| --- | --- | --- |
| No reviewed source baseline commit | `audit-inference` | Single writer only. |
| Large untracked surface or generated local state | `audit-inference` | Single writer only; report candidate lists instead of staging. |
| Reviewed baseline commit exists and current status is understood | `audit-inference` | Worktree-based parallelism may be considered after user approval. |

## Automation Readiness

| Check | Type | Status |
| --- | --- | --- |
| Automation execution mode | `local-observed` | Keep `local` until the source baseline is reviewed. |
| Automation prompt | `audit-inference` | Must inspect `docs/harness/source-baseline-manifest.md`, `.gitignore`, four gateway layers, SQETOOL Claude automation surfaces, and its own TOML. |
| Worktree automation | `audit-inference` | Not ready until a reviewed baseline commit exists and the user approves switching execution mode. |

## Verification

Run after governance changes:

```powershell
C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\harness_check.ps1
```

Manual UI checks remain `not verified` unless the active tool UI confirms:

- Codex loaded `AGENTS.md` and `.codex/rules/project.rules`.
- Claude loaded `CLAUDE.md` and expanded `@AGENTS.md`.
- Cursor Agent sidebar shows `agents_gateway.mdc`.
- Antigravity workspace rules show `.agents/rules/agents_gateway.md`.
