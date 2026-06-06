# SQETOOL Documentation Index

Use this folder as the durable source of project guidance. Keep transient
screenshots, exports, database snapshots, and one-off debugging artifacts out of
`docs/`.

## Document Map

| Document | Owner / Purpose |
| --- | --- |
| `../README.md` | Product, runtime, folder-structure, and validation overview. |
| `architecture-workflow-contract.md` | Data boundaries, workflow boundaries, UI entrypoint boundaries, and folder ownership rules. |
| `ui-layout-theme-contract.md` | Qt layout, theme, sidebar color hierarchy, visual stress, and native probe acceptance rules. |
| `risk-ledger.md` | Durable risk notes for changes that need explicit tracking. |
| `exec-plans/` | Active and completed plans for complex work only. |
| `harness/` | Agent governance, verification routing, source baselines, and compatibility notes. |

## Folder Hygiene

- Add new project guidance here only when it is durable and reusable.
- Put complex active plans in `exec-plans/active/`; move finished durable plans
  to `exec-plans/completed/`.
- Put agent or verification-system guidance in `harness/`, not in product
  contracts.
- Keep screenshots, report exports, local database files, and temporary probes
  in `Outputs/`, `data/`, or `scratch/` according to their runtime purpose.
- Before creating a new document, check this index and update the existing
  owner document when the topic already belongs there.
