"""Build-time metadata loader with development-safe fallback values."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _load_build_metadata(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _runtime_build_metadata() -> dict[str, Any]:
    if not getattr(sys, "frozen", False):
        return {}
    return _load_build_metadata(Path(sys.executable).resolve().parent / "build-info.json")


_METADATA = _runtime_build_metadata()
__git_commit__ = str(_METADATA.get("git_commit") or "development")
__build_timestamp__ = str(_METADATA.get("build_timestamp") or "")
__dirty_worktree__ = bool(_METADATA.get("dirty_worktree", False))


def build_label() -> str:
    """Return a compact label suitable for logs and about dialogs."""
    parts = [__git_commit__]
    if __build_timestamp__:
        parts.append(__build_timestamp__)
    if __dirty_worktree__:
        parts.append("dirty")
    return " ".join(part for part in parts if part)
