"""Shared helpers for the NCR supplier / outsource-supplier combo boxes.

Both the defect entry form (`defect_form.py`) and the defect list filter
(`defect_list.py`) load supplier names from the shared ``supplier_records`` view
by category and enforce a mutual-exclusion lock between the (formal) supplier and
the outsource supplier. The data query and the enable/hint structure are
identical; only the "is this combo filled?" predicate differs — the form treats
the ``N/A`` sentinel as empty, while the list keys off the placeholder at index
0 — so that predicate is injected by the caller.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from PySide6.QtWidgets import QComboBox, QLabel

from ncr.models.labels import HINT_OUTSOURCE_LOCKED, HINT_SUPPLIER_LOCKED

SUPPLIER_CATEGORY_FORMAL = "正式供應商"
SUPPLIER_CATEGORY_OUTSOURCE = "委外供應商"


def load_supplier_names_by_category(
    conn: sqlite3.Connection, category: str
) -> list[str]:
    """Return supplier names for one category, ordered case-insensitively."""
    cursor = conn.execute(
        """
        SELECT name
        FROM supplier_records
        WHERE category = ?
        ORDER BY name COLLATE NOCASE
        """,
        (category,),
    )
    return [row[0] for row in cursor.fetchall()]


def apply_supplier_exclusion_lock(
    *,
    supplier_combo: QComboBox,
    outsource_combo: QComboBox,
    hint_label: QLabel,
    is_filled: Callable[[QComboBox], bool],
) -> None:
    """Enforce mutual exclusion: filling one combo disables the other.

    ``is_filled`` decides whether a combo counts as filled; callers inject their
    own rule (the form ignores the ``N/A`` sentinel, the list ignores index 0).
    """
    supplier_filled = is_filled(supplier_combo)
    outsource_filled = is_filled(outsource_combo)

    supplier_combo.setEnabled(not outsource_filled)
    outsource_combo.setEnabled(not supplier_filled)

    if supplier_filled:
        hint_label.setText(HINT_SUPPLIER_LOCKED)
        hint_label.show()
    elif outsource_filled:
        hint_label.setText(HINT_OUTSOURCE_LOCKED)
        hint_label.show()
    else:
        hint_label.hide()
