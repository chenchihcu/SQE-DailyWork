from __future__ import annotations

from functools import lru_cache
from PySide6.QtCore import QRectF, Qt, QTimer, Signal
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

from ui.design_tokens import PALETTE as _PALETTE
from ui.layout_constants import (
    SIDEBAR_LOGO_HEIGHT,
    SIDEBAR_LOGO_SECTION_BOTTOM_SPACING,
    SIDEBAR_LOGO_SECTION_MARGINS,
    SIDEBAR_LOGO_SECTION_SPACING,
    SIDEBAR_MASTER_SUBGROUP_GAP,
    SIDEBAR_MASTER_SUBGROUP_LABEL_BOTTOM_SPACING,
    SIDEBAR_MASTER_SUBGROUP_TOP_SPACING,
    SIDEBAR_NAV_GROUP_GAP,
    SIDEBAR_NAV_ITEM_HEIGHT,
    SIDEBAR_NAV_TOP_SPACING,
    SIDEBAR_WIDTH,
)
from ui.theme import asset_path

_NAV_ICON_SIZE = 18
_NAV_ICON_COLOR = _PALETTE["sidebar_text"]
_NAV_ICON_COLOR_ACTIVE = _PALETTE["sidebar_text_active"]

# 頁面語意鍵：main_window 負責把 PAGE_KEY 對應到 QStackedWidget 索引，側欄不耦合堆疊索引。
PAGE_HOME = "HOME"  # Compatibility-only; retired from sidebar navigation.
PAGE_VISIT_CREATE = "VISIT_CREATE"  # Compatibility-only; visit create UI retired.
PAGE_ANOMALY_CREATE = "ANOMALY_CREATE"
PAGE_EVENT_QUERY = "EVENT_QUERY"
PAGE_EVENT_OVERDUE = "EVENT_OVERDUE"
PAGE_EVENT_ROOT_CAUSE = "EVENT_ROOT_CAUSE"
PAGE_EVENT_OPEN_ACTIONS = "EVENT_OPEN_ACTIONS"
PAGE_EVENT_OPS = "EVENT_OPS"
PAGE_MANAGER_VIEW = "MANAGER_VIEW"
PAGE_SUPPLIER_OVERVIEW = "SUPPLIER_OVERVIEW"
PAGE_EVENT_CREATE_VISIT = PAGE_VISIT_CREATE
PAGE_EVENT_CREATE_ANOMALY = PAGE_ANOMALY_CREATE
PAGE_STATS = "STATS"
PAGE_NCR_CREATE = "NCR_CREATE"
PAGE_NCR_PENDING_OUTSOURCE = "NCR_PENDING_OUTSOURCE"
PAGE_NCR_PENDING_MATERIAL = "NCR_PENDING_MATERIAL"
# Compatibility-only key for older callers. Active navigation uses the two
# formal processing-line entries above.
PAGE_NCR_PENDING = PAGE_NCR_PENDING_OUTSOURCE
PAGE_NCR_HISTORY = "NCR_HISTORY"
PAGE_NCR = PAGE_NCR_PENDING
PAGE_NCR_STATS = "NCR_STATS"
PAGE_MASTER_RAW_SUPPLIER = "MASTER_RAW_SUPPLIER"
PAGE_MASTER_OUTSOURCE_SUPPLIER = "MASTER_OUTSOURCE_SUPPLIER"
PAGE_MASTER_RAW_MATERIAL = "MASTER_RAW_MATERIAL"
PAGE_MASTER_SEMI_FINISHED = "MASTER_SEMI_FINISHED"
PAGE_MASTER = PAGE_MASTER_RAW_SUPPLIER  # Compatibility-only alias.
PAGE_APPEARANCE_SETTINGS = "APPEARANCE_SETTINGS"

# Compatibility-only command key. Product navigation uses PAGE_APPEARANCE_SETTINGS.
ACTION_OPEN_APPEARANCE_REDESIGN = "OPEN_APPEARANCE_REDESIGN"

# 供應商事件側欄五項正式名稱（PAGE_KEY 不變；main_window 頁標題引用此 SSOT）。
NAV_LABEL_EVENT_QUERY = "事件查詢"
NAV_LABEL_EVENT_OVERDUE = "逾期案件"
NAV_LABEL_EVENT_ROOT_CAUSE = "根因待查"
NAV_LABEL_EVENT_OPEN_ACTIONS = "處置項目"
NAV_LABEL_EVENT_OPS = "作業佇列"
NAV_LABEL_MANAGER_VIEW = "案件總覽"

