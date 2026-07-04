from __future__ import annotations

import logging
from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QDateEdit,
    QVBoxLayout,
)

from ui.layout_constants import (
    DIALOG_OUTER_MARGINS,
    FORM_VERTICAL_SPACING,
)
from ui.widgets.common_widgets import (
    DirtyTrackingMixin,
    RequiredFieldLabel,
    mark_button_variant,
)
from ui.window_sizing import fit_dialog_to_available_screen

logger = logging.getLogger(__name__)


class ExportRangeDialog(DirtyTrackingMixin, QDialog):
    """自訂日期區間選擇對話框，用於匯出 Excel 報告前供使用者設定篩選範圍。"""

    def __init__(self, title: str = "匯出 Excel 報告", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(380)
        self.setModal(True)

        self._setup_ui()
        self._init_dirty_tracking([
            self.start_date_edit.dateChanged,
            self.end_date_edit.dateChanged,
        ])

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        layout.setSpacing(FORM_VERTICAL_SPACING)

        # 提示標籤
        hint_label = QLabel("請選擇您要匯出 Excel 報告的統計與明細時間範圍：")
        hint_label.setWordWrap(True)
        hint_label.setProperty("role", "helperText")
        layout.addWidget(hint_label)

        # 表單佈局
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        
        # 開始日期 (預設為今年一月一日)
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate(QDate.currentDate().year(), 1, 1))
        
        # 結束日期 (預設為今天)
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())

        form_layout.addRow(RequiredFieldLabel("開始日期"), self.start_date_edit)
        form_layout.addRow(RequiredFieldLabel("結束日期"), self.end_date_edit)
        
        layout.addLayout(form_layout)

        # 確定與取消按鈕
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText("確認匯出")
        mark_button_variant(ok_btn, "primary")

        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.setText("取消")
        mark_button_variant(cancel_btn, "secondary")

        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        fit_dialog_to_available_screen(self, preferred_width=400, preferred_height=200)

    def _on_accept(self) -> None:
        self._dirty = False
        self.accept()

    def get_date_range(self) -> tuple[str, str]:
        """回傳 (開始日期, 結束日期) 字串元組，格式為 YYYY-MM-DD。"""
        start = self.start_date_edit.date().toString("yyyy-MM-dd")
        end = self.end_date_edit.date().toString("yyyy-MM-dd")
        return start, end
