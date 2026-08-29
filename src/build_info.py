"""Build-time metadata for release traceability.

``scripts/write_build_info.py`` regenerates this file during packaging.
Development checkouts keep the placeholder values below.
"""

from __future__ import annotations

__git_commit__ = "d8cf432"
__build_timestamp__ = "2026-08-29T02:53:13Z"
__dirty_worktree__ = True


def build_label() -> str:
    """Return a compact label suitable for logs and about dialogs."""
    parts = [__git_commit__]
    if __build_timestamp__:
        parts.append(__build_timestamp__)
    if __dirty_worktree__:
        parts.append("dirty")
    return " ".join(part for part in parts if part)
