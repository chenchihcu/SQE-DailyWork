from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from ui.layout_constants import (
    SIDEBAR_LOGO_HEIGHT,
    SIDEBAR_NAV_ITEM_HEIGHT,
    SIDEBAR_WIDTH,
)
from ui.theme import asset_path

_NAV_ITEMS = [
    ("首頁",       "首頁",       False),
    ("異常管理",   "異常管理",   True),   # badge_enabled=True
    ("訪廠紀錄",   "訪廠紀錄",   False),
    ("統計分析",   "統計分析",   False),
]

_SECONDARY_ITEMS = [
    ("已結案紀錄", "已結案紀錄", False),
    ("基礎資料",   "基礎資料",   False),
]


class _NavButton(QPushButton):
    """單一側欄導覽按鈕，支援 badge 數字顯示。"""

    def __init__(self, label: str, *, badge_enabled: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("NavButton")
        self.setFixedHeight(SIDEBAR_NAV_ITEM_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 0, 12, 0)
        row.setSpacing(8)

        self._label = QLabel(label)
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
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        for child in self.findChildren(QLabel):
            style.unpolish(child)
            style.polish(child)


class SidebarNav(QFrame):
    """左側 220px 深色固定側欄，發出 page_changed(int) signal。

    索引對應：
        0 = 首頁
        1 = 異常管理
        2 = 訪廠紀錄
        3 = 統計分析
        4 = 已結案紀錄
        5 = 基礎資料
    """

    page_changed = Signal(int)
    quick_create_clicked = Signal()

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

        for idx, (label, _name, badge) in enumerate(_NAV_ITEMS):
            btn = self._make_nav_btn(label, idx, badge_enabled=badge)
            root.addWidget(btn)

        root.addWidget(self._build_divider())
        root.addWidget(self._build_group_label("查詢紀錄"))

        offset = len(_NAV_ITEMS)
        for idx, (label, _name, badge) in enumerate(_SECONDARY_ITEMS):
            btn = self._make_nav_btn(label, offset + idx, badge_enabled=badge)
            root.addWidget(btn)

        root.addStretch(1)
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

    def _build_group_label(self, text: str) -> QWidget:
        wrapper = QWidget()
        wrapper.setObjectName("SidebarGroupLabel")
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(16, 8, 16, 2)
        lbl = QLabel(text.upper())
        lbl.setObjectName("SidebarGroupLabelText")
        layout.addWidget(lbl)
        return wrapper

    def _build_divider(self) -> QFrame:
        divider = QFrame()
        divider.setObjectName("SidebarDivider")
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFixedHeight(1)
        return divider

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setObjectName("SidebarFooter")

        layout = QVBoxLayout(footer)
        layout.setContentsMargins(12, 8, 12, 16)
        layout.setSpacing(0)

        btn = QPushButton("＋ 新增異常")
        btn.setObjectName("SidebarQuickCreate")
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self.quick_create_clicked)
        layout.addWidget(btn)

        return footer

    def _make_nav_btn(self, label: str, index: int, *, badge_enabled: bool = False) -> _NavButton:
        btn = _NavButton(label, badge_enabled=badge_enabled)
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
