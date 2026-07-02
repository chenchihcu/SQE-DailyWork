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

from PySide6.QtCharts import QChartView
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


class StableChartView(QChartView):
    """sizeHint 不跟隨 sceneRect(即當前尺寸)成長的 QChartView。

    QGraphicsView.sizeHint() 以 sceneRect 為準,而 QChart 會隨 view resize
    撐大 scene;放進 widgetResizable QScrollArea 會形成高度正回饋迴圈
    (每次 relayout 高度遞增)。固定回報 minimumHeight 作為 preferred 高度,
    高度分配交由 QGridLayout 的 row stretch 決定。
    """
    def sizeHint(self) -> QSize:
        return QSize(600, max(self.minimumHeight(), CHART_MIN_HEIGHT))
