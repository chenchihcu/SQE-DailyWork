from __future__ import annotations

import logging
from PySide6.QtCore import QDate, Qt

logger = logging.getLogger(__name__)
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from database.connection import get_connection
import ncr.services.stats_service as ncr_stats_service
from ui.design_tokens import PALETTE
from ui.layout_constants import (
    PANEL_MARGINS,
    INLINE_SPACING,
    INLINE_TIGHT_SPACING,
    RANK_PANEL_MARGINS,
)
from ui.theme import TOKENS
from ui.widgets.common_widgets import EmptyStateWidget, apply_clickable_affordance
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
        
        month_label = QLabel("月份")
        month_label.setProperty("role", "sectionTitle")
        
        self.month_input = QDateEdit()
        self.month_input.setDisplayFormat("yyyy-MM")
        self.month_input.setDate(QDate.currentDate())
        self.month_input.setCalendarPopup(True)
        self.month_input.dateChanged.connect(self._on_filter_changed)

        self.all_time_toggle = QCheckBox("全期資料")
        apply_clickable_affordance(self.all_time_toggle, tooltip="切換顯示全期累計或指定月份")
        self.all_time_toggle.toggled.connect(self._on_all_time_toggled)

        control_row.addWidget(month_label)
        control_row.addWidget(self.month_input)
        control_row.addWidget(self.all_time_toggle)

        source_tag_label = QLabel("倉庫不合格品統計")
        source_tag_label.setProperty("role", "sourceTag")
        source_tag_label.setToolTip("此統計畫面之數據來源僅限於不合格品登記紀錄")
        control_row.addWidget(source_tag_label)
        control_row.addStretch(1)

        top_layout.addLayout(control_row)
        root.addWidget(top_panel)

        # ── 可捲動圖表顯示區 ──────────────────────────────────
        scroll = QScrollArea()
        scroll.setObjectName("NcrStatsScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        scroll_content = QWidget()
        scroll_content.setObjectName("NcrStatsScrollContent")
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(12)

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

        self.grid_layout = QGridLayout()
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(16)
        # 強制兩欄等寬、兩列等高，確保 2x2 網格正確分佈
        self.grid_layout.setColumnStretch(0, 1)
        self.grid_layout.setColumnStretch(1, 1)
        self.grid_layout.setRowStretch(0, 1)
        self.grid_layout.setRowStretch(1, 1)
        chart_layout.addLayout(self.grid_layout)

        self.scroll_layout.addWidget(chart_panel)
        
        # 底部建議資訊欄 (Insights)
        self.insight_label = self._create_insight_label("載入中...")
        self.scroll_layout.addWidget(self.insight_label)

        scroll.setWidget(scroll_content)
        root.addWidget(scroll, 1)

    def _create_info_banner(self, formula: str, purpose: str) -> QFrame:
        banner = QFrame()
        banner.setObjectName("ncrStatsInfoBanner")
        bg_color = TOKENS["panel_alt_bg"]
        border_color = TOKENS["border"]
        text_color = TOKENS["text_muted"]

        banner.setStyleSheet(f"""
            QFrame#ncrStatsInfoBanner {{
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
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        formula_label = QLabel(f"<b>統計說明：</b>{formula}")
        purpose_label = QLabel(f"<b>管理目的：</b>{purpose}")
        formula_label.setWordWrap(True)
        purpose_label.setWordWrap(True)

        layout.addWidget(formula_label)
        layout.addWidget(purpose_label)
        return banner

    def _create_insight_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setMinimumHeight(40)
        
        bg_color = TOKENS["panel_alt_bg"]
        border_color = TOKENS["info"]
        text_color = TOKENS["text_primary"]

        label.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                border-left: 4px solid {border_color};
                padding: 10px 14px;
                color: {text_color};
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }}
        """)
        return label

    def _month_key(self) -> str:
        if self.all_time_toggle.isChecked():
            return "ALL"
        return self.month_input.date().toString("yyyyMM")

    def _month_text(self) -> str:
        if self.all_time_toggle.isChecked():
            return "全期累計"
        return self.month_input.date().toString("yyyy-MM")

    def _on_all_time_toggled(self, checked: bool):
        # blockSignals 防止 setEnabled 觸發 dateChanged → 避免 refresh_data 被呼叫兩次
        self.month_input.blockSignals(True)
        self.month_input.setEnabled(not checked)
        self.month_input.blockSignals(False)
        self.refresh_data()

    def _on_filter_changed(self):
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

        yyyymm = self._month_key()

        try:
            with get_connection() as conn:
                top_suppliers = ncr_stats_service.get_top_suppliers_stats_filtered(conn, yyyymm)
                top_products = ncr_stats_service.get_top_products_stats_filtered(conn, yyyymm)
                scrap_rework = ncr_stats_service.get_scrap_rework_ratio_filtered(conn, yyyymm)
                return_slips = ncr_stats_service.get_return_slip_ratio_filtered(conn, yyyymm)
        except Exception as exc:
            logger.exception("載入 NCR 統計數據失敗")
            err_lbl = QLabel(f"無法載入統計數據：{exc}")
            err_lbl.setProperty("role", "errorText")
            self.grid_layout.addWidget(err_lbl, 0, 0)
            self.insight_label.setText("載入數據時發生錯誤。")
            return

        has_data = any((top_suppliers, top_products, scrap_rework, return_slips))

        if not has_data:
            empty = EmptyStateWidget("暫無數據", f"在所選期間 ({self._month_text()}) 尚無不合格品資料")
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

        # 4. 廠內退料/託外退料 比例% (環形圖)
        return_slip_view = self._build_donut_chart(
            return_slips, "return_slip_type", "廠內退料 / 託外退料 比例佔比",
            {"廠內退料": _C_INFO, "託外退料": _C_PENDING}
        )
        self.grid_layout.addWidget(return_slip_view, 1, 1)

        # 產生 Insights 管理建議
        self._generate_insights(top_suppliers, top_products, scrap_rework, return_slips)

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
            for r in return_slips:
                qty = int(r["total_qty"] or 0)
                if r["return_slip_type"] == "廠內退料":
                    in_house += qty
                elif r["return_slip_type"] == "託外退料":
                    outsource += qty
            total = in_house + outsource
            if total > 0:
                in_house_pct = (in_house / total) * 100
                insights.append(
                    f"🔄 <b>退料來源：</b>廠內退料佔 <b>{in_house_pct:.1f}%</b>，託外退料佔 <b>{(100 - in_house_pct):.1f}%</b>。"
                    f"廠內退料涉及內部製程不良，託外退料涉及外協加工品質，請按比例調度改善資源。"
                )
