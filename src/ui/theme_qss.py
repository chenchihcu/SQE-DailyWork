"""QSS 樣式表範本 — 拆分的區段組合器。

各 widget 類別對應的 QSS 已拆入私用模組 _qss_*.py，
此檔案作為組合器：保留公開 API（get_theme_qss、asset_path），
呼叫各區段函式並串接結果。
"""

from __future__ import annotations

import re
from pathlib import Path

from ui._qss_appearance import get_appearance_qss
from ui.appearance_preferences import AppearancePreferences
from ui._qss_base import get_base_qss
from ui._qss_controls import get_controls_qss
from ui._qss_data_widgets import get_data_widgets_qss
from ui._qss_dialogs_etc import get_dialogs_etc_qss
from ui._qss_sidebar import get_sidebar_qss
from ui._qss_tabs import get_tabs_qss


def asset_path(asset_name: str) -> Path:
    return Path(__file__).resolve().parent / "assets" / asset_name


def _asset_qss_url(asset_name: str) -> str:
    return asset_path(asset_name).as_posix()


def _scale_font_sizes(qss: str, factor: float) -> str:
    if factor == 1.0:
        return qss

    def replace(match: re.Match[str]) -> str:
        pixels = int(match.group(1))
        return f"font-size: {max(1, round(pixels * factor))}px;"

    return re.sub(r"font-size:\s*(\d+)px;", replace, qss)


def get_theme_qss(preferences: AppearancePreferences | None = None) -> str:
    preferences = preferences or AppearancePreferences.default()
    checkbox_tick_url = _asset_qss_url("checkbox_tick.svg")
    qss = "\n".join([
        get_base_qss(),
        get_tabs_qss(),
        get_controls_qss(),
        get_data_widgets_qss(),
        get_dialogs_etc_qss(checkbox_tick_url),
        get_sidebar_qss(),
        get_appearance_qss(preferences),
    ])
    return _scale_font_sizes(qss, 1.15 if preferences.text_scale == "large" else 1.0)
