"""Shared filesystem path-component validation and export filename sanitization."""

from __future__ import annotations

import re

INVALID_PATH_CHARACTERS = frozenset('\x00<>:"/\\|?*')
_ILLEGAL_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def contains_invalid_path_char(value: str) -> bool:
    """Return True when ``value`` contains characters unsafe for path components."""
    return any(char in value for char in INVALID_PATH_CHARACTERS)


def sanitize_filename_part(value: object, *, fallback: str = "未命名") -> str:
    """Normalize one export filename segment by replacing illegal characters."""
    text = str(value or "").strip()
    if not text:
        text = fallback
    cleaned = _ILLEGAL_FILENAME_CHARS.sub("_", text)
    cleaned = re.sub(r"\s+", "_", cleaned).strip(" ._")
    return cleaned or fallback
