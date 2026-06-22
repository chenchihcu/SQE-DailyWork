"""Visual regression harness for SQE DailyWork Qt surfaces.

Captures a target via ``qt_visual_probe.py`` and compares each PNG against a
committed baseline with a dependency-free QImage pixel diff.

Honesty guard (important): pixel diffs are fragile across machines because Windows
font set and DPI scaling change rendering. Each baseline carries a manifest of the
environment it was captured under (qt_platform / selected_font / scale /
device_pixel_ratio). When the current environment does not match, the comparison
is SKIPPED with a printed reason — never reported as a pass. Baselines must be
generated on the target machine with ``--update`` (do not commit baselines made on
a host without the production CJK fonts).

Exit codes: 0 = pass or skipped (env mismatch / no baseline) · 1 = regression.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROBE = REPO_ROOT / "scripts" / "qt_visual_probe.py"
DEFAULT_BASELINE_ROOT = REPO_ROOT / "tests" / "visual_baseline"
MANIFEST_NAME = "baseline_manifest.json"
ENV_KEYS = ("qt_platform", "selected_font", "scale", "device_pixel_ratio")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SQE DailyWork Qt visual regression check.")
    parser.add_argument("--target", required=True, help="qt_visual_probe target to regress.")
    parser.add_argument("--scale", default="1.0", help="Single DPI scale factor (e.g. 1.25).")
    parser.add_argument("--baseline-root", type=Path, default=DEFAULT_BASELINE_ROOT)
    parser.add_argument("--work-dir", type=Path, default=REPO_ROOT / "Outputs" / "visual_qa" / "_regress")
    parser.add_argument("--tolerance", type=float, default=0.001, help="Max fraction of differing bytes (default 0.001).")
    parser.add_argument("--min-width", action="store_true", help="Pass --min-width to the probe.")
    parser.add_argument("--allow-offscreen", action="store_true",
                        help="Structural/debug only: forward --allow-offscreen to the probe. The "
                             "manifest then records qt_platform=offscreen, so native runs skip (not pass).")
    parser.add_argument("--update", action="store_true", help="Write current capture as the new baseline.")
    return parser.parse_args()


def _run_probe(args: argparse.Namespace) -> dict:
    out_stem = args.work_dir / args.target / f"{args.target}.png"
    out_stem.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, str(PROBE),
        "--target", args.target,
        "--scale", args.scale,
        "--output", str(out_stem),
    ]
    if args.min_width:
        cmd.append("--min-width")
    if args.allow_offscreen:
        cmd.append("--allow-offscreen")
    completed = subprocess.run(cmd, capture_output=True, text=True)
    if completed.returncode not in (0, 3):  # 3 == not visual-trustworthy (env), still has JSON
        sys.stderr.write(completed.stdout + "\n" + completed.stderr)
        raise SystemExit(f"probe failed for {args.target} (exit {completed.returncode})")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        sys.stderr.write(completed.stdout)
        raise SystemExit("could not parse probe JSON output")


def _current_env(probe_json: dict) -> dict:
    return {key: probe_json.get(key) for key in ENV_KEYS}


def _byte_diff_ratio(path_a: Path, path_b: Path):
    """Return (ratio, same_geometry). Loads via QImage; format-normalized to RGBA8888."""
    from PySide6.QtGui import QImage

    img_a = QImage(str(path_a)).convertToFormat(QImage.Format.Format_RGBA8888)
    img_b = QImage(str(path_b)).convertToFormat(QImage.Format.Format_RGBA8888)
    if img_a.size() != img_b.size():
        return 1.0, False
    bytes_a = img_a.constBits().tobytes()
    bytes_b = img_b.constBits().tobytes()
    if bytes_a == bytes_b:
        return 0.0, True
    total = max(len(bytes_a), 1)
    differing = sum(1 for x, y in zip(bytes_a, bytes_b) if x != y)
    return differing / total, True


def _write_diff_png(path_a: Path, path_b: Path, out_path: Path) -> None:
    from PySide6.QtGui import QImage, qRgba

    img_a = QImage(str(path_a)).convertToFormat(QImage.Format.Format_RGBA8888)
    img_b = QImage(str(path_b)).convertToFormat(QImage.Format.Format_RGBA8888)
    if img_a.size() != img_b.size():
        return
    diff = QImage(img_a.size(), QImage.Format.Format_RGBA8888)
    red, white = qRgba(220, 40, 60, 255), qRgba(255, 255, 255, 255)
    for y in range(img_a.height()):
        for x in range(img_a.width()):
            diff.setPixel(x, y, red if img_a.pixel(x, y) != img_b.pixel(x, y) else white)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    diff.save(str(out_path))


def main() -> int:
    args = _parse_args()
    probe_json = _run_probe(args)
    screenshots = [Path(p) for p in probe_json.get("screenshots", []) if p]
    if not screenshots and probe_json.get("screenshot"):
        screenshots = [Path(probe_json["screenshot"])]

    baseline_dir = args.baseline_root / args.target
    manifest_path = baseline_dir / MANIFEST_NAME

    if args.update:
        baseline_dir.mkdir(parents=True, exist_ok=True)
        names = []
        for shot in screenshots:
            dest = baseline_dir / shot.name
            dest.write_bytes(shot.read_bytes())
            names.append(shot.name)
        manifest = {"env": _current_env(probe_json), "files": names}
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"updated": str(baseline_dir), **manifest}, ensure_ascii=False, indent=2))
        return 0

    if not manifest_path.exists():
        print(json.dumps({
            "result": "skipped",
            "reason": f"no baseline for '{args.target}' — run with --update on the target machine first",
            "baseline_dir": str(baseline_dir),
        }, ensure_ascii=False, indent=2))
        return 0

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    current = _current_env(probe_json)
    if manifest.get("env") != current:
        print(json.dumps({
            "result": "skipped",
            "reason": "environment differs from baseline (font/platform/scale) — pixel diff would be unreliable",
            "baseline_env": manifest.get("env"),
            "current_env": current,
        }, ensure_ascii=False, indent=2))
        return 0

    failures = []
    for shot in screenshots:
        baseline_png = baseline_dir / shot.name
        if not baseline_png.exists():
            failures.append({"file": shot.name, "reason": "missing baseline file"})
            continue
        ratio, same_geom = _byte_diff_ratio(shot, baseline_png)
        if not same_geom:
            failures.append({"file": shot.name, "reason": "size mismatch", "ratio": 1.0})
        elif ratio > args.tolerance:
            diff_out = args.work_dir / args.target / f"DIFF_{shot.name}"
            _write_diff_png(shot, baseline_png, diff_out)
            failures.append({"file": shot.name, "ratio": ratio, "diff": str(diff_out)})

    result = {
        "result": "fail" if failures else "pass",
        "target": args.target,
        "scale": args.scale,
        "tolerance": args.tolerance,
        "compared": [s.name for s in screenshots],
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
