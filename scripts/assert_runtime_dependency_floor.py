"""Fail closed when a release runtime dependency is below its security floor."""

from __future__ import annotations

import json
import re
from importlib import metadata
from typing import Callable


MINIMUM_RUNTIME_DEPENDENCIES = {"Pillow": "12.3.0"}


def _numeric_version(value: str) -> tuple[int, ...]:
    normalized = value.strip()
    if not re.fullmatch(r"\d+(?:\.\d+)*", normalized):
        raise ValueError(
            "version must be a stable dotted-numeric release: "
            f"{value!r}"
        )
    return tuple(int(part) for part in normalized.split("."))


def _meets_minimum(installed: str, minimum: str) -> bool:
    installed_parts = _numeric_version(installed)
    minimum_parts = _numeric_version(minimum)
    width = max(len(installed_parts), len(minimum_parts))
    return installed_parts + (0,) * (width - len(installed_parts)) >= (
        minimum_parts + (0,) * (width - len(minimum_parts))
    )


def build_runtime_dependency_floor_report(
    version_reader: Callable[[str], str] = metadata.version,
) -> dict:
    dependencies = []
    failures = []
    for distribution, minimum in MINIMUM_RUNTIME_DEPENDENCIES.items():
        try:
            installed = version_reader(distribution)
            try:
                meets_floor = _meets_minimum(installed, minimum)
            except ValueError:
                meets_floor = False
            item = {
                "distribution": distribution,
                "minimum": minimum,
                "installed": installed,
                "meets_floor": meets_floor,
            }
            dependencies.append(item)
            if not meets_floor:
                failures.append(item)
        except metadata.PackageNotFoundError:
            item = {
                "distribution": distribution,
                "minimum": minimum,
                "installed": None,
                "meets_floor": False,
            }
            dependencies.append(item)
            failures.append(item)

    return {
        "result": "pass" if not failures else "fail",
        "dependencies": dependencies,
        "failures": failures,
    }


def main() -> int:
    report = build_runtime_dependency_floor_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["result"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
