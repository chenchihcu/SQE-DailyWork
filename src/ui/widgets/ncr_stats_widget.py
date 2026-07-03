from __future__ import annotations

import logging
logger = logging.getLogger(__name__)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QDialog,
)

from ui.widgets.export_range_dialog import ExportRangeDialog
import ncr.services.export_service as ncr_export_service


from database.connection import get_connection
import ncr.services.stats_service as ncr_stats_service
from ui.design_tokens import PALETTE
from ui.layout_constants import (
    PANEL_MARGINS,
    INLINE_SPACING,
    INLINE_TIGHT_SPACING,
    RANK_PANEL_MARGINS,
)
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
    render_chart_to_png,
)
from ui.widgets.ncr_stats_chart_mixin import (
    _NcrStatsChartMixin,
    _C_DANGER,
    _C_SUCCESS,
    _C_INFO,
    _C_PENDING,
    _C_NA,
)


class NcrStatsWidget(QWidget, _NcrStatsChartMixin):
    def __init__(self, main_window=None, *, lazy_load: bool = False):
        super().__init__()
        self.setObjectName("NcrStatsView")
        self.main_window = main_window
        self._setup_ui()
        self._has_loaded = False
        if not lazy_load:
            self.refresh_data()

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

        control_row = QHBoxLayout()
        control_row.setSpacing(INLINE_SPACING)
        
        period_label = create_period_label()
        self.range_selectors = create_year_month_range_selectors(
            self._on_range_changed,
            parent=self,
        )

        control_row.addWidget(period_label)
        for widget in self.range_selectors.widgets():
            control_row.addWidget(widget)

        source_tag_label = QLabel("倉庫不合格品統計")
        source_tag_label.setProperty("role", "sourceTag")
        source_tag_label.setToolTip("此統計畫面之數據來源僅限於不合格品登記紀錄")
        control_row.addWidget(source_tag_label)
        control_row.addStretch(1)

        btn_refresh = QPushButton("重新整理")
        btn_refresh.setProperty("variant", "secondary")
        btn_refresh.setMinimumWidth(100)
        apply_clickable_affordance(btn_refresh, tooltip="重新整理統計數據")
        btn_refresh.clicked.connect(self.refresh_data)
        control_row.addWidget(btn_refresh)

        self.btn_export = QPushButton("匯出 Excel")
        self.btn_export.setProperty("variant", "primary")
        self.btn_export.setMinimumWidth(118)
        apply_clickable_affordance(self.btn_export, tooltip="匯出自訂日期區間的統計 Excel 報告")
        self.btn_export.clicked.connect(self.export_ncr_excel)
        control_row.addWidget(self.btn_export)

        top_layout.addLayout(control_row)
        root.addWidget(top_panel)

        # ── 可捲動圖表顯示區 ──────────────────────────────────
        scroll, self.scroll_layout = create_stats_scroll_area(
            scroll_object_name="NcrStatsScrollArea",
            content_object_name="NcrStatsScrollContent",
            margins=(0, 0, 0, 0),
        )

        # 管理建議 / 說明橫幅
        self.info_banner = self._create_info_banner(
            "基於倉庫不良品登記主檔分析；Top5 以退料金額與件數綜合比重之總件數排序。",
            "協助 SQE 與倉管人員追蹤產線不良退料模式、聚焦不良高發廠商與產品，以及退料類型佔比。"
        )
        self.scroll_layout.addWidget(self.info_banner)

        # 2x2 網格佈局容器
        chart_panel = QFrame()
        chart_panel.setProperty("role", "panel")
        chart_layout = QVBoxLayout(chart_panel)
        chart_layout.setContentsMargins(*RANK_PANEL_MARGINS)
        chart_layout.setSpacing(INLINE_TIGHT_SPACING)

        self.grid_layout = create_stats_grid_layout(equal_rows=True)
        chart_layout.addLayout(self.grid_layout)

        self.scroll_layout.addWidget(chart_panel)
        
        # 底部建議資訊欄 (Insights)
        self.insight_label = self._create_insight_label("載入中...")
        self.scroll_layout.addWidget(self.insight_label)

        root.addWidget(scroll, 1)

    def _create_info_banner(self, formula: str, purpose: str) -> QFrame:
        return StatsInfoBanner(
            formula,
            purpose,
            formula_prefix="統計說明",
            purpose_prefix="管理目的",
            object_name="ncrStatsInfoBanner",
            margins=(12, 8, 12, 8),
            spacing=4,
        )

    def _create_insight_label(self, text: str) -> QLabel:
        return create_insight_label(text, minimum_height=40)

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
        self.refresh_data()

    def _on_range_changed(self, source: str):
        # 「碰到的控件優先」夾限：改起始使其超過迄則把迄拖到起始，反之亦然
        start_key = self.range_selectors.start_key()
        end_key = self.range_selectors.end_key()
        if start_key > end_key:
            if source == "start":
                self.range_selectors.set_range(start_key, start_key)
            else:
                self.range_selectors.set_range(end_key, end_key)
        self.refresh_data()

    def refresh_data(self):
        self._has_loaded = True
        # 清空網格
        while self.grid_layout.count() > 0:
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        start_key, end_key = self._range_keys()
        iso_start, iso_end = range_iso_dates(start_key, end_key)

        try:
            with get_connection() as conn:
                top_suppliers = ncr_stats_service.get_top_suppliers_stats_by_range(conn, iso_start, iso_end)
                top_products = ncr_stats_service.get_top_products_stats_by_range(conn, iso_start, iso_end)
                scrap_rework = ncr_stats_service.get_scrap_rework_ratio_by_range(conn, iso_start, iso_end)
                return_slips = ncr_stats_service.get_return_slip_ratio_by_range(conn, iso_start, iso_end)
        except Exception as exc:
            logger.exception("載入 NCR 統計數據失敗")
            err_lbl = QLabel(f"無法載入統計數據：{exc}")
            err_lbl.setProperty("role", "errorText")
            self.grid_layout.addWidget(err_lbl, 0, 0)
            self.insight_label.setText("載入數據時發生錯誤。")
            return

        has_data = any((top_suppliers, top_products, scrap_rework, return_slips))

        if not has_data:
            empty = EmptyStateWidget("暫無數據", f"在所選期間 ({self._range_text()}) 尚無不合格品資料")
            self.grid_layout.addWidget(empty, 0, 0, 1, 2)
            self.insight_label.setText("暫無可用數據以生成管理建議。")
            return

        # 1. Top 5 供應商 (水平條形圖)
        supplier_view = self._build_horizontal_bar_chart(
            top_suppliers, "supplier_name", "Top 5 不合格品供應商", PALETTE["info_chart"]
        )
        self.grid_layout.addWidget(supplier_view, 0, 0)

        # 2. Top 5 產品名稱 (水平條形圖)
        product_view = self._build_horizontal_bar_chart(
            top_products, "product_name", "Top 5 不合格品產品名稱", "#8B5CF6"
        )
        self.grid_layout.addWidget(product_view, 0, 1)

        # 3. 報廢/重工 比例% (環形圖)
        disposition_view = self._build_donut_chart(
            scrap_rework, "disposition", "報廢 / 重工 比例佔比",
            {"報廢": _C_DANGER, "重工": _C_SUCCESS}
        )
        self.grid_layout.addWidget(disposition_view, 1, 0)

        # 4. 退料來源比例% (環形圖)
        return_slip_view = self._build_donut_chart(
            return_slips, "return_slip_type", "退料來源比例佔比",
            {"廠內退料": _C_INFO, "託外退料": _C_PENDING, "未註明": _C_NA}
        )
        self.grid_layout.addWidget(return_slip_view, 1, 1)

        # 產生 Insights 管理建議
        self._generate_insights(top_suppliers, top_products, scrap_rework, return_slips)
        
        # 強制 Layout 重新佈局與刷新
        if self.grid_layout is not None:
            self.grid_layout.activate()
            self.grid_layout.update()
        self.update()

    def _generate_insights(
        self, top_suppliers: list, top_products: list, scrap_rework: list, return_slips: list
    ):
        """產生管理建議文字；若發生非預期例外，設定提示訊息而非保留過期文字。"""
        insights = []
        try:
            self._build_insights_text(top_suppliers, top_products, scrap_rework, return_slips, insights)
        except Exception:
            logger.exception("產生管理建議文字失敗")
            insights = ["⚠️ <b>建議產生時發生錯誤，請確認資料格式。</b>"]
        if insights:
            self.insight_label.setText("<br>".join(insights))
        else:
            self.insight_label.setText("此期間暫無足夠資料生成管理建議。")

    def _build_insights_text(
        self, top_suppliers: list, top_products: list, scrap_rework: list, return_slips: list,
        insights: list
    ) -> None:
        """在 insights 清單中填入管理建議文字（由 _generate_insights 呼叫）。"""

        
        # 1. 供應商預警
        if top_suppliers:
            top_s = top_suppliers[0]
            insights.append(
                f"⚠️ <b>供應商預警：</b>不合格品數最多的供應商為 <b>{top_s['supplier_name']}</b>，"
                f"期間不合格數量達 <b>{top_s['total_qty']}</b> 件。建議 SQE 加強對該廠品質的進料檢驗與稽核。"
            )
        else:
            insights.append("✅ <b>供應商品質：</b>此期間無明顯的高頻不合格供應商。")

        # 2. 產品分析
        if top_products:
            top_p = top_products[0]
            insights.append(
                f"📦 <b>高發不合格品：</b>品名為 <b>{top_p['product_name']}</b> 的不合格數量最高，"
                f"達 <b>{top_p['total_qty']}</b> 件。請工程與生產部門配合調查是否為製程或模具變異。"
            )

        # 3. 處置比例
        if scrap_rework:
            scrap_item = next((r for r in scrap_rework if r["disposition"] == "報廢"), None)
            rework_item = next((r for r in scrap_rework if r["disposition"] == "重工"), None)
            scrap_qty = int(scrap_item["total_qty"] or 0) if scrap_item else 0
            rework_qty = int(rework_item["total_qty"] or 0) if rework_item else 0
            total = scrap_qty + rework_qty
            
            if total > 0:
                scrap_pct = (scrap_qty / total) * 100
                if scrap_pct > 30:
                    insights.append(
                        f"🔴 <b>損失警示：</b>不合格品中<b>報廢率</b>達 <b>{scrap_pct:.1f}%</b>（報廢 {scrap_qty} 件），"
                        "報廢佔比較高，將直接增加製造成本。應優先推動品質改善以降低報廢損失。"
                    )
                else:
                    insights.append(
                        f"🟢 <b>損失防護：</b>不合格品報廢佔比較低（{scrap_pct:.1f}%），"
                        f"多數處置為重工（{rework_qty} 件），有效挽回材料價值。"
                    )

        # 4. 退料來源
        if return_slips:
            in_house = 0
            outsource = 0
            unspecified = 0
            for r in return_slips:
                qty = int(r["total_qty"] or 0)
                if r["return_slip_type"] == "廠內退料":
                    in_house += qty
                elif r["return_slip_type"] == "託外退料":
                    outsource += qty
                else:
                    unspecified += qty
            total = in_house + outsource
            total += unspecified
            if total > 0:
                in_house_pct = (in_house / total) * 100
                outsource_pct = (outsource / total) * 100
                unspecified_pct = (unspecified / total) * 100
                note = (
                    f"，未註明佔 <b>{unspecified_pct:.1f}%</b>（{unspecified} 件），"
                    "請補齊退料類型以維持來源分析完整。"
                    if unspecified
                    else "。"
                )
                insights.append(
                    f"🔄 <b>退料來源：</b>廠內退料佔 <b>{in_house_pct:.1f}%</b>，"
                    f"託外退料佔 <b>{outsource_pct:.1f}%</b>{note}"
                    f"廠內退料涉及內部製程不良，託外退料涉及外協加工品質，請按比例調度改善資源。"
                )

    def export_ncr_excel(self):
        # 1. 彈出日期區間對話框
        dialog = ExportRangeDialog("不合格品統計匯出設定", self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
            
        start_date, end_date = dialog.get_date_range()
        
        # 2. 彈出儲存路徑
        import os
        from datetime import datetime
        default_name = f"SQE_NCR_Report_{start_date.replace('-', '')}_to_{end_date.replace('-', '')}_{datetime.now().strftime('%H%M%S')}.xlsx"
        
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
            temp_dir, pid, ["supplier", "product", "disposition", "return_slip"], "temp_ncr"
        )
        cleanup_temp_files(temp_paths)  # 確保刪除先前遺留的暫存檔

        try:
            with get_connection() as conn:
                # 取得這段時間範圍的統計與明細
                top_suppliers = ncr_stats_service.get_top_suppliers_stats_by_range(conn, start_date, end_date)
                top_products = ncr_stats_service.get_top_products_stats_by_range(conn, start_date, end_date)
                scrap_rework = ncr_stats_service.get_scrap_rework_ratio_by_range(conn, start_date, end_date)
                return_slips = ncr_stats_service.get_return_slip_ratio_by_range(conn, start_date, end_date)
                defects_detail = ncr_stats_service.get_defects_detail_by_range(conn, start_date, end_date)

            has_data = len(defects_detail) > 0

            # 如果有數據，則在背景繪製圖表並 grab 儲存
            active_temp_paths = {}
            if has_data:
                # 1. Supplier chart
                if top_suppliers and render_chart_to_png(
                    lambda: self._build_horizontal_bar_chart(top_suppliers, "supplier_name", "Top 5 不合格品供應商", PALETTE["info_chart"]),
                    temp_paths["supplier"],
                ):
                    active_temp_paths["supplier"] = temp_paths["supplier"]

                # 2. Product chart
                if top_products and render_chart_to_png(
                    lambda: self._build_horizontal_bar_chart(top_products, "product_name", "Top 5 不合格品產品名稱", "#8B5CF6"),
                    temp_paths["product"],
                ):
                    active_temp_paths["product"] = temp_paths["product"]

                # 3. Scrap/Rework chart
                if scrap_rework and render_chart_to_png(
                    lambda: self._build_donut_chart(scrap_rework, "disposition", "報廢 / 重工 比例佔比", {"報廢": _C_DANGER, "重工": _C_SUCCESS}),
                    temp_paths["disposition"],
                ):
                    active_temp_paths["disposition"] = temp_paths["disposition"]

                # 4. Return slip chart
                if return_slips and render_chart_to_png(
                    lambda: self._build_donut_chart(
                        return_slips,
                        "return_slip_type",
                        "退料來源比例佔比",
                        {"廠內退料": _C_INFO, "託外退料": _C_PENDING, "未註明": _C_NA},
                    ),
                    temp_paths["return_slip"],
                ):
                    active_temp_paths["return_slip"] = temp_paths["return_slip"]

            # 呼叫匯出服務
            ok, msg = ncr_export_service.export_ncr_excel_report(
                file_path,
                start_date,
                end_date,
                defects_detail,
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

