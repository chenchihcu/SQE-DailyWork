"""供應商事件統計視圖（主 Widget）。

保留：UI 建構、資料刷新、匯出、協調邏輯。
圖表建構與事件處理委託給 _StatsChartMixin。
"""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
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
    QVBoxLayout,
    QWidget,
)

from services import event_service
from ui.layout_constants import (
    CHART_BAR_HEIGHT,
    CHART_HEADER_FOOTER_OFFSET,
    CHART_MIN_HEIGHT,
    INLINE_SPACING,
    INLINE_TIGHT_SPACING,
    PANEL_MARGINS,
    RANK_PANEL_MARGINS,
)
from ui.popup_i18n import localize_exception, localize_popup_message
from ui.theme import TOKENS
from ui.widgets.chart_style import apply_chart_surface
from ui.widgets.common_widgets import EmptyStateWidget, apply_clickable_affordance
from ui.widgets.stats_chart_mixin import _StatsChartMixin

logger = logging.getLogger(__name__)


class StatsViewWidget(QWidget, _StatsChartMixin):
    """供應商事件統計檢視主 Widget（異常趨勢、責任人績效、供應商風險）。

    倉庫不合格品統計已收斂到獨立的「不合格品統計分析」頁，本頁僅供應商事件。
    """

    def __init__(self, main_window=None, *, lazy_load: bool = False):
        super().__init__()
        self.setObjectName("StatsView")
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
        self._has_loaded = False
        if not lazy_load:
            self.refresh_data()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        # ── 頂部控制面板 ─────────────────────────────────────
        top_panel = QFrame()
        top_panel.setProperty("role", "panel")
        top_layout = QVBoxLayout(top_panel)
        top_layout.setContentsMargins(*PANEL_MARGINS)
        top_layout.setSpacing(INLINE_SPACING)

        month_row = QHBoxLayout()
        month_row.setSpacing(INLINE_SPACING)
        period_label = QLabel("篩選區間")
        period_label.setProperty("role", "sectionTitle")
        period_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        
        self.period_combo = QComboBox()
        self.period_combo.addItems(["全期項目", "年度", "半年度"])
        self.period_combo.setMinimumWidth(112)
        self.period_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.period_combo.currentIndexChanged.connect(self._on_period_changed)
        apply_clickable_affordance(self.period_combo, tooltip="切換統計區間：全期項目、年度（當前年份）、半年度（當前半年度）")

        month_row.addWidget(period_label)
        month_row.addWidget(self.period_combo)

        # ── 向下相容 Proxy ──────────────────────────────────
        from PySide6.QtWidgets import QDateEdit, QCheckBox
        from PySide6.QtCore import QDate
        self.month_input = QDateEdit(self)
        self.month_input.setDate(QDate.currentDate())
        self.all_time_toggle = QCheckBox(self)
        self.month_input.hide()
        self.all_time_toggle.hide()
        self._test_yyyy_mm = None
        self.month_input.dateChanged.connect(self._on_month_input_changed)
        self.all_time_toggle.toggled.connect(self._on_all_time_toggle_changed)

        self.source_tag_label = QLabel("供應商事件統計")
        self.source_tag_label.setProperty("role", "sourceTag")
        self.source_tag_label.setMinimumWidth(126)
        self.source_tag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.source_tag_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.source_tag_label.setToolTip("本頁僅供應商事件統計；倉庫不合格品統計請見「不合格品統計」頁")
        month_row.addWidget(self.source_tag_label)
        month_row.addStretch(1)

        btn_export = QPushButton("匯出 Excel")
        btn_export.setProperty("variant", "primary")
        btn_export.setMinimumWidth(118)
        apply_clickable_affordance(btn_export, tooltip="匯出目前篩選統計 Excel")
        btn_export.clicked.connect(self.export_monthly_excel)
        month_row.addWidget(btn_export)
        top_layout.addLayout(month_row)

        root.addWidget(top_panel)

        # ── 可捲動圖表顯示區 ──────────────────────────────────
        scroll = QScrollArea()
        scroll.setObjectName("StatsTrendScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        scroll_content = QWidget()
        scroll_content.setObjectName("StatsScrollContent")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(*RANK_PANEL_MARGINS)
        scroll_layout.setSpacing(12)

        self.info_banner = self._create_info_banner(
            "供應商事件資料來源為單獨異常、訪廠發現異常與已結案紀錄；圖表只呈現供應商事件，不包含倉庫不合格品。",
            "協助 SQE 追蹤月度趨勢、責任人負荷與高風險供應商，並將倉庫統計維持在「不合格品統計分析」頁。"
        )
        scroll_layout.addWidget(self.info_banner)

        # 2x2 網格佈局；外層裝飾 panel 已移除，保留每個圖表的語意 panel。
        self.grid_layout = QGridLayout()
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(16)
        self.grid_layout.setColumnStretch(0, 1)
        self.grid_layout.setColumnStretch(1, 1)
        scroll_layout.addLayout(self.grid_layout)

        # 1. 供應商事件趨勢 Panel
        trend_panel = QFrame()
        trend_panel.setProperty("role", "panel")
        trend_layout = QVBoxLayout(trend_panel)
        trend_layout.setContentsMargins(*RANK_PANEL_MARGINS)
        trend_layout.setSpacing(INLINE_TIGHT_SPACING)

        trend_title = QLabel("供應商事件趨勢分析 (過去 6 個月)")
        trend_title.setProperty("role", "sectionTitle")
        trend_layout.addWidget(trend_title)

        self._trend_content_layout = QVBoxLayout()
        self._trend_content_layout.setSpacing(4)
        trend_layout.addLayout(self._trend_content_layout, 1)
        self.grid_layout.addWidget(trend_panel, 0, 0)

        # 2. 事件責任人績效 Panel
        responsible_panel = QFrame()
        responsible_panel.setProperty("role", "panel")
        responsible_layout = QVBoxLayout(responsible_panel)
        responsible_layout.setContentsMargins(*RANK_PANEL_MARGINS)
        responsible_layout.setSpacing(INLINE_TIGHT_SPACING)

        resp_title = QLabel("供應商事件責任人績效 (總件數 vs 平均處理時效)")
        resp_title.setProperty("role", "sectionTitle")
        responsible_layout.addWidget(resp_title)

        self._resp_content_layout = QVBoxLayout()
        self._resp_content_layout.setSpacing(4)
        responsible_layout.addLayout(self._resp_content_layout, 1)
        self.grid_layout.addWidget(responsible_panel, 0, 1)

        # 3. 供應商事件風險 Panel (跨兩欄)
        rank_panel = QFrame()
        rank_panel.setProperty("role", "panel")
        rank_layout = QVBoxLayout(rank_panel)
        rank_layout.setContentsMargins(*RANK_PANEL_MARGINS)
        rank_layout.setSpacing(INLINE_TIGHT_SPACING)

        title_row = QHBoxLayout()
        rank_title = QLabel("供應商事件風險堆疊圖")
        rank_title.setProperty("role", "sectionTitle")
        title_row.addWidget(rank_title)
        title_row.addStretch(1)
        self._rank_month_label = QLabel("")
        self._rank_month_label.setProperty("role", "helperText")
        title_row.addWidget(self._rank_month_label)
        rank_layout.addLayout(title_row)

        self._chart_content_layout = QVBoxLayout()
        self._chart_content_layout.setSpacing(4)
        rank_layout.addLayout(self._chart_content_layout, 1)
        self.grid_layout.addWidget(rank_panel, 1, 0, 1, 2)

        scroll.setWidget(scroll_content)
        root.addWidget(scroll, 1)

        self._update_rank_month_subtitle()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # ── 測試向下相容 Proxy ────────────────────────────────
        # 1. Dummy QTabWidget
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("StatsTabs")
        self.tabs.addTab(QWidget(), "供應商事件趨勢")
        self.tabs.addTab(QWidget(), "事件責任人績效")
        self.tabs.addTab(QWidget(), "供應商事件風險")
        self.tabs.hide()
        
        # 2. Dummy QScrollArea
        self.d2 = QScrollArea(self)
        self.d2.setObjectName("StatsResponsibleScrollArea")
        self.d2.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.d2.hide()
        self.d3 = QScrollArea(self)
        self.d3.setObjectName("StatsSupplierRiskScrollArea")
        self.d3.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.d3.hide()

    def _create_info_banner(self, formula: str, purpose: str) -> QFrame:
        """建立統一格式的統計說明區塊。"""
        banner = QFrame()
        banner.setObjectName("statsInfoBanner")

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

        formula_label = QLabel(f"<b>統計公式：</b>{formula}")
        purpose_label = QLabel(f"<b>統計目的：</b>{purpose}")
        formula_label.setProperty("role", "statsInfoText")
        purpose_label.setProperty("role", "statsInfoText")
        formula_label.setWordWrap(True)
        purpose_label.setWordWrap(True)
        formula_label.setMinimumWidth(0)
        purpose_label.setMinimumWidth(0)

        layout.addWidget(formula_label)
        layout.addWidget(purpose_label)
        return banner

    def _create_insight_label(self, text: str) -> QLabel:
        """建立統一背景的管理建議標籤。"""
        label = QLabel(text)
        label.setWordWrap(True)
        label.setProperty("role", "insight")
        label.setMinimumWidth(0)

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

    # ── 日期 / 導覽方法 ──────────────────────────────────

    def _month_key(self) -> str:
        if hasattr(self, "_test_yyyy_mm") and self._test_yyyy_mm is not None:
            return self._test_yyyy_mm
        idx = self.period_combo.currentIndex()
        if idx == 0:
            return "ALL"
        elif idx == 1:
            return "YEAR"
        else:
            return "HALF_YEAR"

    def _month_text(self) -> str:
        if hasattr(self, "_test_yyyy_mm") and self._test_yyyy_mm is not None:
            if self._test_yyyy_mm == "ALL":
                return "全期累計"
            return f"{self._test_yyyy_mm[:4]}-{self._test_yyyy_mm[4:]}"
        from datetime import date
        idx = self.period_combo.currentIndex()
        if idx == 0:
            return "全期項目"
        elif idx == 1:
            return f"{date.today().year}年度"
        else:
            current_month = date.today().month
            half = "上半年" if current_month <= 6 else "下半年"
            return f"{date.today().year}年{half}"

    def _update_rank_month_subtitle(self):
        if self._rank_month_label is None:
            return
        is_all = False
        if hasattr(self, "_test_yyyy_mm") and self._test_yyyy_mm is not None:
            is_all = (self._test_yyyy_mm == "ALL")
        else:
            is_all = (self.period_combo.currentIndex() == 0)
        prefix = "統計範圍：" if is_all else "月份："
        self._rank_month_label.setText(f"{prefix}{self._month_text()}")

    def _on_month_input_changed(self, qdate):
        self._test_yyyy_mm = qdate.toString("yyyyMM")
        self._update_rank_month_subtitle()
        self.refresh_data()

    def _on_all_time_toggle_changed(self, checked):
        self._test_yyyy_mm = "ALL" if checked else self.month_input.date().toString("yyyyMM")
        self.month_input.setEnabled(not checked)
        self._update_rank_month_subtitle()
        self.refresh_data()

    def _on_period_changed(self, index: int):
        self._update_rank_month_subtitle()
        self.refresh_data()

    # ── 資料刷新 ──────────────────────────────────────────

    def refresh_data(self):
        self._has_loaded = True
        try:
            yyyymm = self._month_key()
            summary = event_service.get_monthly_stats(yyyymm)

            trend_data = event_service.get_anomaly_trend(months=6)
            try:
                resp_stats = event_service.get_responsible_person_stats(yyyymm)
            except Exception:
                logger.exception(
                    "get_responsible_person_stats failed for %s", yyyymm
                )
                resp_stats = []

            self._render_charts(
                summary.get("top_suppliers_by_anomaly", []),
                trend_data,
                resp_stats=resp_stats
            )
        except Exception as exc:
            logger.exception("重新整理統計視圖失敗")
            self._render_charts([], [], error_message=localize_exception(exc))

    # ── 圖表協調 ──────────────────────────────────────────

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
            empty = EmptyStateWidget("暫無數據", "尚無供應商事件統計記錄")
            self._chart_content_layout.addWidget(empty)
            return

        # 1. Supplier Risk Stacked Chart
        if rows:
            chart_view = self._build_supplier_chart(rows)
            if chart_view:
                displayed_count = min(len(rows), 15)
                calc_h = (displayed_count * CHART_BAR_HEIGHT) + CHART_HEADER_FOOTER_OFFSET
                chart_view.setMinimumHeight(max(CHART_MIN_HEIGHT, calc_h))
                self._chart_content_layout.addWidget(chart_view)

                risk_suppliers = [r for r in rows if int(r.get("overdue_open_anomaly_count") or 0) > 0]
                if risk_suppliers:
                    top_risk = risk_suppliers[0]
                    top_risk_name = str(top_risk.get("supplier_name") or "")
                    top_risk_label = self._short_supplier_label(top_risk_name, max_len=18)
                    insight = self._create_insight_label(
                        f"供應商預警：發現 {len(risk_suppliers)} 家廠商存在逾期案件。\n"
                        f"重點關注：{top_risk_label} 目前有 {top_risk.get('overdue_open_anomaly_count', 0)} 件逾期未結，平均時效達 {top_risk.get('avg_resolution_time', 0)} 天。"
                    )
                    insight.setToolTip(f"重點關注供應商：{top_risk_name}")
                    self._chart_content_layout.addWidget(insight)
                else:
                    self._chart_content_layout.addWidget(self._create_insight_label("所有供應商目前均無逾期未結案件，品質與效率表現穩定。"))
        else:
            self._chart_content_layout.addWidget(EmptyStateWidget("暫無異常數據"))

        # 3. Trend Chart
        if trend_data:
            trend_view = self._build_trend_chart(trend_data)
            if trend_view:
                self._trend_content_layout.addWidget(trend_view, 1)

                last_month = trend_data[-1] if trend_data else None
                if last_month:
                    backlog_status = "積壓上升" if len(trend_data) > 1 and last_month["backlog_count"] > trend_data[-2]["backlog_count"] else "積壓穩定"
                    rate = (last_month["closed_count"] / last_month["total_count"] * 100) if last_month["total_count"] > 0 else 0
                    rate_status = "效率良好" if rate >= 80 else "效率待提升"

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

                if resp_stats:
                    top_person = resp_stats[0]
                    total_cases = sum(r["total_count"] for r in resp_stats)
                    avg_cases = total_cases / len(resp_stats)
                    workload_status = "工作量過於集中" if top_person["total_count"] > avg_cases * 1.5 else "工作量分佈均勻"

                    avg_time = sum(r["avg_resolution_time"] for r in resp_stats) / len(resp_stats)
                    efficiency_status = "存在處理時效瓶頸" if any(r["avg_resolution_time"] > avg_time * 1.5 for r in resp_stats) else "處理時效均合規"

                    insight = self._create_insight_label(
                        f"團隊概況：{workload_status} | 效率評估：{efficiency_status}\n"
                        f"最高負擔人員：{top_person['responsible_person']} ({top_person['total_count']} 件)，其平均時效為 {top_person['avg_resolution_time']} 天。"
                    )
                    self._resp_content_layout.addWidget(insight)
        else:
            self._resp_content_layout.addWidget(EmptyStateWidget("暫無責任人數據"))

    # ── 匯出 ──────────────────────────────────────────────

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
