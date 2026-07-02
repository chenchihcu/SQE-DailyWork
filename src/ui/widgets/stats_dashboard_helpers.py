from __future__ import annotations

import os
from datetime import date
from collections.abc import Callable

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.common_widgets import apply_clickable_affordance

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


def create_year_month_selectors(
    on_changed: Callable[[], None],
    *,
    parent: QWidget | None = None,
) -> tuple[QComboBox, QLabel, QComboBox, QLabel]:
    """建立年份與月份下拉選單，選單後加上年與月字樣。"""
    # Year options: 2025 to 2030
    year_combo = QComboBox(parent)
    year_combo.addItems(["2025", "2026", "2027", "2028", "2029", "2030"])
    
    year_label = QLabel("年", parent)
    year_label.setProperty("role", "sectionTitle")
    year_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    
    # Month options: 01 to 12
    month_combo = QComboBox(parent)
    month_combo.addItems([f"{m:02d}" for m in range(1, 13)])
    
    month_label = QLabel("月", parent)
    month_label.setProperty("role", "sectionTitle")
    month_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    
    # Default to current year and month
    from datetime import date
    current_year = str(date.today().year)
    current_month = f"{date.today().month:02d}"
    
    if current_year in ["2025", "2026", "2027", "2028", "2029", "2030"]:
        year_combo.setCurrentText(current_year)
    else:
        year_combo.setCurrentText("2026") # fallback
    month_combo.setCurrentText(current_month)
    
    # Connect signals after setting default values to prevent early triggering during construction
    year_combo.currentIndexChanged.connect(lambda: on_changed())
    month_combo.currentIndexChanged.connect(lambda: on_changed())
    
    apply_clickable_affordance(year_combo, tooltip="選擇統計年份")
    apply_clickable_affordance(month_combo, tooltip="選擇統計月份")
    
    return year_combo, year_label, month_combo, month_label


def create_hidden_month_controls(
    parent: QWidget,
    on_month_changed: Callable[[QDate], None],
    on_all_time_toggled: Callable[[bool], None],
) -> tuple[QDateEdit, QCheckBox]:
    month_input = QDateEdit(parent)
    month_input.setDate(QDate.currentDate())
    all_time_toggle = QCheckBox(parent)
    month_input.hide()
    all_time_toggle.hide()
    month_input.dateChanged.connect(on_month_changed)
    all_time_toggle.toggled.connect(on_all_time_toggled)
    return month_input, all_time_toggle


def period_month_key(period_combo: QComboBox, test_yyyy_mm: str | None) -> str:
    if test_yyyy_mm is not None:
        return test_yyyy_mm
    index = period_combo.currentIndex()
    if index == 0:
        return "ALL"
    if index == 1:
        return "YEAR"
    return "HALF_YEAR"


def period_month_text(period_combo: QComboBox, test_yyyy_mm: str | None) -> str:
    if test_yyyy_mm is not None:
        if test_yyyy_mm == "ALL":
            return "全期累計"
        if test_yyyy_mm == "YEAR":
            return f"{date.today().year}年度"
        if test_yyyy_mm == "HALF_YEAR":
            half = "上半年" if date.today().month <= 6 else "下半年"
            return f"{date.today().year}年{half}"
        return f"{test_yyyy_mm[:4]}-{test_yyyy_mm[4:]}"

    index = period_combo.currentIndex()
    if index == 0:
        return "全期項目"
    if index == 1:
        return f"{date.today().year}年度"
    half = "上半年" if date.today().month <= 6 else "下半年"
    return f"{date.today().year}年{half}"


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
            except Exception:
                pass


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
