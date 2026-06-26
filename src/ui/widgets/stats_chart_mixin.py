"""統計檢視圖表的 Mixin 類別。

從 StatsViewWidget 中提取所有圖表建構方法與事件處理，
透過 Mixin 模式注入回原 widget，保持 _render_charts 等協調邏輯在 widget 本體。

領域規則
===================
- 混合(Mixin)方法僅存取 self 上由主 Widget 提供的屬性/方法
- 不持有 QWidget 子類別的狀態  —  狀態一律由主 Widget 管理
- Duck Typing：self._month_key()、self.defect_grid 等會於執行期由主 Widget 滿足
"""

from __future__ import annotations

import logging

import ncr.services.stats_service as ncr_stats_service
from database.connection import get_connection
from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QHorizontalBarSeries,
    QHorizontalStackedBarSeries,
    QLineSeries,
    QPieSeries,
    QScatterSeries,
    QValueAxis,
)
from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPen
from PySide6.QtWidgets import QApplication, QLabel, QSizePolicy, QToolTip

from ui.design_tokens import PALETTE
from ui.layout_constants import CHART_BAR_HEIGHT, CHART_HEADER_FOOTER_OFFSET, CHART_MIN_HEIGHT
from ui.status_colors import get_status_palette
from ui.theme import TOKENS
from services import event_service
from ui.widgets.chart_style import apply_chart_surface

logger = logging.getLogger(__name__)

# ── 圖表常數 ──────────────────────────────────────────────
SUPPLIER_LABEL_MAX_LEN = 12
CHART_AXIS_LABEL_POINT_SIZE = 11
CHART_AXIS_TITLE_POINT_SIZE = 11
CHART_AXIS_LABEL_ANGLE = 65
CHART_OPEN_PALETTE = get_status_palette("待處理")
CHART_CLOSED_PALETTE = get_status_palette("已結案")
CHART_OVERDUE_PALETTE = get_status_palette("逾期未結")
CHART_OPEN_COLOR = QColor(CHART_OPEN_PALETTE.chart)
CHART_CLOSED_COLOR = QColor(CHART_CLOSED_PALETTE.chart)
CHART_OVERDUE_COLOR = QColor(CHART_OVERDUE_PALETTE.chart)
_C_DANGER = QColor(PALETTE["danger_chart"])
_C_PENDING = QColor(PALETTE["pending_chart"])
_C_SUCCESS = QColor(PALETTE["success_chart"])
_C_INFO = QColor(PALETTE["info_chart"])
_C_CHART4 = QColor(PALETTE["chart_4"])


