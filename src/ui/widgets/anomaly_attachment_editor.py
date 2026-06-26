"""Reusable attachment picker + caption editor for anomaly image attachments."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services import attachment_manager
from ui.widgets.common_widgets import mark_button_variant as _mark_button_variant


# ── Constants ─────────────────────────────────────────────────────────────
ANOMALY_ATTACHMENT_FILTER = "Images (*.jpg *.jpeg *.png)"
ATTACHMENT_PREVIEW_SIZE = QSize(132, 92)
ATTACHMENT_ITEM_SIZE = QSize(164, 142)


# ── AttachmentEditor ──────────────────────────────────────────────────────
class AttachmentEditor(QWidget):
    """Reusable picker + caption editor for anomaly image attachments.

    Tracks pending source paths and a per-file caption. Once the owning dialog
    has an anomaly_id (after create / before close), it calls ``save_to_anomaly``
    to copy files into the anomaly folder and persist captions.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pending_attachments: list[Path] = []
        self._pending_captions: dict[str, str] = {}
        self._existing_attachments: list[Path] = []
        self._deleted_attachments: list[str] = []

        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("AttachmentPreviewList")
        self.list_widget.setMinimumHeight(172)
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setMovement(QListWidget.Movement.Static)
        self.list_widget.setWrapping(True)
        self.list_widget.setSpacing(8)
        self.list_widget.setIconSize(ATTACHMENT_PREVIEW_SIZE)
        self.list_widget.setToolTip("雙擊縮圖或檔名可編輯圖說")
        self.list_widget.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.list_widget.itemChanged.connect(self._on_item_changed)

        hint = QLabel(
            "雙擊縮圖或檔名以新增／編輯圖說（檔名與圖說都會輸出至報告）"
        )
        hint.setProperty("role", "messageText")
        hint.setProperty("tone", "info")

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)
        self.add_button = QPushButton("選擇圖片…")
        self.remove_button = QPushButton("移除選取")
        _mark_button_variant(self.add_button, "secondary")
        _mark_button_variant(self.remove_button, "secondary")
        self.add_button.clicked.connect(self._pick)
        self.remove_button.clicked.connect(self._remove_selected)
        button_row.addWidget(self.add_button)
        button_row.addWidget(self.remove_button)
        button_row.addStretch(1)

        col.addWidget(self.list_widget)
        col.addWidget(hint)
        col.addLayout(button_row)

    def set_read_only(self, read_only: bool) -> None:
        self.add_button.setEnabled(not read_only)
        self.remove_button.setEnabled(not read_only)
        if read_only:
            self.list_widget.setEditTriggers(
                QAbstractItemView.EditTrigger.NoEditTriggers
            )
            self.list_widget.setToolTip("預覽模式下不可編輯圖說")
        else:
            self.list_widget.setEditTriggers(
                QAbstractItemView.EditTrigger.DoubleClicked
                | QAbstractItemView.EditTrigger.EditKeyPressed
            )
            self.list_widget.setToolTip("雙擊縮圖或檔名可編輯圖說")

    @staticmethod
    def _format_text(filename: str, caption: str) -> str:
        caption = (caption or "").strip()
        return f"{filename} — {caption}" if caption else filename

    @staticmethod
    def _preview_icon(path: Path) -> QIcon:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return QIcon()
        scaled = pixmap.scaled(
            ATTACHMENT_PREVIEW_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        return QIcon(scaled)

    def _pick(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "選擇附件圖片", "", ANOMALY_ATTACHMENT_FILTER
        )
        if not paths:
            return
        existing = {str(p) for p in self._pending_attachments}
        for raw in paths:
            path = Path(raw)
            if path.suffix.lower() not in attachment_manager.ALLOWED_IMAGE_SUFFIXES:
                continue
            if str(path) in existing:
                continue
            self._pending_attachments.append(path)
            existing.add(str(path))
            self._pending_captions[str(path)] = ""
            item = QListWidgetItem(
                self._preview_icon(path), self._format_text(path.name, "")
            )
            item.setSizeHint(ATTACHMENT_ITEM_SIZE)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setData(Qt.ItemDataRole.UserRole + 1, path.name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            item.setToolTip(path.name)
            self.list_widget.addItem(item)

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        stored = item.data(Qt.ItemDataRole.UserRole)
        old_display_name = item.data(Qt.ItemDataRole.UserRole + 1) or ""
        text = item.text().strip()

        new_filename = text
        caption = ""
        for candidate in [" — ", " - ", " -", "- "]:
            if candidate in text:
                parts = text.split(candidate, 1)
                new_filename = parts[0].strip()
                caption = parts[1].strip()
                break

        old_p = Path(old_display_name)
        new_p = Path(new_filename)
        if not new_p.suffix and old_p.suffix:
            new_filename = f"{new_filename}{old_p.suffix}"

        if not new_filename:
            new_filename = old_display_name or "image.jpg"

        stored_path = Path(str(stored))
        old_path_str = str(stored_path)
        new_path = stored_path.parent / new_filename
        new_path_str = str(new_path)

        if old_path_str in self._pending_captions:
            cap = self._pending_captions.pop(old_path_str)
            self._pending_captions[new_path_str] = caption if caption else cap
        else:
            self._pending_captions[new_path_str] = caption

        item.setData(Qt.ItemDataRole.UserRole, new_path_str)
        item.setData(Qt.ItemDataRole.UserRole + 1, new_filename)

        formatted = self._format_text(new_filename, caption)
        if item.text() != formatted:
            self.list_widget.blockSignals(True)
            try:
                item.setText(formatted)
            finally:
                self.list_widget.blockSignals(False)
        item.setToolTip(formatted)

    def _remove_selected(self) -> None:
        for item in self.list_widget.selectedItems():
            stored = item.data(Qt.ItemDataRole.UserRole)
            filename = item.data(Qt.ItemDataRole.UserRole + 1) or ""
            row = self.list_widget.row(item)
            self.list_widget.takeItem(row)

            self._pending_attachments = [
                p for p in self._pending_attachments if str(p) != stored
            ]
            self._pending_captions.pop(str(stored), None)

            is_existing = any(
                str(p) == stored for p in self._existing_attachments
            )
            if is_existing:
                self._existing_attachments = [
                    p for p in self._existing_attachments if str(p) != stored
                ]
                if filename:
                    self._deleted_attachments.append(filename)

    def load_existing_attachments(self, anomaly_id: str) -> None:
        self._pending_attachments.clear()
        self._pending_captions.clear()
        self._existing_attachments.clear()
        self._deleted_attachments.clear()
        self.list_widget.clear()

        key = (anomaly_id or "").strip()
        if not key:
            return

        files = attachment_manager.list_anomaly_attachments(key)
        captions = attachment_manager.get_anomaly_captions(key)

        for path in files:
            self._existing_attachments.append(path)
            caption = captions.get(path.name, "")
            self._pending_captions[str(path)] = caption

            item = QListWidgetItem(
                self._preview_icon(path), self._format_text(path.name, caption)
            )
            item.setSizeHint(ATTACHMENT_ITEM_SIZE)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setData(Qt.ItemDataRole.UserRole + 1, path.name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            item.setToolTip(self._format_text(path.name, caption))
            self.list_widget.addItem(item)

    def save_to_anomaly(self, anomaly_id: str) -> None:
        key = (anomaly_id or "").strip()
        if not key:
            return

        for filename in self._deleted_attachments:
            attachment_manager.delete_anomaly_attachment(key, filename)
        self._deleted_attachments.clear()

        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            stored_path_str = item.data(Qt.ItemDataRole.UserRole)
            display_name = item.data(Qt.ItemDataRole.UserRole + 1)

            is_pending = any(
                str(p) == stored_path_str for p in self._pending_attachments
            )
            if is_pending:
                attachment_manager.import_single_anomaly_attachment(
                    key, stored_path_str, display_name
                )
            else:
                p = Path(stored_path_str)
                if p.name != display_name:
                    attachment_manager.rename_anomaly_attachment(
                        key, p.name, display_name
                    )

        self._pending_attachments.clear()

        all_captions: dict[str, str] = {}
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            stored_path_str = item.data(Qt.ItemDataRole.UserRole)
            filename = item.data(Qt.ItemDataRole.UserRole + 1)
            caption = self._pending_captions.get(stored_path_str, "").strip()
            if filename:
                all_captions[filename] = caption

        attachment_manager.set_anomaly_captions(key, all_captions)
        self.load_existing_attachments(key)
