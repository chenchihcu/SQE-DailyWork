from __future__ import annotations

from functools import lru_cache
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
    QVBoxLayout,
    QWidget,
)

from services import event_service
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

# 頁面語意鍵：main_window 負責把 PAGE_KEY 對應到 QStackedWidget 索引，側欄不耦合堆疊索引。
PAGE_HOME = "HOME"
PAGE_STATS = "STATS"
PAGE_NCR_CREATE = "NCR_CREATE"
PAGE_NCR_PENDING = "NCR_PENDING"
PAGE_NCR_HISTORY = "NCR_HISTORY"
PAGE_NCR = PAGE_NCR_PENDING
PAGE_NCR_STATS = "NCR_STATS"
PAGE_MASTER = "MASTER"

# 導覽 action 形式：("page", PAGE_KEY) 或 ("scope", EVENT_SCOPE_*)。
# 事件的 4 個 scope 升級為一等導覽列，事件頁不再有頁內 scope 分頁。
# 結構：(群組標題 | None, [(label, action, badge_enabled, icon), ...])
_NAV_GROUPS = [
    (None, [
        ("首頁", ("page", PAGE_HOME), False, "icons/home.svg"),
    ]),
    ("供應商事件", [
        ("單獨異常", ("scope", event_service.EVENT_SCOPE_ANOMALY_ONLY), True, "icons/anomaly.svg"),
        ("訪廠發現異常", ("scope", event_service.EVENT_SCOPE_VISIT_WITH_ANOMALY), False, "icons/anomaly.svg"),
        ("訪廠紀錄", ("scope", event_service.EVENT_SCOPE_VISIT_ONLY), False, "icons/anomaly.svg"),
        ("已結案", ("scope", event_service.EVENT_SCOPE_CLOSED_ONLY), False, "icons/anomaly.svg"),
        ("異常事件統計", ("page", PAGE_STATS), False, "icons/stats.svg"),
    ]),
    ("倉庫不合格品", [
        ("建立不合格品", ("page", PAGE_NCR_CREATE), False, "icons/warehouse.svg"),
        ("待處理不合格品", ("page", PAGE_NCR_PENDING), True, "icons/warehouse.svg"),
        ("歷史紀錄", ("page", PAGE_NCR_HISTORY), False, "icons/closed.svg"),
        ("不合格品統計分析", ("page", PAGE_NCR_STATS), False, "icons/stats.svg"),
    ]),
    ("系統", [
        ("基礎資料", ("page", PAGE_MASTER), False, "icons/master.svg"),
    ]),
]


@lru_cache(maxsize=32)
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
    """左側 220px 深色固定側欄，點擊發出 nav_activated(action) signal。

    action 為 ("page", PAGE_KEY) 或 ("scope", EVENT_SCOPE_*)。事件的 4 個 scope
    （單獨異常 / 訪廠發現異常 / 訪廠紀錄 / 已結案）以及倉庫不合格品三個工作頁
    升級為一等導覽列；main_window 負責把 PAGE_KEY 對應到 QStackedWidget 索引。

    導覽項目以「供應商事件 / 倉庫不合格品 / 系統」三組標題分隔，區分兩條工作流程資料線。
    """

    nav_activated = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SidebarNav")
        self.setFixedWidth(SIDEBAR_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        self._buttons: list[_NavButton] = []
        self._active_action: object | None = None

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

        # 領域分組：群組標題（非按鈕 QLabel）+ 間距呈現工作流程結構；
        # 每個導覽列攜帶 action（("page", KEY) 或 ("scope", SCOPE)），不耦合堆疊索引。
        nav_layout.addSpacing(4)
        for header, items in _NAV_GROUPS:
            if header is not None:
                nav_layout.addSpacing(_NAV_GROUP_GAP)
                nav_layout.addWidget(self._make_group_header(header))
            for label, action, badge_enabled, icon in items:
                nav_layout.addWidget(
                    self._make_nav_btn(label, action, badge_enabled=badge_enabled, icon=icon)
                )

        nav_layout.addStretch(1)

        # 讓深色側欄背景透出（Phase D 會以正式 QSS 取代行內透明設定）
        nav_body.setStyleSheet("background: transparent;")
        nav_scroll.setWidget(nav_body)
        nav_scroll.viewport().setStyleSheet("background: transparent;")
        root.addWidget(nav_scroll, 1)

        self.set_active(("page", PAGE_HOME))

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

    def _make_group_header(self, text: str) -> QLabel:
        """建立側欄領域分組標題（靜態 QLabel，不進入 self._buttons）。"""
        label = QLabel(text)
        label.setObjectName("SidebarGroupHeader")
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        return label

    def _make_nav_btn(
        self,
        label: str,
        action: object,
        *,
        badge_enabled: bool = False,
        icon: str | None = None,
    ) -> _NavButton:
        btn = _NavButton(label, badge_enabled=badge_enabled, icon=icon)
        btn.action = action
        btn.clicked.connect(lambda _checked=False, a=action: self._on_nav_activated(a))
        self._buttons.append(btn)
        return btn

    def _on_nav_activated(self, action: object) -> None:
        # main_window 為 active 狀態的唯一真相：路由成功後會呼叫 set_active；
        # 若導覽被攔截（例如 NCR 髒資料守衛），舊高亮維持不變。
        self.nav_activated.emit(action)

    def button_for_action(self, action: object) -> "_NavButton | None":
        for btn in self._buttons:
            if getattr(btn, "action", None) == action:
                return btn
        return None

    def set_active(self, action: object) -> None:
        self._active_action = action
        for btn in self._buttons:
            btn.set_active(getattr(btn, "action", None) == action)

    def set_badge(self, action: object, count: int) -> None:
        btn = self.button_for_action(action)
        if btn is not None:
            btn.set_badge(count)
