"""Assert coverage totals against docs/release/coverage-baseline.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _aggregate_module_percent(report: dict, module_key: str) -> tuple[float, int, int]:
    numerator = 0
    denominator = 0
    needle = f"src/{module_key}/"
    for file_path, payload in report.get("files", {}).items():
        normalized = file_path.replace("\\", "/")
        if needle not in normalized:
            continue
        summary = payload.get("summary", {})
        numerator += int(summary.get("covered_lines", 0))
        denominator += int(summary.get("num_statements", 0))
    if denominator == 0:
        return 0.0, 0, 0
    return (numerator / denominator) * 100.0, numerator, denominator


def main() -> int:
    repo_root = _repo_root()
    baseline_path = repo_root / "docs" / "release" / "coverage-baseline.json"
    summary_path = repo_root / "scratch" / "coverage-summary.json"

    if not baseline_path.is_file():
        print("Coverage baseline file missing; skipping fail-under gate.")
        return 0
    if not summary_path.is_file():
        print(f"Missing coverage summary: {summary_path}", file=sys.stderr)
        return 1

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    report = json.loads(summary_path.read_text(encoding="utf-8"))

    line_rate = float(report["totals"]["percent_covered"])
    print(f"Coverage line percent: {line_rate}")

    fail_under = float(baseline["fail_under_line_percent"])
    if line_rate < fail_under:
        print(
            f"Coverage regress: line percent {line_rate} < fail-under {fail_under}",
            file=sys.stderr,
        )
        return 1

    for module_key, min_percent in baseline.get("core_module_min_percent", {}).items():
        module_rate, covered, total = _aggregate_module_percent(report, module_key)
        if total == 0:
            print(f"Coverage note: no statements for core module '{module_key}' (skipped).")
            continue
        print(f"Coverage {module_key} aggregate: {module_rate:.1f}% ({covered}/{total})")
        if module_rate < float(min_percent):
            print(
                f"Coverage regress: {module_key} aggregate {module_rate:.1f}% "
                f"< min {min_percent}",
                file=sys.stderr,
            )
            return 1

    print("Coverage baseline gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
