"""QSS section: root widgets, frames, and panels."""

from __future__ import annotations

from textwrap import dedent

from ui.theme_tokens import TOKENS, TYPOGRAPHY


def get_base_qss() -> str:
    return dedent(f"""\
        QWidget {{
            color: {TOKENS["text_primary"]};
            font-family: {TYPOGRAPHY["font_family"]};
            font-size: {TYPOGRAPHY["base"]}px;
            background: transparent;
        }}

        QMainWindow,
        QWidget#AppRoot {{
            background: {TOKENS["page_bg"]};
        }}

        QFrame[role="panel"],
        QFrame[role="subpanel"],
        QFrame[role="card"] {{
            background: {TOKENS["panel_bg"]};
            border: 1px solid {TOKENS["border_soft"]};
            border-radius: {TOKENS["radius_lg"]}px;
        }}

        QFrame[role="panel"] QFrame[role="subpanel"],
        QFrame[role="panel"] QFrame[role="card"] {{
            background: transparent;
        }}

        QFrame[role="panel"] QFrame[role="subpanel"][surface="raised"],
        QFrame[role="panel"] QFrame[role="card"][surface="raised"] {{
            background: {TOKENS["panel_bg"]};
        }}

        QFrame[role="card"]:hover {{
            border-color: {TOKENS["focus_ring"]};
            background: {TOKENS["surface_hover"]};
        }}

        QFrame#ContentHost {{
            border: none;
            border-radius: 0;
            background: transparent;
        }}

        QLabel[role="pageTitle"] {{
            background: transparent;
            font-size: {TYPOGRAPHY["page_title"]}px;
            font-weight: 700;
            color: {TOKENS["text_primary"]};
            padding: 0 2px;
        }}

        QLabel[role="sectionTitle"] {{
            background: transparent;
            font-size: {TYPOGRAPHY["section_title"]}px;
            font-weight: 700;
            color: {TOKENS["text_primary"]};
        }}

        QLabel[role="helperText"] {{
            background: transparent;
            color: {TOKENS["text_secondary"]};
            font-size: {TYPOGRAPHY["helper_text"]}px;
            font-weight: 700;
        }}

        QLabel[role="sourceTag"],
        QLabel[role="selectionStatus"] {{
            background: {TOKENS["surface_active"]};
            border: 1px solid {TOKENS["border_soft"]};
            border-radius: {TOKENS["radius_sm"]}px;
            color: {TOKENS["text_secondary"]};
            font-size: {TYPOGRAPHY["caption"]}px;
            font-weight: 700;
            padding: 3px 8px;
        }}

        QFrame[role="statsInfoBanner"] {{
            background: {TOKENS["panel_alt_bg"]};
            border: 1px solid {TOKENS["border"]};
            border-radius: {TOKENS["radius_md"]}px;
        }}

        QLabel[role="statsInfoText"] {{
            background: transparent;
            border: none;
            color: {TOKENS["text_muted"]};
            font-size: {TYPOGRAPHY["caption"]}px;
        }}

        QLabel[role="insight"] {{
            background: {TOKENS["panel_alt_bg"]};
            border-left: 4px solid {TOKENS["info"]};
            border-top-right-radius: {TOKENS["radius_sm"]}px;
            border-bottom-right-radius: {TOKENS["radius_sm"]}px;
            color: {TOKENS["text_primary"]};
            font-size: {TYPOGRAPHY["body_small"]}px;
            padding: 6px 10px;
        }}

        QLabel[role="errorText"] {{
            background: transparent;
            color: {TOKENS["danger"]};
            font-weight: 700;
        }}

        QLabel[role="messageText"] {{
            background: {TOKENS["surface_accent"]};
            border: 1px solid {TOKENS["info_border"]};
            border-radius: {TOKENS["radius_sm"]}px;
            color: {TOKENS["info"]};
            font-size: {TYPOGRAPHY["helper_text"]}px;
            font-weight: 400;
            padding: 4px 8px;
        }}

        QLabel[role="messageText"][tone="warning"] {{
            background: {TOKENS["warning_bg"]};
            border: 1px solid {TOKENS["warning_border"]};
            color: {TOKENS["warning"]};
        }}

        QLabel[role="messageText"][tone="danger"] {{
            background: {TOKENS["surface_danger"]};
            border: 1px solid {TOKENS["danger_border"]};
            color: {TOKENS["danger"]};
        }}

        QLabel[role="messageText"][tone="success"] {{
            background: {TOKENS["success_bg"]};
            border: 1px solid {TOKENS["status_success_border"]};
            color: {TOKENS["success"]};
        }}

        QFrame[role="separator"] {{
            background: {TOKENS["border_soft"]};
            border: none;
        }}

        QLabel[role="counterText"] {{
            background: transparent;
            color: {TOKENS["text_muted"]};
            font-size: {TYPOGRAPHY["caption"]}px;
            font-weight: 400;
        }}

        QLabel[role="counterText"][tone="danger"] {{
            color: {TOKENS["danger"]};
            font-weight: 700;
        }}
    """).strip()
