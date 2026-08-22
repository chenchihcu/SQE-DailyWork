from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ui.layout_constants import PAGE_HEADER_HEIGHT


class PageHeaderBar(QFrame):
    """頁面頂部白色標題列，顯示頁名稱與 breadcrumb。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageHeaderBar")
        self.setFixedHeight(PAGE_HEADER_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(24, 8, 24, 8)
        outer.setSpacing(12)

        text_column = QVBoxLayout()
        text_column.setSpacing(2)
        text_column.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._title = QLabel()
        self._title.setObjectName("PageHeaderTitle")
        self._title.setAccessibleName("頁面標題")
        text_column.addWidget(self._title)

        self._breadcrumb = QLabel()
        self._breadcrumb.setObjectName("PageHeaderBreadcrumb")
        self._breadcrumb.setAccessibleName("頁面路徑")
        self._breadcrumb.hide()
        text_column.addWidget(self._breadcrumb)

        outer.addLayout(text_column, 1)

        self._actions_host = QWidget()
        self._actions_layout = QHBoxLayout(self._actions_host)
        self._actions_layout.setContentsMargins(0, 0, 0, 0)
        self._actions_layout.setSpacing(8)
        outer.addWidget(self._actions_host, 0, Qt.AlignmentFlag.AlignRight)

    def add_action_widget(self, widget: QWidget) -> None:
        self._actions_layout.addWidget(widget)

    def set_page(self, title: str, breadcrumb: str = "") -> None:
        self._title.setText(title)
        if breadcrumb:
            self._breadcrumb.setText(breadcrumb)
            self._breadcrumb.show()
        else:
            self._breadcrumb.hide()
