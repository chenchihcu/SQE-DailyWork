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

from services.appearance_preferences_service import load_application_preferences
from services.event import _query_service
from ui.layout_constants import (
    INLINE_SPACING,
    INLINE_TIGHT_SPACING,
    PANEL_MARGINS,
    RANK_PANEL_MARGINS,
    STATS_EXPORT_BUTTON_MIN_WIDTH,
    STATS_REFRESH_BUTTON_MIN_WIDTH,
    STATS_SOURCE_TAG_MIN_WIDTH,
)
from ui.popup_i18n import localize_exception
from ui.widgets.common_widgets import (
    AnalyticsWorkflowShell,
    EmptyStateWidget,
    apply_clickable_affordance,
)
from ui.widgets.stats_dashboard_helpers import (
    build_temp_chart_paths,
    cleanup_temp_files,
    create_period_label,
    create_stats_grid_layout,
    create_stats_scroll_area,
    create_year_month_range_selectors,
    normalize_range_keys,
    range_display_text,
    range_iso_dates,
    render_chart_to_png,
    missing_chart_labels,
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
        self.workflow_shell = AnalyticsWorkflowShell(self)
        self.workflow_shell.hide()

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(*PANEL_MARGINS)
        top_layout.setSpacing(INLINE_SPACING)

        period_label = create_period_label()
        prefs = load_application_preferences()
        self.range_selectors = create_year_month_range_selectors(
            self._on_range_changed,
            parent=self,
            default_span_months=prefs.stats_default_span_months,
        )

        top_layout.addWidget(period_label)
        for widget in self.range_selectors.widgets():
            top_layout.addWidget(widget)

        self.source_tag_label = QLabel("供應商事件")
        self.source_tag_label.setProperty("role", "sourceTag")
        self.source_tag_label.setMinimumWidth(STATS_SOURCE_TAG_MIN_WIDTH)
        self.source_tag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.source_tag_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.source_tag_label.setToolTip("本頁僅分析權責與已結案紀錄；倉庫不合格品統計請參閱獨立不合格品模組。")
        top_layout.addWidget(self.source_tag_label)
        top_layout.addStretch(1)

        btn_refresh = QPushButton("重新整理")
        btn_refresh.setProperty("variant", "secondary")
        btn_refresh.setMinimumWidth(STATS_REFRESH_BUTTON_MIN_WIDTH)
        apply_clickable_affordance(btn_refresh, tooltip="重新整理統計數據")
        btn_refresh.clicked.connect(self.refresh_data)
        top_layout.addWidget(btn_refresh)

        btn_export = QPushButton("匯出 Excel")
        btn_export.setProperty("variant", "primary")
        btn_export.setMinimumWidth(STATS_EXPORT_BUTTON_MIN_WIDTH)
        apply_clickable_affordance(btn_export, tooltip="匯出目前篩選統計 Excel")
        btn_export.clicked.connect(self.export_monthly_excel)
        top_layout.addWidget(btn_export)

        root.addLayout(top_layout)

        # ── 可捲動圖表顯示區 ──────────────────────────────────
        scroll, scroll_layout = create_stats_scroll_area(
            scroll_object_name="StatsTrendScrollArea",
            content_object_name="StatsScrollContent",
            margins=(0, 0, 0, 0),
        )

        chart_panel = QFrame()
        chart_panel.setObjectName("StatsFourPhaseChartPanel")
        chart_panel.setProperty("role", "panel")
        chart_layout = QVBoxLayout(chart_panel)
        chart_layout.setContentsMargins(*RANK_PANEL_MARGINS)
        chart_layout.setSpacing(INLINE_TIGHT_SPACING)

        self.grid_layout = create_stats_grid_layout(equal_rows=True)
        chart_layout.addLayout(self.grid_layout)
        scroll_layout.addWidget(chart_panel, 1)

        root.addWidget(scroll, 1)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

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
            _ = _query_service.get_monthly_stats(end_key)

            iso_start, iso_end = range_iso_dates(start_key, end_key)
            # 趨勢圖窗口 = 使用者選定的完整月份區間（服務端上限 12 個月）
            trend_data = _query_service.get_anomaly_trend_by_range(iso_start, iso_end)
            visit_trend_data = _query_service.get_visit_trend_by_range(iso_start, iso_end)
            partial_failures: set[str] = set()
            try:
                resp_stats = _query_service.get_responsible_person_stats_by_range(
                    iso_start, iso_end
                )
            except Exception:
                logger.exception(
                    "get_responsible_person_stats_by_range failed for %s ~ %s",
                    iso_start, iso_end,
                )
                resp_stats = []
                partial_failures.add("responsible")
            try:
                category_pareto_data = _query_service.get_anomaly_category_pareto_by_range(
                    iso_start, iso_end
                )
            except Exception:
                logger.exception(
                    "get_anomaly_category_pareto_by_range failed for %s ~ %s",
                    iso_start,
                    iso_end,
                )
                category_pareto_data = []
                partial_failures.add("category")
            try:
                process_keyword_pareto_data = (
                    _query_service.get_anomaly_process_keyword_pareto_by_range(
                        iso_start, iso_end
                    )
                )
            except Exception:
                logger.exception(
                    "get_anomaly_process_keyword_pareto_by_range failed for %s ~ %s",
                    iso_start,
                    iso_end,
                )
                process_keyword_pareto_data = []
                partial_failures.add("process_keyword")

            self._render_charts(
                trend_data=trend_data,
                visit_trend_data=visit_trend_data,
                resp_stats=resp_stats,
                category_pareto_data=category_pareto_data,
                process_keyword_pareto_data=process_keyword_pareto_data,
                partial_failures=partial_failures,
            )
        except Exception as exc:
            logger.exception("重新整理統計視圖失敗")
            self._render_charts([], [], [], [], [], error_message=localize_exception(exc))

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

    def _render_charts(
        self,
        trend_data: list[dict],
        visit_trend_data: list[dict],
        resp_stats: list[dict],
        category_pareto_data: list[dict],
        process_keyword_pareto_data: list[dict] | None = None,
        *,
        error_message: str | None = None,
        partial_failures: set[str] | None = None,
    ):
        process_keyword_pareto_data = process_keyword_pareto_data or []
        self._clear_chart_grid()

        if error_message:
            lbl = QLabel(f"錯誤：{error_message}")
            lbl.setProperty("role", "errorText")
            self.grid_layout.addWidget(lbl, 0, 0, 2, 2)
            self.grid_layout.activate()
            self.grid_layout.update()
            self.update()
            return

        partial_failures = partial_failures or set()

        # 1. Trend Chart
        if trend_data:
            trend_view = self._build_trend_chart(trend_data)
            if trend_view:
                self.grid_layout.addWidget(trend_view, 0, 0)
            else:
                self.grid_layout.addWidget(EmptyStateWidget("暫無趨勢數據"), 0, 0)
        else:
            self.grid_layout.addWidget(EmptyStateWidget("暫無趨勢數據"), 0, 0)

        # 2. Visit Trend Chart
        if visit_trend_data:
            visit_view = self._build_visit_trend_chart(visit_trend_data)
            if visit_view:
                self.grid_layout.addWidget(visit_view, 0, 1)
            else:
                self.grid_layout.addWidget(EmptyStateWidget("暫無訪廠數據"), 0, 1)
        else:
            self.grid_layout.addWidget(EmptyStateWidget("暫無訪廠數據"), 0, 1)

        # 3. Category Pareto Chart
        if "category" in partial_failures:
            self.grid_layout.addWidget(
                EmptyStateWidget(
                    "異常類別統計暫時無法載入",
                    "請按「重新整理」重試。",
                ),
                1,
                0,
            )
        elif category_pareto_data:
            category_view = self._build_category_pareto_chart(category_pareto_data)
            if category_view:
                self.grid_layout.addWidget(category_view, 1, 0)
            else:
                self.grid_layout.addWidget(EmptyStateWidget("暫無異常類別數據"), 1, 0)
        else:
            self.grid_layout.addWidget(EmptyStateWidget("暫無異常類別數據"), 1, 0)

        # 4. Responsible Person Stacked Chart
        if "responsible" in partial_failures:
            self.grid_layout.addWidget(
                EmptyStateWidget(
                    "責任人統計暫時無法載入",
                    "請按「重新整理」重試。",
                ),
                1,
                1,
            )
        elif resp_stats:
            resp_view = self._build_responsible_stacked_chart(resp_stats)
            if resp_view:
                self.grid_layout.addWidget(resp_view, 1, 1)
            else:
                self.grid_layout.addWidget(EmptyStateWidget("暫無責任人數據"), 1, 1)
        else:
            self.grid_layout.addWidget(EmptyStateWidget("暫無責任人數據"), 1, 1)

        if "process_keyword" in partial_failures:
            self.grid_layout.addWidget(
                EmptyStateWidget(
                    "SMT 製程關鍵詞統計暫時無法載入",
                    "請按「重新整理」重試。",
                ),
                2,
                0,
                1,
                2,
            )
        elif process_keyword_pareto_data:
            keyword_view = self._build_process_keyword_pareto_chart(process_keyword_pareto_data)
            if keyword_view:
                self.grid_layout.addWidget(keyword_view, 2, 0, 1, 2)
            else:
                self.grid_layout.addWidget(
                    EmptyStateWidget("暫無 SMT 製程關鍵詞數據"),
                    2,
                    0,
                    1,
                    2,
                )
        else:
            self.grid_layout.addWidget(
                EmptyStateWidget("暫無 SMT 製程關鍵詞數據"),
                2,
                0,
                1,
                2,
            )

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
        from ui.export_helpers import get_default_export_filepath, handle_export_completion
        default_name = f"SQE_Quality_Report_{start_date.replace('-', '')}_to_{end_date.replace('-', '')}_{datetime.now().strftime('%H%M%S')}.xlsx"
        target_default = get_default_export_filepath(default_name)

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "匯出 Excel 報告",
            target_default,
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
            ["trend", "visit_anomaly", "responsible", "category_pareto", "process_keyword_pareto"],
            "temp_evt",
        )
        cleanup_temp_files(temp_paths)  # 確保刪除先前遺留的暫存檔

        try:
            # 取得這段時間範圍的數據
            trend_data = _query_service.get_anomaly_trend_by_range(start_date, end_date)
            visit_trend_data = _query_service.get_visit_trend_by_range(start_date, end_date)
            resp_stats = _query_service.get_responsible_person_stats_by_range(start_date, end_date)
            category_pareto_data = _query_service.get_anomaly_category_pareto_by_range(start_date, end_date)
            process_keyword_pareto_data = (
                _query_service.get_anomaly_process_keyword_pareto_by_range(start_date, end_date)
            )
            events_detail = _query_service.list_events_by_range(start_date, end_date)

            has_data = len(events_detail) > 0

            # 如果有數據，則在背景繪製圖表並 grab 儲存
            active_temp_paths = {}
            requested_chart_keys = []
            if has_data:
                # 1. Trend chart
                if trend_data:
                    requested_chart_keys.append("trend")
                    if render_chart_to_png(
                        lambda: self._build_trend_chart(trend_data), temp_paths["trend"]
                    ):
                        active_temp_paths["trend"] = temp_paths["trend"]

                # 2. Visit anomaly chart
                if visit_trend_data:
                    requested_chart_keys.append("visit_anomaly")
                    if render_chart_to_png(
                        lambda: self._build_visit_trend_chart(visit_trend_data), temp_paths["visit_anomaly"]
                    ):
                        active_temp_paths["visit_anomaly"] = temp_paths["visit_anomaly"]

                # 3. Responsible stacked chart
                if resp_stats:
                    requested_chart_keys.append("responsible")
                    if render_chart_to_png(
                        lambda: self._build_responsible_stacked_chart(resp_stats), temp_paths["responsible"]
                    ):
                        active_temp_paths["responsible"] = temp_paths["responsible"]

                # 4. Category Pareto chart
                if category_pareto_data:
                    requested_chart_keys.append("category_pareto")
                    if render_chart_to_png(
                        lambda: self._build_category_pareto_chart(category_pareto_data),
                        temp_paths["category_pareto"],
                    ):
                        active_temp_paths["category_pareto"] = temp_paths["category_pareto"]

                if process_keyword_pareto_data:
                    requested_chart_keys.append("process_keyword_pareto")
                    if render_chart_to_png(
                        lambda: self._build_process_keyword_pareto_chart(
                            process_keyword_pareto_data
                        ),
                        temp_paths["process_keyword_pareto"],
                    ):
                        active_temp_paths["process_keyword_pareto"] = temp_paths[
                            "process_keyword_pareto"
                        ]

            # 呼叫匯出服務
            from services.event import _export_service

            ok, msg = _export_service.export_events_report(
                file_path,
                start_date,
                end_date,
                temp_chart_paths=active_temp_paths if has_data else None
            )

            if ok:
                missing_charts = missing_chart_labels(
                    requested_chart_keys,
                    active_temp_paths,
                    {
                        "trend": "異常趨勢圖",
                        "visit_anomaly": "訪廠與異常趨勢圖",
                        "responsible": "責任人統計圖",
                        "category_pareto": "異常類別柏拉圖",
                        "process_keyword_pareto": "SMT 製程關鍵詞柏拉圖",
                    },
                )
                if missing_charts:
                    QMessageBox.warning(
                        self,
                        "完成但有警告",
                        "Excel 資料已匯出，但以下圖表未產生：\n- "
                        + "\n- ".join(missing_charts)
                        + f"\n\n{msg}",
                    )
                else:
                    handle_export_completion(file_path, f"Excel 報告匯出成功！\n{msg}", self)
            else:
                QMessageBox.critical(self, "失敗", f"Excel 報告匯出失敗：\n{msg}")

        except Exception as exc:
            logger.exception("匯出 Excel 報告出錯")
            QMessageBox.critical(self, "錯誤", f"匯出過程發生非預期錯誤：{exc}")
        finally:
            cleanup_temp_files(temp_paths)
