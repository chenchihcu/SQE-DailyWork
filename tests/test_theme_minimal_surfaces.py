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
            "sidebar_panel",
            "sidebar_muted",
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

    def test_retired_stats_tabs_qss_is_not_reintroduced(self) -> None:
        qss = get_theme_qss()
        self.assertNotIn("StatsTabs", qss)

    def test_stats_dashboard_shared_roles_are_styled(self) -> None:
        qss = get_theme_qss()
        banner = _selector_block(qss, 'QFrame[role="statsInfoBanner"]')
        self.assertIn(f'background: {TOKENS["panel_alt_bg"]};', banner)
        self.assertIn(f'border: 1px solid {TOKENS["border"]};', banner)

        insight = _selector_block(qss, 'QLabel[role="insight"]')
        self.assertIn(f'background: {TOKENS["panel_alt_bg"]};', insight)
        self.assertIn(f'border-left: 4px solid {TOKENS["info"]};', insight)

    def test_semantic_button_colors_are_preserved(self) -> None:
        qss = get_theme_qss()

        primary = _selector_block(qss, 'QPushButton[variant="primary"]')
        self.assertIn(f'background: {TOKENS["primary_btn"]};', primary)

        danger = _selector_block(qss, 'QPushButton[variant="danger"]')
        self.assertIn(f'color: {TOKENS["danger"]};', danger)
        self.assertIn(f'border: 1px solid {TOKENS["danger_border"]};', danger)

    def test_sidebar_palette_uses_distinct_visual_roles(self) -> None:
        self.assertNotEqual(TOKENS["sidebar_bg"], TOKENS["sidebar_panel"])
        self.assertNotEqual(TOKENS["sidebar_active_bg"], TOKENS["sidebar_bg"])
        self.assertNotEqual(TOKENS["sidebar_active_indicator"], TOKENS["sidebar_active_bg"])
        self.assertNotEqual(TOKENS["status_danger_chart"], TOKENS["primary_btn"])
        self.assertNotEqual(TOKENS["brand_green"], TOKENS["primary_btn"])

        qss = get_theme_qss()
        logo = _selector_block(qss, "QWidget#SidebarLogoSection")
        self.assertIn(f'background: {TOKENS["sidebar_panel"]};', logo)

        active = _selector_block(qss, 'QPushButton#NavButton[nav_active="true"]')
        self.assertIn(f'background: {TOKENS["sidebar_active_bg"]};', active)
        self.assertIn(f'border-left: 4px solid {TOKENS["sidebar_active_indicator"]};', active)

        badge = _selector_block(qss, "QLabel#NavBadge")
        self.assertIn(f'background: {TOKENS["status_danger_chart"]};', badge)

        group_header = _selector_block(qss, "QLabel#SidebarGroupHeader")
        self.assertIn(f'color: {TOKENS["sidebar_muted"]};', group_header)


if __name__ == "__main__":
    unittest.main()
