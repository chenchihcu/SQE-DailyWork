from __future__ import annotations

import calendar
import logging
import os
from datetime import date
from collections.abc import Callable
from typing import NamedTuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.common_widgets import apply_clickable_affordance

logger = logging.getLogger(__name__)

PERIOD_OPTIONS = ("全期項目", "年度", "半年度")
PERIOD_TOOLTIP = "切換統計區間：全期項目、年度（當前年份）、半年度（當前半年度）"


def create_period_label() -> QLabel:
    label = QLabel("篩選區間")
    label.setProperty("role", "sectionTitle")
    label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return label


def create_period_combo(
    on_changed: Callable[[int], None],
    *,
    minimum_width: int | None = 112,
    fixed_size: bool = True,
    tooltip: str = PERIOD_TOOLTIP,
) -> QComboBox:
    combo = QComboBox()
    combo.addItems(list(PERIOD_OPTIONS))
    if minimum_width is not None:
        combo.setMinimumWidth(minimum_width)
    if fixed_size:
        combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    combo.currentIndexChanged.connect(on_changed)
    apply_clickable_affordance(combo, tooltip=tooltip)
    return combo


# ── 起迄年月範圍：純函式（無 QApplication 也可單元測試） ──────────────

YEAR_OPTIONS = ("2025", "2026", "2027", "2028", "2029", "2030")


def _parse_month_key(month_key: str) -> tuple[int, int]:
    """解析 yyyyMM 鍵為 (year, month)；非法鍵回退今天所在月份。"""
    key = str(month_key or "").strip()
    if len(key) == 6 and key.isdigit() and 1 <= int(key[4:]) <= 12:
        return int(key[:4]), int(key[4:])
    today = date.today()
    return today.year, today.month


def normalize_range_keys(start_key: str, end_key: str) -> tuple[str, str]:
    """確保起始不晚於結束；start > end 時交換（yyyyMM 字串比較即字典序）。"""
    s_y, s_m = _parse_month_key(start_key)
    e_y, e_m = _parse_month_key(end_key)
    start = f"{s_y:04d}{s_m:02d}"
    end = f"{e_y:04d}{e_m:02d}"
    if start > end:
        start, end = end, start
    return start, end


def range_month_window(start_key: str, end_key: str) -> tuple[str, str]:
    """把起迄 yyyyMM 鍵換算成趨勢查詢窗口 (start_date, end_date)，
    兩端都取當月 1 日的 ISO 日期（趨勢 *_by_range 以月字串比對，日不影響）。"""
    start_key, end_key = normalize_range_keys(start_key, end_key)
    return (
        f"{start_key[:4]}-{start_key[4:]}-01",
        f"{end_key[:4]}-{end_key[4:]}-01",
    )


def range_iso_dates(start_key: str, end_key: str) -> tuple[str, str]:
    """把起迄 yyyyMM 鍵換算成 ISO 日期範圍：起月 1 日到迄月最後一天，
    供以 `date BETWEEN ? AND ?` 比對完整日期的範圍查詢使用。"""
    start_key, end_key = normalize_range_keys(start_key, end_key)
    end_year, end_month = int(end_key[:4]), int(end_key[4:])
    last_day = calendar.monthrange(end_year, end_month)[1]
    return (
        f"{start_key[:4]}-{start_key[4:]}-01",
        f"{end_year:04d}-{end_month:02d}-{last_day:02d}",
    )


def range_display_text(start_key: str, end_key: str) -> str:
    """區間顯示文字：「2026-02 至 2026-07」；起迄同月退化為「2026-07」。"""
    start_key, end_key = normalize_range_keys(start_key, end_key)
    start_text = f"{start_key[:4]}-{start_key[4:]}"
    end_text = f"{end_key[:4]}-{end_key[4:]}"
    if start_text == end_text:
        return end_text
    return f"{start_text} 至 {end_text}"


def range_month_span(start_key: str, end_key: str) -> int:
    """回傳含首尾的月份數（例如 2026-02 至 2026-07 為 6）。"""
    start_key, end_key = normalize_range_keys(start_key, end_key)
    s_total = int(start_key[:4]) * 12 + int(start_key[4:])
    e_total = int(end_key[:4]) * 12 + int(end_key[4:])
    return e_total - s_total + 1


