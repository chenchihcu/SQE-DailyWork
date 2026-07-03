"""供應商事件統計視圖（主 Widget）。

保留：UI 建構、資料刷新、匯出、協調邏輯。
圖表建構與事件處理委託給 _StatsChartMixin。
"""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import Qt
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
    create_insight_label,
    create_period_label,
    create_stats_grid_layout,
    create_stats_scroll_area,
    create_year_month_range_selectors,
    normalize_range_keys,
    range_display_text,
    range_iso_dates,
    range_month_span,
    render_chart_to_png,
    short_chart_label,
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
        self.insight_label: QLabel | None = None
        self._chart_content_layout: QVBoxLayout | None = None
        self._trend_content_layout: QVBoxLayout | None = None
        self._resp_content_layout: QVBoxLayout | None = None
        self._category_content_layout: QVBoxLayout | None = None
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
        self.range_selectors = create_year_month_range_selectors(
            self._on_range_changed,
            parent=self,
        )

        month_row.addWidget(period_label)
        for widget in self.range_selectors.widgets():
            month_row.addWidget(widget)

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
            margins=(0, 0, 0, 0),
        )

        self.info_banner = self._create_info_banner(
            "供應商事件資料來源為單獨異常、訪廠發現異常與已結案紀錄；圖表只呈現供應商事件，不包含倉庫不合格品。",
            "協助 SQE 追蹤月度趨勢、責任人負荷與高風險供應商，並將倉庫統計維持在「不合格品統計分析」頁。"
        )
        scroll_layout.addWidget(self.info_banner)

        chart_panel = QFrame()
        chart_panel.setObjectName("StatsFourPhaseChartPanel")
        chart_panel.setProperty("role", "panel")
        chart_layout = QVBoxLayout(chart_panel)
        chart_layout.setContentsMargins(*RANK_PANEL_MARGINS)
        chart_layout.setSpacing(INLINE_TIGHT_SPACING)

        self.grid_layout = create_stats_grid_layout(equal_rows=True)
        chart_layout.addLayout(self.grid_layout)
        scroll_layout.addWidget(chart_panel)

        self.insight_label = self._create_insight_label("載入中...")
        self.insight_label.setMinimumHeight(40)
        scroll_layout.addWidget(self.insight_label)

        root.addWidget(scroll, 1)

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

    def _range_keys(self) -> tuple[str, str]:
        return normalize_range_keys(
            self.range_selectors.start_key(),
            self.range_selectors.end_key(),
        )

    def _range_text(self) -> str:
        start_key, end_key = self._range_keys()
        return range_display_text(start_key, end_key)

    def set_range(self, start_key: str, end_key: str) -> None:
        """公開掛鉤（測試 / 視覺探針用）：操作真實可見下拉後刷新。"""
        self.range_selectors.set_range(start_key, end_key)
        self._update_range_labels()
        self.refresh_data()

    def _update_range_labels(self):
        # 圖表標題由 chart builder 根據實際資料區間生成；這裡保留公開掛鉤
        # 讓測試/視覺探針呼叫 set_range 時不用分支。
        return

    def _on_range_changed(self, source: str):
        # 「碰到的控件優先」夾限：改起始使其超過迄則把迄拖到起始，反之亦然
        start_key = self.range_selectors.start_key()
        end_key = self.range_selectors.end_key()
        if start_key > end_key:
            if source == "start":
                self.range_selectors.set_range(start_key, start_key)
            else:
                self.range_selectors.set_range(end_key, end_key)
        self._update_range_labels()
        self.refresh_data()

    # ── 資料刷新 ──────────────────────────────────────────

    def refresh_data(self):
        self._has_loaded = True
        try:
            start_key, end_key = self._range_keys()
            # 保留此呼叫以觸發 monthly_stats_cache 刷新（回傳值不使用），錨定迄月
            _ = event_service.get_monthly_stats(end_key)

            iso_start, iso_end = range_iso_dates(start_key, end_key)
            # 趨勢圖窗口 = 使用者選定的完整月份區間（服務端上限 12 個月）
            trend_data = event_service.get_anomaly_trend_by_range(iso_start, iso_end)
            visit_trend_data = event_service.get_visit_trend_by_range(iso_start, iso_end)
            try:
                resp_stats = event_service.get_responsible_person_stats_by_range(
                    iso_start, iso_end
                )
            except Exception:
                logger.exception(
                    "get_responsible_person_stats_by_range failed for %s ~ %s",
                    iso_start, iso_end,
                )
                resp_stats = []
            try:
                category_pareto_data = event_service.get_anomaly_category_pareto_by_range(
                    iso_start, iso_end
                )
            except Exception:
                logger.exception(
                    "get_anomaly_category_pareto_by_range failed for %s ~ %s",
                    iso_start,
                    iso_end,
                )
                category_pareto_data = []

            self._render_charts(
                trend_data=trend_data,
                visit_trend_data=visit_trend_data,
                resp_stats=resp_stats,
                category_pareto_data=category_pareto_data,
            )
        except Exception as exc:
            logger.exception("重新整理統計視圖失敗")
            self._render_charts([], [], [], [], error_message=localize_exception(exc))

    # ── 圖表協調 ──────────────────────────────────────────

    def _clear_chart_grid(self) -> None:
        while self.grid_layout.count() > 0:
            item = self.grid_layout.takeAt(0)
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

    def _set_insights(self, insights: list[str]) -> None:
        if self.insight_label is None:
            return
        self.insight_label.setText(
            "\n".join(insights) if insights else "暫無可用數據以生成管理建議。"
        )

    def _render_charts(
        self,
        trend_data: list[dict],
        visit_trend_data: list[dict],
        resp_stats: list[dict],
        category_pareto_data: list[dict],
        *,
        error_message: str | None = None,
    ):
        self._clear_chart_grid()

        if error_message:
            lbl = QLabel(f"錯誤：{error_message}")
            lbl.setProperty("role", "errorText")
            self.grid_layout.addWidget(lbl, 0, 0, 2, 2)
            self._set_insights([f"載入統計資料時發生錯誤：{error_message}"])
            return

        insights: list[str] = []

        # 1. Trend Chart
        if trend_data:
            trend_view = self._build_trend_chart(trend_data)
            if trend_view:
                self.grid_layout.addWidget(trend_view, 0, 0)

                last_month = trend_data[-1] if trend_data else None
                if last_month:
                    backlog_status = "積壓上升" if len(trend_data) > 1 and last_month["backlog_count"] > trend_data[-2]["backlog_count"] else "積壓穩定"
                    rate = (last_month["closed_count"] / last_month["total_count"] * 100) if last_month["total_count"] > 0 else 0
                    rate_status = "效率良好" if rate >= 80 else "效率待提升"
                    insights.append(
                        f"目前狀態：{backlog_status} | 結案效率：{rate_status}\n"
                        f"區間末月（{last_month['yyyymm']}）積壓總數：{last_month['backlog_count']} 件；當月結案率：{rate:.1f}%"
                    )
            else:
                self.grid_layout.addWidget(EmptyStateWidget("暫無趨勢數據"), 0, 0)
        else:
            self.grid_layout.addWidget(EmptyStateWidget("暫無趨勢數據"), 0, 0)

        # 2. Visit Trend Chart
        if visit_trend_data:
            visit_view = self._build_visit_trend_chart(visit_trend_data)
            if visit_view:
                self.grid_layout.addWidget(visit_view, 0, 1)

                last_month_visit = visit_trend_data[-1] if visit_trend_data else None
                if last_month_visit:
                    total_visits = last_month_visit["visit_count"]
                    total_anomalies = last_month_visit["visit_anomaly_count"]
                    if total_visits == 0 and total_anomalies > 0:
                        # 分母(訪廠月份)與分子(異常月份)可因事後改日期而分屬不同月;
                        # 此時「平均每場 0.0 件/正常」與圖面矛盾,改輸出事實描述。
                        insights.append(
                            f"區間末月（{last_month_visit['yyyymm']}）：無訪廠紀錄，但有 {total_anomalies} 件訪廠連結異常（請確認異常日期與訪廠日期是否同月）。"
                        )
                    else:
                        ratio = total_anomalies / total_visits if total_visits > 0 else 0
                        ratio_status = "發現異常比例偏高" if ratio >= 1.5 else "發現異常比例正常"
                        insights.append(
                            f"區間末月（{last_month_visit['yyyymm']}）：訪廠 {total_visits} 次，發現異常 {total_anomalies} 件 (平均每場 {ratio:.1f} 件)\n"
                            f"訪廠評估：{ratio_status}，請持續追蹤供應商改善進度。"
                        )
            else:
                self.grid_layout.addWidget(EmptyStateWidget("暫無訪廠數據"), 0, 1)
        else:
            self.grid_layout.addWidget(EmptyStateWidget("暫無訪廠數據"), 0, 1)

        # 3. Category Pareto Chart
        if category_pareto_data:
            category_view = self._build_category_pareto_chart(category_pareto_data)
            if category_view:
                self.grid_layout.addWidget(category_view, 1, 0)

                primary_category = category_pareto_data[0]
                top_three_total = sum(int(row.get("count", 0) or 0) for row in category_pareto_data[:3])
                total_count = sum(int(row.get("count", 0) or 0) for row in category_pareto_data)
                top_three_ratio = (top_three_total / total_count * 100) if total_count else 0.0
                insights.append(
                    f"主要異常類別：{primary_category['category']} {primary_category['count']} 件，占 {primary_category['percent']:.1f}%。\n"
                    f"前三大類別累積 {top_three_total} 件，占全部異常 {top_three_ratio:.1f}%，可優先投入改善資源。"
                )
            else:
                self.grid_layout.addWidget(EmptyStateWidget("暫無異常類別數據"), 1, 0)
        else:
            self.grid_layout.addWidget(EmptyStateWidget("暫無異常類別數據"), 1, 0)

        # 4. Responsible Person Stacked Chart
        if resp_stats:
            resp_view = self._build_responsible_stacked_chart(resp_stats)
            if resp_view:
                self.grid_layout.addWidget(resp_view, 1, 1)

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

                    insights.append(
                        f"責任人負載分析：區間內未結案共 {total_open} 件。\n"
                        f"重點關注：{most_backlogged['responsible_person']} 區間內有 {most_backlogged['open_count']} 件未結案，其最早未結案件累計自 {format_long_m(most_backlogged['min_open_date'])}。"
                    )
                else:
                    insights.append("目前所有責任人均無待處理的未結案件，品質事件結案進度良好。")
            else:
                self.grid_layout.addWidget(EmptyStateWidget("暫無責任人數據"), 1, 1)
        else:
            self.grid_layout.addWidget(EmptyStateWidget("暫無責任人數據"), 1, 1)
        
        self._set_insights(insights)

        # 強制 Layout 重新佈局與刷新
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
        temp_paths = build_temp_chart_paths(
            temp_dir,
            pid,
            ["trend", "visit_anomaly", "responsible", "category_pareto"],
            "temp_evt",
        )
        cleanup_temp_files(temp_paths)  # 確保刪除先前遺留的暫存檔

        try:
            # 取得這段時間範圍的數據
            trend_data = event_service.get_anomaly_trend_by_range(start_date, end_date)
            visit_trend_data = event_service.get_visit_trend_by_range(start_date, end_date)
            resp_stats = event_service.get_responsible_person_stats_by_range(start_date, end_date)
            category_pareto_data = event_service.get_anomaly_category_pareto_by_range(start_date, end_date)
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

                # 4. Category Pareto chart
                if category_pareto_data and render_chart_to_png(
                    lambda: self._build_category_pareto_chart(category_pareto_data),
                    temp_paths["category_pareto"],
                ):
                    active_temp_paths["category_pareto"] = temp_paths["category_pareto"]

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
