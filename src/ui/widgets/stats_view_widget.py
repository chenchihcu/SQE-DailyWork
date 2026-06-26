"""供應商事件統計視圖（主 Widget）。

保留：UI 建構、資料刷新、匯出、協調邏輯。
圖表建構與事件處理委託給 _StatsChartMixin。
"""

from __future__ import annotations

import logging
from datetime import datetime

import ncr.services.stats_service as ncr_stats_service
from database.connection import get_connection
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
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
    """供應商事件統計檢視主 Widget（含異常統計與倉庫不合格品統計）。"""

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
        self._summary_buttons: dict[str, QPushButton] = {}
        self._decision_summary_context: dict[str, str | None] = {}
        self._setup_ui()
        self._has_loaded = False
        if not lazy_load:
            self.refresh_data()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

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

        self.source_tag_label = QLabel("供應商事件 / 倉庫實物不合格品")
        self.source_tag_label.setProperty("role", "sourceTag")
        self.source_tag_label.setToolTip("統計頁分頁顯示供應商事件與倉庫實物不合格品，資料來源保持分離")
        month_row.addWidget(self.source_tag_label)
        month_row.addStretch(1)

        btn_export = QPushButton("匯出 Excel")
        btn_export.setProperty("variant", "primary")
        apply_clickable_affordance(btn_export, tooltip="匯出目前月份統計 Excel")
        btn_export.clicked.connect(self.export_monthly_excel)
        month_row.addWidget(btn_export)
        top_layout.addLayout(month_row)

        self.decision_summary = QFrame()
        self.decision_summary.setObjectName("StatsDecisionSummary")
        self.decision_summary.setProperty("role", "summaryStrip")
        summary_layout = QGridLayout(self.decision_summary)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(INLINE_SPACING)
        for index, key in enumerate(("risk", "overdue", "trend", "warehouse")):
            button = self._create_summary_button(key)
            self._summary_buttons[key] = button
            summary_layout.addWidget(button, index // 2, index % 2)
        summary_layout.setColumnStretch(0, 1)
        summary_layout.setColumnStretch(1, 1)
        top_layout.addWidget(self.decision_summary)

        root.addWidget(top_panel)

        # --- Tab System ---
        self.tabs = QTabWidget()
        self.tabs.setObjectName("StatsTabs")
        self.tabs.setDocumentMode(True)

        # 1. Trend Tab
        trend_tab, trend_tab_layout = self._create_scrollable_tab("StatsTrendScrollArea")

        trend_panel = QFrame()
        trend_panel.setProperty("role", "panel")
        trend_layout = QVBoxLayout(trend_panel)
        trend_layout.setContentsMargins(*RANK_PANEL_MARGINS)
        trend_layout.setSpacing(INLINE_TIGHT_SPACING)

        trend_title_row = QHBoxLayout()
        trend_title = QLabel("供應商事件趨勢分析 (過去 6 個月)")
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
        self.tabs.addTab(trend_tab, "供應商事件趨勢")

        # 2. Responsible Person Tab
        resp_tab, resp_tab_layout = self._create_scrollable_tab("StatsResponsibleScrollArea")

        responsible_panel = QFrame()
        responsible_panel.setProperty("role", "panel")
        responsible_layout = QVBoxLayout(responsible_panel)
        responsible_layout.setContentsMargins(*RANK_PANEL_MARGINS)
        responsible_layout.setSpacing(INLINE_TIGHT_SPACING)

        resp_title_row = QHBoxLayout()
        resp_title = QLabel("供應商事件責任人績效 (總件數 vs 平均處理時效)")
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
        self.tabs.addTab(resp_tab, "事件責任人績效")

        # 3. Supplier Risk Tab
        supplier_tab, supplier_tab_layout = self._create_scrollable_tab("StatsSupplierRiskScrollArea")

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

        rank_info = self._create_info_banner(
            "X 軸為異常件數，Y 軸為平均時效 (天)；虛線代表全體平均基準。",
            "定位「高頻次且處理緩慢」的高風險廠商，作為優先輔導與稽核之依據。"
        )
        rank_layout.addWidget(rank_info)

        self._chart_content_layout = QVBoxLayout()
        self._chart_content_layout.setSpacing(4)
        rank_layout.addLayout(self._chart_content_layout, 1)
        supplier_tab_layout.addWidget(rank_panel)
        self.tabs.addTab(supplier_tab, "供應商事件風險")

        # 4. Defect Analysis Tab
        defect_tab, defect_tab_layout = self._create_scrollable_tab("StatsWarehouseScrollArea")

        defect_panel = QFrame()
        defect_panel.setProperty("role", "panel")
        defect_layout = QVBoxLayout(defect_panel)
        defect_layout.setContentsMargins(*RANK_PANEL_MARGINS)
        defect_layout.setSpacing(INLINE_TIGHT_SPACING)

        defect_title_row = QHBoxLayout()
        defect_title = QLabel("倉庫不合格品實物處置分析")
        defect_title.setProperty("role", "sectionTitle")
        defect_title_row.addWidget(defect_title)
        defect_title_row.addStretch(1)
        defect_layout.addLayout(defect_title_row)

        defect_info = self._create_info_banner(
            "顯示倉庫不合格品處置比例、Top 5 產品與供應商處置關聯。",
            "協助倉庫與 SQE 監控不合格品實物流向、報廢率與高發產品，優化退料與處置流程。"
        )
        defect_layout.addWidget(defect_info)

        self._defect_content_layout = QVBoxLayout()
        self._defect_content_layout.setSpacing(4)

        self.defect_grid = QGridLayout()
        self.defect_grid.setContentsMargins(0, 0, 0, 0)
        self.defect_grid.setSpacing(16)
        self._defect_content_layout.addLayout(self.defect_grid, 1)

        defect_layout.addLayout(self._defect_content_layout, 1)
        defect_tab_layout.addWidget(defect_panel)
        self.tabs.addTab(defect_tab, "倉庫不合格品統計")

        root.addWidget(self.tabs, 1)
        self._update_rank_month_subtitle()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # ── 輔助建構方法 ──────────────────────────────────────

    def _create_scrollable_tab(self, object_name: str) -> tuple[QWidget, QVBoxLayout]:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 4, 0, 0)
        tab_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName(object_name)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        scroll.setWidget(content)

        tab_layout.addWidget(scroll, 1)
        return tab, content_layout

    def _create_summary_button(self, key: str) -> QPushButton:
        button = QPushButton("暫無資料")
        button.setObjectName(f"DecisionSummary_{key}")
        button.setProperty("role", "decisionSummary")
        button.setMinimumWidth(0)
        button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda _checked=False, action_key=key: self._on_decision_summary_clicked(action_key))
        return button

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

            self._refresh_decision_summary(summary, trend_data)
            self._render_charts(
                summary.get("top_suppliers_by_anomaly", []),
                trend_data,
                resp_stats=resp_stats
            )
            self._refresh_defect_charts()
        except Exception as exc:
            logger.exception("重新整理統計視圖失敗")
            self._refresh_decision_summary({}, [])
            self._render_charts([], [], error_message=localize_exception(exc))

    # ── 決策摘要 ──────────────────────────────────────────

    def _summary_button_available(self) -> bool:
        return self.main_window is not None

    def _set_summary_button(
        self,
        key: str,
        *,
        text: str,
        tooltip: str,
        enabled: bool,
    ) -> None:
        button = self._summary_buttons.get(key)
        if button is None:
            return
        button.setText(text)
        button.setToolTip(tooltip)
        button.setStatusTip(tooltip)
        button.setEnabled(enabled and self._summary_button_available())

    def _refresh_decision_summary(self, summary: dict, trend_data: list[dict]) -> None:
        rows = list(summary.get("top_suppliers_by_anomaly") or [])
        risk_row = next(
            (
                row
                for row in rows
                if int(row.get("overdue_open_anomaly_count") or 0) > 0
            ),
            rows[0] if rows else None,
        )
        risk_supplier = str(risk_row.get("supplier_name") or "").strip() if risk_row else ""
        risk_overdue = int(risk_row.get("overdue_open_anomaly_count") or 0) if risk_row else 0
        risk_supplier_label = self._short_supplier_label(risk_supplier, max_len=14)
        self._decision_summary_context["risk_supplier"] = risk_supplier or None
        self._set_summary_button(
            "risk",
            text=(
                f"最高風險：{risk_supplier_label} / 逾期 {risk_overdue} 件"
                if risk_supplier
                else "最高風險：暫無資料"
            ),
            tooltip=(
                f"跳到該供應商待處理異常清單：{risk_supplier}"
                if risk_supplier
                else "目前沒有供應商風險資料"
            ),
            enabled=bool(risk_supplier),
        )

        has_event_summary = bool(summary)
        overdue_count = int(summary.get("overdue_open_anomaly_count") or 0)
        open_count = int(summary.get("open_anomaly_count") or 0)
        self._set_summary_button(
            "overdue",
            text=(
                f"逾期未結：{overdue_count} 件 / 待處理 {open_count} 件"
                if has_event_summary
                else "逾期未結：暫無資料"
            ),
            tooltip="跳到待處理供應商異常清單",
            enabled=has_event_summary,
        )

        latest = trend_data[-1] if trend_data else None
        if latest:
            total_count = int(latest.get("total_count") or 0)
            closed_count = int(latest.get("closed_count") or 0)
            close_rate = (closed_count / total_count * 100) if total_count else 0.0
            latest_text = (
                f"最新月份：{latest.get('yyyymm', '-')}"
                f" / 新增 {total_count} / 結案率 {close_rate:.1f}%"
            )
        else:
            latest_text = "最新月份：暫無資料"
        self._set_summary_button(
            "trend",
            text=latest_text,
            tooltip="跳到已結案供應商事件清單",
            enabled=latest is not None,
        )

        warehouse_text = "倉庫 Top 產品：暫無資料"
        warehouse_enabled = False
        warehouse_product_name = ""
        product_rows: list[dict] = []
        try:
            with get_connection() as conn:
                warehouse_summary = ncr_stats_service.get_warehouse_nonconforming_summary(conn)
                product_rows = ncr_stats_service.get_top_products_stats_filtered(conn)
            if product_rows:
                top_product = product_rows[0]
                warehouse_product_name = str(top_product["product_name"] or "").strip() or "未命名產品"
                product_qty = int(top_product["total_qty"] or 0)
                product_label = self._short_supplier_label(warehouse_product_name, max_len=14)
                warehouse_text = f"倉庫 Top 產品：{product_label} / {product_qty} 件"
                warehouse_enabled = True
            elif warehouse_summary:
                open_count = int(warehouse_summary.get("open_count") or 0)
                warehouse_text = f"倉庫待處理：{open_count} 件"
                warehouse_enabled = True
        except Exception:
            logger.exception("讀取倉庫摘要失敗")
            warehouse_enabled = False
        self._set_summary_button(
            "warehouse",
            text=warehouse_text,
            tooltip=(
                f"跳到倉庫不合格品追蹤頁：{warehouse_product_name}"
                if product_rows
                else "跳到倉庫不合格品追蹤頁"
            ),
            enabled=warehouse_enabled,
        )

    def _on_decision_summary_clicked(self, key: str) -> None:
        if self.main_window is None:
            return
        if key == "warehouse":
            open_tracker = getattr(
                self.main_window, "open_warehouse_nonconforming_tracker", None
            )
            if callable(open_tracker):
                open_tracker()
            return

        open_filters = getattr(self.main_window, "open_event_query_with_filters", None)
        if not callable(open_filters):
            return
        month_key = self._month_key()
        if key == "risk":
            open_filters(
                event_type="ANOMALY",
                supplier_keyword=self._decision_summary_context.get("risk_supplier") or "",
                yyyymm=month_key,
                status="待處理",
                event_scope=event_service.EVENT_SCOPE_ANOMALY_ONLY,
            )
        elif key == "overdue":
            open_filters(
                event_type="ANOMALY",
                yyyymm=month_key,
                status="待處理",
                event_scope=event_service.EVENT_SCOPE_ANOMALY_ONLY,
                overdue_only=True,
            )
        elif key == "trend":
            open_filters(
                event_type="ANOMALY",
                yyyymm=month_key,
                status="已結案",
                event_scope=event_service.EVENT_SCOPE_CLOSED_ONLY,
            )

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
