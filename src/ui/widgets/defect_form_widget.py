"""Compatibility re-export shim for the split-up defect-form module family.

The original monolithic defect_form_widget.py was split into
close_anomaly_dialog.py / anomaly_attachment_editor.py / defect_form_widgets.py /
new_anomaly_dialog.py / new_visit_dialog.py. This module keeps only the names
that external callers (tests, scripts/qt_visual_probe.py, event_actions.py)
still import via this path (audit finding B11 trimmed the ~80 leftover unused
imports). New code should import from the concrete modules directly.
"""

from __future__ import annotations

# QMessageBox is re-exported as a patch anchor for tests that stub its static
# methods class-wide (see tests/test_anomaly_category_dropdown.py setUp).
from PySide6.QtWidgets import QMessageBox  # noqa: F401

from ui.widgets.close_anomaly_dialog import (  # noqa: F401
    AttachmentEditor,
    CloseAnomalyDialog,
)
from ui.widgets.anomaly_attachment_editor import ATTACHMENT_ITEM_SIZE  # noqa: F401
from ui.widgets.defect_form_widgets import (  # noqa: F401
    ANOMALY_CATEGORY_OPTIONS,
    TECH_TRANSFER_STATE_NA,
    TECH_TRANSFER_STATE_NO,
    TECH_TRANSFER_STATE_YES,
    VISIT_TECH_TRANSFER_ITEMS,
    ProductSectionEditor,
    TechTransferCard,
)
from ui.widgets.new_anomaly_dialog import NewAnomalyDialog  # noqa: F401
from ui.widgets.new_visit_dialog import NewVisitDialog  # noqa: F401
