"""NCR stats chart-building mixin extracted from ncr_stats_widget.py."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QApplication, QSizePolicy
from PySide6.QtCharts import (
    QChart,
    QChartView,
    QHorizontalBarSeries,
    QBarSet,
    QPieSeries,
    QPieSlice,
    QValueAxis,
    QBarCategoryAxis,
)

from ui.design_tokens import PALETTE
from ui.layout_constants import CHART_MIN_HEIGHT
from ui.theme import TOKENS
from ui.widgets.chart_style import apply_chart_surface, apply_integer_count_axis, StableChartView
from ui.widgets.stats_dashboard_helpers import dedupe_chart_labels, short_chart_label

# Chart colour aliases sourced from shared design_tokens so theme updates propagate.
_C_DANGER = QColor(PALETTE["danger_chart"])       # 報廢 / 高風險
_C_SUCCESS = QColor(PALETTE["success_chart"])      # 重工 / 達標
_C_INFO = QColor(PALETTE["info_chart"])            # 廠內退料 / Top 供應商
_C_PENDING = QColor(PALETTE["pending_chart"])      # 託外退料
_C_NA = QColor(PALETTE["na_chart"])               # 未分類 / 預設

CHART_AXIS_LABEL_POINT_SIZE = 11
CHART_AXIS_TITLE_POINT_SIZE = 11


class _NcrStatsChartMixin:
    """Mixin providing chart-building methods for NCR statistics widgets."""

    def _build_horizontal_bar_chart(
        self, rows: list[dict], name_key: str, title: str, color_hex: str
    ) -> QChartView:
        categories = []
        bar_set = QBarSet("件數 / 數量")
        bar_set.setBrush(QColor(color_hex))

        # 逆序以讓數量最多者排在上方
        data = list(rows)[:5]
        data.reverse()

        max_qty = 0
        for r in data:
            name = r[name_key] or "未命名"
            qty = int(r["total_qty"] or 0)
            categories.append(short_chart_label(name, max_len=14))
            bar_set.append(qty)
            if qty > max_qty:
                max_qty = qty

        categories = dedupe_chart_labels(categories)

        series = QHorizontalBarSeries()
        series.append(bar_set)
        series.setLabelsVisible(True)
        series.setBarWidth(0.6)

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(title)
        apply_chart_surface(chart)
        chart.legend().setVisible(False)

        app_font_family = QApplication.font().family()
        axis_font = QFont(app_font_family, CHART_AXIS_LABEL_POINT_SIZE)

        axis_y = QBarCategoryAxis()
        axis_y.append(categories)
        axis_y.setLabelsColor(QColor(TOKENS.get("chart_axis_text", "#333333")))
        axis_y.setLabelsFont(axis_font)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        axis_x = QValueAxis()
        axis_x.setLabelFormat("%d")
        axis_x.setLabelsColor(QColor(TOKENS.get("chart_axis_text", "#333333")))
        axis_x.setLabelsFont(axis_font)
        axis_x.setGridLinePen(QPen(QColor(TOKENS.get("chart_grid", "#c5d4de")), 1, Qt.PenStyle.DashLine))
        apply_integer_count_axis(axis_x, max_qty if max_qty > 0 else 5, padding=5)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        view = StableChartView(chart)
        view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        view.setMinimumHeight(CHART_MIN_HEIGHT)
        # 垂直方向使用 Expanding 而非 Fixed，確保 QGridLayout 的 setRowStretch 能生效
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        return view

    def _build_donut_chart(
        self, rows: list[dict], name_key: str, title: str, color_map: dict[str, QColor]
    ) -> QChartView:
        series = QPieSeries()
        series.setHoleSize(0.4)  # Donut chart hole

        total_qty = sum(int(r["total_qty"] or 0) for r in rows)

        for r in rows:
            name = r[name_key] or "未註明"
            qty = int(r["total_qty"] or 0)
            if qty > 0:
                pct = (qty / total_qty * 100) if total_qty > 0 else 0
                slice_obj = series.append(f"{name} ({qty}件, {pct:.1f}%)", qty)
                slice_obj.setLabelVisible(True)
                slice_obj.setLabelPosition(QPieSlice.LabelPosition.LabelOutside)
                slice_obj.setBrush(color_map.get(name, _C_NA))

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(title)
        apply_chart_surface(chart)
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        chart.legend().setLabelColor(QColor(TOKENS.get("chart_axis_text", "#333333")))

        view = StableChartView(chart)
        view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        view.setMinimumHeight(CHART_MIN_HEIGHT)
        # 垂直方向使用 Expanding 而非 Fixed，確保環形圖不被壓縮至高度 0
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        return view
