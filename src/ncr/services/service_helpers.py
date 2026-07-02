"""Shared helpers for the NCR service layer."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def unique_violation_as_value_error(message: str) -> Iterator[None]:
    """Re-raise a UNIQUE-constraint IntegrityError as a user-facing ValueError.

    product_service and supplier_service previously copy-pasted this
    try/except shape around every create/update crud call (audit finding
    D12); any other IntegrityError still propagates unchanged.
    """
    try:
        yield
    except sqlite3.IntegrityError as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise ValueError(message) from exc
        raise
