# Event Quick Review (概念 A)

Plan status: completed

## Scope

Master-Detail Quick Review on consolidated 事件查詢 (`EventListWidget` with
`mode="query"` and no fixed scope). Single-click preview, double-click full page,
right-click action menu. No schema changes.

## Delivered

- `src/ui/layout_constants.py` — Quick Review splitter constants
- `src/ui/widgets/event_next_action.py` — next-action resolver
- `src/ui/widgets/event_quick_review_panel.py` — preview panel
- `src/ui/widgets/defect_list_widget.py` — splitter + interaction contract
- `tests/test_event_quick_review.py` — focused unit tests
- `scripts/qt_visual_probe.py` — `event-list-scope0-empty-preview` / `-selected` captures
- `tests/visual_baseline/event-list/baseline_manifest.json` — updated file list
- `docs/ui-layout-theme-contract.md` — Master-Detail interaction table

## Verification (Cloud / Linux)

- `PYTHONPATH=src:. QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_event_quick_review tests.test_event_list_widget_render_stability tests.test_event_action_menu_consistency tests.test_micro_interactions tests.test_layout_constants` — PASS
- Native Windows visual gate (probe/regress Round 4) — **blocked on cloud VM**; requires Microsoft JhengHei UI host per AGENTS.md

## Residual risk

- Visual baseline PNGs must be regenerated on a Windows host with `--update` before CI visual regress passes.
- Quick Review status badges use inline palette styling; Round 3 QSS role migration optional follow-up.

## Next action

Run on Windows:

```powershell
$env:PYTHONPATH='src;.'
foreach ($s in '1.0','1.25','1.5') {
  .venv\Scripts\python.exe scripts\qt_visual_probe.py --target event-list --scale $s --min-width --output Outputs\visual_qa\event-list-qr --update
}
.venv\Scripts\python.exe scripts\qt_visual_regress.py --target event-list
.venv\Scripts\python.exe scripts\button_audit_report.py
```
