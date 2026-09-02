"""Write build metadata JSON without mutating tracked application source."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _git_commit(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() or "unknown"
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _dirty_worktree(repo_root: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return bool(result.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        return False


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Destination build-info.json path inside the staged onedir tree.",
    )
    return parser.parse_args(argv)


def _package_version(module_name: str) -> str:
    try:
        module = __import__(module_name)
        return str(getattr(module, "__version__", "unknown"))
    except (ImportError, AttributeError):
        return "unknown"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = _repo_root()
    sys.path.insert(0, str(repo_root / "src"))
    from app_version import __version__

    commit = _git_commit(repo_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dirty = _dirty_worktree(repo_root)

    payload = {
        "version": __version__,
        "git_commit": commit,
        "build_timestamp": timestamp,
        "dirty_worktree": dirty,
        "python_version": sys.version.split()[0],
        "pyside6_version": _package_version("PySide6"),
        "pyinstaller_version": _package_version("PyInstaller"),
    }
    target = args.output.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote build metadata JSON: {target} commit={commit} dirty={dirty}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
