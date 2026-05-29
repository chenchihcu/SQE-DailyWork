from __future__ import annotations

import re
import unittest

from ui.theme import TOKENS, get_theme_qss


def _selector_block(qss: str, selector: str) -> str:
    escaped = re.escape(selector)
    match = re.search(rf"{escaped}[^{{]*\{{(.*?)\}}", qss, re.DOTALL)
    if match is None:
        raise AssertionError(f"missing selector: {selector}")
    return match.group(1)


class ThemeMinimalSurfacesTests(unittest.TestCase):
    def test_color_polish_tokens_are_declared(self) -> None:
        for token in (
            "surface_hover",
            "surface_active",
            "focus_ring",
            "status_na_bg",
            "filter_active_bg",
            "attachment_selected_border",
            "empty_state_bg",
        ):
            self.assertIn(token, TOKENS)

    def test_surface_frames_use_panel_tokens(self) -> None:
        qss = get_theme_qss()
        for selector in (
            'QFrame[role="panel"]',
            'QFrame[role="subpanel"]',
            'QFrame[role="card"]',
        ):
            block = _selector_block(qss, selector)
            self.assertIn(f'background: {TOKENS["panel_bg"]};', block)
            self.assertIn(f'border: 1px solid {TOKENS["border_soft"]};', block)

    def test_main_workflow_tabs_use_reference_layers(self) -> None:
        qss = get_theme_qss()

        pane = _selector_block(qss, "QTabWidget#MainWorkflowTabs::pane")
        self.assertIn(f'background: {TOKENS["panel_bg"]};', pane)
        self.assertIn(f'border: 1px solid {TOKENS["border"]};', pane)

        tab = _selector_block(qss, "QTabWidget#MainWorkflowTabs QTabBar::tab")
        self.assertIn(f'background: {TOKENS["nav_dark_bg"]};', tab)
        self.assertIn(f'color: {TOKENS["nav_dark_text"]};', tab)

        selected = _selector_block(qss, "QTabWidget#MainWorkflowTabs QTabBar::tab:selected")
        self.assertIn(f'background: {TOKENS["nav_dark_bg"]};', selected)
        self.assertIn(f'color: {TOKENS["nav_dark_text_active"]};', selected)

    def test_event_scope_tabs_use_filter_active_tokens(self) -> None:
        qss = get_theme_qss()

        tab = _selector_block(qss, "QTabBar#EventQueryScopeTabs::tab")
        self.assertIn(f'background: {TOKENS["panel_bg"]};', tab)
        self.assertIn(f'border: 1px solid {TOKENS["border"]};', tab)

        selected = _selector_block(qss, "QTabBar#EventQueryScopeTabs::tab:selected")
        self.assertIn(f'background: {TOKENS["filter_active_bg"]};', selected)
        self.assertIn(f'color: {TOKENS["filter_active_text"]};', selected)
        self.assertIn(f'border: 1px solid {TOKENS["filter_active_border"]};', selected)

    def test_semantic_button_colors_are_preserved(self) -> None:
        qss = get_theme_qss()

        primary = _selector_block(qss, 'QPushButton[variant="primary"]')
        self.assertIn(f'background: {TOKENS["primary_btn"]};', primary)

        danger = _selector_block(qss, 'QPushButton[variant="danger"]')
        self.assertIn(f'color: {TOKENS["danger"]};', danger)
        self.assertIn(f'border: 1px solid {TOKENS["danger_border"]};', danger)


if __name__ == "__main__":
    unittest.main()
