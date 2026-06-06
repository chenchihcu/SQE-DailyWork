from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from ui.design_tokens import PALETTE as _PALETTE
from ui.layout_constants import (
    SIDEBAR_LOGO_HEIGHT,
    SIDEBAR_NAV_ITEM_HEIGHT,
    SIDEBAR_WIDTH,
)
from ui.theme import asset_path

_NAV_ICON_SIZE = 18
_NAV_GROUP_GAP = 14  # 群組以「圖示 + 間距」區隔，取代原本的分組標題文字
_NAV_ICON_COLOR = _PALETTE["sidebar_text"]
_NAV_ICON_COLOR_ACTIVE = _PALETTE["sidebar_text_active"]

# (label, page_name, badge_enabled, icon_asset)
_OVERVIEW_ITEMS = [
    ("首頁", "首頁", False, "icons/home.svg"),
]

_EVENT_ITEMS = [
    ("異常一覽表", "異常一覽表", True, "icons/anomaly.svg"),   # badge_enabled=True
    ("訪廠紀錄一覽表", "訪廠紀錄一覽表", False, "icons/visit.svg"),
]

_INSIGHT_ITEMS = [
    ("異常事件統計", "異常事件統計", False, "icons/stats.svg"),
    ("異常已結案查詢", "異常已結案查詢", False, "icons/closed.svg"),
]

_MASTER_ITEMS = [
    ("基礎資料", "基礎資料", False, "icons/master.svg"),
]

# 倉庫不合格品 module pages, embedded in-process after the SQE DailyWork pages.
# Flat index 6 (must match ncr.embed.NCR_PAGE_SPECS order).
_NCR_ITEMS = [
    ("不合格品追蹤", True, "icons/warehouse.svg"),
]


def _render_tinted_nav_icon(
    asset_name: str, color: str, size: int = _NAV_ICON_SIZE
) -> QPixmap:
    """Render a monochrome SVG nav icon and recolor its opaque pixels to ``color``."""
    base = QPixmap(size, size)
    base.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(str(asset_path(asset_name)))
    if renderer.isValid():
        painter = QPainter(base)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
    tinted = QPixmap(base.size())
    tinted.fill(Qt.GlobalColor.transparent)
    painter = QPainter(tinted)
    painter.drawPixmap(0, 0, base)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), QColor(color))
    painter.end()
    return tinted


