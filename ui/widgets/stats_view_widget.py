from __future__ import annotations

from datetime import datetime

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QHorizontalStackedBarSeries,
    QLineSeries,
    QScatterSeries,
    QValueAxis,
)
from PySide6.QtCore import QDate, QMargins, Qt
from PySide6.QtGui import QBrush, QColor, QCursor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDateEdit,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from services import event_service
from ui.layout_constants import (
    CARD_INNER_MARGINS,
    CHART_BAR_HEIGHT,
    CHART_HEADER_FOOTER_OFFSET,
    CHART_MIN_HEIGHT,
    GRID_GUTTER,
    INLINE_SPACING,
    INLINE_TIGHT_SPACING,
    PANEL_MARGINS,
    RANK_PANEL_MARGINS,
    ROOT_SECTION_SPACING,
    ROW_GAP,
)
from ui.popup_i18n import localize_exception, localize_popup_message
from ui.status_colors import get_status_palette
from ui.theme import TOKENS
from ui.widgets.common_widgets import (
    EmptyStateWidget, 
    KpiCard, 
    apply_clickable_affordance
)

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




class StatsViewWidget(QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self._rank_month_label: QLabel | None = None
        self._chart_content_layout: QVBoxLayout | None = None
        self._trend_content_layout: QVBoxLayout | None = None
        self._resp_content_layout: QVBoxLayout | None = None
        self._chart_view: QChartView | None = None
        self._chart: QChart | None = None
        self._chart_series: QHorizontalStackedBarSeries | None = None
        self._chart_supplier_names: list[str] = []
        self._chart_ongoing_values: list[int] = []
        self._chart_overdue_values: list[int] = []
        self._chart_closed_values: list[int] = []
        self._chart_total_values: list[int] = []
        self._chart_avg_time_values: list[float] = []
        self._last_supplier_data: list[dict] = []
        self._setup_ui()
        self.refresh_data()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        top_panel = QFrame()
        top_panel.setProperty("role", "panel")
        top_layout = QVBoxLayout(top_panel)
        top_layout.setContentsMargins(*PANEL_MARGINS)
        top_layout.setSpacing(INLINE_SPACING)

        month_row = QHBoxLayout()
        month_row.setSpacing(INLINE_SPACING)
        month_label = QLabel("月份")
        month_label.setProperty("role", "sectionTitle")
        self.month_input = QDateEdit()
        self.month_input.setDisplayFormat("yyyy-MM")
        self.month_input.setDate(QDate.currentDate())
        self.month_input.setCalendarPopup(True)
        self.month_input.dateChanged.connect(self._on_month_changed)
        
        self.all_time_toggle = QCheckBox("全期資料")
        apply_clickable_affordance(self.all_time_toggle, tooltip="切換顯示全期累計或指定月份")
        self.all_time_toggle.toggled.connect(self._on_all_time_toggled)
        
        month_row.addWidget(month_label)
        month_row.addWidget(self.month_input)
        month_row.addWidget(self.all_time_toggle)
        month_row.addStretch(1)

        btn_export = QPushButton("匯出 Excel")
        btn_export.setProperty("variant", "primary")
        apply_clickable_affordance(btn_export, tooltip="匯出目前月份統計 Excel")
        btn_export.clicked.connect(self.export_monthly_excel)
        month_row.addWidget(btn_export)
        top_layout.addLayout(month_row)

        root.addWidget(top_panel)

        # --- Tab System ---
        self.tabs = QTabWidget()

        # 1. Trend Tab
        trend_tab = QWidget()
        trend_tab_layout = QVBoxLayout(trend_tab)
        trend_tab_layout.setContentsMargins(0, 4, 0, 0)
        
        trend_panel = QFrame()
        trend_panel.setProperty("role", "panel")
        trend_layout = QVBoxLayout(trend_panel)
        trend_layout.setContentsMargins(*RANK_PANEL_MARGINS)
        trend_layout.setSpacing(INLINE_TIGHT_SPACING)

        trend_title_row = QHBoxLayout()
        trend_title = QLabel("品質異常趨勢分析 (過去 6 個月)")
        trend_title.setProperty("role", "sectionTitle")
        trend_title_row.addWidget(trend_title)
        trend_title_row.addStretch(1)
        trend_layout.addLayout(trend_title_row)

        trend_info = self._create_info_banner(
            "柱狀圖為當月新增與結案數；折線圖為全期累計尚未結案之積壓總數。",
            "監控月度解決效率，並預警歷史積壓是否持續擴大，確保系統負荷正常。"
        )
        trend_layout.addWidget(trend_info)

        self._trend_content_layout = QVBoxLayout()
        self._trend_content_layout.setSpacing(4)
        trend_layout.addLayout(self._trend_content_layout, 1)
        trend_tab_layout.addWidget(trend_panel)
        self.tabs.addTab(trend_tab, "品質異常趨勢分析")

        # 2. Responsible Person Tab
        resp_tab = QWidget()
        resp_tab_layout = QVBoxLayout(resp_tab)
        resp_tab_layout.setContentsMargins(0, 4, 0, 0)

        responsible_panel = QFrame()
        responsible_panel.setProperty("role", "panel")
        responsible_layout = QVBoxLayout(responsible_panel)
        responsible_layout.setContentsMargins(*RANK_PANEL_MARGINS)
        responsible_layout.setSpacing(INLINE_TIGHT_SPACING)

        resp_title_row = QHBoxLayout()
        resp_title = QLabel("責任人績效分析 (總件數 vs 平均處理時效)")
        resp_title.setProperty("role", "sectionTitle")
        resp_title_row.addWidget(resp_title)
        resp_title_row.addStretch(1)
        responsible_layout.addLayout(resp_title_row)

        resp_info = self._create_info_banner(
            "柱狀圖為個人負責案件總數；折線圖為該人員之平均處理天數。",
            "評估團隊工作量分佈均衡度與處理效率，輔助人力資源調度。"
        )
        responsible_layout.addWidget(resp_info)

        self._resp_content_layout = QVBoxLayout()
        self._resp_content_layout.setSpacing(4)
        responsible_layout.addLayout(self._resp_content_layout, 1)
        resp_tab_layout.addWidget(responsible_panel)
        self.tabs.addTab(resp_tab, "責任人績效分析")

        # 3. Supplier Risk Tab
        supplier_tab = QWidget()
        supplier_tab_layout = QVBoxLayout(supplier_tab)
        supplier_tab_layout.setContentsMargins(0, 4, 0, 0)

        rank_panel = QFrame()
        rank_panel.setProperty("role", "panel")
        rank_layout = QVBoxLayout(rank_panel)
        rank_layout.setContentsMargins(*RANK_PANEL_MARGINS)
        rank_layout.setSpacing(INLINE_TIGHT_SPACING)

        title_row = QHBoxLayout()
        rank_title = QLabel("供應商風險堆疊圖")
        rank_title.setProperty("role", "sectionTitle")
        title_row.addWidget(rank_title)
        title_row.addStretch(1)
        self._rank_month_label = QLabel("")
        self._rank_month_label.setProperty("role", "helperText")
        title_row.addWidget(self._rank_month_label)
        rank_layout.addLayout(title_row)

        rank_info = self._create_info_banner(
            "X 軸為異常件數，Y 軸為平均時效 (天)；虛線代表全體平均基準。",
            "定位「高頻次且處理緩慢」的高風險廠商，作為優先輔導與稽核之依據。"
        )
        rank_layout.addWidget(rank_info)

        self._chart_content_layout = QVBoxLayout()
        self._chart_content_layout.setSpacing(4)
        rank_layout.addLayout(self._chart_content_layout, 1)
        supplier_tab_layout.addWidget(rank_panel)
        self.tabs.addTab(supplier_tab, "供應商風險分析")

        root.addWidget(self.tabs, 1)
        self._update_rank_month_subtitle()

    def _create_info_banner(self, formula: str, purpose: str) -> QFrame:
        """建立統一格式的統計說明區塊。"""
        banner = QFrame()
        banner.setObjectName("statsInfoBanner")
        
        # 使用面板次要背景色與圓角
        bg_color = TOKENS["panel_alt_bg"]
        border_color = TOKENS["border"]
        text_color = TOKENS["text_muted"]
        
        banner.setStyleSheet(f"""
            QFrame#statsInfoBanner {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 6px;
            }}
            QLabel {{
                background-color: transparent;
                border: none;
                color: {text_color};
            }}
        """)
        
        layout = QVBoxLayout(banner)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(1)
        
        formula_label = QLabel(f"<b>Σ 統計公式：</b>{formula}")
        purpose_label = QLabel(f"<b>🎯 統計目的：</b>{purpose}")
        formula_label.setProperty("role", "statsInfoText")
        purpose_label.setProperty("role", "statsInfoText")
        
        layout.addWidget(formula_label)
        layout.addWidget(purpose_label)
        return banner

    def _create_insight_label(self, text: str) -> QLabel:
        """建立帶有圖標與背景的管理建議標籤。"""
        label = QLabel(text)
        label.setWordWrap(True)
        label.setProperty("role", "insight")
        
        # 使用自定義樣式
        bg_color = TOKENS["panel_alt_bg"]
        border_color = TOKENS["info"]
        text_color = TOKENS["text_primary"]
        
        label.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                border-left: 4px solid {border_color};
                padding: 6px 10px;
                color: {text_color};
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }}
        """)
        return label

    def _month_key(self) -> str:
        if hasattr(self, "all_time_toggle") and self.all_time_toggle.isChecked():
            return "ALL"
        return self.month_input.date().toString("yyyyMM")

    def _month_text(self) -> str:
        if hasattr(self, "all_time_toggle") and self.all_time_toggle.isChecked():
            return "全期累計"
        return self.month_input.date().toString("yyyy-MM")

    def _update_rank_month_subtitle(self):
        if self._rank_month_label is None:
            return
        prefix = "統計範圍：" if self.all_time_toggle.isChecked() else "月份："
        self._rank_month_label.setText(f"{prefix}{self._month_text()}")

    def _on_all_time_toggled(self, checked: bool):
        self.month_input.setEnabled(not checked)
        self._update_rank_month_subtitle()
        self.refresh_data()

    def _on_month_changed(self, _date: QDate):
        self._update_rank_month_subtitle()
        self.refresh_data()

    def refresh_data(self):
        try:
            yyyymm = self._month_key()
            summary = event_service.get_monthly_stats(yyyymm)
            
            trend_data = event_service.get_anomaly_trend(months=6)
            try:
                resp_stats = event_service.get_responsible_person_stats(yyyymm)
            except (AttributeError, Exception):
                resp_stats = []
                
            self._render_charts(
                summary.get("top_suppliers_by_anomaly", []), 
                trend_data,
                resp_stats=resp_stats
            )
        except Exception as exc:
            self._render_charts([], [], error_message=localize_exception(exc))

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

    def _clear_top_suppliers(self):
        if any(l is None for l in (self._chart_content_layout, self._trend_content_layout, self._resp_content_layout)):
            return
        for layout in (self._chart_content_layout, self._trend_content_layout, self._resp_content_layout):
            while layout.count() > 0:
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
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

    def _render_charts(self, rows: list[dict], trend_data: list[dict], *, resp_stats: list[dict] | None = None, error_message: str | None = None):
        self._clear_top_suppliers()
        if any(l is None for l in (self._chart_content_layout, self._trend_content_layout, self._resp_content_layout)):
            return
            
        if error_message:
            for layout in (self._chart_content_layout, self._trend_content_layout, self._resp_content_layout):
                lbl = QLabel(f"錯誤：{error_message}")
                lbl.setProperty("role", "errorText")
                layout.addWidget(lbl)
            return
            
        if not rows and not trend_data and not resp_stats:
            empty = EmptyStateWidget("暫無數據", "尚無相關異常統計記錄")
            self._chart_content_layout.addWidget(empty)
            return

        # 1. Supplier Risk Stacked Chart
        if rows:
            chart_view = self._build_supplier_chart(rows)
            if chart_view:
                calc_h = (len(rows) * CHART_BAR_HEIGHT) + CHART_HEADER_FOOTER_OFFSET
                chart_view.setMinimumHeight(max(CHART_MIN_HEIGHT, calc_h))
                self._chart_content_layout.addWidget(chart_view)
                
                # Add Supplier Insights
                risk_suppliers = [r for r in rows if int(r.get("overdue_open_anomaly_count") or 0) > 0]
                if risk_suppliers:
                    top_risk = risk_suppliers[0]
                    insight = self._create_insight_label(
                        f"⚠️ 供應商預警：發現 {len(risk_suppliers)} 家廠商存在逾期案件。\n"
                        f"重點關注：{top_risk['supplier_name']} 目前有 {top_risk.get('overdue_open_anomaly_count', 0)} 件逾期未結，平均時效達 {top_risk.get('avg_resolution_time', 0)} 天。"
                    )
                    self._chart_content_layout.addWidget(insight)
                else:
                    self._chart_content_layout.addWidget(self._create_insight_label("✅ 所有供應商目前均無逾期未結案件，品質與效率表現穩定。"))
        else:
            self._chart_content_layout.addWidget(EmptyStateWidget("暫無異常數據"))


        # 3. Trend Chart
        if trend_data:
            trend_view = self._build_trend_chart(trend_data)
            if trend_view:
                self._trend_content_layout.addWidget(trend_view, 1)
                
                # Add Trend Insights
                last_month = trend_data[-1] if trend_data else None
                if last_month:
                    backlog_status = "🔴 積壓上升" if len(trend_data) > 1 and last_month["backlog_count"] > trend_data[-2]["backlog_count"] else "🟢 積壓穩定"
                    rate = (last_month["closed_count"] / last_month["total_count"] * 100) if last_month["total_count"] > 0 else 0
                    rate_status = "✅ 效率良好" if rate >= 80 else "⚠️ 效率待提升"
                    
                    insight = self._create_insight_label(
                        f"目前狀態：{backlog_status} | 結案效率：{rate_status}\n"
                        f"最新月份積壓總數：{last_month['backlog_count']} 件；當月結案率：{rate:.1f}%"
                    )
                    self._trend_content_layout.addWidget(insight)
        else:
            self._trend_content_layout.addWidget(EmptyStateWidget("暫無趨勢數據"))

        # 4. Responsible Person Chart
        if resp_stats:
            resp_view = self._build_responsible_chart(resp_stats)
            if resp_view:
                self._resp_content_layout.addWidget(resp_view)
                
                # Add Responsible Insights
                if resp_stats:
                    top_person = resp_stats[0]
                    # Check for workload balance
                    total_cases = sum(r["total_count"] for r in resp_stats)
                    avg_cases = total_cases / len(resp_stats)
                    workload_status = "⚠️ 工作量過於集中" if top_person["total_count"] > avg_cases * 1.5 else "🟢 工作量分佈均勻"
                    
                    # Check for efficiency outliers
                    avg_time = sum(r["avg_resolution_time"] for r in resp_stats) / len(resp_stats)
                    efficiency_status = "🕒 存在處理時效瓶頸" if any(r["avg_resolution_time"] > avg_time * 1.5 for r in resp_stats) else "✅ 處理時效均合規"
                    
                    insight = self._create_insight_label(
                        f"團隊概況：{workload_status} | 效率評估：{efficiency_status}\n"
                        f"最高負擔人員：{top_person['responsible_person']} ({top_person['total_count']} 件)，其平均時效為 {top_person['avg_resolution_time']} 天。"
                    )
                    self._resp_content_layout.addWidget(insight)
        else:
            self._resp_content_layout.addWidget(EmptyStateWidget("暫無責任人數據"))

    def _build_supplier_chart(self, rows: list[dict]) -> QChartView | None:
        if not rows:
            return None

        # 數據準備
        data = rows[:15] # Top 15
        data.reverse()
        self._last_supplier_data = list(data) # 確保是副本
        categories = [self._short_supplier_label(r["supplier_name"], max_len=SUPPLIER_LABEL_MAX_LEN) for r in data]
        
        # 1. Stacked Bar Series
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
            # Calculate ongoing (open but not overdue)
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
        
        # 2. Chart
        chart = QChart()
        chart.addSeries(bar_series)
        chart.addSeries(line_series)
        chart.setTitle("供應商品質風險堆疊分析")
        chart.setBackgroundVisible(False)
        chart.setMargins(QMargins(10, 10, 10, 10))
        
        # 3. Axes
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
        
        # Tooltips
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
        """相容性方法，供測試與現有邏輯使用"""
        self._on_supplier_bar_hovered(status, index, self._last_supplier_data)

    def _on_chart_bar_clicked(self, index: int, bar_set: QBarSet):
        """點擊圖表跳轉至異常列表"""
        data = self._last_supplier_data
        if not data or index < 0 or index >= len(data):
            return
            
        row = data[index]
        if self.main_window:
            # 根據點擊的 BarSet 決定過濾狀態與導覽目標
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



    def _build_trend_chart(self, trend_data: list[dict]) -> QChartView | None:
        if not trend_data:
            return None
            
        categories = [d["yyyymm"] for d in trend_data]
        
        # 1. Bar Series (New & Closed)
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
        
        # 2. Line Series (Backlog)
        backlog_series = QLineSeries()
        backlog_series.setName("積壓未結 (全期)")
        backlog_series.setColor(QColor(TOKENS.get("warning", "#ffc107")))
        backlog_series.setPointsVisible(True)

        # Points for better visibility
        backlog_points = QScatterSeries()
        backlog_points.setMarkerSize(10)
        backlog_points.setColor(QColor(TOKENS.get("warning", "#ffc107")))
        backlog_points.setBorderColor(QColor("white"))

        for i, d in enumerate(trend_data):
            backlog_series.append(i, d["backlog_count"])
            backlog_points.append(i, d["backlog_count"])
            
        # 4. Axes
        app_font_family = QApplication.font().family()
        
        # 標籤樣式設定
        label_font = QFont(app_font_family, 9)
        backlog_series.setPointLabelsVisible(True)
        backlog_series.setPointLabelsFormat("@yPoint")
        backlog_series.setPointLabelsFont(label_font)
        backlog_series.setPointLabelsColor(QColor(TOKENS.get("warning", "#ffc107")))
            
        # 3. Chart
        chart = QChart()
        chart.addSeries(bar_series)
        chart.addSeries(backlog_series)
        chart.addSeries(backlog_points)
        backlog_points.setName("")
        chart.setBackgroundVisible(False)
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
        
        # Left Y Axis (Monthly Count)
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
        
        # Right Y Axis (Cumulative Backlog)
        max_backlog = max([d["backlog_count"] for d in trend_data], default=5)
        axis_y_backlog = QValueAxis()
        axis_y_backlog.setTitleText("累積積壓數")
        axis_y_backlog.setLabelFormat("%i")
        axis_y_backlog.setRange(0, max_backlog + 5)
        axis_y_backlog.setLabelsColor(QColor(TOKENS.get("warning", "#ffc107")))
        axis_y_backlog.setLabelsFont(axis_label_font)
        axis_y_backlog.setTitleFont(axis_title_font)
        axis_y_backlog.setGridLineVisible(False) # Avoid overlapping grids
        chart.addAxis(axis_y_backlog, Qt.AlignmentFlag.AlignRight)
        backlog_series.attachAxis(axis_y_backlog)
        backlog_points.attachAxis(axis_y_backlog)

        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        if TOKENS.get("chart_axis_text"):
            chart.legend().setLabelColor(QColor(TOKENS["chart_axis_text"]))
            
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        chart_view.setMinimumHeight(CHART_MIN_HEIGHT)
        
        # Tooltips
        bar_series.hovered.connect(lambda status, idx, bs: self._on_trend_bar_hovered(status, idx, trend_data))
        backlog_points.hovered.connect(lambda pt, state: self._on_trend_line_hovered(state, pt, trend_data))

        return chart_view

    def _on_trend_bar_hovered(self, status: bool, index: int, data: list[dict]):
        if not status or index < 0 or index >= len(data):
            QToolTip.hideText()
            return
            
        row = data[index]
        # Calculate monthly resolution rate
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
        
        # Find index by x coordinate (which is the index in categories)
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

    def _build_responsible_chart(self, rows: list[dict]) -> QChartView | None:
        if not rows:
            return None
            
        # Limit to top 15 to avoid clutter
        data = rows[:15]
        categories = [self._short_supplier_label(r["responsible_person"], max_len=10) for r in data]
        
        # 1. Series
        bar_set = QBarSet("總件數")
        bar_set.setColor(CHART_OPEN_COLOR)
        bar_set.setBorderColor(CHART_OPEN_COLOR.darker(110))
        
        line_series = QLineSeries()
        line_series.setName("平均處理時效 (天)")
        line_series.setColor(QColor(TOKENS["info"])) # Using info color for time metric
        line_series.setPointsVisible(True)
        
        for i, row in enumerate(data):
            bar_set.append(row["total_count"])
            line_series.append(i, row["avg_resolution_time"])
            
        app_font_family = QApplication.font().family()

        # 標籤樣式設定
        label_font = QFont(app_font_family, 9)
        line_series.setPointLabelsVisible(True)
        line_series.setPointLabelsFormat("@yPoint d")
        line_series.setPointLabelsFont(label_font)
        line_series.setPointLabelsColor(QColor(TOKENS["info"]))

        bar_series = QBarSeries()
        bar_series.append(bar_set)
        bar_series.setLabelsVisible(True)
        bar_series.setLabelsPosition(QBarSeries.LabelsPosition.LabelsOutsideEnd)
        
        # 2. Chart
        chart = QChart()
        chart.addSeries(bar_series)
        chart.addSeries(line_series)
        chart.setBackgroundVisible(False)
        chart.setMargins(QMargins(8, 8, 8, 8))
        
        # 3. Axes
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
        axis_y_rate.setLabelFormat("%.1f") # Removed " 天" to fix rendering issue (?)
        axis_y_rate.setLabelsColor(QColor(TOKENS["chart_axis_text"]))
        axis_y_rate.setLabelsFont(axis_label_font)
        axis_y_rate.setTitleFont(axis_title_font)
        chart.addAxis(axis_y_rate, Qt.AlignmentFlag.AlignRight)
        line_series.attachAxis(axis_y_rate)
        
        # 4. Styling
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        if TOKENS.get("chart_axis_text"):
            chart.legend().setLabelColor(QColor(TOKENS["chart_axis_text"]))
            
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        chart_view.setMinimumHeight(CHART_MIN_HEIGHT)
        
        # Tooltips
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

    def export_monthly_excel(self):
        month = self._month_key()
        default_name = f"SQE_Monthly_{month}_{datetime.now().strftime('%H%M%S')}.xlsx"
        target, _ = QFileDialog.getSaveFileName(
            self,
            "匯出統計",
            default_name,
            "Excel Files (*.xlsx)",
        )
        if not target:
            return
        ok, msg = event_service.export_monthly_excel(target, month)
        if ok:
            QMessageBox.information(self, "成功", localize_popup_message(msg))
        else:
            QMessageBox.critical(self, "失敗", localize_popup_message(msg))
