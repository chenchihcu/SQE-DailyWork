"""Filesystem support for per-anomaly working folders."""

from __future__ import annotations

import re
from pathlib import Path


ANOMALY_FOLDER_ROOT = (
    Path(__file__).resolve().parents[3] / "Outputs" / "ncr number file"
)
_INVALID_WINDOWS_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _safe_folder_component(value: str) -> str:
    """Return a Windows-safe name while preserving readable supplier text."""
    normalized = _INVALID_WINDOWS_NAME_CHARS.sub("_", str(value or "").strip())
    normalized = normalized.rstrip(" .")
    if not normalized:
        raise ValueError("Supplier name is required for anomaly folder")
    return normalized


def prepare_anomaly_folder_root() -> Path:
    """Ensure the configured anomaly-folder root is writable before DB creation."""
    ANOMALY_FOLDER_ROOT.mkdir(parents=True, exist_ok=True)
    return ANOMALY_FOLDER_ROOT


def create_anomaly_folder(*, supplier_name: str, anomaly_no: str) -> Path:
    """Create or reuse ``<supplier name><anomaly no>`` below the output root."""
    safe_supplier = _safe_folder_component(supplier_name)
    safe_anomaly_no = _safe_folder_component(anomaly_no)
    folder = prepare_anomaly_folder_root() / f"{safe_supplier}{safe_anomaly_no}"
    folder.mkdir(exist_ok=True)
    return folder


def relocate_anomaly_folder(
    *,
    old_supplier_name: str,
    old_anomaly_no: str,
    new_supplier_name: str,
    new_anomaly_no: str,
) -> Path:
    """Rename an existing working folder and its snapshot when identity changes."""
    root = prepare_anomaly_folder_root()
    old_name = (
        f"{_safe_folder_component(old_supplier_name)}"
        f"{_safe_folder_component(old_anomaly_no)}"
    )
    new_name = (
        f"{_safe_folder_component(new_supplier_name)}"
        f"{_safe_folder_component(new_anomaly_no)}"
    )
    old_folder = root / old_name
    new_folder = root / new_name
    if old_folder == new_folder or not old_folder.exists():
        return new_folder
    if new_folder.exists():
        raise FileExistsError(f"Anomaly folder already exists: {new_folder}")
    old_folder.rename(new_folder)
    old_markdown = new_folder / f"{old_name}.md"
    new_markdown = new_folder / f"{new_name}.md"
    if old_markdown.is_file():
        old_markdown.rename(new_markdown)
    return new_folder
