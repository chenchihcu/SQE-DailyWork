"""Reopen-anomaly dialog for the anomaly case workbench."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from services.event import _anomaly_service as event_service
from ui.layout_constants import (
    DIALOG_OUTER_MARGINS,
    FORM_MAX_WIDTH,
    WORKBENCH_DIALOG_WIDE_MIN_WIDTH,
)
from ui.popup_i18n import localize_exception, localize_popup_message
from ui.widgets.bullet_list_widget import BulletListWidget
from ui.widgets.common_widgets import DirtyTrackingMixin, RequiredFieldLabel
from ui.widgets.defect_form_widgets import (
    apply_dialog_layout,
    set_tone,
    style_dialog_buttons,
)

logger = logging.getLogger(__name__)

REOPEN_REASON_MAX_LEN = 1000


class ReopenAnomalyDialog(DirtyTrackingMixin, QDialog):
    """Collect a required reopen reason and call the service reopen path."""

    def __init__(
        self,
        anomaly_id: str,
        ref_no: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.anomaly_id = (anomaly_id or "").strip()
        self.ref_no = (ref_no or "").strip()
        if not self.anomaly_id:
            raise ValueError("Anomaly id is required")
        self.setModal(True)
        self.setWindowTitle("重新開啟異常")
        self.setMinimumWidth(WORKBENCH_DIALOG_WIDE_MIN_WIDTH)
        self.setMaximumWidth(FORM_MAX_WIDTH)
        self._setup_ui()
        self._update_validation()
        self._connect_dirty_signals()

    def _setup_ui(self) -> None:
        self.reason_input = BulletListWidget(placeholder="為什麼要重新開啟此案件？")
        self.reason_input.setAccessibleName("重開原因")

        self.reason_counter = QLabel(f"0 / {REOPEN_REASON_MAX_LEN}")
        self.reason_counter.setProperty("role", "counterText")
        self.reason_counter.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        ref_text = self.ref_no or self.anomaly_id
        hint = QLabel(
            f"將異常單「{ref_text}」設為「待處理」。"
            "原有的結案對策與日期將會被清除。"
        )
        hint.setWordWrap(True)
        hint.setProperty("role", "meta")

        reason_field = QWidget()
        reason_layout = QVBoxLayout(reason_field)
        reason_layout.setContentsMargins(0, 0, 0, 0)
        reason_layout.addWidget(self.reason_input)
        reason_layout.addWidget(self.reason_counter)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        content_layout.addWidget(hint)
        content_layout.addWidget(RequiredFieldLabel("重開原因"))
        content_layout.addWidget(reason_field)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        self._save_button = style_dialog_buttons(buttons)
        if self._save_button:
            self._save_button.setAccessibleName("確認重新開啟")
        buttons.accepted.connect(self._on_submit)

        apply_dialog_layout(self, content, buttons)
        self._button_box = buttons
        self.reason_input.valueChanged.connect(self._update_validation)

    def _connect_dirty_signals(self) -> None:
        self._init_dirty_tracking([self.reason_input.valueChanged])

    def _update_validation(self) -> None:
        text = self.reason_input.get_formatted_text()
        length = len(text)
        over_limit = length > REOPEN_REASON_MAX_LEN
        self.reason_counter.setText(f"{length} / {REOPEN_REASON_MAX_LEN}")
        set_tone(self.reason_counter, "danger" if over_limit else "normal")
        valid = bool(text.strip()) and not over_limit
        if self._save_button is not None:
            self._save_button.setEnabled(valid)

    def _on_submit(self) -> None:
        reason = self.reason_input.get_formatted_text().strip()
        try:
            result = event_service.reopen_anomaly(
                self.anomaly_id,
                reopen_reason=reason,
            )
            warnings = list(result.get("warnings") or [])
            if warnings:
                QMessageBox.warning(
                    self,
                    "完成但有警告",
                    localize_popup_message(
                        "異常已重新開啟\n\n"
                        + "\n".join(str(item) for item in warnings)
                    ),
                )
            else:
                QMessageBox.information(
                    self,
                    "成功",
                    localize_popup_message("異常已重新開啟"),
                )
            self._dirty = False
            self.accept()
        except ValueError as exc:
            QMessageBox.warning(self, "驗證失敗", localize_exception(exc))
        except Exception as exc:
            logger.exception("重新開啟異常失敗")
            QMessageBox.critical(
                self,
                "錯誤",
                localize_popup_message(f"重新開啟失敗：{localize_exception(exc)}"),
            )
