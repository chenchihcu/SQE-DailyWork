from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QDate, QSize, Qt
from PySide6.QtGui import QIcon, QIntValidator, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListView,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
)

from database.product_stage import (
    PRODUCT_STAGE_MASS_PRODUCTION,
    PRODUCT_STAGE_OPTIONS,
    normalize_product_stage_ui,
)
from services import attachment_manager, event_service
from ui.layout_constants import (
    DIALOG_OUTER_MARGINS,
    FORM_HORIZONTAL_SPACING,
    FORM_MAX_WIDTH,
    FORM_VERTICAL_SPACING,
    GRID_GUTTER,
    GROUPBOX_CONTENT_MARGINS,
    INLINE_SPACING,
    REF_CELL_MARGINS,
    REF_GRID_SPACING_H,
    REF_GRID_SPACING_V,
    ROW_GAP,
    TECH_CARD_INNER_MARGINS,
    DIALOG_MIN_HEIGHT,
)
from ui.popup_i18n import localize_exception, localize_popup_message
from ui.window_sizing import fit_dialog_to_available_screen
from ui.widgets.common_widgets import (
    RequiredFieldLabel,
    SupplierProductFormMixin,
    make_paired_form_row as _make_paired_form_row,
    mark_button_variant as _mark_button_variant,
    safe_ui_operation,
    set_combo_current_data as _set_combo_current_data,
)
from ui.widgets.close_anomaly_dialog import AttachmentEditor, CloseAnomalyDialog
from ui.widgets.anomaly_attachment_editor import ATTACHMENT_ITEM_SIZE
from ui.widgets.defect_form_widgets import (
    # Constants
    ANOMALY_CATEGORY_OPTIONS,
    ANOMALY_TECH_REF_CARD_DEFS,
    TECH_TRANSFER_STATE_NA,
    TECH_TRANSFER_STATE_NO,
    TECH_TRANSFER_STATE_YES,
    VISIT_TECH_TRANSFER_ITEMS,
    # Helpers (private-name aliases for internal use)
    apply_dialog_layout as _apply_dialog_layout,
    product_label as _product_label,
    set_combo_current_text as _set_combo_current_text,
    set_text_edit_visible_rows as _set_text_edit_visible_rows,
    set_tone as _set_tone,
    style_dialog_buttons as _style_dialog_buttons,
    # Widgets
    DefectNoteTable,
    ProductSectionEditor,
    TechTransferCard,
    VisitSelectionDialog,
)

logger = logging.getLogger(__name__)


# ── NewAnomalyDialog extracted to new_anomaly_dialog.py ────────────────────
from .new_anomaly_dialog import NewAnomalyDialog  # noqa: F401

# ── NewVisitDialog extracted to new_visit_dialog.py ──────────────────────
from .new_visit_dialog import NewVisitDialog  # noqa: F401