class _StatsChartMixin:
    """提供異常統計與不合格品統計的圖表建構能力。

    透過多重繼承與 StatsViewWidget 組合使用：
        class StatsViewWidget(QWidget, _StatsChartMixin):
            ...

    圖表方法會透過 self 存取主 Widget 提供的以下屬性/方法：
    - self.main_window              (set in __init__)
    - self.defect_grid              (set in _setup_ui)
    - self._chart_content_layout    (set in _setup_ui)
    - self._trend_content_layout    (set in _setup_ui)
    - self._resp_content_layout     (set in _setup_ui)
    - self._month_key()             (provided by widget)
    - self._month_text()            (provided by widget)
    - self._create_insight_label()  (provided by widget)
    """

    # ── 輔助方法 ──────────────────────────────────────────

    def _short_supplier_label(self, supplier_name: str, *, max_len: int = SUPPLIER_LABEL_MAX_LEN) -> str:
        text = str(supplier_name or "").strip() or "-"
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

    def _dedupe_chart_labels(self, labels: list[str]) -> list[str]:
        if len(labels) == len(set(labels)):
            return labels
        width = len(str(len(labels)))
        return [f"{index + 1:0{width}d}. {label}" for index, label in enumerate(labels)]

    def _clear_top_suppliers(self):
        if any(l is None for l in (self._chart_content_layout, self._trend_content_layout, self._resp_content_layout)):
            return
        for layout in (self._chart_content_layout, self._trend_content_layout, self._resp_content_layout):
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

    # ── 供應商風險圖表 ────────────────────────────────────

    def _build_supplier_chart(self, rows: list[dict]) -> QChartView | None:
        if not rows:
            return None

        data = rows[:15]
        data.reverse()
        self._last_supplier_data = list(data)
        categories = self._dedupe_chart_labels([
            self._short_supplier_label(r["supplier_name"], max_len=SUPPLIER_LABEL_MAX_LEN)
            for r in data
        ])

        overdue_set = QBarSet("逾期未結")
        overdue_set.setColor(CHART_OVERDUE_COLOR)

        ongoing_set = QBarSet("進行中")
        ongoing_set.setColor(CHART_OPEN_COLOR)

        closed_set = QBarSet("已結案")
        closed_set.setColor(CHART_CLOSED_COLOR)

        line_series = QLineSeries()
        line_series.setName("平均處理時效 (天)")
        line_series.setColor(QColor(TOKENS.get("info", "#2196f3")))
        line_series.setPointsVisible(True)

        for i, r in enumerate(data):
            total_open = int(r.get("open_anomaly_count") or 0)
            overdue = int(r.get("overdue_open_anomaly_count") or 0)
            ongoing = max(0, total_open - overdue)
            closed = int(r.get("closed_anomaly_count") or 0)

            overdue_set.append(overdue)
            ongoing_set.append(ongoing)
            closed_set.append(closed)
            line_series.append(float(r.get("avg_resolution_time") or 0), i)

        bar_series = QHorizontalStackedBarSeries()
        bar_series.append(overdue_set)
        bar_series.append(ongoing_set)
        bar_series.append(closed_set)
        bar_series.setLabelsVisible(True)

        chart = QChart()
        chart.addSeries(bar_series)
        chart.addSeries(line_series)
        chart.setTitle("供應商品質風險堆疊分析")
        apply_chart_surface(chart)
        chart.setMargins(QMargins(10, 10, 10, 10))

        app_font_family = QApplication.font().family()
        axis_font = QFont(app_font_family, CHART_AXIS_LABEL_POINT_SIZE)
        title_font = QFont(app_font_family, CHART_AXIS_TITLE_POINT_SIZE, QFont.Weight.Bold)

        axis_y = QBarCategoryAxis()
        axis_y.append(categories)
        axis_y.setLabelsFont(axis_font)
        axis_y.setLabelsColor(QColor(TOKENS.get("chart_axis_text", "#333333")))
        axis_y.setTruncateLabels(False)
        axis_y.setLabelsAngle(0)
        axis_y.setTitleText("")
        axis_y.setTitleVisible(False)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        bar_series.attachAxis(axis_y)
        line_series.attachAxis(axis_y)

        axis_x_count = QValueAxis()
        axis_x_count.setTitleText("異常件數")
        axis_x_count.setLabelFormat("%d")
        axis_x_count.setLabelsFont(axis_font)
        axis_x_count.setLabelsColor(QColor(TOKENS.get("chart_axis_text", "#333333")))
        axis_x_count.setGridLinePen(QPen(QColor(TOKENS.get("chart_grid", "#c5d4de")), 1, Qt.PenStyle.DashLine))
        max_total = max((int(r.get("anomaly_count", 0)) for r in data), default=10)
        axis_x_count.setRange(0, max_total + 1)
        chart.addAxis(axis_x_count, Qt.AlignmentFlag.AlignBottom)
        bar_series.attachAxis(axis_x_count)

        axis_x_time = QValueAxis()
        axis_x_time.setTitleText("平均處理時效 (天)")
        axis_x_time.setLabelFormat("%.1f")
        axis_x_time.setLabelsFont(axis_font)
        axis_x_time.setLabelsColor(QColor(TOKENS.get("info", "#2196f3")))
        axis_x_time.setGridLineVisible(False)
        max_time = max((float(r.get("avg_resolution_time") or 0) for r in data), default=10)
        axis_x_time.setRange(0, max_time + 5)
        chart.addAxis(axis_x_time, Qt.AlignmentFlag.AlignTop)
        line_series.attachAxis(axis_x_time)

        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        chart.legend().setLabelColor(QColor(TOKENS.get("chart_axis_text", "#333333")))

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        chart_view.setMinimumHeight(max(CHART_MIN_HEIGHT, len(categories) * 28 + 150))

        bar_series.hovered.connect(lambda status, idx, bs: self._on_chart_bar_hovered(status, idx, bs))
        bar_series.clicked.connect(lambda idx, bs: self._on_chart_bar_clicked(idx, bs))

        self._chart = chart
        self._chart_series = bar_series
        self._chart_view = chart_view
        return chart_view

    def _on_supplier_bar_hovered(self, status: bool, index: int, data: list[dict]):
        if not status or index < 0 or index >= len(data):
            QToolTip.hideText()
            return

        row = data[index]
        total_open = int(row.get("open_anomaly_count") or 0)
        overdue = int(row.get("overdue_open_anomaly_count") or 0)
        ongoing = max(0, total_open - overdue)

        QToolTip.showText(
            QCursor.pos(),
            (
                f"供應商：{row['supplier_name']}\n"
                f"月份：{self._month_text()}\n"
                "------------------\n"
                f"總異常件數：{row['anomaly_count']}\n"
                f"逾期未結：{overdue}\n"
                f"進行中：{ongoing}\n"
                f"已結案：{row['closed_anomaly_count']}\n"
                f"平均處理時效：{row.get('avg_resolution_time', 0)} 天"
            ),
            self
        )

    def _on_chart_bar_hovered(self, status: bool, index: int, bar_set: QBarSet):
        data = self._last_supplier_data
        if not isinstance(data, list):
            QToolTip.hideText()
            return
        self._on_supplier_bar_hovered(status, index, data)

    def _on_chart_bar_clicked(self, index: int, bar_set: QBarSet):
        data = self._last_supplier_data
        if not data or index < 0 or index >= len(data):
            return

        row = data[index]
        if self.main_window:
            status_filter = "ALL"
            label = bar_set.label()
            if "逾期" in label or "進行中" in label:
                status_filter = "待處理"

            scope = (
                event_service.EVENT_SCOPE_CLOSED_ONLY
                if status_filter == "已結案"
                else event_service.EVENT_SCOPE_ANOMALY_ONLY
            )
            self.main_window.open_event_query_with_filters(
                event_type="ANOMALY",
                supplier_keyword=str(row["supplier_name"]),
                yyyymm=str(self._month_key()),
                status=status_filter,
                event_scope=scope,
            )

    # ── 趨勢圖表 ──────────────────────────────────────────

    def _build_trend_chart(self, trend_data: list[dict]) -> QChartView | None:
        if not trend_data:
            return None

        categories = [d["yyyymm"] for d in trend_data]

        new_set = QBarSet("新增異常")
        new_set.setColor(CHART_OPEN_COLOR)
        new_set.setBorderColor(CHART_OPEN_COLOR.darker(110))

        closed_set = QBarSet("已結案數")
        closed_set.setColor(CHART_CLOSED_COLOR)
        closed_set.setBorderColor(CHART_CLOSED_COLOR.darker(110))

        for d in trend_data:
            new_set.append(d["total_count"])
            closed_set.append(d["closed_count"])

        bar_series = QBarSeries()
        bar_series.append(new_set)
        bar_series.append(closed_set)
        bar_series.setLabelsVisible(True)
        bar_series.setLabelsPosition(QBarSeries.LabelsPosition.LabelsOutsideEnd)

        backlog_series = QLineSeries()
        backlog_series.setName("積壓未結 (全期)")
        backlog_series.setColor(QColor(TOKENS.get("warning", "#ffc107")))
        backlog_series.setPointsVisible(True)

        backlog_points = QScatterSeries()
        backlog_points.setMarkerSize(10)
        backlog_points.setColor(QColor(TOKENS.get("warning", "#ffc107")))
        backlog_points.setBorderColor(QColor("white"))

        for i, d in enumerate(trend_data):
            backlog_series.append(i, d["backlog_count"])
            backlog_points.append(i, d["backlog_count"])

        app_font_family = QApplication.font().family()

        label_font = QFont(app_font_family, 9)
        backlog_series.setPointLabelsVisible(True)
        backlog_series.setPointLabelsFormat("@yPoint")
        backlog_series.setPointLabelsFont(label_font)
        backlog_series.setPointLabelsColor(QColor(TOKENS.get("warning", "#ffc107")))

        chart = QChart()
        chart.addSeries(bar_series)
        chart.addSeries(backlog_series)
        chart.addSeries(backlog_points)
        backlog_points.setName("")
        apply_chart_surface(chart)
        chart.setMargins(QMargins(8, 8, 8, 8))

        axis_label_font = QFont(app_font_family)
        axis_label_font.setPointSize(CHART_AXIS_LABEL_POINT_SIZE)
        axis_title_font = QFont(app_font_family)
        axis_title_font.setPointSize(CHART_AXIS_TITLE_POINT_SIZE)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setLabelsColor(QColor(TOKENS["chart_axis_text"]))
        axis_x.setLabelsFont(axis_label_font)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        bar_series.attachAxis(axis_x)
        backlog_series.attachAxis(axis_x)
        backlog_points.attachAxis(axis_x)

        max_bar = max([d["total_count"] for d in trend_data] + [d["closed_count"] for d in trend_data], default=5)
        axis_y_count = QValueAxis()
        axis_y_count.setTitleText("當月件數")
        axis_y_count.setLabelFormat("%i")
        axis_y_count.setRange(0, max_bar + 2)
        axis_y_count.setLabelsColor(QColor(TOKENS["chart_axis_text"]))
        axis_y_count.setLabelsFont(axis_label_font)
        axis_y_count.setTitleFont(axis_title_font)
        axis_y_count.setGridLineVisible(True)
        chart.addAxis(axis_y_count, Qt.AlignmentFlag.AlignLeft)
        bar_series.attachAxis(axis_y_count)

        max_backlog = max([d["backlog_count"] for d in trend_data], default=5)
        axis_y_backlog = QValueAxis()
        axis_y_backlog.setTitleText("累積積壓數")
        axis_y_backlog.setLabelFormat("%i")
        axis_y_backlog.setRange(0, max_backlog + 5)
        axis_y_backlog.setLabelsColor(QColor(TOKENS.get("warning", "#ffc107")))
        axis_y_backlog.setLabelsFont(axis_label_font)
        axis_y_backlog.setTitleFont(axis_title_font)
        axis_y_backlog.setGridLineVisible(False)
        chart.addAxis(axis_y_backlog, Qt.AlignmentFlag.AlignRight)
        backlog_series.attachAxis(axis_y_backlog)
        backlog_points.attachAxis(axis_y_backlog)

        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        if TOKENS.get("chart_axis_text"):
            chart.legend().setLabelColor(QColor(TOKENS["chart_axis_text"]))
        for _marker in chart.legend().markers(backlog_points):
            _marker.setVisible(False)

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        chart_view.setMinimumHeight(CHART_MIN_HEIGHT)

        bar_series.hovered.connect(lambda status, idx, bs: self._on_trend_bar_hovered(status, idx, trend_data))
        backlog_points.hovered.connect(lambda pt, state: self._on_trend_line_hovered(state, pt, trend_data))

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
                f"新增異常：{row['total_count']}\n"
                f"已結案數：{row['closed_count']}\n"
                f"當月結案率：{rate:.1f}%\n"
                f"逾期未結：{row['overdue_count']} (當月件)"
            ),
            self
        )

    def _on_trend_line_hovered(self, status: bool, point: any, data: list[dict]):
        if not status:
            QToolTip.hideText()
            return

        index = int(round(point.x()))
        if index < 0 or index >= len(data):
            return

        row = data[index]
        QToolTip.showText(
            QCursor.pos(),
            (
                f"月份：{row['yyyymm']}\n"
                f"累積未結積壓：{row['backlog_count']}\n"
                f"包含本月及歷史所有未結案項目"
            ),
            self
        )

    # ── 負責人圖表 ────────────────────────────────────────

    def _build_responsible_chart(self, rows: list[dict]) -> QChartView | None:
        if not rows:
            return None

        data = rows[:15]
        categories = self._dedupe_chart_labels([
            self._short_supplier_label(r["responsible_person"], max_len=10)
            for r in data
        ])

        bar_set = QBarSet("總件數")
        bar_set.setColor(CHART_OPEN_COLOR)
        bar_set.setBorderColor(CHART_OPEN_COLOR.darker(110))

        line_series = QLineSeries()
        line_series.setName("平均處理時效 (天)")
        line_series.setColor(QColor(TOKENS["info"]))
        line_series.setPointsVisible(True)

        for i, row in enumerate(data):
            bar_set.append(row["total_count"])
            line_series.append(i, row["avg_resolution_time"])

        app_font_family = QApplication.font().family()

        label_font = QFont(app_font_family, 9)
        line_series.setPointLabelsVisible(True)
        line_series.setPointLabelsFormat("@yPoint d")
        line_series.setPointLabelsFont(label_font)
        line_series.setPointLabelsColor(QColor(TOKENS["info"]))

        bar_series = QBarSeries()
        bar_series.append(bar_set)
        bar_series.setLabelsVisible(True)
        bar_series.setLabelsPosition(QBarSeries.LabelsPosition.LabelsOutsideEnd)

        chart = QChart()
        chart.addSeries(bar_series)
        chart.addSeries(line_series)
        apply_chart_surface(chart)
        chart.setMargins(QMargins(8, 8, 8, 8))

        axis_label_font = QFont(app_font_family)
        axis_label_font.setPointSize(CHART_AXIS_LABEL_POINT_SIZE)
        axis_title_font = QFont(app_font_family)
        axis_title_font.setPointSize(CHART_AXIS_TITLE_POINT_SIZE)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setLabelsAngle(CHART_AXIS_LABEL_ANGLE)
        axis_x.setLabelsColor(QColor(TOKENS["chart_axis_text"]))
        axis_x.setLabelsFont(axis_label_font)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        bar_series.attachAxis(axis_x)
        line_series.attachAxis(axis_x)

        axis_y_count = QValueAxis()
        axis_y_count.setTitleText("總件數")
        axis_y_count.setLabelFormat("%i")
        axis_y_count.setLabelsColor(QColor(TOKENS["chart_axis_text"]))
        axis_y_count.setLabelsFont(axis_label_font)
        axis_y_count.setTitleFont(axis_title_font)
        max_count = max((r["total_count"] for r in data), default=10)
        axis_y_count.setRange(0, max_count + 1)
        axis_y_count.applyNiceNumbers()
        chart.addAxis(axis_y_count, Qt.AlignmentFlag.AlignLeft)
        bar_series.attachAxis(axis_y_count)

        axis_y_rate = QValueAxis()
        axis_y_rate.setTitleText("平均處理時效 (天)")
        max_time = max((r["avg_resolution_time"] for r in data), default=10)
        axis_y_rate.setRange(0, max_time + 5)
        axis_y_rate.setLabelFormat("%.1f")
        axis_y_rate.setLabelsColor(QColor(TOKENS["chart_axis_text"]))
        axis_y_rate.setLabelsFont(axis_label_font)
        axis_y_rate.setTitleFont(axis_title_font)
        chart.addAxis(axis_y_rate, Qt.AlignmentFlag.AlignRight)
        line_series.attachAxis(axis_y_rate)

        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        if TOKENS.get("chart_axis_text"):
            chart.legend().setLabelColor(QColor(TOKENS["chart_axis_text"]))

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        calc_h = (len(data) * 18) + 240
        chart_view.setMinimumHeight(max(CHART_MIN_HEIGHT, calc_h))

        bar_series.hovered.connect(lambda status, idx, bs: self._on_resp_hovered(status, idx, data))

        return chart_view

    def _on_resp_hovered(self, status: bool, index: int, data: list[dict]):
        if not status or index < 0 or index >= len(data):
            QToolTip.hideText()
            return

        row = data[index]
        QToolTip.showText(
            QCursor.pos(),
            (
                f"責任人：{row['responsible_person']}\n"
                f"總件數：{row['total_count']}\n"
                f"平均處理時效：{row['avg_resolution_time']} 天\n"
                f"月份：{self._month_text()}"
            ),
            self
        )

    # ── 不合格品（倉庫）圖表 ──────────────────────────────

    def _refresh_defect_charts(self):
        while self.defect_grid.count() > 0:
            item = self.defect_grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()

        try:
            with get_connection() as conn:
                pie_rows = ncr_stats_service.get_disposition_stats(conn)
                trend_rows = ncr_stats_service.get_trend_stats(conn, months=6)
                product_rows = ncr_stats_service.get_top_products_stats_filtered(conn)
                supplier_rows = ncr_stats_service.get_supplier_disposition_stats(conn)
        except Exception as exc:
            logger.exception("載入倉庫不合格品統計數據失敗")
            err_lbl = QLabel(f"無法載入倉庫不合格品統計數據：{exc}")
            self.defect_grid.addWidget(err_lbl, 0, 0)
            return

        pie_view = self._build_defect_pie_chart(pie_rows)
        trend_view = self._build_defect_trend_chart(trend_rows)
        product_view = self._build_defect_product_chart(product_rows)
        supplier_view = self._build_defect_supplier_chart(supplier_rows)

        for row_index, view in enumerate((pie_view, trend_view, product_view, supplier_view)):
            self.defect_grid.addWidget(view, row_index, 0)
            if view:
                view.setMinimumHeight(CHART_MIN_HEIGHT)
                view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.defect_grid.setColumnStretch(0, 1)

    def _build_defect_pie_chart(self, rows) -> QChartView:
        series = QPieSeries()
        series.setHoleSize(0.35)
        series.setPieSize(0.85)
        total_qty = sum(int(r["total_qty"] or 0) for r in rows)

        colors = {
            "報廢": _C_DANGER,
            "退貨": _C_PENDING,
            "重工": _C_SUCCESS,
        }

        for r in rows:
            disp = r["disposition"] or "未註明"
            qty = int(r["total_qty"] or 0)
            if qty > 0:
                pct = (qty / total_qty * 100) if total_qty > 0 else 0
                slice_obj = series.append(f"{disp} ({qty}件, {pct:.1f}%)", qty)
                slice_obj.setLabelVisible(False)
                slice_obj.setBrush(colors.get(disp, _C_INFO))

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("倉庫不合格品處置數量佔比")
        apply_chart_surface(chart)
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignRight)
        chart.legend().setLabelColor(QColor(TOKENS.get("chart_axis_text", "#333333")))

        view = QChartView(chart)
        view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        return view

    def _build_defect_trend_chart(self, rows) -> QChartView:
        series = QLineSeries()
        series.setName("月度不合格品總數 (件)")
        series.setColor(_C_CHART4)
        series.setPointsVisible(True)

        categories = []
        max_qty = 0
        for i, r in enumerate(rows):
            month = r["event_month"]
            qty = int(r["total_qty"] or 0)
            categories.append(month)
            series.append(i, qty)
            if qty > max_qty:
                max_qty = qty

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("近六個月倉庫不合格品趨勢")
        apply_chart_surface(chart)
        chart.legend().setVisible(False)

        app_font_family = QApplication.font().family()
        axis_label_font = QFont(app_font_family, CHART_AXIS_LABEL_POINT_SIZE)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setLabelsColor(QColor(TOKENS.get("chart_axis_text", "#333333")))
        axis_x.setLabelsFont(axis_label_font)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setLabelFormat("%d")
        axis_y.setLabelsColor(QColor(TOKENS.get("chart_axis_text", "#333333")))
        axis_y.setLabelsFont(axis_label_font)
        axis_y.setGridLinePen(QPen(QColor(TOKENS.get("chart_grid", "#c5d4de")), 1, Qt.PenStyle.DashLine))
        axis_y.setRange(0, max_qty + 5 if max_qty > 0 else 10)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        view = QChartView(chart)
        view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        return view

    def _build_defect_product_chart(self, rows) -> QChartView:
        series = QHorizontalBarSeries()
        series.setLabelsVisible(True)
        series.setBarWidth(0.6)

        bar_set = QBarSet("不合格品總數")
        bar_set.setBrush(_C_INFO)
        categories = []

        data = list(rows)[:5]
        for r in reversed(data):
            categories.append(self._short_supplier_label(r["product_name"], max_len=12))
            bar_set.append(int(r["total_qty"] or 0))
        categories = self._dedupe_chart_labels(categories)

        series.append(bar_set)

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("Top 5 倉庫不合格品產品")
        apply_chart_surface(chart)
        chart.legend().setVisible(False)

        app_font_family = QApplication.font().family()
        axis_label_font = QFont(app_font_family, CHART_AXIS_LABEL_POINT_SIZE)

        axis_y = QBarCategoryAxis()
        axis_y.append(categories)
        axis_y.setLabelsColor(QColor(TOKENS.get("chart_axis_text", "#333333")))
        axis_y.setLabelsFont(axis_label_font)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        axis_x = QValueAxis()
        axis_x.setLabelFormat("%d")
        axis_x.setLabelsColor(QColor(TOKENS.get("chart_axis_text", "#333333")))
        axis_x.setLabelsFont(axis_label_font)
        axis_x.setGridLinePen(QPen(QColor(TOKENS.get("chart_grid", "#c5d4de")), 1, Qt.PenStyle.DashLine))
        max_qty = max((int(r["total_qty"] or 0) for r in data), default=10)
        axis_x.setRange(0, max_qty + 2)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        view = QChartView(chart)
        view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        return view

    def _build_defect_supplier_chart(self, rows) -> QChartView:
        suppliers = []
        for r in rows:
            if r["supplier_name"] not in suppliers:
                suppliers.append(r["supplier_name"])

        supplier_totals = {s: 0 for s in suppliers}
        for r in rows:
            supplier_totals[r["supplier_name"]] += int(r["total_qty"] or 0)
        suppliers.sort(key=lambda s: supplier_totals[s], reverse=True)
        suppliers = list(reversed(suppliers[:5]))

        series = QHorizontalStackedBarSeries()
        series.setLabelsVisible(True)
        series.setBarWidth(0.6)

        set_scrap = QBarSet("報廢")
        set_scrap.setBrush(_C_DANGER)
        set_return = QBarSet("退貨")
        set_return.setBrush(_C_PENDING)
        set_rework = QBarSet("重工")
        set_rework.setBrush(_C_SUCCESS)

        short_suppliers = []
        for s in suppliers:
            short_suppliers.append(self._short_supplier_label(s, max_len=10))
            scrap = 0
            ret = 0
            rework = 0
            for r in rows:
                if r["supplier_name"] != s:
                    continue
                qty = int(r["total_qty"] or 0)
                disp = r["disposition"]
                if disp == "報廢":
                    scrap += qty
                elif disp == "退貨":
                    ret += qty
                elif disp == "重工":
                    rework += qty
            set_scrap.append(scrap)
            set_return.append(ret)
            set_rework.append(rework)
        short_suppliers = self._dedupe_chart_labels(short_suppliers)

        series.append(set_scrap)
        series.append(set_return)
        series.append(set_rework)

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("供應商 / 倉庫處置關聯分析")
        apply_chart_surface(chart)
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        chart.legend().setLabelColor(QColor(TOKENS.get("chart_axis_text", "#333333")))

        app_font_family = QApplication.font().family()
        axis_label_font = QFont(app_font_family, CHART_AXIS_LABEL_POINT_SIZE)

        axis_y = QBarCategoryAxis()
        axis_y.append(short_suppliers)
        axis_y.setLabelsColor(QColor(TOKENS.get("chart_axis_text", "#333333")))
        axis_y.setLabelsFont(axis_label_font)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        axis_x = QValueAxis()
        axis_x.setLabelFormat("%d")
        axis_x.setLabelsColor(QColor(TOKENS.get("chart_axis_text", "#333333")))
        axis_x.setLabelsFont(axis_label_font)
        axis_x.setGridLinePen(QPen(QColor(TOKENS.get("chart_grid", "#c5d4de")), 1, Qt.PenStyle.DashLine))
        max_total = max(supplier_totals.values(), default=10)
        axis_x.setRange(0, max_total + 2)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        view = QChartView(chart)
        view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        return view