class _NavButton(QPushButton):
    """單一側欄導覽按鈕，支援 badge 數字顯示。"""

    def __init__(
        self,
        label: str,
        *,
        badge_enabled: bool = False,
        icon: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("NavButton")
        self.setFixedHeight(SIDEBAR_NAV_ITEM_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 0, 12, 0)
        row.setSpacing(10)

        self._icon_normal: QPixmap | None = None
        self._icon_active: QPixmap | None = None
        self._icon_label = QLabel()
        self._icon_label.setObjectName("NavIcon")
        self._icon_label.setFixedSize(_NAV_ICON_SIZE, _NAV_ICON_SIZE)
        self._icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        if icon:
            self._icon_normal = _render_tinted_nav_icon(icon, _NAV_ICON_COLOR)
            self._icon_active = _render_tinted_nav_icon(icon, _NAV_ICON_COLOR_ACTIVE)
            self._icon_label.setPixmap(self._icon_normal)
        row.addWidget(self._icon_label)

        self._label = QLabel(label)
        self._label.setObjectName("NavLabel")
        self._label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row.addWidget(self._label, 1)

        self._badge = QLabel()
        self._badge.setObjectName("NavBadge")
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._badge.hide()
        if badge_enabled:
            row.addWidget(self._badge)

        self._badge_enabled = badge_enabled

    def set_badge(self, count: int) -> None:
        if not self._badge_enabled:
            return
        if count > 0:
            self._badge.setText(str(min(count, 99)))
            self._badge.show()
        else:
            self._badge.hide()

    def set_active(self, active: bool) -> None:
        self.setProperty("nav_active", "true" if active else "false")
        if self._icon_normal is not None:
            self._icon_label.setPixmap(self._icon_active if active else self._icon_normal)
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        for child in self.findChildren(QLabel):
            style.unpolish(child)
            style.polish(child)

    def _is_active(self) -> bool:
        return self.property("nav_active") == "true"

    def enterEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if self._icon_active is not None and not self._is_active():
            self._icon_label.setPixmap(self._icon_active)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if self._icon_normal is not None and not self._is_active():
            self._icon_label.setPixmap(self._icon_normal)
        super().leaveEvent(event)


class SidebarNav(QFrame):
    """左側 220px 深色固定側欄，發出 page_changed(int) signal。

    索引對應：
        0 = 首頁
        1 = 異常一覽表
        2 = 訪廠紀錄一覽表
        3 = 異常事件統計
        4 = 異常已結案查詢
        5 = 基礎資料
        6 = 倉庫不合格品追蹤（內含待處理、結案溯源、連續登錄 tabs）

    導覽項目放在可捲動區域內，區分事件管理與倉庫不合格品實物管理。
    """

    page_changed = Signal(int)
    quick_create_clicked = Signal()
    warehouse_create_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SidebarNav")
        self.setFixedWidth(SIDEBAR_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        self._buttons: list[_NavButton] = []
        self._active_index: int = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_logo_section())
        root.addSpacing(8)

        # ── 可捲動導覽區（logo 與 footer 固定，項目過多時於此捲動）──────────
        nav_scroll = QScrollArea()
        nav_scroll.setObjectName("SidebarScroll")
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setFrameShape(QFrame.Shape.NoFrame)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        nav_body = QWidget()
        nav_body.setObjectName("SidebarNavBody")
        nav_layout = QVBoxLayout(nav_body)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)

        # 分組以「圖示 + 間距」呈現工作流程結構，不再使用分組標題文字或分隔線。
        # 頁面索引與堆疊路由維持不變（見 docs/architecture-workflow-contract.md）。
        nav_layout.addSpacing(4)

        for idx, (label, _name, badge, icon) in enumerate(_OVERVIEW_ITEMS):
            nav_layout.addWidget(self._make_nav_btn(label, idx, badge_enabled=badge, icon=icon))

        nav_layout.addSpacing(_NAV_GROUP_GAP)

        offset = len(_OVERVIEW_ITEMS)
        for idx, (label, _name, badge, icon) in enumerate(_EVENT_ITEMS):
            nav_layout.addWidget(self._make_nav_btn(label, offset + idx, badge_enabled=badge, icon=icon))

        nav_layout.addSpacing(_NAV_GROUP_GAP)

        offset += len(_EVENT_ITEMS)
        for idx, (label, _name, badge, icon) in enumerate(_INSIGHT_ITEMS):
            nav_layout.addWidget(self._make_nav_btn(label, offset + idx, badge_enabled=badge, icon=icon))

        nav_layout.addSpacing(_NAV_GROUP_GAP)

        offset += len(_INSIGHT_ITEMS)
        for idx, (label, _name, badge, icon) in enumerate(_MASTER_ITEMS):
            nav_layout.addWidget(self._make_nav_btn(label, offset + idx, badge_enabled=badge, icon=icon))

        # ── 倉庫不合格品實物管理（嵌入式，索引 6）────────────────
        nav_layout.addSpacing(_NAV_GROUP_GAP)

        ncr_offset = (
            len(_OVERVIEW_ITEMS)
            + len(_EVENT_ITEMS)
            + len(_INSIGHT_ITEMS)
            + len(_MASTER_ITEMS)
        )
        for idx, (label, badge, icon) in enumerate(_NCR_ITEMS):
            nav_layout.addWidget(self._make_nav_btn(label, ncr_offset + idx, badge_enabled=badge, icon=icon))

        nav_layout.addStretch(1)

        # 讓深色側欄背景透出（Phase D 會以正式 QSS 取代行內透明設定）
        nav_body.setStyleSheet("background: transparent;")
        nav_scroll.setWidget(nav_body)
        nav_scroll.viewport().setStyleSheet("background: transparent;")
        root.addWidget(nav_scroll, 1)

        root.addWidget(self._build_footer())

        self.set_active(0)

    @staticmethod
    def _make_white_logo(path: str, max_w: int, max_h: int) -> QPixmap | None:
        """載入 logo 並將所有不透明像素染白，適用於深色背景。"""
        original = QPixmap(path)
        if original.isNull():
            return None
        scaled = original.scaled(
            max_w, max_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        white = QPixmap(scaled.size())
        white.fill(Qt.GlobalColor.transparent)
        p = QPainter(white)
        p.drawPixmap(0, 0, scaled)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        p.fillRect(white.rect(), QColor("#FFFFFF"))
        p.end()
        return white

    def _build_logo_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("SidebarLogoSection")
        section.setFixedHeight(SIDEBAR_LOGO_HEIGHT)

        layout = QVBoxLayout(section)
        layout.setContentsMargins(16, 10, 16, 8)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        white_logo = self._make_white_logo(str(asset_path("mitcorp_logo.png")), 130, 30)
        if white_logo is not None:
            logo_label = QLabel()
            logo_label.setObjectName("SidebarLogoPixmap")
            logo_label.setPixmap(white_logo)
            layout.addWidget(logo_label)
        else:
            title = QLabel("Mitcorp")
            title.setObjectName("SidebarAppTitle")
            layout.addWidget(title)

        subtitle = QLabel("SQE Tool")
        subtitle.setObjectName("SidebarAppSubtitle")
        layout.addWidget(subtitle)

        return section

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setObjectName("SidebarFooter")

        layout = QVBoxLayout(footer)
        layout.setContentsMargins(12, 10, 12, 16)
        layout.setSpacing(8)

        label = QLabel("快速建立")
        label.setObjectName("SidebarFooterLabel")
        layout.addWidget(label)

        btn = QPushButton("＋ 新增異常")
        btn.setObjectName("SidebarQuickCreate")
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self.quick_create_clicked)
        layout.addWidget(btn)

        warehouse_btn = QPushButton("＋ 建立不合格品")
        warehouse_btn.setObjectName("SidebarWarehouseQuickCreate")
        warehouse_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        warehouse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        warehouse_btn.clicked.connect(self.warehouse_create_clicked)
        layout.addWidget(warehouse_btn)

        return footer

    def _make_nav_btn(
        self,
        label: str,
        index: int,
        *,
        badge_enabled: bool = False,
        icon: str | None = None,
    ) -> _NavButton:
        btn = _NavButton(label, badge_enabled=badge_enabled, icon=icon)
        btn.clicked.connect(lambda _checked=False, i=index: self._on_nav_clicked(i))
        self._buttons.append(btn)
        return btn

    def _on_nav_clicked(self, index: int) -> None:
        self.set_active(index)
        self.page_changed.emit(index)

    def set_active(self, index: int) -> None:
        self._active_index = index
        for i, btn in enumerate(self._buttons):
            btn.set_active(i == index)

    def set_badge(self, index: int, count: int) -> None:
        if 0 <= index < len(self._buttons):
            self._buttons[index].set_badge(count)
