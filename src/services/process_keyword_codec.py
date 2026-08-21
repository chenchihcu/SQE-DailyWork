"""Parse, normalize, and serialize SMT process keywords on anomalies."""

from __future__ import annotations

import re

MAX_PROCESS_KEYWORDS_PER_ANOMALY = 12
MAX_PROCESS_KEYWORD_LENGTH = 40

_WHITESPACE_RE = re.compile(r"[\s\u3000]+")


def _iter_raw_keyword_lines(value: object) -> list[str]:
    if isinstance(value, str):
        return value.splitlines()
    if isinstance(value, (list, tuple, set)):
        return [str(item or "") for item in value]
    return []


def _normalize_keyword_tokens(raw_lines: object, *, apply_limit: bool) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for raw_line in _iter_raw_keyword_lines(raw_lines):
        candidate = _WHITESPACE_RE.sub(" ", str(raw_line)).strip()
        if not candidate:
            continue
        key = candidate.casefold()
        if key in seen:
            continue
        seen.add(key)
        tokens.append(candidate[:MAX_PROCESS_KEYWORD_LENGTH])
        if apply_limit and len(tokens) >= MAX_PROCESS_KEYWORDS_PER_ANOMALY:
            break
    return tokens


def parse_process_keywords(value: object) -> list[str]:
    """Split stored newline-delimited keywords into normalized unique tokens."""
    text = str(value or "")
    if not text.strip():
        return []
    return _normalize_keyword_tokens(text, apply_limit=True)


def serialize_process_keywords(keywords: object) -> str:
    """Normalize keyword list or delimited text for persistence."""
    if isinstance(keywords, str):
        parsed = parse_process_keywords(keywords)
    elif isinstance(keywords, (list, tuple, set)):
        parsed = _normalize_keyword_tokens(keywords, apply_limit=True)
    else:
        parsed = []
    return "\n".join(parsed)


def format_process_keywords_display(value: object, *, separator: str = "、") -> str:
    """Human-readable single-line display for lists and exports."""
    tokens = parse_process_keywords(value)
    return separator.join(tokens)


def validate_process_keywords(value: object) -> str:
    """Return normalized storage text or raise ValueError."""
    tokens = _normalize_keyword_tokens(value, apply_limit=False)

    if len(tokens) > MAX_PROCESS_KEYWORDS_PER_ANOMALY:
        raise ValueError(
            f"SMT 製程關鍵詞最多 {MAX_PROCESS_KEYWORDS_PER_ANOMALY} 個"
        )
    return "\n".join(tokens)
