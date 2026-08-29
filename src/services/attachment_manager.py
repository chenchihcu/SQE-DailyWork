"""Attachment storage for anomaly cases.

Files are stored on disk under the project data directory:
``data/attachments/anomaly/{anomaly_id}/``. One folder is used per anomaly.
Optional legacy captions are kept in ``captions.json`` inside the same folder.
The Phase 2 metadata contract lives in SQLite; this module remains the
filesystem adapter and keeps the legacy image-only APIs for compatibility.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import sqlite3
import shutil
from pathlib import Path
from typing import Iterable

from database.connection import DATA_DIR

from services.path_name_helpers import contains_invalid_path_char

logger = logging.getLogger(__name__)

ANOMALY_ATTACHMENT_ROOT = DATA_DIR / "attachments" / "anomaly"
ALLOWED_IMAGE_SUFFIXES: frozenset[str] = frozenset({".jpg", ".jpeg", ".png"})
ALLOWED_ATTACHMENT_SUFFIXES: frozenset[str] = frozenset(
    {
        *ALLOWED_IMAGE_SUFFIXES,
        ".csv",
        ".doc",
        ".docx",
        ".json",
        ".log",
        ".pdf",
        ".ppt",
        ".pptx",
        ".txt",
        ".xls",
        ".xlsx",
        ".yaml",
        ".yml",
    }
)
CAPTIONS_FILENAME = "captions.json"


def _sync_anomaly_markdown(anomaly_id: str) -> None:
    """Refresh the anomaly snapshot after an attachment mutation."""
    from services.event._anomaly_markdown import sync_anomaly_markdown_by_id

    try:
        sync_anomaly_markdown_by_id(anomaly_id)
    except (OSError, ValueError, sqlite3.Error):
        logger.debug(
            "Skipped anomaly markdown sync because the anomaly row is unavailable",
            exc_info=True,
        )


def _anomaly_dir(anomaly_id: str) -> Path:
    key = (anomaly_id or "").strip()
    if not key:
        raise ValueError("Anomaly id is required")
    _validate_storage_name(key, field_name="Anomaly id")
    return ANOMALY_ATTACHMENT_ROOT / key


def stored_attachment_path(anomaly_id: str, filename: str) -> Path:
    """Resolve one stored evidence path without creating or mutating it."""
    key = (anomaly_id or "").strip()
    name = (filename or "").strip()
    if not key or not name:
        raise ValueError("Attachment path requires anomaly id and filename")
    safe_key = _validate_storage_name(key, field_name="Anomaly id")
    safe_name = _normalise_attachment_name(name)
    return ANOMALY_ATTACHMENT_ROOT / safe_key / safe_name


def _validate_storage_name(value: str, *, field_name: str) -> str:
    """Validate one path component before it is joined to the data root."""
    name = str(value or "").strip()
    if not name or name in {".", ".."}:
        raise ValueError(f"{field_name} is required")
    path = Path(name)
    if path.is_absolute() or path.name != name:
        raise ValueError(f"{field_name} must be a file name")
    if contains_invalid_path_char(name):
        raise ValueError(f"{field_name} contains an invalid path character")
    return name


def _normalise_attachment_name(
    name: str,
    *,
    fallback_suffix: str = "",
    allowed_suffixes: frozenset[str] = ALLOWED_ATTACHMENT_SUFFIXES,
) -> str:
    value = _validate_storage_name(name, field_name="Attachment file name")
    path = Path(value)
    if not path.suffix and fallback_suffix:
        value = f"{path.name}{fallback_suffix}"
        path = Path(value)
    if path.suffix.lower() not in allowed_suffixes:
        raise ValueError("Attachment file type is not allowed")
    return value


def _resolve_unique_name(target_dir: Path, name: str) -> Path:
    name = _validate_storage_name(name, field_name="Attachment file name")
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
        try:
            destination = _resolve_unique_name(target_dir, path.name)
        except ValueError:
            logger.warning("Skipped attachment with unsafe file name: %s", path)
            continue
        shutil.copy2(path, destination)
        stored.append(destination)
    if stored:
        _sync_anomaly_markdown(anomaly_id)
    return stored


def list_anomaly_attachments(anomaly_id: str) -> list[Path]:
    """Return image files attached to the given anomaly, sorted by name."""
    key = (anomaly_id or "").strip()
    if not key:
        return []
    try:
        folder = _anomaly_dir(key)
    except ValueError:
        return []
    if not folder.is_dir():
        return []
    items = [
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in ALLOWED_IMAGE_SUFFIXES
    ]
    items.sort(key=lambda p: p.name.casefold())
    return items


def list_stored_attachment_files(anomaly_id: str) -> list[Path]:
    """Return all supported evidence files, including non-image documents.

    ``list_anomaly_attachments`` remains image-only for the legacy close-dialog
    contract.  New evidence consumers should use this broader projection.
    """
    key = (anomaly_id or "").strip()
    if not key:
        return []
    folder = _anomaly_dir(key)
    if not folder.is_dir():
        return []
    items = [
        p
        for p in folder.iterdir()
        if p.is_file() and p.name != CAPTIONS_FILENAME
        and p.suffix.lower() in ALLOWED_ATTACHMENT_SUFFIXES
    ]
    items.sort(key=lambda p: p.name.casefold())
    return items


def attachment_file_type(path: Path | str) -> str:
    """Return a stable MIME hint for metadata rows and exports."""
    guessed, _encoding = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def get_anomaly_captions(anomaly_id: str) -> dict[str, str]:
    """Return a {filename: caption} mapping for an anomaly's attachments.

    Returns an empty dict when no captions file exists or it cannot be parsed.
    """
    key = (anomaly_id or "").strip()
    if not key:
        return {}
    try:
        captions_path = _anomaly_dir(key) / CAPTIONS_FILENAME
    except ValueError:
        return {}
    if not captions_path.is_file():
        return {}
    try:
        raw = json.loads(captions_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items() if str(v).strip()}


def set_anomaly_captions(anomaly_id: str, captions: dict[str, str]) -> None:
    """Merge new captions into the captions.json file for an anomaly.

    Empty/whitespace-only captions are removed. Entries for filenames that no
    longer exist on disk are dropped.
    """
    key = (anomaly_id or "").strip()
    if not key:
        raise ValueError("Anomaly id is required")
    folder = _anomaly_dir(key)
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
                logger.debug(
                    "Could not remove empty anomaly captions file", exc_info=True
                )
        _sync_anomaly_markdown(key)
        return
    captions_path.write_text(
        json.dumps(pruned, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _sync_anomaly_markdown(key)


def delete_anomaly_attachment(anomaly_id: str, filename: str) -> bool:
    """Delete a specific attachment file and its caption entry.

    Returns True if the file was deleted, False if it didn't exist.
    """
    key = (anomaly_id or "").strip()
    name = (filename or "").strip()
    if not key or not name:
        return False
    try:
        safe_key = _validate_storage_name(key, field_name="Anomaly id")
        safe_name = _normalise_attachment_name(name)
    except ValueError:
        return False
    path = ANOMALY_ATTACHMENT_ROOT / safe_key / safe_name
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

    try:
        safe_key = _validate_storage_name(key, field_name="Anomaly id")
        safe_old = _normalise_attachment_name(old)
    except ValueError:
        return False

    folder = ANOMALY_ATTACHMENT_ROOT / safe_key
    old_path = folder / safe_old
    if not old_path.is_file():
        return False

    # Ensure new name has a valid extension
    try:
        new = _normalise_attachment_name(
            new,
            fallback_suffix=old_path.suffix,
            allowed_suffixes=ALLOWED_IMAGE_SUFFIXES,
        )
    except ValueError:
        return False

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
            _sync_anomaly_markdown(key)
            return True
        except OSError:
            if temp_path.exists():
                try:
                    temp_path.rename(old_path)
                except OSError:
                    logger.error(
                        "Attachment rename rollback failed, orphaned temp file "
                        "left at %s (original was %s); manual cleanup required.",
                        temp_path,
                        old_path,
                    )
            return False

    # Normal rename
    new_target_path = _resolve_unique_name(folder, new)
    try:
        old_path.rename(new_target_path)
        _update_caption_key(key, old, new_target_path.name)
        _sync_anomaly_markdown(key)
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

    try:
        name = _normalise_attachment_name(
            (target_name or path.name).strip(),
            fallback_suffix=path.suffix,
            allowed_suffixes=ALLOWED_IMAGE_SUFFIXES,
        )
    except ValueError:
        return None

    destination = _resolve_unique_name(target_dir, name)
    shutil.copy2(path, destination)
    _sync_anomaly_markdown(anomaly_id)
    return destination


def import_single_attachment(
    anomaly_id: str,
    src_path: Path | str,
    target_name: str | None = None,
) -> Path | None:
    """Copy one supported evidence file into the anomaly storage folder."""
    target_dir = _anomaly_dir(anomaly_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = Path(src_path)
    if not path.is_file():
        return None
    try:
        name = _normalise_attachment_name(target_name or path.name)
    except ValueError:
        return None
    destination = _resolve_unique_name(target_dir, name)
    shutil.copy2(path, destination)
    _sync_anomaly_markdown(anomaly_id)
    return destination
