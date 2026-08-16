"""智慧延遲載入頁面容器 (LazyPageWidget)。

在應用程式冷啟動期間延遲昂貴的 UI 構建與資料庫查詢，
僅在分頁首次被切換顯示、查詢或存取內部屬性時才按需初始化。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, TypeVar, Any

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QVBoxLayout, QWidget

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=QWidget)


class LazyPageWidget(QWidget):
    """延遲建構的頁面容器代理。

    封裝一個 factory 回呼，在首次呼叫 `ensure_widget()`、切換顯示、
    或透過屬性轉發存取時才真正建構實體元件，並透明相容 Qt 的 `findChild` 與屬性存取。
    """

    def __init__(
        self,
        factory: Callable[[], QWidget],
        parent: QWidget | None = None,
        *,
        object_name: str | None = None,
    ) -> None:
        super().__init__(parent)
        if object_name:
            self.setObjectName(object_name)
        self._factory = factory
        self._real_widget: QWidget | None = None
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._has_loaded = False

    def is_instantiated(self) -> bool:
        """檢查實體元件是否已經建構。"""
        return self._real_widget is not None

    def ensure_widget(self) -> QWidget:
        """確保實體元件已被建構並加入版面配置，返回實體元件。"""
        if self._real_widget is None:
            self._real_widget = self._factory()
            self._layout.addWidget(self._real_widget)
            self._has_loaded = True
        return self._real_widget

    def showEvent(self, event: Any) -> None:  # noqa: N802
        """當頁面顯示時確保實體元件已建構。"""
        self.ensure_widget()
        super().showEvent(event)

    def widget(self) -> QWidget:
        """相容方法：取得內部實體元件。"""
        return self.ensure_widget()

    def refresh_data(self) -> None:
        """資料刷新：若已實體化則轉發 refresh_data。"""
        if self._real_widget is not None and hasattr(self._real_widget, "refresh_data"):
            self._real_widget.refresh_data()

    def findChild(self, arg__1: type, name: str = "", options: Any = None) -> Any:  # noqa: N802
        """Qt 子元件尋找重寫：先確保實體化以相容測試與宿主元件查詢。"""
        self.ensure_widget()
        if options is not None:
            return super().findChild(arg__1, name, options)
        return super().findChild(arg__1, name)

    def findChildren(self, arg__1: type, *args: Any, **kwargs: Any) -> list:  # noqa: N802
        """Qt 多子元件尋找重寫：先確保實體化以相容測試。"""
        self.ensure_widget()
        return super().findChildren(arg__1, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        """屬性與方法透明代理至底層實體元件。"""
        if name in (
            "_real_widget",
            "_factory",
            "_layout",
            "_has_loaded",
            "staticMetaObject",
        ):
            raise AttributeError(f"{self.__class__.__name__!r} object has no attribute {name!r}")
        real = self.ensure_widget()
        return getattr(real, name)