def default_range_keys(span_months: int = 6) -> tuple[str, str]:
    """預設區間：迄 = 今年今月（夾限於 YEAR_OPTIONS 範圍），起 = 迄往前
    span_months - 1 個月（夾限於最早選項年 1 月）。"""
    today = date.today()
    min_year, max_year = int(YEAR_OPTIONS[0]), int(YEAR_OPTIONS[-1])
    end_year, end_month = today.year, today.month
    if end_year < min_year:
        end_year, end_month = min_year, 1
    elif end_year > max_year:
        end_year, end_month = max_year, 12
    start_total = end_year * 12 + (end_month - 1) - (span_months - 1)
    start_year, start_month_index = divmod(start_total, 12)
    start_month = start_month_index + 1
    if start_year < min_year:
        start_year, start_month = min_year, 1
    return f"{start_year:04d}{start_month:02d}", f"{end_year:04d}{end_month:02d}"


# ── 起迄年月範圍選擇器（widget 工廠） ─────────────────────────────────


class YearMonthRangeSelectors(NamedTuple):
    """起迄年月選擇器的 widget 束（依版面順序排列）。"""

    start_year: QComboBox
    start_year_label: QLabel
    start_month: QComboBox
    start_month_label: QLabel
    to_label: QLabel
    end_year: QComboBox
    end_year_label: QLabel
    end_month: QComboBox
    end_month_label: QLabel

    def widgets(self) -> tuple[QWidget, ...]:
        return tuple(self)

    def start_key(self) -> str:
        return f"{self.start_year.currentText()}{self.start_month.currentText()}"

    def end_key(self) -> str:
        return f"{self.end_year.currentText()}{self.end_month.currentText()}"

    def set_range(self, start_key: str, end_key: str) -> None:
        """程式化設定四個下拉（blockSignals，不觸發 on_changed）。"""
        start_key, end_key = normalize_range_keys(start_key, end_key)
        pairs = (
            (self.start_year, start_key[:4]),
            (self.start_month, start_key[4:]),
            (self.end_year, end_key[:4]),
            (self.end_month, end_key[4:]),
        )
        for combo, text in pairs:
            combo.blockSignals(True)
            try:
                combo.setCurrentText(text)
            finally:
                combo.blockSignals(False)


def _create_suffix_label(text: str, parent: QWidget | None) -> QLabel:
    label = QLabel(text, parent)
    label.setProperty("role", "sectionTitle")
    label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return label


def create_year_month_range_selectors(
    on_changed: Callable[[str], None],
    *,
    parent: QWidget | None = None,
    default_span_months: int = 6,
) -> YearMonthRangeSelectors:
    """建立起迄年月下拉選單組：起[年][月] 至 迄[年][月]。

    on_changed 收到 "start" 或 "end"，表示使用者動到哪一端。
    預設值先設定、訊號後連接（避免建構期間提前觸發，見 b1f0580）。"""
    month_items = [f"{m:02d}" for m in range(1, 13)]

    def _make_pair(role: str) -> tuple[QComboBox, QLabel, QComboBox, QLabel]:
        year_combo = QComboBox(parent)
        year_combo.addItems(list(YEAR_OPTIONS))
        year_label = _create_suffix_label("年", parent)
        month_combo = QComboBox(parent)
        month_combo.addItems(month_items)
        month_label = _create_suffix_label("月", parent)
        tip_role = "起始" if role == "start" else "結束"
        apply_clickable_affordance(year_combo, tooltip=f"選擇統計{tip_role}年份")
        apply_clickable_affordance(month_combo, tooltip=f"選擇統計{tip_role}月份")
        return year_combo, year_label, month_combo, month_label

    start_year, start_year_label, start_month, start_month_label = _make_pair("start")
    end_year, end_year_label, end_month, end_month_label = _make_pair("end")
    to_label = _create_suffix_label("至", parent)

    selectors = YearMonthRangeSelectors(
        start_year, start_year_label, start_month, start_month_label,
        to_label,
        end_year, end_year_label, end_month, end_month_label,
    )

    # 先設預設值（blockSignals 內部處理），再連訊號
    default_start, default_end = default_range_keys(default_span_months)
    selectors.set_range(default_start, default_end)

    start_year.currentIndexChanged.connect(lambda: on_changed("start"))
    start_month.currentIndexChanged.connect(lambda: on_changed("start"))
    end_year.currentIndexChanged.connect(lambda: on_changed("end"))
    end_month.currentIndexChanged.connect(lambda: on_changed("end"))

    return selectors


def create_stats_scroll_area(
    *,
    scroll_object_name: str,
    content_object_name: str,
    margins: tuple[int, int, int, int],
    spacing: int = 12,
) -> tuple[QScrollArea, QVBoxLayout]:
    scroll = QScrollArea()
    scroll.setObjectName(scroll_object_name)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    content = QWidget()
    content.setObjectName(content_object_name)
    layout = QVBoxLayout(content)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    scroll.setWidget(content)
    return scroll, layout


