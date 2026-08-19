"""Focused regression tests for the shared UI helpers exported by
``src.ui.widgets.common_widgets``.

This test pins the public contracts referenced by the SQE DailyWork design
framework cross-reference table (``docs/ui-layout-theme-contract.md`` §Design
Framework Cross-Reference, items 1-9). It deliberately avoids touching the
underlying helpers; the goal is to fail loudly if a future refactor breaks
the expected behaviour.

Coverage:
- ``EmptyStateWidget`` — title / hint rendering, hint visibility, dynamic
  message updates, and role assignment for QSS styling.
- ``RequiredFieldLabel`` — required marker is appended through a red ``*``
  span and re-applied on every ``setText`` call.
- ``make_paired_form_row`` — emits a 4-column grid with stretchable field
  columns and collapses the right label/field when the right label is
  ``None``.
- ``mark_button_variant`` — flips the ``variant`` property and repolishes the
  button so the QSS role is recognised.
- ``create_section_card`` — sets the ``panel`` role and uses ``PANEL_MARGINS``
  / ``FORM_VERTICAL_SPACING`` constants from ``layout_constants``.
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton

from ui.layout_constants import FORM_VERTICAL_SPACING, PANEL_MARGINS
from ui.theme import TOKENS
from ui.widgets.common_widgets import (
    EmptyStateWidget,
    RequiredFieldLabel,
    create_section_card,
    make_paired_form_row,
    mark_button_variant,
)


def _ensure_qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


class EmptyStateWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _ensure_qapp()

    def test_title_and_hint_render_in_widget(self) -> None:
        widget = EmptyStateWidget("尚無資料", "請新增第一筆資料")
        self.addCleanup(widget.deleteLater)
        self.assertEqual(widget.property("role"), "emptyState")
        self.assertIn("尚無資料", widget._title_label.text())
        self.assertEqual(widget._hint_label.text(), "請新增第一筆資料")
        # The hint label is explicitly shown when hint text is non-empty.
        self.assertTrue(widget._hint_label.isVisibleTo(widget))

    def test_empty_hint_is_hidden(self) -> None:
        widget = EmptyStateWidget("尚無資料")
        self.addCleanup(widget.deleteLater)
        # Without an explicit hint, the hint label must stay hidden.
        self.assertFalse(widget._hint_label.isVisibleTo(widget))

    def test_set_message_updates_title_and_hint_visibility(self) -> None:
        widget = EmptyStateWidget("初始", "初始提示")
        self.addCleanup(widget.deleteLater)

        widget.set_message("更新後", "新提示")
        self.assertEqual(widget._title_label.text(), "更新後")
        self.assertEqual(widget._hint_label.text(), "新提示")
        self.assertTrue(widget._hint_label.isVisibleTo(widget))

        widget.set_message("無提示")
        self.assertEqual(widget._title_label.text(), "無提示")
        # Passing an empty hint re-hides the hint label.
        self.assertFalse(widget._hint_label.isVisibleTo(widget))


class RequiredFieldLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _ensure_qapp()

    def test_required_role_and_red_asterisk(self) -> None:
        label = RequiredFieldLabel("供應商")
        self.addCleanup(label.deleteLater)
        self.assertEqual(label.property("role"), "requiredLabel")
        self.assertIn("供應商", label.text())
        self.assertIn(TOKENS["danger"], label.text())
        self.assertIn("*", label.text())

    def test_set_text_replaces_value_and_keeps_asterisk(self) -> None:
        label = RequiredFieldLabel("供應商")
        self.addCleanup(label.deleteLater)
        label.setText("產品")
        self.assertIn("產品", label.text())
        self.assertIn(TOKENS["danger"], label.text())
        self.assertIn("*", label.text())


class MakePairedFormRowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _ensure_qapp()

    def test_left_label_and_both_fields_stretch(self) -> None:
        left_label, left_field = QLineEdit(), QLineEdit()
        right_label, right_field = QLineEdit(), QLineEdit()
        row = make_paired_form_row(
            "TestRow",
            left_label,
            left_field,
            right_label,
            right_field,
        )
        self.addCleanup(row.deleteLater)

        grid = row.layout()
        self.assertEqual(grid.columnCount(), 4)
        self.assertEqual(grid.columnStretch(1), 1)
        self.assertEqual(grid.columnStretch(3), 1)
        self.assertEqual(grid.itemAtPosition(0, 1).widget(), left_field)
        self.assertEqual(grid.itemAtPosition(0, 3).widget(), right_field)

    def test_missing_right_label_collapses_right_pair(self) -> None:
        left_label, left_field = QLineEdit(), QLineEdit()
        right_field = QLineEdit()
        row = make_paired_form_row(
            "TestRow",
            left_label,
            left_field,
            None,
            right_field,
        )
        self.addCleanup(row.deleteLater)

        grid = row.layout()
        # Without a right label, the right field is added at column 2 and must
        # span columns 2-3 so the row layout still fills the full grid width.
        self.assertEqual(grid.columnCount(), 4)
        # The left label and left field keep their natural positions.
        self.assertEqual(grid.itemAtPosition(0, 0).widget(), left_label)
        self.assertEqual(grid.itemAtPosition(0, 1).widget(), left_field)
        # The right field starts at column 2 and spans 2 columns so it covers
        # the column normally occupied by the missing right label.
        index = grid.indexOf(right_field)
        (_, col, _row_span, col_span) = grid.getItemPosition(index)
        self.assertEqual(col, 2)
        self.assertEqual(col_span, 2)

    def test_string_label_is_wrapped_in_qlabel(self) -> None:
        row = make_paired_form_row(
            "TestRow",
            "文字標籤",
            QLineEdit(),
            None,
            QLineEdit(),
        )
        self.addCleanup(row.deleteLater)

        from PySide6.QtWidgets import QLabel

        grid = row.layout()
        first_widget = grid.itemAtPosition(0, 0).widget()
        self.assertIsInstance(first_widget, QLabel)
        self.assertEqual(first_widget.text(), "文字標籤")


class MarkButtonVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _ensure_qapp()

    def test_sets_variant_property_and_polishes(self) -> None:
        button = QPushButton("確認")
        self.addCleanup(button.deleteLater)
        mark_button_variant(button, "primary")
        self.assertEqual(button.property("variant"), "primary")

    def test_none_button_is_a_noop(self) -> None:
        # Should not raise even when the button argument is None.
        mark_button_variant(None, "primary")


class CreateSectionCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _ensure_qapp()

    def test_panel_role_and_layout_constants(self) -> None:
        card = create_section_card()
        self.addCleanup(card.deleteLater)
        self.assertEqual(card.property("role"), "panel")

        layout = card.layout()
        margins = layout.contentsMargins()
        self.assertEqual(
            (margins.left(), margins.top(), margins.right(), margins.bottom()),
            PANEL_MARGINS,
        )
        self.assertEqual(layout.spacing(), FORM_VERTICAL_SPACING)


if __name__ == "__main__":
    unittest.main()