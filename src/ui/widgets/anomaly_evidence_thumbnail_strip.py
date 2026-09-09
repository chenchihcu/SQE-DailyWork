"""Read-only field-photo thumbnail strip for anomaly overview surfaces."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database.repo_helpers import (
    ANOMALY_ATTACHMENT_CATEGORY_CORRECTIVE_ACTION,
    ANOMALY_ATTACHMENT_CATEGORY_EFFECTIVENESS,
    ANOMALY_ATTACHMENT_CATEGORY_EVIDENCE,
    ANOMALY_ATTACHMENT_CATEGORY_FA_REPORT,
    ANOMALY_ATTACHMENT_CATEGORY_NG_PHOTO,
    ANOMALY_ATTACHMENT_CATEGORY_OTHER,
    ANOMALY_ATTACHMENT_CATEGORY_SPECIFICATION,
    ANOMALY_ATTACHMENT_CATEGORY_SUPPLIER_8D,
    ANOMALY_ATTACHMENT_CATEGORY_SUPPLIER_AUDIT,
)
from services import attachment_manager
from services.event import _anomaly_workbench_service
from ui.layout_constants import (
    CONTROL_ROW_SPACING,
    FORM_VERTICAL_SPACING,
    WORKBENCH_OVERVIEW_MAX_THUMBNAILS,
    WORKBENCH_OVERVIEW_THUMB_SIZE,
)
from ui.widgets.common_widgets import apply_clickable_affordance

logger = logging.getLogger(__name__)

_FIELD_PHOTO_CATEGORIES = frozenset(
    {
        ANOMALY_ATTACHMENT_CATEGORY_NG_PHOTO,
        ANOMALY_ATTACHMENT_CATEGORY_EVIDENCE,
        ANOMALY_ATTACHMENT_CATEGORY_OTHER,
        ANOMALY_ATTACHMENT_CATEGORY_FA_REPORT,
    }
)
_EXCLUDED_FIELD_PHOTO_CATEGORIES = frozenset(
    {
        ANOMALY_ATTACHMENT_CATEGORY_CORRECTIVE_ACTION,
        ANOMALY_ATTACHMENT_CATEGORY_EFFECTIVENESS,
        ANOMALY_ATTACHMENT_CATEGORY_SUPPLIER_8D,
        ANOMALY_ATTACHMENT_CATEGORY_SUPPLIER_AUDIT,
        ANOMALY_ATTACHMENT_CATEGORY_SPECIFICATION,
    }
)


def _is_field_photo_attachment(attachment: dict) -> bool:
    if bool(attachment.get("legacy_physical")):
        return True
    category = str(attachment.get("category") or "").strip()
    if category in _EXCLUDED_FIELD_PHOTO_CATEGORIES:
        return False
    return category in _FIELD_PHOTO_CATEGORIES


def _image_attachments(anomaly_id: str) -> list[dict]:
    try:
        attachments = _anomaly_workbench_service.list_attachments(anomaly_id)
    except Exception:
        logger.exception("讀取異常附件失敗 anomaly_id=%s", anomaly_id)
        return []
    images: list[dict] = []
    for attachment in attachments:
        if str(attachment.get("storage_state") or "present") != "present":
            continue
        if not _is_field_photo_attachment(attachment):
            continue
        stored_name = str(
            attachment.get("stored_name") or attachment.get("file_name") or ""
        ).strip()
        if not stored_name:
            continue
        suffix_lower = Path(stored_name).suffix.lower()
        if suffix_lower not in attachment_manager.ALLOWED_IMAGE_SUFFIXES:
            continue
        try:
            path = attachment_manager.stored_attachment_path(anomaly_id, stored_name)
        except ValueError:
            continue
        if not path.is_file():
            continue
        images.append(attachment)
    return images


class _ClickableThumbnailLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class AnomalyEvidenceThumbnailStrip(QWidget):
    """Compact thumbnail grid with optional jump to the attachments tab."""

    view_all_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AnomalyEvidenceThumbnailStrip")
        self._anomaly_id = ""
        self._thumb_labels: list[QLabel] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(FORM_VERTICAL_SPACING)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(CONTROL_ROW_SPACING)
        self.title_label = QLabel("現場照片")
        self.title_label.setProperty("role", "meta")
        self.view_all_button = QPushButton("查看全部附件")
        self.view_all_button.setProperty("variant", "secondary")
        self.view_all_button.setAccessibleName("查看全部附件")
        self.view_all_button.clicked.connect(self.view_all_requested.emit)
        apply_clickable_affordance(
            self.view_all_button, tooltip="前往附件與佐證分頁"
        )
        header_row.addWidget(self.title_label)
        header_row.addStretch(1)
        header_row.addWidget(self.view_all_button)
        root.addLayout(header_row)

        self.grid_host = QWidget()
        self.grid_layout = QGridLayout(self.grid_host)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setHorizontalSpacing(CONTROL_ROW_SPACING)
        self.grid_layout.setVerticalSpacing(CONTROL_ROW_SPACING)
        root.addWidget(self.grid_host)

        self.empty_label = QLabel("尚無現場照片")
        self.empty_label.setProperty("role", "messageText")
        self.empty_label.setProperty("tone", "info")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        root.addWidget(self.empty_label)

        for index in range(WORKBENCH_OVERVIEW_MAX_THUMBNAILS):
            thumb = _ClickableThumbnailLabel()
            thumb.setObjectName("AnomalyOverviewPhotoThumb")
            thumb.setFixedSize(
                WORKBENCH_OVERVIEW_THUMB_SIZE,
                WORKBENCH_OVERVIEW_THUMB_SIZE,
            )
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb.setProperty("role", "attachmentThumb")
            thumb.setScaledContents(False)
            thumb.setCursor(Qt.CursorShape.PointingHandCursor)
            thumb.hide()
            thumb.clicked.connect(self._open_attachments)
            self._thumb_labels.append(thumb)
            row = index // 2
            column = index % 2
            self.grid_layout.addWidget(thumb, row, column)

    def set_anomaly(self, anomaly_id: str) -> None:
        self._anomaly_id = str(anomaly_id or "").strip()
        self.refresh()

    def refresh(self) -> None:
        for label in self._thumb_labels:
            label.hide()
            label.clear()
            label.setToolTip("")
        if not self._anomaly_id:
            self._set_empty_state(True, title="現場照片", count=0)
            return

        images = _image_attachments(self._anomaly_id)
        count = len(images)
        self._set_empty_state(count <= 0, title="現場照片", count=count)
        if count <= 0:
            return

        shown = 0
        for attachment in images:
            if shown >= len(self._thumb_labels):
                break
            stored_name = str(
                attachment.get("stored_name") or attachment.get("file_name") or ""
            ).strip()
            try:
                path = attachment_manager.stored_attachment_path(
                    self._anomaly_id, stored_name
                )
            except ValueError:
                continue
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                continue
            label = self._thumb_labels[shown]
            label.setPixmap(
                pixmap.scaled(
                    WORKBENCH_OVERVIEW_THUMB_SIZE,
                    WORKBENCH_OVERVIEW_THUMB_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            caption = str(attachment.get("description") or "").strip()
            tooltip = stored_name
            if caption:
                tooltip = f"{stored_name}\n{caption}"
            label.setToolTip(tooltip)
            label.show()
            shown += 1

        if shown == 0:
            self._set_empty_state(True, title="現場照片", count=0)

    def _set_empty_state(self, empty: bool, *, title: str, count: int) -> None:
        if count > 0:
            self.title_label.setText(f"{title} ({count})")
        else:
            self.title_label.setText(title)
        self.empty_label.setVisible(empty)
        self.grid_host.setVisible(not empty)
        self.view_all_button.setVisible(count > 0)

    def _open_attachments(self) -> None:
        self.view_all_requested.emit()