def create_stats_grid_layout(*, equal_rows: bool = False) -> QGridLayout:
    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setSpacing(16)
    grid.setColumnStretch(0, 1)
    grid.setColumnStretch(1, 1)
    if equal_rows:
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
    return grid


class StatsInfoBanner(QFrame):
    def __init__(
        self,
        formula: str,
        purpose: str,
        *,
        formula_prefix: str,
        purpose_prefix: str,
        object_name: str,
        margins: tuple[int, int, int, int],
        spacing: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setProperty("role", "statsInfoBanner")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*margins)
        layout.setSpacing(spacing)

        formula_label = QLabel(f"<b>{formula_prefix}：</b>{formula}")
        purpose_label = QLabel(f"<b>{purpose_prefix}：</b>{purpose}")
        for label in (formula_label, purpose_label):
            label.setProperty("role", "statsInfoText")
            label.setWordWrap(True)
            label.setMinimumWidth(0)
            layout.addWidget(label)


def create_insight_label(
    text: str,
    *,
    minimum_height: int | None = None,
) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setProperty("role", "insight")
    label.setMinimumWidth(0)
    if minimum_height is not None:
        label.setMinimumHeight(minimum_height)
    return label


# ── Chart category-axis label helpers ────────────────────────────────────
# Shared by ncr_stats_chart_mixin.py and stats_chart_mixin.py, which used to
# each maintain their own independent label-shortening/dedup implementation
# with different truncation strategies (audit finding D7).


def short_chart_label(label: str, *, max_len: int) -> str:
    """Head-and-tail truncate a chart category label to max_len chars,
    inserting an ellipsis in the middle so both the start and end of a long
    label stay visible (more legible than a simple tail-truncation for long
    supplier/product names)."""
    text = str(label or "").strip() or "-"
    if max_len <= 1:
        return text[:max_len]
    if len(text) <= max_len:
        return text
    body_len = max_len - 1
    head_len = (body_len + 1) // 2
    tail_len = body_len // 2
    head = text[:head_len]
    tail = text[-tail_len:] if tail_len > 0 else ""
    return f"{head}…{tail}"


def dedupe_chart_labels(labels: list[str]) -> list[str]:
    """If any two labels in the list collide after truncation, prefix every
    label with a zero-padded 1-based index so Qt chart category axes never
    receive duplicate category names (which Qt silently merges, corrupting
    bar/series alignment)."""
    if len(labels) == len(set(labels)):
        return labels
    width = len(str(len(labels)))
    return [f"{index + 1:0{width}d}. {label}" for index, label in enumerate(labels)]


# ── Excel-export temp-chart-PNG workflow ─────────────────────────────────
# Shared by ncr_stats_widget.py::export_ncr_excel and
# stats_view_widget.py::export_monthly_excel, which used to each hand-roll
# an identical temp-path dict + pre-cleanup + render + finally-cleanup
# sequence (audit finding D8).


def build_temp_chart_paths(
    temp_dir: str, pid: int, keys: list[str], prefix: str
) -> dict[str, str]:
    """Build a {key: temp_png_path} mapping for chart-export scratch files,
    e.g. build_temp_chart_paths(dir, pid, ['trend'], 'temp_evt') ->
    {'trend': '<dir>/temp_evt_trend_<pid>.png'}."""
    return {
        key: os.path.join(temp_dir, f"{prefix}_{key}_{pid}.png")
        for key in keys
    }


def cleanup_temp_files(paths: dict[str, str]) -> None:
    """Best-effort removal of every path in the mapping; swallows per-file
    errors so one locked/missing file doesn't block cleanup of the rest."""
    for p in paths.values():
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                logger.debug("Could not remove temporary chart file: %s", p, exc_info=True)


def render_chart_to_png(
    chart_view_factory: Callable[[], object],
    output_path: str,
    size: tuple[int, int] = (600, 400),
) -> bool:
    """Call chart_view_factory() to obtain a chart view, resize it, and
    grab().save() it to output_path. Returns True only if a file was
    actually written, so callers can skip registering a failed/missing PNG
    with the export service (the previous hand-rolled versions ignored
    QPixmap.save()'s return value entirely)."""
    try:
        view = chart_view_factory()
        view.resize(*size)
        ok = view.grab().save(output_path)
        return bool(ok) and os.path.exists(output_path)
    except Exception:
        return False
