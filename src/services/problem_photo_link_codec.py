"""Sidecar codec for linking field photos to problem-desc bullet indices."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from pathlib import Path

from services import attachment_manager

logger = logging.getLogger(__name__)

PROBLEM_PHOTO_LINKS_FILENAME = "problem_photo_links.json"
PROBLEM_PHOTO_LINKS_VERSION = 1


def _links_path(anomaly_id: str) -> Path:
    return attachment_manager._anomaly_dir(anomaly_id) / PROBLEM_PHOTO_LINKS_FILENAME


def parse_problem_desc_items(text: str) -> list[str]:
    """Parse newline-delimited problem_desc into item texts (no numbering)."""
    if not text or not str(text).strip():
        return []
    lines = str(text).strip().splitlines()
    extracted: list[str] = []
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
        cleaned = re.sub(r"^(\d+[\.\)]|\-|•|\*)\s*", "", line_str)
        extracted.append(cleaned if cleaned else line_str)
    return extracted


def problem_desc_item_count(text: str) -> int:
    return len(parse_problem_desc_items(text))


def get_problem_photo_links(anomaly_id: str) -> dict[str, int]:
    """Return {stored_filename: 1-based bullet index} for one anomaly."""
    key = (anomaly_id or "").strip()
    if not key:
        return {}
    try:
        path = _links_path(key)
    except ValueError:
        return {}
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.debug("Could not read problem photo links for %s", key, exc_info=True)
        return {}
    if not isinstance(raw, dict):
        return {}
    links_raw = raw.get("links")
    if not isinstance(links_raw, dict):
        return {}
    result: dict[str, int] = {}
    for filename, index in links_raw.items():
        name = str(filename or "").strip()
        if not name:
            continue
        try:
            bullet_index = int(index)
        except (TypeError, ValueError):
            continue
        if bullet_index < 1:
            continue
        result[name] = bullet_index
    return result


def _prune_links(links: dict[str, int], anomaly_id: str) -> dict[str, int]:
    on_disk = {path.name for path in attachment_manager.list_stored_attachment_files(anomaly_id)}
    return {name: index for name, index in links.items() if name in on_disk}


def set_problem_photo_links(anomaly_id: str, links: dict[str, int]) -> None:
    """Persist bullet links, pruning entries for files no longer on disk."""
    key = (anomaly_id or "").strip()
    if not key:
        raise ValueError("Anomaly id is required")
    folder = attachment_manager._anomaly_dir(key)
    folder.mkdir(parents=True, exist_ok=True)
    normalized: dict[str, int] = {}
    for filename, index in (links or {}).items():
        name = str(filename or "").strip()
        if not name:
            continue
        try:
            bullet_index = int(index)
        except (TypeError, ValueError):
            continue
        if bullet_index < 1:
            continue
        normalized[name] = bullet_index
    pruned = _prune_links(normalized, key)
    path = _links_path(key)
    if not pruned:
        if path.is_file():
            try:
                path.unlink()
            except OSError:
                logger.debug("Could not remove empty problem photo links file", exc_info=True)
        attachment_manager._sync_anomaly_markdown(key)
        return
    payload = {"version": PROBLEM_PHOTO_LINKS_VERSION, "links": pruned}
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    attachment_manager._sync_anomaly_markdown(key)


def delete_links_for_filenames(anomaly_id: str, filenames: Iterable[str]) -> None:
    """Remove link entries for the given stored filenames."""
    key = (anomaly_id or "").strip()
    if not key:
        return
    names = {str(name or "").strip() for name in filenames if str(name or "").strip()}
    if not names:
        return
    existing = get_problem_photo_links(key)
    if not existing:
        return
    for name in names:
        existing.pop(name, None)
    set_problem_photo_links(key, existing)


def set_link_for_filename(anomaly_id: str, filename: str, bullet_index: int | None) -> None:
    """Set or clear one filename's bullet link."""
    key = (anomaly_id or "").strip()
    name = str(filename or "").strip()
    if not key or not name:
        return
    existing = get_problem_photo_links(key)
    if bullet_index is None or int(bullet_index) < 1:
        existing.pop(name, None)
    else:
        existing[name] = int(bullet_index)
    set_problem_photo_links(key, existing)


def bullet_index_for_attachment(
    attachment: dict,
    links: dict[str, int] | None = None,
) -> int | None:
    """Resolve bullet index for one attachment projection row."""
    stored_name = str(
        attachment.get("stored_name") or attachment.get("file_name") or ""
    ).strip()
    if not stored_name:
        return None
    if links is None:
        anomaly_id = str(attachment.get("anomaly_id") or "").strip()
        if not anomaly_id:
            return None
        links = get_problem_photo_links(anomaly_id)
    return links.get(stored_name)


FIELD_PHOTO_ATTACHMENT_CATEGORIES = frozenset(
    {
        "NG Photo",
        "Evidence",
        "Other",
        "FA Report",
        "不良照片",
        "證據",
        "其他",
        "FA 報告",
    }
)


def category_supports_problem_bullet_link(category: str) -> bool:
    return str(category or "").strip() in FIELD_PHOTO_ATTACHMENT_CATEGORIES


def bullet_index_combo_options(problem_desc: str) -> list[tuple[str, int | None]]:
    options: list[tuple[str, int | None]] = [("（不關聯）", None)]
    for index, text in enumerate(parse_problem_desc_items(problem_desc), start=1):
        preview = text if len(text) <= 24 else f"{text[:24]}…"
        options.append((f"{index}. {preview}", index))
    return options
