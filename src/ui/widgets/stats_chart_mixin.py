"""統計檢視圖表的 Mixin 類別。

從 StatsViewWidget 中提取所有圖表建構方法與事件處理，
透過 Mixin 模式注入回原 widget，保持 _render_charts 等協調邏輯在 widget 本體。

領域規則
===================
- 混合(Mixin)方法僅存取 self 上由主 Widget 提供的屬性/方法
- 不持有 QWidget 子類別的狀態  —  狀態一律由主 Widget 管理
- Duck Typing：self._range_keys()、self._chart_content_layout 等會於執行期由主 Widget 滿足
"""

from __future__ import annotations

import logging

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QHorizontalBarSeries,
    QHorizontalStackedBarSeries,
    QLineSeries,
    QValueAxis,
)
from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPen
from PySide6.QtWidgets import QApplication, QToolTip, QSizePolicy

from ui.layout_constants import CHART_MIN_HEIGHT
from ui.status_colors import get_status_palette
from ui.theme import TOKENS
from ui.widgets.chart_style import apply_chart_surface, apply_integer_count_axis, StableChartView
from ui.widgets.stats_dashboard_helpers import dedupe_chart_labels, short_chart_label

logger = logging.getLogger(__name__)

# ── 圖表常數 ──────────────────────────────────────────────
SUPPLIER_LABEL_MAX_LEN = 12
PARETO_CATEGORY_LABEL_MAX_LEN = 12
CHART_AXIS_LABEL_POINT_SIZE = 11
CHART_AXIS_TITLE_POINT_SIZE = 11
CHART_AXIS_LABEL_ANGLE = 0
CHART_OPEN_PALETTE = get_status_palette("待處理")
CHART_CLOSED_PALETTE = get_status_palette("已結案")
CHART_OVERDUE_PALETTE = get_status_palette("逾期未結")
CHART_OPEN_COLOR = QColor(CHART_OPEN_PALETTE.chart)
CHART_CLOSED_COLOR = QColor(CHART_CLOSED_PALETTE.chart)
CHART_OVERDUE_COLOR = QColor(CHART_OVERDUE_PALETTE.chart)
PARETO_BAR_COLOR = QColor(TOKENS.get("primary_btn", "#1F6FEB"))
PARETO_LINE_COLOR = QColor(TOKENS.get("brand_green", "#1FA85B"))


