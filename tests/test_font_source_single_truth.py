from __future__ import annotations

import os
import re
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ui.theme as theme
import ncr.ui.ui_style as ui_style


class FontSourceSingleTruthTests(unittest.TestCase):
    """The CJK font fallback chain must have exactly one source of truth.

    The NCR module previously kept its own divergent PREFERRED_CJK_FONT_FAMILIES /
    CJK_FONT_FAMILY_CSS, so the main-theme font-trust check could pass while the
    embedded warehouse page resolved a different font. These pin the unification.
    """

    def test_ncr_reuses_theme_preferred_family_tuple(self) -> None:
        self.assertIs(
            ui_style.PREFERRED_CJK_FONT_FAMILIES,
            theme.PREFERRED_CJK_FONT_FAMILIES,
        )

    def test_ncr_reuses_theme_css_font_chain(self) -> None:
        self.assertEqual(ui_style.CJK_FONT_FAMILY_CSS, theme.CJK_FONT_FAMILY_CSS)

    def test_primary_family_is_jhenghei(self) -> None:
        self.assertEqual(
            theme.PREFERRED_CJK_FONT_FAMILIES[0], "Microsoft JhengHei UI"
        )
        self.assertTrue(theme.CJK_FONT_FAMILY_CSS.endswith("sans-serif"))

    def test_typography_font_family_derives_from_tuple(self) -> None:
        # Every preferred family must appear (double-quoted) in the QWidget chain.
        for family in theme.PREFERRED_CJK_FONT_FAMILIES:
            self.assertIn(f'"{family}"', theme.TYPOGRAPHY["font_family"])

    def test_ncr_stylesheet_avoids_medium_font_weights(self) -> None:
        offenders = re.findall(r"font-weight:\s*(500|600)\b", ui_style.app_stylesheet())
        self.assertEqual(offenders, [], f"NCR QSS still uses 500/600: {offenders}")


if __name__ == "__main__":
    unittest.main()
