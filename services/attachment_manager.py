"""Attachment storage for anomaly cases.

Files are stored on disk under the project data directory:
``data/attachments/anomaly/{anomaly_id}/``. One folder is used per anomaly.
Optional per-image captions are kept in ``captions.json`` inside the same
folder. No database table is used; presence on disk is the source of truth.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Iterable

from database.connection import DATA_DIR

ANOMALY_ATTACHMENT_ROOT = DATA_DIR / "attachments" / "anomaly"
ALLOWED_IMAGE_SUFFIXES: frozenset[str] = frozenset({".jpg", ".jpeg", ".png"})
CAPTIONS_FILENAME = "captions.json"


def _anomaly_dir(anomaly_id: str) -> Path:
    key = (anomaly_id or "").strip()
    if not key:
        raise ValueError("Anomaly id is required")
    return ANOMALY_ATTACHMENT_ROOT / key


def _resolve_unique_name(target_dir: Path, name: str) -> Path:
    candidate = target_dir / name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    counter = 1
    while True:
        alt = target_dir / f"{stem} ({counter}){suffix}"
        if not alt.exists():
            return alt
        counter += 1


def import_anomaly_attachments(
    anomaly_id: str, src_paths: Iterable[Path | str]
) -> list[Path]:
    """Copy source files to the anomaly's attachment folder.

    Files whose extension is not in ALLOWED_IMAGE_SUFFIXES are skipped silently.
    Returns the list of stored paths.
    """
    target_dir = _anomaly_dir(anomaly_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    stored: list[Path] = []
    for src in src_paths:
        path = Path(src)
        if not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_IMAGE_SUFFIXES:
            continue
        destination = _resolve_unique_name(target_dir, path.name)
        shutil.copy2(path, destination)
        stored.append(destination)
    return stored


def list_anomaly_attachments(anomaly_id: str) -> list[Path]:
    """Return image files attached to the given anomaly, sorted by name."""
    key = (anomaly_id or "").strip()
    if not key:
        return []
    folder = ANOMALY_ATTACHMENT_ROOT / key
    if not folder.is_dir():
        return []
    items = [
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in ALLOWED_IMAGE_SUFFIXES
    ]
    items.sort(key=lambda p: p.name.casefold())
    return items


def get_anomaly_captions(anomaly_id: str) -> dict[str, str]:
    """Return a {filename: caption} mapping for an anomaly's attachments.

    Returns an empty dict when no captions file exists or it cannot be parsed.
    """
    key = (anomaly_id or "").strip()
    if not key:
        return {}
    captions_path = ANOMALY_ATTACHMENT_ROOT / key / CAPTIONS_FILENAME
    if not captions_path.is_file():
        return {}
    try:
        raw = json.loads(captions_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items() if str(v).strip()}


def set_anomaly_captions(
    anomaly_id: str, captions: dict[str, str]
) -> None:
    """Merge new captions into the captions.json file for an anomaly.

    Empty/whitespace-only captions are removed. Entries for filenames that no
    longer exist on disk are dropped.
    """
    key = (anomaly_id or "").strip()
    if not key:
        raise ValueError("Anomaly id is required")
    folder = ANOMALY_ATTACHMENT_ROOT / key
    folder.mkdir(parents=True, exist_ok=True)
    existing = get_anomaly_captions(key)
    for filename, caption in (captions or {}).items():
        name = str(filename or "").strip()
        if not name:
            continue
        text = str(caption or "").strip()
        if text:
            existing[name] = text
        elif name in existing:
            del existing[name]
    on_disk = {p.name for p in list_anomaly_attachments(key)}
    pruned = {name: text for name, text in existing.items() if name in on_disk}
    captions_path = folder / CAPTIONS_FILENAME
    if not pruned:
        if captions_path.is_file():
            try:
                captions_path.unlink()
            except OSError:
                pass
        return
    captions_path.write_text(
        json.dumps(pruned, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
def delete_anomaly_attachment(anomaly_id: str, filename: str) -> bool:
    """Delete a specific attachment file and its caption entry.

    Returns True if the file was deleted, False if it didn't exist.
    """
    key = (anomaly_id or "").strip()
    name = (filename or "").strip()
    if not key or not name:
        return False
    path = ANOMALY_ATTACHMENT_ROOT / key / name
    if not path.is_file():
        return False
    try:
        path.unlink()
        # Prune captions to remove the entry for this file
        set_anomaly_captions(key, {})
        return True
    except OSError:
        return False


def rename_anomaly_attachment(anomaly_id: str, old_name: str, new_name: str) -> bool:
    """Rename an existing attachment file and update its caption entry.

    Handles Windows case-only renames and filename collisions.
    """
    key = (anomaly_id or "").strip()
    old = (old_name or "").strip()
    new = (new_name or "").strip()
    if not key or not old or not new or old == new:
        return False

    folder = ANOMALY_ATTACHMENT_ROOT / key
    old_path = folder / old
    if not old_path.is_file():
        return False

    # Ensure new name has a valid extension
    new_p = Path(new)
    if not new_p.suffix or new_p.suffix.lower() not in ALLOWED_IMAGE_SUFFIXES:
        new = new_p.stem + old_path.suffix

    # Special handling for case-only changes on Windows
    if old.lower() == new.lower() and old != new:
        # On Windows, renaming A.jpg to a.jpg requires an intermediate step
        import uuid
        temp_name = f"{old}.{uuid.uuid4().hex}.tmp"
        temp_path = folder / temp_name
        try:
            old_path.rename(temp_path)
            # Now we can resolve the unique name for 'new'
            new_target_path = _resolve_unique_name(folder, new)
            temp_path.rename(new_target_path)
            # Update captions with the actually used name
            _update_caption_key(key, old, new_target_path.name)
            return True
        except OSError:
            if temp_path.exists():
                try: temp_path.rename(old_path)
                except OSError: pass
            return False

    # Normal rename
    new_target_path = _resolve_unique_name(folder, new)
    try:
        old_path.rename(new_target_path)
        _update_caption_key(key, old, new_target_path.name)
        return True
    except OSError:
        return False


def _update_caption_key(anomaly_id: str, old_filename: str, new_filename: str) -> None:
    """Helper to migrate a caption entry from one filename to another."""
    captions = get_anomaly_captions(anomaly_id)
    if old_filename in captions:
        caption_text = captions.pop(old_filename)
        captions[new_filename] = caption_text
        set_anomaly_captions(anomaly_id, captions)


def import_single_anomaly_attachment(
    anomaly_id: str, src_path: Path | str, target_name: str | None = None
) -> Path | None:
    """Import a single file, optionally with a specific target name."""
    target_dir = _anomaly_dir(anomaly_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = Path(src_path)
    if not path.is_file() or path.suffix.lower() not in ALLOWED_IMAGE_SUFFIXES:
        return None

    name = (target_name or path.name).strip()
    # Ensure target name has a valid extension; if missing, use source's
    name_p = Path(name)
    if not name_p.suffix or name_p.suffix.lower() not in ALLOWED_IMAGE_SUFFIXES:
        name = name_p.stem + path.suffix

    destination = _resolve_unique_name(target_dir, name)
    shutil.copy2(path, destination)
    return destination
