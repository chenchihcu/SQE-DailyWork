from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui.theme import PREFERRED_CJK_FONT_FAMILIES, TOKENS, apply_app_theme, get_theme_qss


def _selector_block(qss: str, selector: str) -> str:
    escaped = re.escape(selector)
    match = re.search(rf"{escaped}\s*\{{(.*?)\}}", qss, re.DOTALL)
    if match is None:
        raise AssertionError(f"missing selector: {selector}")
    return match.group(1)


def _selector_block_pattern(qss: str, selector_pattern: str) -> str:
    match = re.search(rf"{selector_pattern}\s*\{{(.*?)\}}", qss, re.DOTALL)
    if match is None:
        raise AssertionError(f"missing selector pattern: {selector_pattern}")
    return match.group(1)


class ThemeTypographyConsistencyTests(unittest.TestCase):
    def test_apply_app_theme_sets_application_font_to_preferred_cjk_family(self) -> None:
        app = QApplication.instance() or QApplication([])
        apply_app_theme(app)
        self.assertIn(app.font().family(), (*PREFERRED_CJK_FONT_FAMILIES, "Segoe UI"))

    def test_widget_font_family_prioritizes_cjk_fallbacks(self) -> None:
        qss = get_theme_qss()
        widget_block = _selector_block(qss, "QWidget")
        self.assertIn('"Microsoft JhengHei UI"', widget_block)
        self.assertIn('"Microsoft JhengHei"', widget_block)
        self.assertIn('"Segoe UI"', widget_block)

    def test_main_workflow_tab_typography_and_colors_match_reference(self) -> None:
        qss = get_theme_qss()
        tab_block = _selector_block(qss, "QTabWidget#MainWorkflowTabs QTabBar::tab")
        self.assertIn("font-size: 13px;", tab_block)
        # Unselected tab weight normalized 600 -> 400 (CJK avoids 500/600 per the
        # universal UI rule); the selected state is carried by colour + weight 700.
        self.assertIn("font-weight: 400;", tab_block)
        self.assertIn(f'color: {TOKENS["nav_dark_text"]};', tab_block)

        hover_block = _selector_block(qss, "QTabWidget#MainWorkflowTabs QTabBar::tab:hover:!selected")
        self.assertIn(f'color: {TOKENS["nav_dark_text_active"]};', hover_block)

        selected_block = _selector_block(qss, "QTabWidget#MainWorkflowTabs QTabBar::tab:selected")
        self.assertIn("font-weight: 700;", selected_block)
        self.assertIn(f'color: {TOKENS["nav_dark_text_active"]};', selected_block)

    def test_tab_label_font_size_is_13px(self) -> None:
        qss = get_theme_qss()
        tab_block = _selector_block(qss, "QTabBar::tab")
        self.assertIn("font-size: 13px;", tab_block)

    def test_theme_qss_avoids_medium_font_weights(self) -> None:
        # CJK renders inconsistently at 500/600 on Windows; the theme must only use
        # 400 / 700 (universal UI rule §6). Pins the normalization against regression.
        qss = get_theme_qss()
        offenders = re.findall(r"font-weight:\s*(500|600)\b", qss)
        self.assertEqual(offenders, [], f"theme QSS still uses 500/600: {offenders}")

    def test_kpi_widgets_have_no_inline_font_size_override(self) -> None:
        _root = Path(__file__).resolve().parents[1]
        home_widget = (_root / "src/ui/widgets/home_widget.py").read_text(encoding="utf-8")
        stats_widget = (_root / "src/ui/widgets/stats_view_widget.py").read_text(encoding="utf-8")
        self.assertNotIn("font-size", home_widget)
        self.assertNotIn("font-size", stats_widget)

    def test_date_input_styles_define_light_background_and_text_color(self) -> None:
        qss = get_theme_qss()
        date_input_block = _selector_block_pattern(
            qss,
            r"QLineEdit,\s*QComboBox,\s*QDateEdit,\s*QSpinBox",
        )
        self.assertIn(f'background: {TOKENS["panel_bg"]};', date_input_block)
        self.assertIn(f'color: {TOKENS["text_primary"]};', date_input_block)

    def test_calendar_popup_uses_light_theme_and_high_contrast_selection(self) -> None:
        qss = get_theme_qss()

        calendar_block = _selector_block(qss, "QCalendarWidget")
        self.assertIn(f'background: {TOKENS["panel_bg"]};', calendar_block)
        self.assertIn(f'border: 1px solid {TOKENS["border"]};', calendar_block)

        nav_button_block = _selector_block(qss, "QCalendarWidget QToolButton")
        self.assertIn(f'background: {TOKENS["panel_alt_bg"]};', nav_button_block)
        self.assertIn(f'color: {TOKENS["text_primary"]};', nav_button_block)

        date_grid_block = _selector_block(qss, "QCalendarWidget QAbstractItemView")
        self.assertIn(f'background: {TOKENS["panel_bg"]};', date_grid_block)
        self.assertIn(f'selection-background-color: {TOKENS["primary_btn"]};', date_grid_block)
        self.assertIn("selection-color: #FFFFFF;", date_grid_block)

    def test_checkbox_indicator_styles_define_visible_box_and_tick_asset(self) -> None:
        qss = get_theme_qss()

        indicator_block = _selector_block(qss, "QCheckBox::indicator")
        self.assertIn("width: 14px;", indicator_block)
        self.assertIn("height: 14px;", indicator_block)
        self.assertIn(f'border: 1px solid {TOKENS["text_secondary"]};', indicator_block)

        checked_block = _selector_block(qss, "QCheckBox::indicator:checked")
        self.assertIn(f'background: {TOKENS["primary_btn"]};', checked_block)
        self.assertIn("image: url(", checked_block)
        self.assertIn("checkbox_tick.svg", checked_block)

        unchecked_disabled_block = _selector_block(qss, "QCheckBox::indicator:unchecked:disabled")
        self.assertIn(f'background: {TOKENS["page_bg"]};', unchecked_disabled_block)

        checked_disabled_block = _selector_block(qss, "QCheckBox::indicator:checked:disabled")
        self.assertIn(f'background: {TOKENS["text_disabled"]};', checked_disabled_block)
        self.assertIn("image: url(", checked_disabled_block)

        self.assertTrue(Path("src/ui/assets/checkbox_tick.svg").is_file())


if __name__ == "__main__":
    unittest.main()