class _StatsChartMixin:
    """提供異常統計與不合格品統計的圖表建構能力。

    透過多重繼承與 StatsViewWidget 組合使用：
        class StatsViewWidget(QWidget, _StatsChartMixin):
            ...

    圖表方法會透過 self 存取主 Widget 提供的以下屬性/方法：
    - self.main_window              (set in __init__)
    - self._chart_content_layout    (set in _setup_ui)
    - self._trend_content_layout    (set in _setup_ui)
    - self._resp_content_layout     (set in _setup_ui)
    - self._range_keys()            (provided by widget)
    - self._range_text()            (provided by widget)
    - self._create_insight_label()  (provided by widget)
    """

    # ── 輔助方法 ──────────────────────────────────────────

    def _trend_chart_title(self, base: str, data: list[dict]) -> str:
        """由趨勢資料本身推導區間標題（頁面篩選與匯出對話框兩種來源都正確）。"""
        first = str(data[0].get("yyyymm", "")) if data else ""
        last = str(data[-1].get("yyyymm", "")) if data else ""
        if not first and not last:
            return base
        range_text = first if first == last else f"{first} 至 {last}"
        return f"{base} ({range_text})"

    def _format_month_axis_label(self, yyyymm: str) -> str:
        raw = str(yyyymm or "")
        digits = raw.replace("-", "")
        if len(digits) == 6 and digits.isdigit():
            return f"{digits[2:4]}/{digits[4:]}"
        return raw

    def _clear_top_suppliers(self):
        layouts = (
            self._chart_content_layout,
            self._trend_content_layout,
            self._resp_content_layout,
            getattr(self, "_category_content_layout", None),
        )
        if any(l is None for l in layouts):
            return
        for layout in layouts:
            while layout.count() > 0:
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.hide()
                    widget.setParent(None)
                    widget.deleteLater()
        self._chart = None
        self._chart_view = None
        self._chart_series = None
        self._chart_supplier_names = []
        self._chart_ongoing_values = []
        self._chart_overdue_values = []
        self._chart_closed_values = []
        self._chart_total_values = []
        self._chart_avg_time_values = []
        QToolTip.hideText()

    # ── 責任人事件統計圖表 ────────────────────────────────────

    def _build_responsible_stacked_chart(self, rows: list[dict]) -> QChartView | None:
        if not rows:
            return None

        # Display top 15 responsible persons, reverse for horizontal chart listing
        data = rows[:15]
        data.reverse()
        self._last_supplier_data = list(data)
        categories = dedupe_chart_labels([
            short_chart_label(r["responsible_person"], max_len=SUPPLIER_LABEL_MAX_LEN)
            for r in data
        ])

        closed_set = QBarSet("已結案")
        closed_set.setColor(CHART_CLOSED_COLOR)

        open_set = QBarSet("未結案")
        open_set.setColor(CHART_OPEN_COLOR)

        for r in data:
            closed_set.append(int(r.get("closed_count") or 0))
            open_set.append(int(r.get("open_count") or 0))

        bar_series = QHorizontalStackedBarSeries()
        bar_series.append(closed_set)
        bar_series.append(open_set)
        bar_series.setLabelsVisible(True)

        chart = QChart()
        chart.addSeries(bar_series)
        chart.setTitle("責任人事件統計 (已結案 vs 未結案)")
        apply_chart_surface(chart)
        chart.setMargins(QMargins(12, 8, 12, 10))

        app_font_family = QApplication.font().family()
        axis_font = QFont(app_font_family, CHART_AXIS_LABEL_POINT_SIZE)
        axis_y_font = QFont(app_font_family, 9)
        title_font = QFont(app_font_family, CHART_AXIS_TITLE_POINT_SIZE, QFont.Weight.Bold)

        axis_y = QBarCategoryAxis()
        axis_y.append(categories)
        axis_y.setLabelsFont(axis_y_font)
        axis_y.setLabelsColor(QColor(TOKENS.get("chart_axis_text", "#333333")))
        axis_y.setTitleFont(title_font)
        axis_y.setTruncateLabels(False)
        axis_y.setTitleText("")
        axis_y.setTitleVisible(False)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        bar_series.attachAxis(axis_y)

        axis_x = QValueAxis()
        axis_x.setTitleText("事件件數")
        axis_x.setLabelFormat("%d")
        axis_x.setLabelsFont(axis_font)
        axis_x.setLabelsColor(QColor(TOKENS.get("chart_axis_text", "#333333")))
        axis_x.setGridLinePen(QPen(QColor(TOKENS.get("chart_grid", "#c5d4de")), 1, Qt.PenStyle.DashLine))
        max_total = max((int(r.get("total_count", 0)) for r in data), default=10)
        apply_integer_count_axis(axis_x, max_total, padding=1)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        bar_series.attachAxis(axis_x)

        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        chart.legend().setLabelColor(QColor(TOKENS.get("chart_axis_text", "#333333")))

        chart_view = StableChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        chart_view.setMinimumHeight(max(CHART_MIN_HEIGHT, len(categories) * 28 + 150))
        chart_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        bar_series.hovered.connect(lambda status, idx, bs: self._on_resp_stacked_hovered(status, idx, data))

        self._chart = chart
        self._chart_series = bar_series
        self._chart_view = chart_view
        return chart_view

    def _on_resp_stacked_hovered(self, status: bool, index: int, data: list[dict]):
        if not status or index < 0 or index >= len(data):
            QToolTip.hideText()
            return

        row = data[index]
        min_open = row.get("min_open_date")
        max_open = row.get("max_open_date")
        
        # Format date range
        def to_yyyymm(d):
            if not d:
                return ""
            digits = d.replace("-", "")
            if len(digits) >= 6 and digits[:6].isdigit():
                return f"{digits[:4]}/{digits[4:6]}"
            return d[:7]

        if min_open:
            min_m = to_yyyymm(min_open)
            max_m = to_yyyymm(max_open) if max_open else min_m
            range_str = min_m if min_m == max_m else f"{min_m} ~ {max_m}"
        else:
            range_str = "無未結案"

        QToolTip.showText(
            QCursor.pos(),
            (
                f"責任人：{row['responsible_person']}\n"
                f"篩選區間總件數：{row['total_count']}\n"
                "------------------\n"
                f"已結案：{row['closed_count']} 件\n"
                f"未結案：{row['open_count']} 件\n"
                f"未結案累計月份：{range_str}"
            ),
            self
        )

    # ── 異常類別柏拉圖 ────────────────────────────────────────

    def _build_category_pareto_chart(self, rows: list[dict]) -> QChartView | None:
        if not rows:
            return None

        data = list(rows)
        display_data = list(reversed(data))
        categories = dedupe_chart_labels([
            short_chart_label(row.get("category") or "-", max_len=PARETO_CATEGORY_LABEL_MAX_LEN)
            for row in display_data
        ])

        count_set = QBarSet("件數")
        count_set.setColor(PARETO_BAR_COLOR)
        count_set.setBorderColor(PARETO_BAR_COLOR.darker(110))

        cumulative_series = QLineSeries()
        cumulative_series.setName("累積佔比")
        cumulative_series.setColor(PARETO_LINE_COLOR)
        cumulative_pen = QPen(PARETO_LINE_COLOR, 3)
        cumulative_series.setPen(cumulative_pen)
        cumulative_series.setPointsVisible(True)

        for index, row in enumerate(display_data):
            count_set.append(int(row.get("count") or 0))
            cumulative_series.append(float(row.get("cumulative_percent") or 0.0), index)

        bar_series = QHorizontalBarSeries()
        bar_series.append(count_set)
        bar_series.setLabelsVisible(True)
        bar_series.setLabelsPosition(QBarSeries.LabelsPosition.LabelsOutsideEnd)

        chart = QChart()
        chart.addSeries(bar_series)
        chart.addSeries(cumulative_series)
        chart.setTitle(f"異常類別柏拉圖分析 ({self._range_text()})")
        apply_chart_surface(chart)
        has_dense_categories = len(categories) > 4
        chart.setMargins(
            QMargins(
                24 if has_dense_categories else 8,
                18,
                56 if has_dense_categories else 24,
                42 if has_dense_categories else 18,
            )
        )

        app_font_family = QApplication.font().family()
        axis_label_font = QFont(app_font_family, 9)
        axis_title_font = QFont(app_font_family)
        axis_title_font.setPointSize(CHART_AXIS_TITLE_POINT_SIZE)
        point_label_font = QFont(app_font_family, 8)
        point_label_font.setBold(True)
        cumulative_series.setPointLabelsVisible(True)
        cumulative_series.setPointLabelsFormat("@xPoint%")
        cumulative_series.setPointLabelsColor(PARETO_LINE_COLOR.darker(110))
        cumulative_series.setPointLabelsFont(point_label_font)
        cumulative_series.setPointLabelsClipping(False)

        axis_y = QBarCategoryAxis()
        axis_y.append(categories)
        axis_y.setLabelsColor(QColor(TOKENS["chart_axis_text"]))
        axis_y.setLabelsFont(axis_label_font)
        axis_y.setTruncateLabels(False)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        bar_series.attachAxis(axis_y)
        cumulative_series.attachAxis(axis_y)

        max_count = max((int(row.get("count") or 0) for row in data), default=5)
        axis_x_count = QValueAxis()
        axis_x_count.setTitleText("件數")
        axis_x_count.setLabelFormat("%i")
        apply_integer_count_axis(axis_x_count, max_count, padding=1)
        axis_x_count.setLabelsColor(QColor(TOKENS["chart_axis_text"]))
        axis_x_count.setLabelsFont(axis_label_font)
        axis_x_count.setTitleFont(axis_title_font)
        axis_x_count.setGridLinePen(QPen(QColor(TOKENS.get("chart_grid", "#c5d4de")), 1, Qt.PenStyle.DashLine))
        chart.addAxis(axis_x_count, Qt.AlignmentFlag.AlignBottom)
        bar_series.attachAxis(axis_x_count)

        axis_x_percent = QValueAxis()
        axis_x_percent.setTitleText("累積佔比")
        axis_x_percent.setLabelFormat("%.0f%%")
        axis_x_percent.setRange(0, 100)
        axis_x_percent.setTickCount(6)
        axis_x_percent.setLabelsColor(PARETO_LINE_COLOR)
        axis_x_percent.setTitleBrush(PARETO_LINE_COLOR)
        axis_x_percent.setLabelsFont(axis_label_font)
        axis_x_percent.setTitleFont(axis_title_font)
        axis_x_percent.setGridLineVisible(False)
        chart.addAxis(axis_x_percent, Qt.AlignmentFlag.AlignTop)
        cumulative_series.attachAxis(axis_x_percent)

        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        if TOKENS.get("chart_axis_text"):
            chart.legend().setLabelColor(QColor(TOKENS["chart_axis_text"]))

        chart_view = StableChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        chart_view.setMinimumHeight(max(CHART_MIN_HEIGHT + 48, len(categories) * 32 + 150))
        chart_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        bar_series.hovered.connect(
            lambda status, idx, bs: self._on_category_pareto_hovered(status, idx, display_data)
        )

        return chart_view

    def _on_category_pareto_hovered(self, status: bool, index: int, data: list[dict]):
        if not status or index < 0 or index >= len(data):
            QToolTip.hideText()
            return

        row = data[index]
        QToolTip.showText(
            QCursor.pos(),
            (
                f"異常類別：{row['category']}\n"
                f"件數：{row['count']} 件\n"
                f"佔比：{row['percent']:.1f}%\n"
                f"累積佔比：{row['cumulative_percent']:.1f}%"
            ),
            self
        )


    def _build_trend_chart(self, trend_data: list[dict]) -> QChartView | None:
        if not trend_data:
            return None

        # 服務端已將範圍上限為 12 個月；此處同步防禦，避免超長區間壓縮長條圖
        data = trend_data[-12:]
        categories = []
        for d in data:
            categories.append(self._format_month_axis_label(d["yyyymm"]))

        new_set = QBarSet("新增件數")
        new_set.setColor(CHART_OPEN_COLOR)
        new_set.setBorderColor(CHART_OPEN_COLOR.darker(110))

        closed_set = QBarSet("結案件數")
        closed_set.setColor(CHART_CLOSED_COLOR)
        closed_set.setBorderColor(CHART_CLOSED_COLOR.darker(110))

        backlog_set = QBarSet("未結案件數")
        backlog_set.setColor(QColor(TOKENS.get("warning", "#ffc107")))
        backlog_set.setBorderColor(QColor(TOKENS.get("warning", "#ffc107")).darker(110))

        for d in data:
            new_set.append(d["total_count"])
            closed_set.append(d["closed_count"])
            backlog_set.append(d["backlog_count"])

        bar_series = QBarSeries()
        bar_series.append(new_set)
        bar_series.append(closed_set)
        bar_series.append(backlog_set)
        bar_series.setLabelsVisible(True)
        bar_series.setLabelsPosition(QBarSeries.LabelsPosition.LabelsOutsideEnd)

        chart = QChart()
        chart.addSeries(bar_series)
        chart.setTitle(self._trend_chart_title("供應商事件處理效率趨勢分析", data))
        apply_chart_surface(chart)
        chart.setMargins(QMargins(8, 8, 8, 8))

        app_font_family = QApplication.font().family()
        axis_label_font = QFont(app_font_family, 9)
        axis_title_font = QFont(app_font_family)
        axis_title_font.setPointSize(CHART_AXIS_TITLE_POINT_SIZE)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        # 超過 8 個月時類別變窄：改垂直標籤，避免相鄰月份黏在一起
        # 或首尾標籤因超出繪圖區邊緣被 Qt 整個隱藏
        axis_x.setLabelsAngle(-90 if len(categories) > 8 else 0)
        axis_x.setLabelsColor(QColor(TOKENS["chart_axis_text"]))
        axis_x.setLabelsFont(axis_label_font)
        # Qt 預設會把窄類別的「26/01」截成「2...」；標籤已極短，關閉截斷
        axis_x.setTruncateLabels(False)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        bar_series.attachAxis(axis_x)

        max_bar = max(
            [d["total_count"] for d in data] +
            [d["closed_count"] for d in data] +
            [d["backlog_count"] for d in data],
            default=5
        )
        axis_y = QValueAxis()
        axis_y.setTitleText("件數")
        axis_y.setLabelFormat("%i")
        apply_integer_count_axis(axis_y, max_bar, padding=2)
        axis_y.setLabelsColor(QColor(TOKENS["chart_axis_text"]))
        axis_y.setLabelsFont(axis_label_font)
        axis_y.setTitleFont(axis_title_font)
        axis_y.setGridLineVisible(True)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        bar_series.attachAxis(axis_y)

        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        if TOKENS.get("chart_axis_text"):
            chart.legend().setLabelColor(QColor(TOKENS["chart_axis_text"]))

        chart_view = StableChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        chart_view.setMinimumHeight(CHART_MIN_HEIGHT)
        chart_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        bar_series.hovered.connect(lambda status, idx, bs: self._on_trend_bar_hovered(status, idx, data))

        return chart_view

    def _on_trend_bar_hovered(self, status: bool, index: int, data: list[dict]):
        if not status or index < 0 or index >= len(data):
            QToolTip.hideText()
            return

        row = data[index]
        rate = 0
        if row["total_count"] > 0:
            rate = (row["closed_count"] / row["total_count"]) * 100

        QToolTip.showText(
            QCursor.pos(),
            (
                f"月份：{row['yyyymm']}\n"
                f"新增件數：{row['total_count']}\n"
                f"結案件數：{row['closed_count']}\n"
                f"未結案件數 (累積)：{row['backlog_count']}\n"
                f"當月結案率：{rate:.1f}%"
            ),
            self
        )

    # ── 訪廠品質趨勢圖表 ────────────────────────────────────────

    def _build_visit_trend_chart(self, visit_data: list[dict]) -> QChartView | None:
        if not visit_data:
            return None

        # 服務端已將範圍上限為 12 個月；此處同步防禦，避免超長區間壓縮長條圖
        data = visit_data[-12:]
        categories = []
        for d in data:
            categories.append(self._format_month_axis_label(d["yyyymm"]))

        visit_palette = get_status_palette("訪廠")
        visit_color = QColor(visit_palette.chart)

        anomaly_palette = get_status_palette("異常")
        anomaly_color = QColor(anomaly_palette.chart)

        visit_set = QBarSet("每月訪廠件數")
        visit_set.setColor(visit_color)
        visit_set.setBorderColor(visit_color.darker(110))

        anomaly_set = QBarSet("每月訪廠發現的異常件數")
        anomaly_set.setColor(anomaly_color)
        anomaly_set.setBorderColor(anomaly_color.darker(110))

        for d in data:
            visit_set.append(d["visit_count"])
            anomaly_set.append(d["visit_anomaly_count"])

        bar_series = QBarSeries()
        bar_series.append(visit_set)
        bar_series.append(anomaly_set)
        bar_series.setLabelsVisible(True)
        bar_series.setLabelsPosition(QBarSeries.LabelsPosition.LabelsOutsideEnd)

        chart = QChart()
        chart.addSeries(bar_series)
        chart.setTitle(self._trend_chart_title("供應商訪廠與訪廠異常趨勢分析", data))
        apply_chart_surface(chart)
        chart.setMargins(QMargins(8, 8, 8, 8))

        app_font_family = QApplication.font().family()
        axis_label_font = QFont(app_font_family, 9)
        axis_title_font = QFont(app_font_family)
        axis_title_font.setPointSize(CHART_AXIS_TITLE_POINT_SIZE)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        # 超過 8 個月時類別變窄：改垂直標籤，避免相鄰月份黏在一起
        # 或首尾標籤因超出繪圖區邊緣被 Qt 整個隱藏
        axis_x.setLabelsAngle(-90 if len(categories) > 8 else 0)
        axis_x.setLabelsColor(QColor(TOKENS["chart_axis_text"]))
        axis_x.setLabelsFont(axis_label_font)
        # Qt 預設會把窄類別的「26/01」截成「2...」；標籤已極短，關閉截斷
        axis_x.setTruncateLabels(False)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        bar_series.attachAxis(axis_x)

        max_bar = max([d["visit_count"] for d in data] + [d["visit_anomaly_count"] for d in data], default=5)
        axis_y = QValueAxis()
        axis_y.setTitleText("件數")
        axis_y.setLabelFormat("%i")
        apply_integer_count_axis(axis_y, max_bar, padding=2)
        axis_y.setLabelsColor(QColor(TOKENS["chart_axis_text"]))
        axis_y.setLabelsFont(axis_label_font)
        axis_y.setTitleFont(axis_title_font)
        axis_y.setGridLineVisible(True)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        bar_series.attachAxis(axis_y)

        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        if TOKENS.get("chart_axis_text"):
            chart.legend().setLabelColor(QColor(TOKENS["chart_axis_text"]))

        chart_view = StableChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        chart_view.setMinimumHeight(CHART_MIN_HEIGHT)
        chart_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        bar_series.hovered.connect(lambda status, idx, bs: self._on_visit_trend_bar_hovered(status, idx, data))

        return chart_view

    def _on_visit_trend_bar_hovered(self, status: bool, index: int, data: list[dict]):
        if not status or index < 0 or index >= len(data):
            QToolTip.hideText()
            return

        row = data[index]
        QToolTip.showText(
            QCursor.pos(),
            (
                f"月份：{row['yyyymm']}\n"
                f"訪廠件數：{row['visit_count']}\n"
                f"訪廠發現的異常件數：{row['visit_anomaly_count']}"
            ),
            self
        )

    # 倉庫不合格品圖表已移至獨立的「不合格品統計分析」頁（NcrStatsWidget），本 Mixin 不再持有。
