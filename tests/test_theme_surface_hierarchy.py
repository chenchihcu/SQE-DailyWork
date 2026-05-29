from __future__ import annotations

import re
import unittest

from ui.theme import TOKENS, get_theme_qss


class ThemeSurfaceHierarchyTests(unittest.TestCase):
    def _assert_rule_contains_background(
        self, qss: str, selector_pattern: str, expected_background: str
    ) -> None:
        match = re.search(rf"{selector_pattern}[^{{]*\{{(?P<body>.*?)\}}", qss, re.DOTALL)
        self.assertIsNotNone(match, f"missing selector pattern: {selector_pattern}")
        assert match is not None
        self.assertIn(
            f"background: {expected_background};",
            match.group("body"),
            f"selector {selector_pattern} should set background to {expected_background}",
        )

    def test_nested_card_and_subpanel_default_to_transparent(self) -> None:
        qss = get_theme_qss()
        self._assert_rule_contains_background(
            qss,
            r'QFrame\[role="panel"\]\s+QFrame\[role="subpanel"\],\s*QFrame\[role="panel"\]\s+QFrame\[role="card"\],\s*QFrame\[role="panel"\]\s+QFrame\[role="kpiCard"\]',
            "transparent",
        )

    def test_nested_raised_override_restores_solid_background(self) -> None:
        qss = get_theme_qss()
        self._assert_rule_contains_background(
            qss,
            r'QFrame\[role="panel"\]\s+QFrame\[role="subpanel"\]\[surface="raised"\],\s*QFrame\[role="panel"\]\s+QFrame\[role="card"\]\[surface="raised"\],\s*QFrame\[role="panel"\]\s+QFrame\[role="kpiCard"\]\[surface="raised"\]',
            TOKENS["panel_bg"],
        )

    def test_panel_base_surface_stays_solid(self) -> None:
        qss = get_theme_qss()
        match = re.search(r'QFrame\[role="panel"\][^{]*\{(?P<body>.*?)\}', qss, re.DOTALL)
        self.assertIsNotNone(match, 'missing selector: QFrame[role="panel"]')
        assert match is not None
        body = match.group("body")
        self.assertIn(f'background: {TOKENS["panel_bg"]};', body)
        self.assertIn(f'border: 1px solid {TOKENS["border_soft"]};', body)
        self.assertIn(f'border-radius: {TOKENS["radius_lg"]}px;', body)

    def test_table_cell_action_button_style_is_link_like(self) -> None:
        qss = get_theme_qss()
        match = re.search(
            r'QTableWidget\s+QPushButton\[role="tableCellAction"\]\s*\{(?P<body>.*?)\}',
            qss,
            re.DOTALL,
        )
        self.assertIsNotNone(
            match,
            'missing selector: QTableWidget QPushButton[role="tableCellAction"]',
        )
        assert match is not None
        body = match.group("body")
        self.assertIn("background: transparent;", body)
        self.assertIn("border: none;", body)
        self.assertIn("border-radius: 0;", body)
        self.assertIn("min-height: 0;", body)

    def test_table_selection_and_header_use_polished_surfaces(self) -> None:
        qss = get_theme_qss()

        self._assert_rule_contains_background(
            qss,
            r"QTableWidget::item:selected",
            TOKENS["surface_active"],
        )
        self._assert_rule_contains_background(
            qss,
            r"QHeaderView::section",
            TOKENS["surface_active"],
        )

    def test_kpi_tone_cards_use_status_palette_layers(self) -> None:
        qss = get_theme_qss()
        for tone, bg_token, border_token in (
            ("pending", "status_pending_bg", "status_pending_border"),
            ("success", "status_success_bg", "status_success_border"),
            ("danger", "status_danger_bg", "status_danger_border"),
            ("info", "status_info_bg", "status_info_border"),
        ):
            match = re.search(
                rf'QFrame\[role="kpiCard"\]\[tone="{tone}"\][^{{]*\{{(?P<body>.*?)\}}',
                qss,
                re.DOTALL,
            )
            self.assertIsNotNone(match, f"missing kpi tone selector: {tone}")
            assert match is not None
            body = match.group("body")
            self.assertIn(f'background: {TOKENS[bg_token]};', body)
            self.assertIn(f'border: 1px solid {TOKENS[border_token]};', body)

    def test_tech_transfer_tri_state_cards_use_semantic_layers(self) -> None:
        qss = get_theme_qss()
        for state, bg_token, border_token in (
            ("selected", "status_success_bg", "status_success_border"),
            ("na", "status_na_bg", "status_na_border"),
        ):
            match = re.search(
                rf'QFrame#techTransferCard\[state="{state}"\]\s*\{{(?P<body>.*?)\}}',
                qss,
                re.DOTALL,
            )
            self.assertIsNotNone(match, f"missing tech transfer state: {state}")
            assert match is not None
            body = match.group("body")
            self.assertIn(f'background: {TOKENS[bg_token]};', body)
            self.assertIn(f'border:', body)
            self.assertIn(TOKENS[border_token], body)

    def test_status_badge_tones_and_ref_na_chip_are_styled(self) -> None:
        qss = get_theme_qss()
        for tone, bg_token, border_token in (
            ("pending", "status_pending_bg", "status_pending_border"),
            ("danger", "status_danger_bg", "status_danger_border"),
            ("info", "status_info_bg", "status_info_border"),
            ("na", "status_na_bg", "status_na_border"),
        ):
            match = re.search(
                rf'QLabel\[role="statusBadge"\]\[tone="{tone}"\]\s*\{{(?P<body>.*?)\}}',
                qss,
                re.DOTALL,
            )
            self.assertIsNotNone(match, f"missing status badge tone: {tone}")
            assert match is not None
            body = match.group("body")
            self.assertIn(f'background: {TOKENS[bg_token]};', body)
            self.assertIn(f'border: 1px solid {TOKENS[border_token]};', body)

        match = re.search(
            r'QLabel\[role="refCardValue"\]\[status="na"\]\s*\{(?P<body>.*?)\}',
            qss,
            re.DOTALL,
        )
        self.assertIsNotNone(match, 'missing selector: refCardValue status="na"')
        assert match is not None
        self.assertIn(f'background: {TOKENS["status_na_bg"]};', match.group("body"))

    def test_attachment_list_and_message_surfaces_are_styled(self) -> None:
        qss = get_theme_qss()

        self._assert_rule_contains_background(
            qss,
            r"QListWidget#AttachmentPreviewList",
            TOKENS["attachment_bg"],
        )
        self._assert_rule_contains_background(
            qss,
            r"QListWidget#AttachmentPreviewList::item:selected",
            TOKENS["attachment_selected_bg"],
        )
        self._assert_rule_contains_background(
            qss,
            r'QLabel\[role="messageText"\]',
            TOKENS["surface_accent"],
        )
        self._assert_rule_contains_background(
            qss,
            r'QLabel\[role="messageText"\]\[tone="warning"\]',
            TOKENS["warning_bg"],
        )


if __name__ == "__main__":
    unittest.main()