NAV_SUBTITLE_EVENT_QUERY = "單獨異常與已結案查詢"
NAV_SUBTITLE_EVENT_OVERDUE = "待處理且處置已逾期的供應商異常"
NAV_SUBTITLE_EVENT_ROOT_CAUSE = "根本原因尚未開始或調查中的待處理異常"
NAV_SUBTITLE_EVENT_OPEN_ACTIONS = "待處理異常的已規劃／執行中處置"
NAV_SUBTITLE_MANAGER_VIEW = "含已結案的品質狀態營運分析"

NAV_TOOLTIP_EVENT_QUERY = (
    "供應商事件清單與篩選總表；頁內 chips 切換單獨異常與已結案。"
)
NAV_TOOLTIP_EVENT_OVERDUE = (
    "待處理異常中，目前處置到期日已過的案件作業佇列（一列一案）。"
)
NAV_TOOLTIP_EVENT_ROOT_CAUSE = (
    "待處理異常中，根本原因尚未開始或調查中的案件作業佇列（一列一案）。"
)
NAV_TOOLTIP_EVENT_OPEN_ACTIONS = (
    "待處理異常底下已規劃或執行中的處置列；徽章計處置筆數，非案件數。"
)
NAV_TOOLTIP_MANAGER_VIEW = (
    "案件品質狀態總覽（可含已結案）；雙擊列開啟案件工作台。"
)
NAV_TOOLTIP_EVENT_OPS = (
    "逾期案件、根因待查、處置項目與案件總覽的作業佇列；頁內 chips 切換範圍。"
)

# 資料庫設定群組與主檔導覽標籤 SSOT（PAGE_KEY 不變；頁首與提示訊息引用此處）。
NAV_LABEL_DB_SETTINGS_GROUP = "資料庫設定"
NAV_LABEL_MASTER_RAW_SUPPLIER = "原物料供應商"
NAV_LABEL_MASTER_OUTSOURCE = "委外加工"
NAV_LABEL_MASTER_RAW_MATERIAL = "原物料"
NAV_LABEL_MASTER_SEMI_FINISHED = "半成品/成品"
NAV_LABEL_MASTER_SUPPLIER_SUBGROUP = "供應商主檔"
NAV_LABEL_MASTER_PRODUCT_SUBGROUP = "料號主檔"

# 導覽 action 形式：("page", PAGE_KEY) 或 ("scope", EVENT_SCOPE_*) 或 ("command", COMMAND_KEY)。
# 事件 scope 在事件查詢頁內以 filter chips 切換；保留 scope action 供相容呼叫端使用。
# 結構：(群組標題 | None, [nav_item, ...])；nav_item 為單列 tuple、("master_pair", ...) 等。
_NAV_ITEM = tuple[str, object, bool, str, str]
_NAV_GROUPS: list[tuple[str | None, list]] = [
    ("供應商事件", [
        ("新增異常", ("page", PAGE_ANOMALY_CREATE), False, "icons/anomaly.svg", ""),
        (
            NAV_LABEL_EVENT_QUERY,
            ("page", PAGE_EVENT_QUERY),
            True,
            "icons/anomaly.svg",
            NAV_TOOLTIP_EVENT_QUERY,
        ),
        (
            NAV_LABEL_EVENT_OPS,
            ("page", PAGE_EVENT_OPS),
            False,
            "icons/anomaly.svg",
            NAV_TOOLTIP_EVENT_OPS,
        ),
        ("異常事件統計", ("page", PAGE_STATS), False, "icons/stats.svg", ""),
    ]),
    ("倉庫不合格品", [
        ("建立不合格品", ("page", PAGE_NCR_CREATE), False, "icons/warehouse.svg", ""),
        ("待處理委外加工", ("page", PAGE_NCR_PENDING_OUTSOURCE), True, "icons/outsource.svg", ""),
        ("待處理原物料", ("page", PAGE_NCR_PENDING_MATERIAL), True, "icons/material.svg", ""),
        ("歷史紀錄", ("page", PAGE_NCR_HISTORY), False, "icons/closed.svg", ""),
        ("不合格品統計分析", ("page", PAGE_NCR_STATS), False, "icons/stats.svg", ""),
    ]),
    (NAV_LABEL_DB_SETTINGS_GROUP, [
        ("供應商總覽", ("page", PAGE_SUPPLIER_OVERVIEW), False, "icons/master.svg", ""),
        (
            "master_pair",
            (
                NAV_LABEL_MASTER_SUPPLIER_SUBGROUP,
                "supplier",
                (
                    (
                        NAV_LABEL_MASTER_RAW_SUPPLIER,
                        ("page", PAGE_MASTER_RAW_SUPPLIER),
                        False,
                        "icons/master.svg",
                        NAV_LABEL_MASTER_RAW_SUPPLIER,
                    ),
                    (
                        NAV_LABEL_MASTER_OUTSOURCE,
                        ("page", PAGE_MASTER_OUTSOURCE_SUPPLIER),
                        False,
                        "icons/master.svg",
                        NAV_LABEL_MASTER_OUTSOURCE,
                    ),
                ),
            ),
        ),
        (
            "master_pair",
            (
                NAV_LABEL_MASTER_PRODUCT_SUBGROUP,
                "product",
                (
                    (
                        NAV_LABEL_MASTER_RAW_MATERIAL,
                        ("page", PAGE_MASTER_RAW_MATERIAL),
                        False,
                        "icons/master.svg",
                        NAV_LABEL_MASTER_RAW_MATERIAL,
                    ),
                    (
                        NAV_LABEL_MASTER_SEMI_FINISHED,
                        ("page", PAGE_MASTER_SEMI_FINISHED),
                        False,
                        "icons/master.svg",
                        NAV_LABEL_MASTER_SEMI_FINISHED,
                    ),
                ),
            ),
        ),
    ]),
    ("系統", [
        ("顯示設定", ("page", PAGE_APPEARANCE_SETTINGS), False, "icons/master.svg", ""),
    ]),
]


