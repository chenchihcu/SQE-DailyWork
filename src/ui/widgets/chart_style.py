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

from PySide6.QtGui import QBrush, QColor

from ui.theme import TOKENS


def apply_chart_surface(chart) -> None:
    # Figure surface = the card's panel_bg (transparent figure lets it show).
    chart.setBackgroundVisible(False)
    # Plot area gets its own semantic token so it reads as a separate layer.
    chart.setPlotAreaBackgroundBrush(QBrush(QColor(TOKENS["chart_plot_bg"])))
    chart.setPlotAreaBackgroundVisible(True)
