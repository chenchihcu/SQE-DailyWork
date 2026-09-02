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
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import QToolTip, QSizePolicy

from services.appearance_preferences_service import load_application_preferences
from ui.layout_constants import CHART_MIN_HEIGHT
from ui.status_colors import get_status_palette
from ui.theme import TOKENS
from ui.widgets.chart_style import (
    CHART_DATA_LABEL_POINT_SIZE,
    StableChartView,
    apply_axis_typography,
    apply_chart_surface,
    apply_integer_count_axis,
    get_chart_font,
)
from ui.widgets.stats_dashboard_helpers import dedupe_chart_labels, short_chart_label

# ── 圖表常數 ──────────────────────────────────────────────
SUPPLIER_LABEL_MAX_LEN = 12
PARETO_CATEGORY_LABEL_MAX_LEN = 12
CHART_OPEN_PALETTE = get_status_palette("待處理")
CHART_CLOSED_PALETTE = get_status_palette("已結案")
CHART_OPEN_COLOR = QColor(CHART_OPEN_PALETTE.chart)
CHART_CLOSED_COLOR = QColor(CHART_CLOSED_PALETTE.chart)


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
        closed_set.setLabelFont(get_chart_font(CHART_DATA_LABEL_POINT_SIZE))

        open_set = QBarSet("未結案")
        open_set.setColor(CHART_OPEN_COLOR)
        open_set.setLabelFont(get_chart_font(CHART_DATA_LABEL_POINT_SIZE))

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

        axis_y = QBarCategoryAxis()
        axis_y.append(categories)
        apply_axis_typography(axis_y)
        axis_y.setTruncateLabels(False)
        axis_y.setTitleText("")
        axis_y.setTitleVisible(False)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        bar_series.attachAxis(axis_y)

        axis_x = QValueAxis()
        axis_x.setLabelFormat("%d")
        apply_axis_typography(axis_x, title="事件件數")
        axis_x.setGridLinePen(QPen(QColor(TOKENS.get("chart_grid", "#c5d4de")), 1, Qt.PenStyle.DashLine))
        max_total = max((int(r.get("total_count", 0)) for r in data), default=10)
        apply_integer_count_axis(axis_x, max_total, padding=1)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        bar_series.attachAxis(axis_x)

        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)

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

        pareto_bar_color = QColor(TOKENS.get("primary_btn", "#1F6FEB"))
        pareto_line_color = QColor(TOKENS.get("brand_green", "#1FA85B"))

        count_set = QBarSet("件數")
        count_set.setColor(pareto_bar_color)
        count_set.setBorderColor(pareto_bar_color.darker(110))
        count_set.setLabelFont(get_chart_font(CHART_DATA_LABEL_POINT_SIZE))

        cumulative_series = QLineSeries()
        cumulative_series.setName("累積佔比")
        cumulative_series.setColor(pareto_line_color)
        cumulative_pen = QPen(pareto_line_color, 3)
        cumulative_series.setPen(cumulative_pen)
        cumulative_series.setPointsVisible(True)
        cumulative_series.setPointLabelsVisible(True)
        cumulative_series.setPointLabelsFormat("@xPoint%")
        cumulative_series.setPointLabelsColor(pareto_line_color.darker(110))
        cumulative_series.setPointLabelsFont(get_chart_font(CHART_DATA_LABEL_POINT_SIZE, bold=True))
        cumulative_series.setPointLabelsClipping(False)

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

        axis_y = QBarCategoryAxis()
        axis_y.append(categories)
        apply_axis_typography(axis_y)
        axis_y.setTruncateLabels(False)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        bar_series.attachAxis(axis_y)
        cumulative_series.attachAxis(axis_y)

        max_count = max((int(row.get("count") or 0) for row in data), default=5)
        axis_x_count = QValueAxis()
        axis_x_count.setLabelFormat("%i")
        apply_integer_count_axis(axis_x_count, max_count, padding=1)
        apply_axis_typography(axis_x_count, title="件數")
        axis_x_count.setGridLinePen(QPen(QColor(TOKENS.get("chart_grid", "#c5d4de")), 1, Qt.PenStyle.DashLine))
        chart.addAxis(axis_x_count, Qt.AlignmentFlag.AlignBottom)
        bar_series.attachAxis(axis_x_count)

        axis_x_percent = QValueAxis()
        axis_x_percent.setLabelFormat("%.0f%%")
        axis_x_percent.setRange(0, 100)
        axis_x_percent.setTickCount(6)
        apply_axis_typography(
            axis_x_percent,
            title="累積佔比",
            color_override=pareto_line_color,
        )
        axis_x_percent.setGridLineVisible(False)
        chart.addAxis(axis_x_percent, Qt.AlignmentFlag.AlignTop)
        cumulative_series.attachAxis(axis_x_percent)

        prefs = load_application_preferences()
        if prefs.pareto_show_cutoff_line and categories:
            cutoff_series = QLineSeries()
            cutoff_series.setName("80% 警戒線")
            cutoff_pen = QPen(QColor(TOKENS.get("warning", "#D97706")), 1.5, Qt.PenStyle.DashDotLine)
            cutoff_series.setPen(cutoff_pen)
            cutoff_series.append(80.0, -0.5)
            cutoff_series.append(80.0, len(categories) - 0.5)
            chart.addSeries(cutoff_series)
            cutoff_series.attachAxis(axis_x_percent)
            cutoff_series.attachAxis(axis_y)

        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)

        chart_view = StableChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        chart_view.setMinimumHeight(max(CHART_MIN_HEIGHT + 48, len(categories) * 32 + 150))
        chart_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        bar_series.hovered.connect(
            lambda status, idx, bs: self._on_category_pareto_hovered(status, idx, display_data)
        )

        return chart_view

    def _build_process_keyword_pareto_chart(self, rows: list[dict]) -> QChartView | None:
        adapted = [
            {
                "category": row.get("keyword") or "-",
                "count": row.get("count", 0),
                "percent": row.get("percent", 0.0),
                "cumulative_percent": row.get("cumulative_percent", 0.0),
                "rank": row.get("rank", 0),
            }
            for row in rows
        ]
        chart_view = self._build_category_pareto_chart(adapted)
        if chart_view is not None and chart_view.chart() is not None:
            chart_view.chart().setTitle(
                f"SMT 製程關鍵詞柏拉圖分析 ({self._range_text()})\n依關鍵詞出現次數統計"
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
        new_set.setLabelFont(get_chart_font(CHART_DATA_LABEL_POINT_SIZE))

        closed_set = QBarSet("結案件數")
        closed_set.setColor(CHART_CLOSED_COLOR)
        closed_set.setBorderColor(CHART_CLOSED_COLOR.darker(110))
        closed_set.setLabelFont(get_chart_font(CHART_DATA_LABEL_POINT_SIZE))

        backlog_set = QBarSet("未結案件數")
        backlog_set.setColor(QColor(TOKENS.get("warning", "#ffc107")))
        backlog_set.setBorderColor(QColor(TOKENS.get("warning", "#ffc107")).darker(110))
        backlog_set.setLabelFont(get_chart_font(CHART_DATA_LABEL_POINT_SIZE))

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

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        # 超過 8 個月時類別變窄：改垂直標籤，避免相鄰月份黏在一起
        # 或首尾標籤因超出繪圖區邊緣被 Qt 整個隱藏
        axis_x.setLabelsAngle(-90 if len(categories) > 8 else 0)
        apply_axis_typography(axis_x)
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
        axis_y.setLabelFormat("%i")
        apply_integer_count_axis(axis_y, max_bar, padding=2)
        apply_axis_typography(axis_y, title="件數")
        axis_y.setGridLineVisible(True)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        bar_series.attachAxis(axis_y)

        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)

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
                f"結案件數（依結案日期）：{row['closed_count']}\n"
                f"未結案件數 (累積)：{row['backlog_count']}\n"
                f"當月結案率：{rate:.1f}%"
            ),
            self
        )