def _tint_pixmap(base: QPixmap, color: str) -> QPixmap:
    """Recolor every opaque pixel of ``base`` to ``color`` via SourceIn
    compositing. Shared by the SVG nav-icon tint and the PNG logo whitening,
    which previously each hand-rolled this sequence (audit finding D19)."""
    tinted = QPixmap(base.size())
    tinted.fill(Qt.GlobalColor.transparent)
    painter = QPainter(tinted)
    painter.drawPixmap(0, 0, base)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), QColor(color))
    painter.end()
    return tinted


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
    return _tint_pixmap(base, color)


class _NavButton(QPushButton):
    """單一側欄導覽按鈕，支援 badge 數字顯示。"""

    def __init__(
        self,
        label: str,
        *,
        badge_enabled: bool = False,
        icon: str | None = None,
        compact: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("NavButton")
        self.setAccessibleName(label)
        self.setFixedHeight(SIDEBAR_NAV_ITEM_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if compact:
            self.setProperty("nav_compact", "true")

        row = QHBoxLayout(self)
        if compact:
            row.setContentsMargins(8, 0, 8, 0)
            row.setSpacing(0)
        else:
            row.setContentsMargins(16, 0, 12, 0)
            row.setSpacing(10)

        self._icon_normal: QPixmap | None = None
        self._icon_active: QPixmap | None = None
        self._icon_label = QLabel(self)
        self._icon_label.setObjectName("NavIcon")
        self._icon_label.setFixedSize(_NAV_ICON_SIZE, _NAV_ICON_SIZE)
        self._icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        if icon and not compact:
            self._icon_normal = _render_tinted_nav_icon(icon, _NAV_ICON_COLOR)
            self._icon_active = _render_tinted_nav_icon(icon, _NAV_ICON_COLOR_ACTIVE)
            self._icon_label.setPixmap(self._icon_normal)
            row.addWidget(self._icon_label)
        else:
            self._icon_label.hide()

        self._label = QLabel(label, self)
        self._label.setObjectName("NavLabel")
        alignment = Qt.AlignmentFlag.AlignVCenter
        alignment |= (
            Qt.AlignmentFlag.AlignHCenter
            if compact
            else Qt.AlignmentFlag.AlignLeft
        )
        self._label.setAlignment(alignment)
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        if compact:
            self._label.setWordWrap(False)
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


class _NavButtonRow(QWidget):
    """並排雙欄導覽列（資料庫設定主檔頁）。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("NavButtonRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._layout = layout


class _NavMasterSubGroup(QWidget):
    """主檔子群組容器：pill 標籤 + 並排雙欄導覽列。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("NavMasterSubGroup")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._layout = layout


class SidebarNav(QFrame):
    """左側 220px 深色固定側欄，點擊發出 nav_activated(action) signal。

    action 為 ("page", PAGE_KEY)。事件的 scope chips（單獨異常 / 已結案）在
    事件查詢頁內切換；倉庫不合格品四個工作頁升級為一等導覽列；main_window 負責把 PAGE_KEY 對應到 QStackedWidget 索引。

    導覽項目以「供應商事件 / 倉庫不合格品 / 資料庫設定 / 系統」四組標題分隔，區分兩條工作流程資料線。
    供應商事件佇列（逾期案件 / 根因待查 / 處置項目 / 案件總覽）在 **作業佇列** 頁內以 chips 切換，非獨立側欄列。
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
        root.addSpacing(SIDEBAR_LOGO_SECTION_BOTTOM_SPACING)

        # ── 可捲動導覽區（logo 與 footer 固定，項目過多時於此捲動）──────────
        nav_scroll = QScrollArea()
        nav_scroll.setObjectName("SidebarScroll")
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setFrameShape(QFrame.Shape.NoFrame)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._nav_scroll = nav_scroll

        nav_body = QWidget()
        nav_body.setObjectName("SidebarNavBody")
        nav_layout = QVBoxLayout(nav_body)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)

        # 領域分組：群組標題（非按鈕 QLabel）+ 間距呈現工作流程結構；
        # 每個導覽列攜帶 action（("page", KEY) 或 ("scope", SCOPE)），不耦合堆疊索引。
        nav_layout.addSpacing(SIDEBAR_NAV_TOP_SPACING)
        master_subgroup_count = 0
        for header, items in _NAV_GROUPS:
            if header is not None:
                nav_layout.addSpacing(SIDEBAR_NAV_GROUP_GAP)
                nav_layout.addWidget(self._make_group_header(header))
            for item in items:
                if item[0] == "master_pair":
                    subgroup_label, variant, pair_items = item[1]
                    if master_subgroup_count == 0:
                        nav_layout.addSpacing(SIDEBAR_MASTER_SUBGROUP_TOP_SPACING)
                    else:
                        nav_layout.addSpacing(SIDEBAR_MASTER_SUBGROUP_GAP)
                    left_item, right_item = pair_items
                    nav_layout.addWidget(
                        self._make_master_subgroup(
                            subgroup_label,
                            variant,
                            left_item,
                            right_item,
                        )
                    )
                    master_subgroup_count += 1
                    continue
                label, action, badge_enabled, icon, tooltip = item
                nav_layout.addWidget(
                    self._make_nav_btn(
                        label,
                        action,
                        badge_enabled=badge_enabled,
                        icon=icon,
                        tooltip=tooltip,
                    )
                )

        nav_layout.addStretch(1)

        # 讓深色側欄背景透出（已移至 QSS 統一管理，避免行內樣式衝突）
        nav_scroll.setWidget(nav_body)
        root.addWidget(nav_scroll, 1)

        self.set_active(("page", PAGE_EVENT_QUERY))

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
        return _tint_pixmap(scaled, "#FFFFFF")

    def _build_logo_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("SidebarLogoSection")
        section.setFixedHeight(SIDEBAR_LOGO_HEIGHT)

        layout = QVBoxLayout(section)
        layout.setContentsMargins(*SIDEBAR_LOGO_SECTION_MARGINS)
        layout.setSpacing(SIDEBAR_LOGO_SECTION_SPACING)
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
        tooltip: str = "",
        compact: bool = False,
    ) -> _NavButton:
        btn = _NavButton(
            label,
            badge_enabled=badge_enabled,
            icon=icon,
            compact=compact,
        )
        if tooltip:
            btn.setToolTip(tooltip)
        btn.action = action
        btn.clicked.connect(lambda _checked=False, a=action: self._on_nav_activated(a))
        self._buttons.append(btn)
        return btn

    def _make_nav_btn_row(
        self,
        left_item: _NAV_ITEM,
        right_item: _NAV_ITEM,
    ) -> _NavButtonRow:
        row = _NavButtonRow()
        for nav_item in (left_item, right_item):
            label, action, badge_enabled, icon, tooltip = nav_item
            btn = self._make_nav_btn(
                label,
                action,
                badge_enabled=badge_enabled,
                icon=icon,
                tooltip=tooltip or label,
                compact=True,
            )
            row._layout.addWidget(btn, 1)
        return row

    def _make_master_subgroup(
        self,
        subgroup_label: str,
        variant: str,
        left_item: _NAV_ITEM,
        right_item: _NAV_ITEM,
    ) -> _NavMasterSubGroup:
        container = _NavMasterSubGroup()
        label = QLabel(subgroup_label)
        label.setObjectName("SidebarMasterSubGroupLabel")
        label.setProperty("master_subgroup", variant)
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        container._layout.addWidget(label)
        container._layout.addSpacing(SIDEBAR_MASTER_SUBGROUP_LABEL_BOTTOM_SPACING)
        container._layout.addWidget(self._make_nav_btn_row(left_item, right_item))
        return container

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
        active_button = None
        for btn in self._buttons:
            is_active = getattr(btn, "action", None) == action
            btn.set_active(is_active)
            if is_active:
                active_button = btn
        if active_button is not None:
            self._ensure_active_visible(active_button)
            QTimer.singleShot(0, lambda btn=active_button: self._ensure_active_visible(btn))

    def _ensure_active_visible(self, button: _NavButton) -> None:
        if button.parent() is not None:
            self._nav_scroll.ensureWidgetVisible(
                button,
                0,
                SIDEBAR_NAV_ITEM_HEIGHT,
            )

    def set_badge(self, action: object, count: int) -> None:
        btn = self.button_for_action(action)
        if btn is not None:
            btn.set_badge(count)
