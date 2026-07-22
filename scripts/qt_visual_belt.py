"""Run every manifest-defined native Qt target at required DPI scales."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "scripts" / "qt_probe_targets.json"
PROBE = REPO_ROOT / "scripts" / "qt_visual_probe.py"


def _opaque_fraction(path: Path) -> float:
    from PySide6.QtGui import QImage

    image = QImage(str(path)).convertToFormat(QImage.Format.Format_RGBA8888)
    if image.isNull() or image.width() <= 0 or image.height() <= 0:
        return 0.0
    pixels = image.constBits().tobytes()
    alphas = pixels[3::4]
    return sum(alpha == 255 for alpha in alphas) / max(len(alphas), 1)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SQE native Qt full visual belt")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT / "Outputs" / "visual_qa" / "full-belt",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    scales = [str(scale) for scale in manifest["required_scales"]]
    results: list[dict] = []
    failures: list[dict] = []

    for target in manifest["targets"]:
        target_name = str(target["name"])
        target_scales = scales if target.get("baseline_required") else ["1.0"]
        for scale in target_scales:
            output = args.output_root / target_name / f"{target_name}.png"
            command = [
                sys.executable,
                str(PROBE),
                "--target",
                target_name,
                "--scale",
                scale,
                "--output",
                str(output),
            ]
            if target.get("min_width"):
                command.append("--min-width")
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            item = {"target": target_name, "scale": scale, "exit": completed.returncode}
            try:
                payload = json.loads(completed.stdout)
            except json.JSONDecodeError:
                payload = {}
            item.update(
                {
                    "visual_trustworthy": payload.get("visual_trustworthy"),
                    "cjk_font_ok": payload.get("cjk_font_ok"),
                    "ncr_cjk_font_ok": payload.get("ncr_cjk_font_ok"),
                    "qss_unknown_property_warnings": payload.get(
                        "qss_unknown_property_warnings"
                    ),
                    "screenshots": payload.get("screenshots", []),
                }
            )
            results.append(item)
            failed = completed.returncode != 0
            failed = failed or payload.get("qss_unknown_property_warnings") != 0
            if target.get("baseline_required"):
                failed = failed or not payload.get("visual_trustworthy")
                failed = failed or not payload.get("cjk_font_ok")
                failed = failed or not payload.get("ncr_cjk_font_ok")
                screenshots = [Path(path) for path in payload.get("screenshots", [])]
                failed = failed or not screenshots or any(
                    not path.is_file() or path.stat().st_size == 0 for path in screenshots
                )
                transparent = [
                    str(path)
                    for path in screenshots
                    if path.is_file() and _opaque_fraction(path) < 0.95
                ]
                item["transparent_screenshots"] = transparent
                failed = failed or bool(transparent)
            if target_name == "pdf-export":
                failed = failed or not payload.get("pdf_cjk_font_ok")
            if failed:
                failures.append(
                    {
                        **item,
                        "stdout": completed.stdout[-1000:],
                        "stderr": completed.stderr[-1000:],
                    }
                )

    print(
        json.dumps(
            {
                "result": "fail" if failures else "pass",
                "manifest": str(args.manifest),
                "checks": len(results),
                "failures": failures,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
