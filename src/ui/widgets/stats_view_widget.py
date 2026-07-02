"""供應商事件統計視圖（主 Widget）。

保留：UI 建構、資料刷新、匯出、協調邏輯。
圖表建構與事件處理委託給 _StatsChartMixin。
"""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import Qt, QDate
from PySide6.QtCharts import QChart, QChartView, QHorizontalStackedBarSeries
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QDialog,
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
from ui.widgets.common_widgets import EmptyStateWidget, apply_clickable_affordance
from ui.widgets.stats_dashboard_helpers import (
    StatsInfoBanner,
    build_temp_chart_paths,
    cleanup_temp_files,
    create_hidden_month_controls,
    create_insight_label,
    create_period_label,
    create_stats_grid_layout,
    create_stats_scroll_area,
    period_month_key,
    period_month_text,
    render_chart_to_png,
    short_chart_label,
    create_year_month_selectors,
)
from ui.widgets.stats_chart_mixin import _StatsChartMixin
from ui.widgets.export_range_dialog import ExportRangeDialog

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
        period_label = create_period_label()
        self.year_combo, self.year_suffix, self.month_combo, self.month_suffix = create_year_month_selectors(
            self._on_selector_changed,
            parent=self
        )

        month_row.addWidget(period_label)
        month_row.addWidget(self.year_combo)
        month_row.addWidget(self.year_suffix)
        month_row.addWidget(self.month_combo)
        month_row.addWidget(self.month_suffix)

        # ── 向下相容 Proxy ──────────────────────────────────
        self.month_input, self.all_time_toggle = create_hidden_month_controls(
            self,
            self._on_month_input_changed,
            self._on_all_time_toggle_changed,
        )
        self._test_yyyy_mm = None

        self.source_tag_label = QLabel("供應商事件統計")
        self.source_tag_label.setProperty("role", "sourceTag")
        self.source_tag_label.setMinimumWidth(126)
        self.source_tag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.source_tag_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.source_tag_label.setToolTip("本頁僅供應商事件統計；倉庫不合格品統計請見「不合格品統計」頁")
        month_row.addWidget(self.source_tag_label)
        month_row.addStretch(1)

        btn_refresh = QPushButton("重新整理")
        btn_refresh.setProperty("variant", "secondary")
        btn_refresh.setMinimumWidth(100)
        apply_clickable_affordance(btn_refresh, tooltip="重新整理統計數據")
        btn_refresh.clicked.connect(self.refresh_data)
        month_row.addWidget(btn_refresh)

        btn_export = QPushButton("匯出 Excel")
        btn_export.setProperty("variant", "primary")
        btn_export.setMinimumWidth(118)
        apply_clickable_affordance(btn_export, tooltip="匯出目前篩選統計 Excel")
        btn_export.clicked.connect(self.export_monthly_excel)
        month_row.addWidget(btn_export)
        top_layout.addLayout(month_row)

        root.addWidget(top_panel)

        # ── 可捲動圖表顯示區 ──────────────────────────────────
        scroll, scroll_layout = create_stats_scroll_area(
            scroll_object_name="StatsTrendScrollArea",
            content_object_name="StatsScrollContent",
            margins=RANK_PANEL_MARGINS,
        )

        self.info_banner = self._create_info_banner(
            "供應商事件資料來源為單獨異常、訪廠發現異常與已結案紀錄；圖表只呈現供應商事件，不包含倉庫不合格品。",
            "協助 SQE 追蹤月度趨勢、責任人負荷與高風險供應商，並將倉庫統計維持在「不合格品統計分析」頁。"
        )
        scroll_layout.addWidget(self.info_banner)

        # 2x2 網格佈局；外層裝飾 panel 已移除，保留每個圖表的語意 panel。
        self.grid_layout = create_stats_grid_layout()
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

        resp_title = QLabel("供應商訪廠與訪廠異常趨勢分析 (過去 6 個月)")
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
        rank_title = QLabel("責任人事件統計 (已結案 vs 未結案)")
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

        # 加上 stretch 吸收剩餘垂直空間，防止圖表長寬比在拉大時嚴重變形
        scroll_layout.addStretch(1)

        root.addWidget(scroll, 1)

        self._update_rank_month_subtitle()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _create_info_banner(self, formula: str, purpose: str) -> QFrame:
        """建立統一格式的統計說明區塊。"""
        return StatsInfoBanner(
            formula,
            purpose,
            formula_prefix="統計公式",
            purpose_prefix="統計目的",
            object_name="statsInfoBanner",
            margins=(8, 4, 8, 4),
            spacing=1,
        )

    def _create_insight_label(self, text: str) -> QLabel:
        """建立統一背景的管理建議標籤。"""
        return create_insight_label(text)

    # ── 日期 / 導覽方法 ──────────────────────────────────

    def _month_key(self) -> str:
        if getattr(self, "_test_yyyy_mm", None) is not None:
            return self._test_yyyy_mm
        year = self.year_combo.currentText()
        month = self.month_combo.currentText()
        return f"{year}{month}"

    def _month_text(self) -> str:
        if getattr(self, "_test_yyyy_mm", None) is not None:
            if self._test_yyyy_mm == "ALL":
                return "全期累計"
            return f"{self._test_yyyy_mm[:4]}-{self._test_yyyy_mm[4:]}"
        year = self.year_combo.currentText()
        month = self.month_combo.currentText()
        return f"{year}-{month}"

    def _update_rank_month_subtitle(self):
        if self._rank_month_label is None:
            return
        is_all = (getattr(self, "_test_yyyy_mm", None) == "ALL")
        prefix = "統計範圍：" if is_all else "月份："
        self._rank_month_label.setText(f"{prefix}{self._month_text()}")

    def _on_month_input_changed(self, qdate):
        self._test_yyyy_mm = qdate.toString("yyyyMM")
        year_str = qdate.toString("yyyy")
        month_str = qdate.toString("MM")
        self.year_combo.blockSignals(True)
        self.month_combo.blockSignals(True)
        self.year_combo.setCurrentText(year_str)
        self.month_combo.setCurrentText(month_str)
        self.year_combo.blockSignals(False)
        self.month_combo.blockSignals(False)
        self._update_rank_month_subtitle()
        self.refresh_data()

    def _on_all_time_toggle_changed(self, checked):
        self._test_yyyy_mm = "ALL" if checked else f"{self.year_combo.currentText()}{self.month_combo.currentText()}"
        self.month_input.setEnabled(not checked)
        self.year_combo.setEnabled(not checked)
        self.month_combo.setEnabled(not checked)
        self._update_rank_month_subtitle()
        self.refresh_data()

    def _on_selector_changed(self):
        year = self.year_combo.currentText()
        month = self.month_combo.currentText()
        qdate = QDate(int(year), int(month), 1)
        self.month_input.blockSignals(True)
        self.month_input.setDate(qdate)
        self.month_input.blockSignals(False)
        self._test_yyyy_mm = f"{year}{month}"
        self._update_rank_month_subtitle()
        self.refresh_data()

    # ── 資料刷新 ──────────────────────────────────────────

    def refresh_data(self):
        self._has_loaded = True
        try:
            yyyymm = self._month_key()
            # 保持此呼叫以觸發 monthly_stats_cache 刷新與向下相容 side-effects
            _ = event_service.get_monthly_stats(yyyymm)

            trend_data = event_service.get_anomaly_trend(months=6)
            visit_trend_data = event_service.get_visit_trend(months=6)
            try:
                resp_stats = event_service.get_responsible_person_stats(yyyymm)
            except Exception:
                logger.exception(
                    "get_responsible_person_stats failed for %s", yyyymm
                )
                resp_stats = []

            self._render_charts(
                trend_data=trend_data,
                visit_trend_data=visit_trend_data,
                resp_stats=resp_stats
            )
        except Exception as exc:
            logger.exception("重新整理統計視圖失敗")
            self._render_charts([], [], [], error_message=localize_exception(exc))

    # ── 圖表協調 ──────────────────────────────────────────

    def _render_charts(self, trend_data: list[dict], visit_trend_data: list[dict], resp_stats: list[dict], *, error_message: str | None = None):
        self._clear_top_suppliers()
        if any(l is None for l in (self._chart_content_layout, self._trend_content_layout, self._resp_content_layout)):
            return

        if error_message:
            for layout in (self._chart_content_layout, self._trend_content_layout, self._resp_content_layout):
                lbl = QLabel(f"錯誤：{error_message}")
                lbl.setProperty("role", "errorText")
                layout.addWidget(lbl)
            return

        if not trend_data and not visit_trend_data and not resp_stats:
            empty = EmptyStateWidget("暫無數據", "尚無供應商事件統計記錄")
            self._chart_content_layout.addWidget(empty)
            return

        # 1. Trend Chart
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

        # 2. Visit Trend Chart
        if visit_trend_data:
            visit_view = self._build_visit_trend_chart(visit_trend_data)
            if visit_view:
                self._resp_content_layout.addWidget(visit_view, 1)

                last_month_visit = visit_trend_data[-1] if visit_trend_data else None
                if last_month_visit:
                    total_visits = last_month_visit["visit_count"]
                    total_anomalies = last_month_visit["visit_anomaly_count"]
                    ratio = total_anomalies / total_visits if total_visits > 0 else 0
                    ratio_status = "發現異常比例偏高" if ratio >= 1.5 else "發現異常比例正常"
                    insight = self._create_insight_label(
                        f"最新月份：訪廠 {total_visits} 次，發現異常 {total_anomalies} 件 (平均每場 {ratio:.1f} 件)\n"
                        f"訪廠評估：{ratio_status}，請持續追蹤供應商改善進度。"
                    )
                    self._resp_content_layout.addWidget(insight)
        else:
            self._resp_content_layout.addWidget(EmptyStateWidget("暫無訪廠數據"))

        # 3. Responsible Person Stacked Chart
        if resp_stats:
            resp_view = self._build_responsible_stacked_chart(resp_stats)
            if resp_view:
                self._chart_content_layout.addWidget(resp_view)

                open_cases_stats = [r for r in resp_stats if r.get("open_count", 0) > 0]
                if open_cases_stats:
                    most_backlogged = max(open_cases_stats, key=lambda x: x["open_count"])
                    total_open = sum(r["open_count"] for r in resp_stats)
                    
                    def format_long_m(d):
                        if not d:
                            return "無"
                        digits = d.replace("-", "")
                        if len(digits) >= 6 and digits[:6].isdigit():
                            return f"{digits[:4]}/{digits[4:6]}"
                        return str(d)
                        
                    insight = self._create_insight_label(
                        f"責任人負載分析：目前全期未結案共 {total_open} 件。\n"
                        f"重點關注：{most_backlogged['responsible_person']} 目前有 {most_backlogged['open_count']} 件未結案，其最早未結案件累計自 {format_long_m(most_backlogged['min_open_date'])}。"
                    )
                    self._chart_content_layout.addWidget(insight)
                else:
                    self._chart_content_layout.addWidget(self._create_insight_label("目前所有責任人均無待處理的未結案件，品質事件結案進度良好。"))
        else:
            self._chart_content_layout.addWidget(EmptyStateWidget("暫無責任人數據"))
        
        # 強制 Layout 重新佈局與刷新
        for layout in (self._chart_content_layout, self._trend_content_layout, self._resp_content_layout):
            if layout is not None:
                layout.activate()
                layout.update()
        if self.grid_layout is not None:
            self.grid_layout.activate()
            self.grid_layout.update()
        self.update()

    # ── 匯出 ──────────────────────────────────────────────

    def export_monthly_excel(self):
        # 1. 彈出日期區間對話框
        dialog = ExportRangeDialog("品質異常統計匯出設定", self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
            
        start_date, end_date = dialog.get_date_range()
        
        # 2. 彈出儲存路徑
        import os
        from datetime import datetime
        default_name = f"SQE_Quality_Report_{start_date.replace('-', '')}_to_{end_date.replace('-', '')}_{datetime.now().strftime('%H%M%S')}.xlsx"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "匯出 Excel 報告",
            default_name,
            "Excel Files (*.xlsx)",
        )
        if not file_path:
            return
            
        # 3. 處理與匯出
        temp_dir = os.path.dirname(file_path)
        pid = os.getpid()
        temp_paths = build_temp_chart_paths(temp_dir, pid, ["trend", "visit_anomaly", "responsible"], "temp_evt")
        cleanup_temp_files(temp_paths)  # 確保刪除先前遺留的暫存檔

        try:
            # 取得這段時間範圍的數據
            trend_data = event_service.get_anomaly_trend_by_range(start_date, end_date)
            visit_trend_data = event_service.get_visit_trend_by_range(start_date, end_date)
            resp_stats = event_service.get_responsible_person_stats_by_range(start_date, end_date)
            events_detail = event_service.list_events_by_range(start_date, end_date)

            has_data = len(events_detail) > 0

            # 如果有數據，則在背景繪製圖表並 grab 儲存
            active_temp_paths = {}
            if has_data:
                # 1. Trend chart
                if trend_data and render_chart_to_png(
                    lambda: self._build_trend_chart(trend_data), temp_paths["trend"]
                ):
                    active_temp_paths["trend"] = temp_paths["trend"]

                # 2. Visit anomaly chart
                if visit_trend_data and render_chart_to_png(
                    lambda: self._build_visit_trend_chart(visit_trend_data), temp_paths["visit_anomaly"]
                ):
                    active_temp_paths["visit_anomaly"] = temp_paths["visit_anomaly"]

                # 3. Responsible stacked chart
                if resp_stats and render_chart_to_png(
                    lambda: self._build_responsible_stacked_chart(resp_stats), temp_paths["responsible"]
                ):
                    active_temp_paths["responsible"] = temp_paths["responsible"]

            # 呼叫匯出服務
            ok, msg = event_service.export_events_report(
                file_path,
                start_date,
                end_date,
                temp_chart_paths=active_temp_paths if has_data else None
            )

            if ok:
                QMessageBox.information(self, "成功", f"Excel 報告匯出成功！\n{msg}")
            else:
                QMessageBox.critical(self, "失敗", f"Excel 報告匯出失敗：\n{msg}")

        except Exception as exc:
            logger.exception("匯出 Excel 報告出錯")
            QMessageBox.critical(self, "錯誤", f"匯出過程發生非預期錯誤：{exc}")
        finally:
            cleanup_temp_files(temp_paths)
