"""QSS 樣式表範本 — 拆分的區段組合器。

各 widget 類別對應的 QSS 已拆入私用模組 _qss_*.py，
此檔案作為組合器：保留公開 API（get_theme_qss、asset_path），
呼叫各區段函式並串接結果。
"""

from __future__ import annotations

from pathlib import Path

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


def get_theme_qss() -> str:
    checkbox_tick_url = _asset_qss_url("checkbox_tick.svg")
    return "\n".join([
        get_base_qss(),
        get_tabs_qss(),
        get_controls_qss(),
        get_data_widgets_qss(),
        get_dialogs_etc_qss(checkbox_tick_url),
        get_sidebar_qss(),
    ])
