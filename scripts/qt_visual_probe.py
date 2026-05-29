from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _ensure_repo_imports() -> None:
    repo_root_text = str(REPO_ROOT)
    if repo_root_text not in sys.path:
        sys.path.insert(0, repo_root_text)


def _prepare_native_qt_platform(*, allow_offscreen: bool) -> dict[str, str | bool]:
    original = os.environ.get("QT_QPA_PLATFORM", "")
    forced_native = False

    if allow_offscreen:
        return {"original_qt_platform": original, "forced_native": forced_native}

    if os.name == "nt":
        if original.lower() == "offscreen" or not original:
            os.environ["QT_QPA_PLATFORM"] = "windows"
            forced_native = True
        return {"original_qt_platform": original, "forced_native": forced_native}

    if original.lower() == "offscreen":
        print(
            "Refusing visual probe with QT_QPA_PLATFORM=offscreen. "
            "Use --allow-offscreen only for non-visual structural checks.",
            file=sys.stderr,
        )
        sys.exit(2)

    return {"original_qt_platform": original, "forced_native": forced_native}


def _has_cjk_writing_system(font_db, family: str) -> bool:
    if not family:
        return False
    systems = font_db.writingSystems(family)
    return any(
        system in systems
        for system in (
            font_db.WritingSystem.TraditionalChinese,
            font_db.WritingSystem.SimplifiedChinese,
            font_db.WritingSystem.Japanese,
            font_db.WritingSystem.Korean,
        )
    )


def _default_output_path() -> Path:
    return Path(tempfile.gettempdir()) / "sqetool_qt_visual_probe.png"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Capture SQETOOL with a native Qt platform so CJK rendering can be "
            "used as visual evidence."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_default_output_path(),
        help="Screenshot output path. Defaults to the OS temp directory.",
    )
    parser.add_argument(
        "--allow-offscreen",
        action="store_true",
        help="Allow offscreen mode for structural probing; output is not visual evidence.",
    )
    parser.add_argument(
        "--no-screenshot",
        action="store_true",
        help="Run platform and font checks without saving a screenshot.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _ensure_repo_imports()
    platform_info = _prepare_native_qt_platform(
        allow_offscreen=bool(args.allow_offscreen)
    )

    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QApplication

    from database.connection import initialize_database
    from ui.main_window import MainWindow
    from ui.theme import apply_app_theme

    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    apply_app_theme(app)

    selected_font = app.font().family()
    cjk_font_ok = _has_cjk_writing_system(QFontDatabase, selected_font)
    is_offscreen = app.platformName().lower() == "offscreen"
    visual_trustworthy = (not is_offscreen) and cjk_font_ok

    screenshot_path = None
    if not args.no_screenshot:
        initialize_database()
        window = MainWindow()
        window.resize(1100, 740)
        window.show()
        app.processEvents()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        window.grab().save(str(args.output))
        screenshot_path = str(args.output)
        window.close()
        app.processEvents()

    result = {
        **platform_info,
        "qt_platform_env": os.environ.get("QT_QPA_PLATFORM", ""),
        "qt_platform": app.platformName(),
        "selected_font": selected_font,
        "cjk_font_ok": cjk_font_ok,
        "visual_trustworthy": visual_trustworthy,
        "screenshot": screenshot_path,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if not visual_trustworthy and not args.allow_offscreen:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
