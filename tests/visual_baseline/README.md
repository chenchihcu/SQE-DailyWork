# Visual regression baselines

Golden PNGs for `scripts/qt_visual_regress.py`. One subfolder per probe target,
each with the captured PNGs plus a `baseline_manifest.json` recording the
environment they were captured under (`qt_platform`, `selected_font`, `scale`,
`device_pixel_ratio`).

## Generate / refresh baselines (run on the production Windows machine)

```powershell
.venv\Scripts\python.exe scripts\qt_visual_regress.py --target event-list --update
.venv\Scripts\python.exe scripts\qt_visual_regress.py --target master-data --update
.venv\Scripts\python.exe scripts\qt_visual_regress.py --target ncr-stats   --update
.venv\Scripts\python.exe scripts\qt_visual_regress.py --target stats-stress --update
```

## Check against baselines

```powershell
.venv\Scripts\python.exe scripts\qt_visual_regress.py --target event-list
```

## Rules

- **Generate baselines only on a machine with the production CJK fonts**
  (Microsoft JhengHei). Baselines captured on a host without those fonts (the
  `selected_font` will be `Segoe UI`) are not representative — do not commit them.
- The check **skips** (exit 0, never a false pass) when the current environment
  does not match the baseline manifest, because cross-machine pixel diffs are
  unreliable. A skip is printed with its reason.
- Treat these PNGs as read-only reference artifacts; refresh them deliberately
  with `--update` after an intended visual change, then review the diff before
  committing.
