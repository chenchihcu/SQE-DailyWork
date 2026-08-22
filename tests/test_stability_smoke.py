"""Lightweight multi-cycle MainWindow navigation stability smoke."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SQE_TESTING", "1")

from PySide6.QtWidgets import QApplication

from ui.main_window import (
    EVENT_PAGE_INDEX,
    HOME_PAGE_INDEX,
    MainWindow,
    STATS_PAGE_INDEX,
)
from ui.theme import apply_app_theme

_DEFAULT_CYCLES = 10
_STABILITY_CYCLES = int(os.environ.get("SQE_STABILITY_CYCLES", str(_DEFAULT_CYCLES)))


class StabilitySmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        apply_app_theme(cls.app)

    @classmethod
    def tearDownClass(cls) -> None:
        pass  # keep shared QApplication alive for the test runner

    def _cycle_main_window(self) -> None:
        window = MainWindow()
        window.show()
        self.app.processEvents()

        window._switch_primary_page(EVENT_PAGE_INDEX)
        self.app.processEvents()
        window._switch_primary_page(STATS_PAGE_INDEX)
        self.app.processEvents()
        window._switch_primary_page(HOME_PAGE_INDEX)
        self.app.processEvents()

        current = window.stack.currentWidget()
        if current is not None and hasattr(current, "refresh_data"):
            current.refresh_data()
            self.app.processEvents()

        window.close()
        self.app.processEvents()

    def test_main_window_navigation_cycles(self) -> None:
        cycles = max(1, _STABILITY_CYCLES)
        for _ in range(cycles):
            self._cycle_main_window()

        final = MainWindow()
        final.show()
        self.app.processEvents()
        self.assertGreater(final.stack.count(), 0)
        final.close()
        self.app.processEvents()
