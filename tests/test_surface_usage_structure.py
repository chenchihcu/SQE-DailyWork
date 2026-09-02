from __future__ import annotations

import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QWidget

from ui.main_window import STATS_PAGE_INDEX, NCR_STATS_PAGE_INDEX, MainWindow
from ui.theme import apply_app_theme
from ui.widgets.common_widgets import (
    AnalyticsWorkflowShell,
    CreateWorkflowShell,
    QueryWorkflowShell,
)


class SurfaceUsageStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        apply_app_theme(cls.app)

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            pass  # do not terminate shared QApplication singleton in test runner

    def setUp(self) -> None:
        self.window = MainWindow()
        self.window.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.window.close()
        self.app.processEvents()

    def _is_descendant_of(self, widget: QWidget, maybe_ancestor: QWidget) -> bool:
        parent = widget.parentWidget()
        while parent is not None:
            if parent is maybe_ancestor:
                return True
            parent = parent.parentWidget()
        return False

    def test_query_page_subpanel_structure_and_roles_are_consistent(self) -> None:
        query = self.window.events_widget
        frames = query.findChildren(QFrame)
        subpanels = [frame for frame in frames if frame.property("role") == "subpanel"]
        panels = [frame for frame in frames if frame.property("role") == "panel"]

        self.assertEqual(1, len(subpanels), "query page should have exactly one subpanel")
        self.assertEqual(1, len(panels), "query page should have exactly one result panel")

        filter_subpanel = subpanels[0]
        result_panel = panels[0]
        self.assertIs(query, filter_subpanel.parentWidget())
        self.assertIs(query, result_panel.parentWidget())
        self.assertFalse(self._is_descendant_of(filter_subpanel, result_panel))
        self.assertFalse(self._is_descendant_of(result_panel, filter_subpanel))
        self.assertIsInstance(filter_subpanel, QueryWorkflowShell)

        ncr_query = self.window.ncr.pending_outsource_widget
        ncr_shell = ncr_query.findChild(QueryWorkflowShell)
        self.assertIsNotNone(ncr_shell)

    def test_create_and_analytics_pages_use_shared_shells(self) -> None:
        self.assertIsInstance(self.window.new_anomaly_page.workflow_shell, CreateWorkflowShell)
        self.window._switch_primary_page(STATS_PAGE_INDEX)
        self.app.processEvents()
        stats_shell = self.window.stats_widget.workflow_shell
        self.assertIsInstance(stats_shell, AnalyticsWorkflowShell)
        self.assertTrue(stats_shell.isVisible())
        self.window._switch_primary_page(NCR_STATS_PAGE_INDEX)
        self.app.processEvents()
        ncr_stats_shell = self.window.ncr_stats_widget.workflow_shell
        self.assertIsInstance(ncr_stats_shell, AnalyticsWorkflowShell)
        self.assertTrue(ncr_stats_shell.isVisible())
        stats_refresh = next(
            button
            for button in self.window.stats_widget.findChildren(QPushButton)
            if button.text() == "重新整理"
        )
        self.assertTrue(self._is_descendant_of(stats_refresh, stats_shell))

    def test_master_data_toolbar_and_tab_host_are_direct_page_siblings(self) -> None:
        master = self.window.master_widget
        self.assertIs(master, master.inline_toolbar.parentWidget())
        self.assertIs(master, master.content_host.parentWidget())

    def test_surface_raised_is_not_used_in_runtime_or_ui_sources(self) -> None:
        raised_widgets = [
            widget
            for widget in self.window.findChildren(QWidget)
            if widget.property("surface") == "raised"
        ]
        self.assertEqual([], raised_widgets)

        project_root = Path(__file__).resolve().parents[1]
        ui_files = [project_root / "src" / "ui" / "main_window.py"]
        ui_files.extend((project_root / "src" / "ui" / "widgets").glob("*.py"))

        for file_path in ui_files:
            content = file_path.read_text(encoding="utf-8")
            self.assertNotIn('setProperty("surface", "raised")', content)
            self.assertNotIn("setProperty('surface', 'raised')", content)

    def test_content_host_remains_transparent_tab_host_and_allows_page_panels(self) -> None:
        content_host = self.window.stack.parentWidget()
        self.assertIsInstance(content_host, QFrame)
        self.assertIsNone(content_host.property("role"))
        self.assertEqual("ContentHost", content_host.objectName())

        _ = self.window.events_widget
        _ = self.window.master_widget

        nested_panels = [
            frame
            for frame in self.window.findChildren(QFrame)
            if frame.property("role") == "panel"
            and frame is not content_host
            and self._is_descendant_of(frame, content_host)
        ]
        self.assertGreater(
            len(nested_panels),
            0,
            "panel-in-panel baseline should remain allowed in current policy",
        )


if __name__ == "__main__":
    unittest.main()
