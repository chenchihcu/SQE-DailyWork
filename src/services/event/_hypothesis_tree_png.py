"""Offscreen Qt renderer for multi-layer hypothesis trees in exports."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

HYPOTHESIS_EXCEL_PNG_LIMIT = 12


def _hypothesis_node_label(row: dict[str, Any], *, max_len: int | None = None) -> str:
    level = int(row.get("level") or 1)
    status = str(row.get("status") or "").strip()
    statement = str(row.get("statement") or "").replace("\n", " ").strip()
    label = f"L{level} [{status}] {statement}"
    if max_len is not None:
        return label[:max_len]
    return label


def format_hypothesis_tree_text(hypotheses: list[dict[str, Any]]) -> str:
    """Plain-text fallback when PNG rendering is disabled or fails."""
    if not hypotheses:
        return ""
    lines: list[str] = []
    for row in hypotheses:
        level = int(row.get("level") or 1)
        indent = "  " * max(level - 1, 0)
        lines.append(f"{indent}{_hypothesis_node_label(row)}")
    return "\n".join(lines)


def render_hypothesis_tree_png(
    hypotheses: list[dict[str, Any]],
    output_path: str | Path,
    *,
    width: int = 520,
    row_height: int = 26,
) -> bool:
    """Render a hypothesis tree to PNG using an offscreen QTreeWidget."""
    if not hypotheses:
        return False
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QTreeWidget, QTreeWidgetItem

        app = QApplication.instance()
        if app is None:
            QApplication([])

        tree = QTreeWidget()
        tree.setHeaderHidden(True)
        tree.setColumnCount(1)
        items: dict[str, QTreeWidgetItem] = {}
        for row in hypotheses:
            hypothesis_id = str(row.get("id") or "").strip()
            parent_id = str(row.get("parent_hypothesis_id") or "").strip()
            label = _hypothesis_node_label(row, max_len=140)
            item = QTreeWidgetItem([label])
            if parent_id and parent_id in items:
                items[parent_id].addChild(item)
            else:
                tree.addTopLevelItem(item)
            if hypothesis_id:
                items[hypothesis_id] = item

        height = max(120, min(640, len(hypotheses) * row_height + 36))
        tree.resize(width, height)
        tree.expandAll()

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        pixmap_ok = tree.grab().save(str(output))
        return bool(pixmap_ok) and output.exists() and output.stat().st_size > 0
    except Exception:
        logger.exception("Hypothesis tree PNG render failed: %s", output_path)
        return False
