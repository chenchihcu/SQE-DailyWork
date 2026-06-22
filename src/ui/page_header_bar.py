from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ui.layout_constants import PAGE_HEADER_HEIGHT


class PageHeaderBar(QFrame):
    """頁面頂部白色標題列，顯示頁名稱與 breadcrumb。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageHeaderBar")
        self.setFixedHeight(PAGE_HEADER_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 8, 24, 8)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._title = QLabel()
        self._title.setObjectName("PageHeaderTitle")
        layout.addWidget(self._title)

        self._breadcrumb = QLabel()
        self._breadcrumb.setObjectName("PageHeaderBreadcrumb")
        self._breadcrumb.hide()
        layout.addWidget(self._breadcrumb)

    def set_page(self, title: str, breadcrumb: str = "") -> None:
        self._title.setText(title)
        if breadcrumb:
            self._breadcrumb.setText(breadcrumb)
            self._breadcrumb.show()
        else:
            self._breadcrumb.hide()
