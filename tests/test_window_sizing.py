from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from ui.window_sizing import (
    fit_dialog_to_available_screen,
    fit_widget_to_available_screen,
    restore_or_fit_window_geometry,
)


class WindowSizingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            pass  # do not terminate shared QApplication singleton in test runner

    def test_fit_widget_preserves_supported_minimum_by_default(self) -> None:
        widget = QWidget()
        try:
            fit_widget_to_available_screen(
                widget,
                preferred_width=1360,
                preferred_height=860,
                minimum_width=1024,
                minimum_height=680,
                maximum_width=1920,
                maximum_height=1200,
            )
            self.assertEqual(1024, widget.minimumWidth())
            self.assertEqual(680, widget.minimumHeight())
            self.assertGreaterEqual(widget.width(), 1024)
            self.assertGreaterEqual(widget.height(), 680)
        finally:
            widget.close()

    def test_fit_widget_can_shrink_minimum_for_dialog_visibility(self) -> None:
        widget = QWidget()
        try:
            fit_widget_to_available_screen(
                widget,
                preferred_width=1200,
                preferred_height=900,
                minimum_width=1200,
                minimum_height=900,
                margin_x=40,
                margin_y=60,
                shrink_minimum_to_screen=True,
            )
            self.assertLessEqual(widget.width(), 1200)
            self.assertLessEqual(widget.height(), 900)
            self.assertLessEqual(widget.minimumWidth(), widget.width())
            self.assertLessEqual(widget.minimumHeight(), widget.height())
        finally:
            widget.close()

    def test_restore_or_fit_standard_mode(self) -> None:
        widget = QWidget()
        try:
            restore_or_fit_window_geometry(
                widget,
                geometry_mode="standard",
                preferred_width=1360,
                preferred_height=860,
                minimum_width=1024,
                minimum_height=680,
            )
            self.assertEqual(1024, widget.minimumWidth())
            self.assertEqual(680, widget.minimumHeight())
            self.assertGreaterEqual(widget.width(), 1024)
            self.assertGreaterEqual(widget.height(), 680)
        finally:
            widget.close()

    def test_restore_or_fit_remember_mode_with_none_data(self) -> None:
        widget = QWidget()
        try:
            restore_or_fit_window_geometry(
                widget,
                geometry_mode="remember",
                geometry_data=None,
                preferred_width=1360,
                preferred_height=860,
                minimum_width=1024,
                minimum_height=680,
            )
            self.assertEqual(1024, widget.minimumWidth())
            self.assertEqual(680, widget.minimumHeight())
            self.assertGreaterEqual(widget.width(), 1024)
            self.assertGreaterEqual(widget.height(), 680)
        finally:
            widget.close()

    def test_restore_or_fit_remember_mode_with_corrupt_data(self) -> None:
        widget = QWidget()
        try:
            restore_or_fit_window_geometry(
                widget,
                geometry_mode="remember",
                geometry_data=b"invalid_corrupt_byte_array",
                preferred_width=1360,
                preferred_height=860,
                minimum_width=1024,
                minimum_height=680,
            )
            self.assertEqual(1024, widget.minimumWidth())
            self.assertEqual(680, widget.minimumHeight())
            self.assertGreaterEqual(widget.width(), 1024)
            self.assertGreaterEqual(widget.height(), 680)
        finally:
            widget.close()

    def test_restore_or_fit_remember_mode_with_valid_saved_geometry(self) -> None:
        source_widget = QWidget()
        source_widget.resize(800, 500)
        saved_geom = source_widget.saveGeometry()
        source_widget.close()

        target_widget = QWidget()
        try:
            restore_or_fit_window_geometry(
                target_widget,
                geometry_mode="remember",
                geometry_data=saved_geom,
                preferred_width=850,
                preferred_height=550,
                minimum_width=600,
                minimum_height=400,
                maximum_width=1920,
                maximum_height=1200,
            )
            self.assertEqual(600, target_widget.minimumWidth())
            self.assertEqual(400, target_widget.minimumHeight())
            self.assertGreaterEqual(target_widget.width(), 600)
            self.assertGreaterEqual(target_widget.height(), 400)
        finally:
            target_widget.close()

    def test_restore_or_fit_remember_mode_oversized_clamped(self) -> None:
        # Create an oversized widget and save its geometry (e.g. 5000x3000)
        source_widget = QWidget()
        source_widget.resize(5000, 3000)
        saved_geom = source_widget.saveGeometry()
        source_widget.close()

        target_widget = QWidget()
        try:
            restore_or_fit_window_geometry(
                target_widget,
                geometry_mode="remember",
                geometry_data=saved_geom,
                preferred_width=1360,
                preferred_height=860,
                minimum_width=1024,
                minimum_height=680,
                maximum_width=1920,
                maximum_height=1200,
            )
            self.assertEqual(1024, target_widget.minimumWidth())
            self.assertEqual(680, target_widget.minimumHeight())
            # Width and height must be clamped to screen / maximum allowed
            self.assertLessEqual(target_widget.width(), 1920)
            self.assertLessEqual(target_widget.height(), 1200)
        finally:
            target_widget.close()

    def test_qt_message_handler_filters_set_geometry(self) -> None:
        from PySide6.QtCore import QtMsgType
        from main import _qt_message_handler

        with self.assertLogs("SQE", level="DEBUG") as cm:
            _qt_message_handler(
                QtMsgType.QtWarningMsg,
                None,
                "QWindowsWindow::setGeometry: Unable to set geometry 3540x1466+0+46",
            )
        self.assertTrue(any("Qt 平台幾何通知" in output for output in cm.output))


if __name__ == "__main__":
    unittest.main()
