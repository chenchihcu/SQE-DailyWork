"""Reusable photo thumbnail grid for anomaly overview surfaces."""

from __future__ import annotations

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
from ui.layout_constants import CONTROL_ROW_SPACING, WORKBENCH_OVERVIEW_THUMB_SIZE
from ui.widgets.common_widgets import apply_clickable_affordance, make_multiline_label

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


class _ClickableThumbnailLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class AnomalyPhotoThumbGrid(QWidget):
    """Compact read-only thumbnail grid for one attachment group."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AnomalyPhotoThumbGrid")
        self._thumb_labels: list[_ClickableThumbnailLabel] = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(CONTROL_ROW_SPACING)
        self._layout = layout

    def set_attachments(
        self,
        anomaly_id: str,
        attachments: list[dict],
        *,
        max_count: int | None = None,
    ) -> None:
        for label in self._thumb_labels:
            self._layout.removeWidget(label)
            label.deleteLater()
        self._thumb_labels.clear()

        shown = 0
        for attachment in attachments:
            if max_count is not None and shown >= max_count:
                break
            stored_name = str(
                attachment.get("stored_name") or attachment.get("file_name") or ""
            ).strip()
            if not stored_name:
                continue
            suffix_lower = Path(stored_name).suffix.lower()
            if suffix_lower not in attachment_manager.ALLOWED_IMAGE_SUFFIXES:
                continue
            if str(attachment.get("storage_state") or "present") != "present":
                continue
            try:
                path = attachment_manager.stored_attachment_path(anomaly_id, stored_name)
            except ValueError:
                continue
            if not path.is_file():
                continue
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                continue
            label = _ClickableThumbnailLabel()
            label.setObjectName("AnomalyOverviewPhotoThumb")
            label.setFixedSize(
                WORKBENCH_OVERVIEW_THUMB_SIZE,
                WORKBENCH_OVERVIEW_THUMB_SIZE,
            )
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setProperty("role", "attachmentThumb")
            label.setCursor(Qt.CursorShape.PointingHandCursor)
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
            label.clicked.connect(self.clicked.emit)
            self._thumb_labels.append(label)
            self._layout.addWidget(label)
            shown += 1
        self._layout.addStretch(1)
        self.setVisible(shown > 0)


class ProblemEvidenceOverviewPanel(QWidget):
    """Read-only per-bullet problem_desc rows with linked field photos."""

    view_all_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ProblemEvidenceOverviewPanel")
        self._anomaly_id = ""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(CONTROL_ROW_SPACING)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(CONTROL_ROW_SPACING)
        self.title_label = QLabel("不良現象與現場照片")
        self.title_label.setProperty("role", "sectionTitle")
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

        self.rows_host = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_host)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(CONTROL_ROW_SPACING)
        root.addWidget(self.rows_host)

        self.unlinked_title = QLabel("未對應條次")
        self.unlinked_title.setProperty("role", "meta")
        self.unlinked_grid = AnomalyPhotoThumbGrid(self)
        self.unlinked_grid.clicked.connect(self.view_all_requested.emit)
        root.addWidget(self.unlinked_title)
        root.addWidget(self.unlinked_grid)

    def set_case(self, anomaly_id: str, problem_desc: str) -> None:
        self._anomaly_id = str(anomaly_id or "").strip()
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        from services.problem_photo_link_codec import parse_problem_desc_items

        items = parse_problem_desc_items(problem_desc)
        if not items:
            items = ["—"]

        try:
            attachments = _anomaly_workbench_service.list_attachments(self._anomaly_id)
        except Exception:
            attachments = []

        image_attachments = [
            row
            for row in attachments
            if _is_field_photo_attachment(row)
            and Path(
                str(row.get("stored_name") or row.get("file_name") or "")
            ).suffix.lower()
            in attachment_manager.ALLOWED_IMAGE_SUFFIXES
        ]
        by_index: dict[int, list[dict]] = {}
        unlinked: list[dict] = []
        for attachment in image_attachments:
            bullet_index = attachment.get("bullet_index")
            if bullet_index is None:
                unlinked.append(attachment)
                continue
            try:
                index = int(bullet_index)
            except (TypeError, ValueError):
                unlinked.append(attachment)
                continue
            by_index.setdefault(index, []).append(attachment)

        for index, text in enumerate(items, start=1):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(CONTROL_ROW_SPACING)
            text_label = make_multiline_label(f"{index}. {text}", role="value")
            text_label.setToolTip(text_label.text())
            row_layout.addWidget(text_label, 3)
            thumb_grid = AnomalyPhotoThumbGrid(row_widget)
            thumb_grid.clicked.connect(self.view_all_requested.emit)
            thumb_grid.set_attachments(
                self._anomaly_id,
                by_index.get(index, []),
            )
            row_layout.addWidget(thumb_grid, 2)
            self.rows_layout.addWidget(row_widget)

        has_unlinked = bool(unlinked)
        self.unlinked_title.setVisible(has_unlinked)
        self.unlinked_grid.setVisible(has_unlinked)
        if has_unlinked:
            self.unlinked_grid.set_attachments(self._anomaly_id, unlinked)
        self.view_all_button.setVisible(bool(image_attachments))
