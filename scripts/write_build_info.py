"""Write src/build_info.py with git commit and build timestamp."""

from __future__ import annotations

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


def main() -> int:
    repo_root = _repo_root()
    target = repo_root / "src" / "build_info.py"
    commit = _git_commit(repo_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dirty = _dirty_worktree(repo_root)

    content = f'''"""Build-time metadata for release traceability.

``scripts/write_build_info.py`` regenerates this file during packaging.
Development checkouts keep the placeholder values below.
"""

from __future__ import annotations

__git_commit__ = "{commit}"
__build_timestamp__ = "{timestamp}"
__dirty_worktree__ = {dirty!r}


def build_label() -> str:
    """Return a compact label suitable for logs and about dialogs."""
    parts = [__git_commit__]
    if __build_timestamp__:
        parts.append(__build_timestamp__)
    if __dirty_worktree__:
        parts.append("dirty")
    return " ".join(part for part in parts if part)
'''
    target.write_text(content, encoding="utf-8")
    print(f"Wrote build metadata: commit={commit} dirty={dirty}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
