"""Runtime flags for automated Qt runs (tests, probes, disposable verify)."""

from __future__ import annotations

import os
from collections.abc import Mapping


def is_automated_runtime(environ: Mapping[str, str] | None = None) -> bool:
    """True when blocking Qt dialogs must not be shown.

    Matches AGENTS Automated Modal Guard: offscreen Qt, SQE_TESTING,
    SQE_PROBE, and SQE_REQUIRE_DISPOSABLE_DB.
    """
    source = os.environ if environ is None else environ
    return (
        source.get("QT_QPA_PLATFORM") == "offscreen"
        or source.get("SQE_TESTING") == "1"
        or source.get("SQE_REQUIRE_DISPOSABLE_DB") == "1"
        or source.get("SQE_PROBE") == "1"
    )


def missing_supplier_create_gate(
    has_suppliers: bool,
    *,
    automated: bool | None = None,
) -> tuple[bool, bool]:
    """Return ``(may_proceed, should_warn)`` for create-page navigation.

    Empty schema-only verify DBs have no suppliers. Automated runs must not
    block on ``QMessageBox.warning``; interactive runs still warn then redirect.
    """
    if has_suppliers:
        return True, False
    if automated is None:
        automated = is_automated_runtime()
    return False, not automated
