from __future__ import annotations

import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame, QLabel, QWidget

from ui.main_window import MainWindow
from ui.theme import apply_app_theme


class SurfaceUsageStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        apply_app_theme(cls.app)


    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            cls.app.quit()

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

    def test_home_page_contains_workbench_panels(self) -> None:
        home = self.window.home_widget
        frames = home.findChildren(QFrame)
        panels = [f for f in frames if f.property("role") == "panel"]

        # Daily cockpit: KPI management panel + one read-only backlog panel.
        panel_names = {p.objectName() for p in panels}
        self.assertEqual(2, len(panels))
        self.assertIn("HomeKpiPanel", panel_names)
        self.assertIn("HomeBacklogPanel", panel_names)

        labels = home.findChildren(QLabel)
        texts = [l.text() for l in labels]
        self.assertNotIn("快速入口", texts)
        self.assertIn("逾期未結", texts)

        kpi_cards = [f for f in frames if f.property("role") == "kpiCard"]
        self.assertEqual(4, len(kpi_cards))

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
        assert isinstance(content_host, QFrame)
        self.assertIsNone(content_host.property("role"))
        self.assertEqual("ContentHost", content_host.objectName())

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
