"""Shared QtChart surface styling (single entry point).

Universal UI rule §10 requires a chart's figure background and plot-area
background to be separate, token-driven layers. Here the figure background stays
transparent so the card's ``panel_bg`` token shows through (figure surface =
card), while the plot area uses its own ``chart_plot_bg`` token so the plotting
region is visually distinct from the figure frame.

Apply this in every chart builder instead of calling ``setBackgroundVisible``
ad-hoc, so the figure/plot separation is defined in one place.
"""

from __future__ import annotations

import math

from PySide6.QtCharts import QChartView, QValueAxis
from PySide6.QtCore import QSize
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import QApplication

from ui.layout_constants import CHART_MIN_HEIGHT
from ui.theme import PREFERRED_CJK_FONT_FAMILIES, get_active_theme_tokens

# ── 標準圖表字級常數（緊湊高密度階層） ──────────────────────────────
CHART_TITLE_POINT_SIZE: int = 11        # 圖表主標題 (Bold)
CHART_AXIS_TITLE_POINT_SIZE: int = 9    # 座標軸標題 (Bold)
CHART_AXIS_LABEL_POINT_SIZE: int = 9    # 座標軸刻度/類別標籤 (Regular)
CHART_LEGEND_POINT_SIZE: int = 8        # 圖例項目標籤 (Regular)
CHART_DATA_LABEL_POINT_SIZE: int = 8    # 長條圖/圓餅圖/折線圖數值標籤 (Regular / Bold)


def get_chart_font(
    point_size: int = CHART_AXIS_LABEL_POINT_SIZE,
    *,
    bold: bool = False,
) -> QFont:
    """取得對齊應用程式 CJK 字型偏好鏈與指定字級的 QFont 物件。"""
    app = QApplication.instance()
    family = (
        app.font().family()
        if app
        else (PREFERRED_CJK_FONT_FAMILIES[0] if PREFERRED_CJK_FONT_FAMILIES else "Microsoft JhengHei UI")
    )
    font = QFont(family, point_size)
    if bold:
        font.setBold(True)
    return font


def apply_chart_surface(chart, *, title: str | None = None) -> None:
    """套用標準圖表背景層次、主標題字型與圖例字型。"""
    tokens = get_active_theme_tokens()
    # Figure surface = the card's panel_bg (transparent figure lets it show).
    chart.setBackgroundVisible(False)
    # Plot area gets its own semantic token so it reads as a separate layer.
    chart.setPlotAreaBackgroundBrush(QBrush(QColor(tokens["chart_plot_bg"])))
    chart.setPlotAreaBackgroundVisible(True)

    if title is not None:
        chart.setTitle(title)
    if chart.title():
        chart.setTitleFont(get_chart_font(CHART_TITLE_POINT_SIZE, bold=True))
        chart.setTitleBrush(QBrush(QColor(tokens.get("text_primary", "#0F172A"))))

    legend = chart.legend()
    if legend:
        legend.setFont(get_chart_font(CHART_LEGEND_POINT_SIZE))
        legend.setLabelColor(QColor(tokens.get("chart_axis_text", "#333333")))


def apply_axis_typography(
    axis,
    *,
    title: str | None = None,
    color_override: QColor | None = None,
    title_color_override: QColor | None = None,
) -> None:
    """統一設定座標軸（QValueAxis / QBarCategoryAxis）的刻度文字與標題字型。"""
    tokens = get_active_theme_tokens()
    axis_color = color_override or QColor(tokens.get("chart_axis_text", "#333333"))
    axis.setLabelsFont(get_chart_font(CHART_AXIS_LABEL_POINT_SIZE))
    axis.setLabelsColor(axis_color)

    if title is not None:
        axis.setTitleText(title)
    if axis.titleText():
        axis.setTitleFont(get_chart_font(CHART_AXIS_TITLE_POINT_SIZE, bold=True))
        if title_color_override:
            axis.setTitleBrush(QBrush(title_color_override))
        elif color_override:
            axis.setTitleBrush(QBrush(color_override))
        else:
            axis.setTitleBrush(QBrush(QColor(tokens.get("chart_axis_text", "#333333"))))


def _nice_integer_interval(raw: float) -> int:
    """回傳 >= raw 的最小 1/2/5×10^n 整數間隔。"""
    if raw <= 1:
        return 1
    exponent = math.floor(math.log10(raw))
    for base in (1, 2, 5):
        candidate = base * (10 ** exponent)
        if candidate >= raw:
            return int(candidate)
    return int(10 ** (exponent + 1))


def apply_integer_count_axis(
    axis: QValueAxis, max_value: int, *, padding: int = 1, max_ticks: int = 6
) -> None:
    """設定「件數」類 QValueAxis 的範圍與刻度,保證格線落在整數值上。

    QValueAxis 預設 tickCount=5(4 段);range 上限取 max+padding 時多半不是
    4 的倍數,格線會落在小數(例 0..6 → 0/1.5/3/4.5/6),再被 %d、%i 標籤格式
    四捨五入成 0,1,3,4,6 這種不等距整數,整數件數的長條就對不上任何標示格線。
    這裡改用 TicksDynamic + 1/2/5×10^n 整數間隔,並把上限進位到間隔的倍數。
    """
    upper = max(1, int(max_value)) + max(0, int(padding))
    interval = _nice_integer_interval(upper / (max_ticks - 1))
    upper = math.ceil(upper / interval) * interval
    axis.setRange(0, upper)
    axis.setTickAnchor(0.0)
    axis.setTickInterval(float(interval))
    axis.setTickType(QValueAxis.TickType.TicksDynamic)


class StableChartView(QChartView):
    """sizeHint 不跟隨 sceneRect(即當前尺寸)成長的 QChartView。

    QGraphicsView.sizeHint() 以 sceneRect 為準,而 QChart 會隨 view resize
    撐大 scene;放進 widgetResizable QScrollArea 會形成高度正回饋迴圈
    (每次 relayout 高度遞增)。固定回報 minimumHeight 作為 preferred 高度,
    高度分配交由 QGridLayout 的 row stretch 決定。
    """
    def sizeHint(self) -> QSize:
        return QSize(600, max(self.minimumHeight(), CHART_MIN_HEIGHT))
