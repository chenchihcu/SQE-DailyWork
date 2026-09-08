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

## Verification (Windows host)

- `PYTHONPATH=src:. QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe -m unittest tests.test_event_quick_review tests.test_event_list_widget_render_stability tests.test_event_action_menu_consistency tests.test_micro_interactions tests.test_layout_constants` — PASS
- `scripts/qt_visual_probe.py --target event-list --scale 1.0/1.25/1.5 --min-width` — exit 0, `visual_trustworthy: true`, `qss_unknown_property_warnings: 0`
- `scripts/qt_visual_regress.py --target event-list --scale 1.0/1.25/1.5 --min-width` — exit 0, `failures: []`
- `scripts/qt_visual_probe.py --target main --scale 1.0 --min-width` — exit 0 (startup lands on 事件查詢 with Quick Review splitter)
- `scripts/button_audit_report.py` — exit 0

## Residual risk

- Quick Review status badges now use shared `statusBadge` + `tone` QSS (no inline stylesheet).
- Other visual targets (`main` aside from startup landing) may still reflect
  pre-splitter layout until a matching `--update` on this host.

## Next action

Keep event-list visual regress on a Windows JhengHei UI host when changing
Quick Review layout. Cloud Linux `visual_trustworthy: false` remains expected.
