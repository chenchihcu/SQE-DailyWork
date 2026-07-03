from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from ui.layout_constants import PAGINATION_TOP_MARGIN
from ui.widgets.common_widgets import apply_clickable_affordance


class PaginationBar(QWidget):
    def __init__(
        self,
        *,
        on_page_changed: Callable[[int], None],
        on_page_size_changed: Callable[[int], None],
        default_page_size: int = 13,
        page_size_options: tuple[int, ...] = (10, 13, 20, 50, 100),
        max_page_buttons: int = 7,
    ):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._on_page_changed = on_page_changed
        self._on_page_size_changed = on_page_size_changed
        self._max_page_buttons = max(3, max_page_buttons)

        options = sorted({size for size in page_size_options if size > 0})
        if default_page_size <= 0:
            default_page_size = 20
        if default_page_size not in options:
            options.append(default_page_size)
            options.sort()
        self._page_size_options = tuple(options)

        self._total_items = 0
        self._page_size = default_page_size
        self._current_page = 1

        self._setup_ui()
        self.set_state(total_items=0, current_page=1, page_size=self._page_size)

    def _setup_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, PAGINATION_TOP_MARGIN, 0, 0)
        root.setSpacing(8)

        # Left side: Stats and Page Size
        self.total_label = QLabel("共 0 筆")
        self.total_label.setProperty("role", "helperText")
        root.addWidget(self.total_label)

        root.addSpacing(8)

        root.addWidget(QLabel("每頁"))
        self.page_size_combo = QComboBox()
        for size in self._page_size_options:
            self.page_size_combo.addItem(str(size), size)
        self.page_size_combo.setFixedWidth(76)
        self.page_size_combo.setToolTip("調整每頁顯示筆數")
        self.page_size_combo.setStatusTip("調整每頁顯示筆數")
        self.page_size_combo.currentIndexChanged.connect(self._handle_page_size_changed)
        root.addWidget(self.page_size_combo)
        root.addWidget(QLabel("筆"))

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        root.addWidget(spacer)

        # Right side: Navigation and Page Buttons
        self.first_btn = QPushButton("«")
        self.first_btn.setProperty("role", "pageBtn")
        self.first_btn.setProperty("variant", "secondary")
        self.first_btn.setToolTip("第一頁")
        self.first_btn.setAccessibleName("第一頁")
        apply_clickable_affordance(self.first_btn, status_tip="前往第一頁")
        self.first_btn.setMinimumWidth(34)
        self.first_btn.clicked.connect(lambda: self._emit_page_change(1))
        root.addWidget(self.first_btn)

        self.prev_btn = QPushButton("‹")
        self.prev_btn.setProperty("role", "pageBtn")
        self.prev_btn.setProperty("variant", "secondary")
        self.prev_btn.setToolTip("上一頁")
        self.prev_btn.setAccessibleName("上一頁")
        apply_clickable_affordance(self.prev_btn, status_tip="前往上一頁")
        self.prev_btn.setMinimumWidth(34)
        self.prev_btn.clicked.connect(lambda: self._emit_page_change(self._current_page - 1))
        root.addWidget(self.prev_btn)

        self.page_buttons_host = QWidget()
        self.page_buttons_layout = QHBoxLayout(self.page_buttons_host)
        self.page_buttons_layout.setContentsMargins(4, 0, 4, 0)
        self.page_buttons_layout.setSpacing(4)
        root.addWidget(self.page_buttons_host)

        self.next_btn = QPushButton("›")
        self.next_btn.setProperty("role", "pageBtn")
        self.next_btn.setProperty("variant", "secondary")
        self.next_btn.setToolTip("下一頁")
        self.next_btn.setAccessibleName("下一頁")
        apply_clickable_affordance(self.next_btn, status_tip="前往下一頁")
        self.next_btn.setMinimumWidth(34)
        self.next_btn.clicked.connect(lambda: self._emit_page_change(self._current_page + 1))
        root.addWidget(self.next_btn)

        self.last_btn = QPushButton("»")
        self.last_btn.setProperty("role", "pageBtn")
        self.last_btn.setProperty("variant", "secondary")
        self.last_btn.setToolTip("最後一頁")
        self.last_btn.setAccessibleName("最後一頁")
        apply_clickable_affordance(self.last_btn, status_tip="前往最後一頁")
        self.last_btn.setMinimumWidth(34)
        self.last_btn.clicked.connect(lambda: self._emit_page_change(self._total_pages_count()))
        root.addWidget(self.last_btn)

        root.addSpacing(12)

        # Jump to page
        self.page_info_label = QLabel("1 / 1")
        self.page_info_label.setProperty("role", "helperText")
        root.addWidget(self.page_info_label)

        self.jump_label_prefix = QLabel("跳至")
        root.addWidget(self.jump_label_prefix)
        self.jump_input = QLineEdit()
        self.jump_input.setFixedWidth(48)
        self.jump_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.jump_input.setPlaceholderText("-")
        self.jump_input.setToolTip("輸入頁碼後按 Enter 跳頁")
        self.jump_input.setStatusTip("輸入頁碼後按 Enter 跳頁")
        self.jump_input.returnPressed.connect(self._handle_jump)
        root.addWidget(self.jump_input)
        self.jump_label_suffix = QLabel("頁")
        root.addWidget(self.jump_label_suffix)

        # 分數倍率(1.25x/1.5x)字寬捨入會讓非伸縮文字標籤末字被裁切(共 N→共、每頁→每、跳至→跳)：
        # 以 sizeHint 為下限(Minimum policy)，靠右側彈性 spacer 吸收差額。
        for _lbl in self.findChildren(QLabel):
            _lbl.setSizePolicy(
                QSizePolicy.Policy.Minimum, _lbl.sizePolicy().verticalPolicy()
            )

    def set_state(
        self, *, total_items: int, current_page: int, page_size: int | None = None
    ) -> None:
        total_items = max(0, int(total_items))
        if page_size is not None and page_size > 0:
            self._page_size = int(page_size)

        index = self.page_size_combo.findData(self._page_size)
        if index < 0:
            self.page_size_combo.addItem(str(self._page_size), self._page_size)
            index = self.page_size_combo.findData(self._page_size)
        self.page_size_combo.blockSignals(True)
        try:
            self.page_size_combo.setCurrentIndex(index)
        finally:
            self.page_size_combo.blockSignals(False)

        total_pages = self._total_pages(total_items, self._page_size)
        self._total_items = total_items
        self._current_page = min(max(1, int(current_page)), total_pages)

        self.total_label.setText(f"共 {self._total_items} 筆")
        self.page_info_label.setText(f"{self._current_page} / {total_pages}")
        
        self.first_btn.setEnabled(self._current_page > 1)
        self.prev_btn.setEnabled(self._current_page > 1)
        self.next_btn.setEnabled(self._current_page < total_pages)
        self.last_btn.setEnabled(self._current_page < total_pages)
        
        self.jump_input.clear()
        self._refresh_page_buttons(total_pages)

    def _refresh_page_buttons(self, total_pages: int) -> None:
        while self.page_buttons_layout.count():
            item = self.page_buttons_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        visible_pages = self._visible_page_numbers(total_pages, self._current_page)
        for page_no in visible_pages:
            btn = QPushButton(str(page_no))
            btn.setProperty("role", "pageBtn")
            is_current = page_no == self._current_page
            btn.setCheckable(True)
            if is_current:
                btn.setProperty("variant", "primary")
                btn.setChecked(True)
            else:
                btn.setProperty("variant", "secondary")
                btn.setChecked(False)
                
            btn.setMinimumWidth(34)
            apply_clickable_affordance(
                btn,
                tooltip=f"第 {page_no} 頁",
                status_tip=f"前往第 {page_no} 頁",
            )
            btn.clicked.connect(
                lambda _checked=False, target_page=page_no: self._emit_page_change(target_page)
            )
            self.page_buttons_layout.addWidget(btn)

    def _handle_page_size_changed(self, index: int) -> None:
        page_size = self.page_size_combo.itemData(index)
        if page_size is None:
            return
        self._page_size = int(page_size)
        self._on_page_size_changed(self._page_size)

    def _handle_jump(self) -> None:
        text = self.jump_input.text().strip()
        if not text.isdigit():
            self.jump_input.setText(str(self._current_page))
            return
        target = int(text)
        self._emit_page_change(target)

    def _emit_page_change(self, target_page: int) -> None:
        total_pages = self._total_pages_count()
        target = min(max(1, int(target_page)), total_pages)
        if target == self._current_page:
            # Still refresh input text in case it was out of range
            self.jump_input.setText(str(self._current_page))
            return
        self._on_page_changed(target)

    def _total_pages_count(self) -> int:
        return self._total_pages(self._total_items, self._page_size)

    def _visible_page_numbers(self, total_pages: int, current_page: int) -> list[int]:
        if total_pages <= self._max_page_buttons:
            return list(range(1, total_pages + 1))

        half = self._max_page_buttons // 2
        start = max(1, current_page - half)
        end = start + self._max_page_buttons - 1
        if end > total_pages:
            end = total_pages
            start = end - self._max_page_buttons + 1
        return list(range(start, end + 1))

    @staticmethod
    def _total_pages(total_items: int, page_size: int) -> int:
        if page_size <= 0:
            return 1
        pages = (total_items + page_size - 1) // page_size
        return max(1, pages)
