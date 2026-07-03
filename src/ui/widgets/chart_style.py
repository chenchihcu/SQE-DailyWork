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
from PySide6.QtGui import QBrush, QColor

from ui.layout_constants import CHART_MIN_HEIGHT
from ui.theme import TOKENS


def apply_chart_surface(chart) -> None:
    # Figure surface = the card's panel_bg (transparent figure lets it show).
    chart.setBackgroundVisible(False)
    # Plot area gets its own semantic token so it reads as a separate layer.
    chart.setPlotAreaBackgroundBrush(QBrush(QColor(TOKENS["chart_plot_bg"])))
    chart.setPlotAreaBackgroundVisible(True)


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
