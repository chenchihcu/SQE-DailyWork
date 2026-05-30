from __future__ import annotations

import os

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services import event_service
from ui.layout_constants import (
    CARD_INNER_MARGINS,
    GRID_GUTTER,
    HERO_BANNER_MARGINS,
    PANEL_MARGINS,
    ROOT_SECTION_SPACING,
    ROW_GAP,
)
from ui.status_colors import get_status_palette
from ui.theme import asset_path
from ui.widgets.common_widgets import BrandDivider, KpiCard, apply_clickable_affordance
from ui.widgets.reference_widget import _features_html, _make_rich_label

REPORT_BUTTON_TEXT = "匯出週報簡報"
REPORT_BUTTON_WORKING_TEXT = "匯出中…"
QUICK_ACTION_MIN_HEIGHT = 80


class OverdueAlertBanner(QFrame):
    """紅色逾期警示橫幅，僅在逾期異常 > 0 時顯示。"""

    def __init__(self, main_window, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._main_window = main_window
        self.setObjectName("OverdueBanner")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(12)

        icon = QLabel("⚠")
        icon.setObjectName("OverdueBannerText")
        icon.setFixedWidth(20)
        layout.addWidget(icon)

        self._text = QLabel()
        self._text.setObjectName("OverdueBannerText")
        layout.addWidget(self._text, 1)

        link_btn = QPushButton("查看逾期異常 →")
        link_btn.setObjectName("OverdueBannerLink")
        link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        link_btn.clicked.connect(self._go_to_overdue)
        layout.addWidget(link_btn)

        self.hide()

    def update_count(self, count: int) -> None:
        if count > 0:
            self._text.setText(f"有 {count} 筆異常已逾期，請立即追蹤改善")
            self.show()
        else:
            self.hide()

    def _go_to_overdue(self) -> None:
        self._main_window.open_event_query_with_filters(
            event_type="ANOMALY",
            status="待處理",
            event_scope=event_service.EVENT_SCOPE_ANOMALY_ONLY,
        )


class HeroBannerFrame(QFrame):
    """首頁 Hero Banner：MITCorp logo、工業內視鏡線稿與供應商品質工作台定位。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HeroBanner")
        self.setMinimumHeight(148)
        self._setup_content()

    def _setup_content(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(*HERO_BANNER_MARGINS)
        layout.setSpacing(20)

        # --- 左側：品牌識別 (Logo + 公司名稱) ---
        brand_layout = QVBoxLayout()
        brand_layout.setSpacing(12)
        brand_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        logo = QLabel("Mitcorp")
        logo.setObjectName("MitcorpHeroLogo")
        logo.setProperty("role", "heroBrandLogo")
        logo_pixmap = QPixmap(str(asset_path("mitcorp_logo.png")))
        if not logo_pixmap.isNull():
            scaled_logo = logo_pixmap.scaled(
                240,
                56,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo.setPixmap(scaled_logo)
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            logo.setFixedSize(240, 56)
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        brand_layout.addWidget(logo)

        eyebrow = QLabel("Medical Intubation Technology Corporation")
        eyebrow.setProperty("role", "heroBannerEyebrow")
        eyebrow.setAlignment(Qt.AlignmentFlag.AlignLeft)
        brand_layout.addWidget(eyebrow)

        layout.addLayout(brand_layout)

        product_line = QLabel()
        product_line.setObjectName("HeroProductLine")
        product_line.setAlignment(Qt.AlignmentFlag.AlignCenter)
        product_line.setFixedSize(160, 70)
        product_pixmap = QPixmap(str(asset_path("mitcorp_videoscope_line.svg")))
        if not product_pixmap.isNull():
            product_line.setPixmap(
                product_pixmap.scaled(
                    160,
                    70,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        layout.addWidget(product_line, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch(1)

        # --- 右側：功能文案 ---
        copy_widget = QWidget()
        copy_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        copy_layout = QVBoxLayout(copy_widget)
        copy_layout.setContentsMargins(0, 0, 0, 0)
        copy_layout.setSpacing(14)
        copy_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        title = QLabel("異常事件追溯 · 資料統計分析")
        title.setProperty("role", "heroBannerTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignRight)
        title.setWordWrap(True)
        copy_layout.addWidget(title)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(6)
        for text in ("Industrial Videoscope", "Made in Taiwan", "Quality · Innovation"):
            chip = QLabel(text)
            chip.setProperty("role", "heroBannerMeta")
            meta_row.addWidget(chip)
        copy_layout.addLayout(meta_row)

        layout.addWidget(copy_widget)


class HomeWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._kpi_cards: dict[str, KpiCard] = {}
        self._report_worker = None
        self._overdue_banner: OverdueAlertBanner | None = None
        self._setup_ui()
        self.refresh_data()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(ROOT_SECTION_SPACING)

        # --- 逾期警示橫幅（僅逾期>0時顯示）---
        self._overdue_banner = OverdueAlertBanner(self.main_window)
        root.addWidget(self._overdue_banner)

        # --- Hero Banner ---
        root.addWidget(HeroBannerFrame())

        # --- KPI 摘要 ---
        kpi_panel = QFrame()
        kpi_panel.setProperty("role", "panel")
        kpi_outer = QVBoxLayout(kpi_panel)
        kpi_outer.setContentsMargins(*PANEL_MARGINS)
        kpi_outer.setSpacing(8)

        self._kpi_title = QLabel()
        self._kpi_title.setProperty("role", "sectionTitle")
        kpi_outer.addWidget(self._kpi_title)
        kpi_outer.addWidget(BrandDivider())

        kpi_grid = QGridLayout()
        kpi_grid.setHorizontalSpacing(GRID_GUTTER)
        kpi_grid.setVerticalSpacing(ROW_GAP)
        # Row 0: 最重要的 3 個主指標
        row0_defs = [
            ("anomaly_count",            "總異常件數", get_status_palette("異常").chart,       "danger"),
            ("closed_anomaly_count",     "已結案",     get_status_palette("已結案").chart,     "success"),
            ("overdue_open_anomaly_count","逾期未結",  get_status_palette("逾期未結").chart,   "danger"),
        ]
        # Row 1: 次要明細指標
        row1_defs = [
            ("standalone_open_anomaly_count", "單獨異常",    get_status_palette("單獨異常").chart,    "pending"),
            ("visit_open_anomaly_count",      "訪廠發現異常", get_status_palette("訪廠發現異常").chart, "info"),
        ]
        for col, (key, text, color, tone) in enumerate(row0_defs):
            card = KpiCard(text, color, tone=tone)
            self._kpi_cards[key] = card
            kpi_grid.addWidget(card, 0, col)
            kpi_grid.setColumnStretch(col, 1)
        # Row 1: 僅 2 張卡，放在 col 0~1，col 2 以彈性空間補足視覺平衡
        for col, (key, text, color, tone) in enumerate(row1_defs):
            card = KpiCard(text, color, tone=tone)
            self._kpi_cards[key] = card
            kpi_grid.addWidget(card, 1, col)
        # col 2 (row 1) 沒有 card — 保留 columnStretch(2)=1 以維持等寬
        kpi_outer.addLayout(kpi_grid)
        root.addWidget(kpi_panel)

        # --- 說明 + 快速操作 ---
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(*PANEL_MARGINS)
        info_layout.setSpacing(24)

        # 左側：功能說明
        features_card = QFrame()
        features_card.setObjectName("HomeFeaturesPanel")
        features_card.setProperty("role", "panel")
        features_layout = QVBoxLayout(features_card)
        features_layout.setContentsMargins(*CARD_INNER_MARGINS)
        features_layout.setSpacing(10)
        features_label = QLabel("功能導覽")
        features_label.setProperty("role", "sectionTitle")
        features_layout.addWidget(features_label)
        features_layout.addWidget(_make_rich_label(_features_html(relaxed=True)))
        info_layout.addWidget(features_card, 45)

        # 右側：快速操作
        quick_card = QFrame()
        quick_card.setObjectName("HomeQuickActionPanel")
        quick_card.setProperty("role", "panel")
        quick_layout = QVBoxLayout(quick_card)
        quick_layout.setContentsMargins(*CARD_INNER_MARGINS)
        quick_layout.setSpacing(16)
        quick_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        quick_title = QLabel("快速操作")
        quick_title.setProperty("role", "sectionTitle")
        quick_title.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        quick_layout.addWidget(quick_title)

        btn_visit = self._create_quick_action_button(
            "登錄訪廠紀錄",
            tone="visit",
            tooltip="建立新的訪廠紀錄",
            object_name="HomeQuickVisitButton",
        )
        btn_visit.clicked.connect(self.main_window.open_new_visit_dialog)
        quick_layout.addWidget(btn_visit)

        btn_anomaly = self._create_quick_action_button(
            "登錄訪廠缺失",
            tone="anomaly",
            tooltip="在訪廠紀錄中新增現場缺失",
            object_name="HomeQuickAnomalyButton",
        )
        btn_anomaly.clicked.connect(
            getattr(
                self.main_window,
                "open_new_visit_defect_dialog",
                self.main_window.open_new_anomaly_dialog,
            )
        )
        quick_layout.addWidget(btn_anomaly)

        self._btn_report = self._create_quick_action_button(
            REPORT_BUTTON_TEXT,
            tone="report",
            tooltip="產生 SQE 週會簡報 PowerPoint",
            object_name="HomeQuickReportButton",
        )
        self._btn_report.clicked.connect(self._generate_weekly_report)
        quick_layout.addWidget(self._btn_report)

        info_layout.addWidget(quick_card, 55)

        root.addLayout(info_layout)
        root.addStretch(1)

    def _create_quick_action_button(
        self,
        text: str,
        *,
        tone: str,
        tooltip: str,
        object_name: str,
    ) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(object_name)
        button.setProperty("role", "quickActionButton")
        button.setProperty("tone", tone)
        button.setProperty("variant", "primary" if tone == "anomaly" else "secondary")
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setMinimumHeight(QUICK_ACTION_MIN_HEIGHT)
        apply_clickable_affordance(button, tooltip=tooltip)
        return button

    def _generate_weekly_report(self):
        from services.report_service import ReportWorker

        self._btn_report.setEnabled(False)
        self._btn_report.setText(REPORT_BUTTON_WORKING_TEXT)

        self._report_worker = ReportWorker()
        self._report_worker.finished.connect(self._on_report_done)
        self._report_worker.failed.connect(self._on_report_failed)
        self._report_worker.start()

    def _on_report_done(self, path: str):
        self._btn_report.setEnabled(True)
        self._btn_report.setText(REPORT_BUTTON_TEXT)

        msg = QMessageBox(self)
        msg.setWindowTitle("週報產出完成")
        msg.setText(f"檔案已儲存至：\n{path}")
        msg.setStandardButtons(
            QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Ok
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Ok)
        if msg.exec() == QMessageBox.StandardButton.Open:
            os.startfile(path)

    def _on_report_failed(self, error: str):
        self._btn_report.setEnabled(True)
        self._btn_report.setText(REPORT_BUTTON_TEXT)
        QMessageBox.critical(self, "週報產出失敗", f"發生錯誤：\n{error}")

    def refresh_data(self):
        month_text = QDate.currentDate().toString("yyyy-MM")
        self._kpi_title.setText(f"本月品質概況（{month_text}）")
        try:
            summary = event_service.get_monthly_stats()
            for key, card in self._kpi_cards.items():
                card.set_value(str(int(summary.get(key, 0))))
            if self._overdue_banner is not None:
                self._overdue_banner.update_count(
                    int(summary.get("overdue_open_anomaly_count", 0))
                )
        except Exception:
            for card in self._kpi_cards.values():
                card.set_value("—")
