"""Pins the Wave-2 inline field validation + dirty-close behaviour.

Covers the shared helpers in ``common_widgets`` (set_field_invalid /
DirtyTrackingMixin) and their wiring into the master-data edit dialogs, so the
field-level error border, real-time clearing, and unsaved-changes guard do not
silently regress.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QLineEdit

from database import connection as database_connection
from ui.widgets.common_widgets import DirtyTrackingMixin, set_field_invalid
from ui.widgets.close_anomaly_dialog import CloseAnomalyDialog
from ui.widgets.new_anomaly_dialog import NewAnomalyDialog
from ui.widgets.new_visit_dialog import NewVisitDialog
from ui.widgets.product_form_dialog import ProductFormDialog
from ui.widgets.supplier_form_dialog import SupplierFormDialog
from ui.widgets.supplier_contact_manager_dialog import SupplierContactManagerDialog


class InlineValidationAndDirtyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._database_temp_dir = tempfile.TemporaryDirectory()
        cls._original_db_path = database_connection.DB_PATH
        cls._original_legacy_db_path = database_connection.LEGACY_DB_PATH
        temp_root = Path(cls._database_temp_dir.name)
        database_connection.DB_PATH = temp_root / "sqe_v2.db"
        database_connection.LEGACY_DB_PATH = temp_root / "sqe.db"
        database_connection.initialize_database()
        cls.app = QApplication.instance() or QApplication([])
        DirtyTrackingMixin._confirm_discard = lambda self: True

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            cls.app.quit()
        database_connection.DB_PATH = cls._original_db_path
        database_connection.LEGACY_DB_PATH = cls._original_legacy_db_path
        cls._database_temp_dir.cleanup()

    def tearDown(self) -> None:
        self.app.processEvents()

    # ── shared helper ────────────────────────────────────────────────────
    def test_set_field_invalid_toggles_property(self) -> None:
        line = QLineEdit()
        self.assertFalse(bool(line.property("invalid")))
        set_field_invalid(line, True)
        self.assertTrue(bool(line.property("invalid")))
        set_field_invalid(line, False)
        self.assertFalse(bool(line.property("invalid")))

    def test_event_dialogs_use_shared_dirty_tracking_mixin(self) -> None:
        for dialog_cls in (NewAnomalyDialog, NewVisitDialog, CloseAnomalyDialog):
            self.assertTrue(issubclass(dialog_cls, DirtyTrackingMixin))

    # ── ProductFormDialog ────────────────────────────────────────────────
    def test_product_dialog_marks_invalid_fields_without_accepting(self) -> None:
        dialog = ProductFormDialog([])
        self.addCleanup(dialog.close)

        dialog._on_submit()  # all required fields empty

        self.assertTrue(bool(dialog.product_code_input.property("invalid")))
        self.assertTrue(bool(dialog.product_name_input.property("invalid")))
        self.assertTrue(bool(dialog.primary_supplier_combo.property("invalid")))
        self.assertFalse(dialog.inline_error.isHidden())
        self.assertNotEqual(dialog.inline_error.text().strip(), "")
        self.assertEqual(dialog.result(), 0)  # not accepted

    def test_product_dialog_clears_errors_on_edit(self) -> None:
        dialog = ProductFormDialog([])
        self.addCleanup(dialog.close)
        dialog._on_submit()
        self.assertTrue(bool(dialog.product_code_input.property("invalid")))

        dialog.product_code_input.setText("P-001")  # textChanged -> _clear_validation

        self.assertFalse(bool(dialog.product_code_input.property("invalid")))
        self.assertTrue(dialog.inline_error.isHidden())

    def test_product_dialog_is_dirty_tracking_mixin(self) -> None:
        dialog = ProductFormDialog([])
        self.addCleanup(dialog.close)
        self.assertIsInstance(dialog, DirtyTrackingMixin)
        self.assertFalse(dialog._dirty)

        dialog.product_name_input.setText("abc")  # user edit
        self.assertTrue(dialog._dirty)

    def test_product_dialog_closeevent_guards_unsaved_changes(self) -> None:
        dialog = ProductFormDialog([])
        self.addCleanup(dialog.close)
        dialog.product_name_input.setText("abc")
        self.assertTrue(dialog._dirty)

        dialog._confirm_discard = lambda: False  # user clicks "No"
        event = QCloseEvent()
        dialog.closeEvent(event)
        self.assertFalse(event.isAccepted())  # close blocked

        dialog._confirm_discard = lambda: True  # user clicks "Yes"
        event2 = QCloseEvent()
        dialog.closeEvent(event2)
        self.assertTrue(event2.isAccepted())  # close allowed

    def test_product_dialog_clean_close_is_not_blocked(self) -> None:
        dialog = ProductFormDialog([])
        self.addCleanup(dialog.close)
        self.assertFalse(dialog._dirty)
        event = QCloseEvent()
        dialog.closeEvent(event)
        self.assertTrue(event.isAccepted())

    # ── SupplierFormDialog ───────────────────────────────────────────────
    def test_supplier_dialog_inline_validation_and_dirty(self) -> None:
        dialog = SupplierFormDialog()
        self.addCleanup(dialog.close)
        self.assertIsInstance(dialog, DirtyTrackingMixin)

        dialog._on_submit()  # supplier name empty
        self.assertTrue(bool(dialog.supplier_name_input.property("invalid")))
        self.assertFalse(dialog.inline_error.isHidden())
        self.assertEqual(dialog.result(), 0)

        dialog.supplier_name_input.setText("ACME")  # fixes it
        self.assertFalse(bool(dialog.supplier_name_input.property("invalid")))
        self.assertTrue(dialog._dirty)

    # ── SupplierContactManagerDialog (light guard) ───────────────────────
    def test_contact_manager_light_dirty_and_inline(self) -> None:
        dialog = SupplierContactManagerDialog("missing-supplier", "測試供應商")
        dialog._confirm_discard = lambda: True
        self.addCleanup(dialog.close)
        self.assertIsInstance(dialog, DirtyTrackingMixin)
        self.assertFalse(dialog._dirty)

        dialog._on_add()  # empty name -> inline error, no DB write
        self.assertTrue(bool(dialog.new_name.property("invalid")))
        self.assertFalse(dialog.inline_error.isHidden())

        dialog.new_name.setText("王小明")  # typing marks dirty + clears error
        self.assertTrue(dialog._dirty)
        self.assertFalse(bool(dialog.new_name.property("invalid")))


if __name__ == "__main__":
    unittest.main()
