"""Bullet list with per-row field photo attachments for anomaly problem_desc."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services import attachment_manager
from services.problem_photo_link_codec import (
    delete_links_for_filenames,
    get_problem_photo_links,
    set_problem_photo_links,
)
from ui.layout_constants import (
    CONTROL_ROW_SPACING,
    EVIDENCE_BULLET_MAX_PHOTOS_PER_ROW,
    EVIDENCE_BULLET_PHOTO_BUTTON_WIDTH,
    EVIDENCE_BULLET_THUMB_SIZE,
)
from ui.widgets.bullet_list_widget import BulletListItemRow, BulletListWidget

ANOMALY_ATTACHMENT_FILTER = "Images (*.jpg *.jpeg *.png)"


@dataclass
class _RowPhoto:
    path: Path
    stored_name: str | None = None
    pending: bool = True

    @property
    def key(self) -> str:
        return str(self.path)


class EvidenceBulletListItemRow(BulletListItemRow):
    """One problem-desc row with optional inline field photos."""

    photosChanged = Signal()

    def __init__(self, index: int = 1, text: str = "", parent=None):
        super().__init__(index=index, text=text, parent=parent)
        self._photos: list[_RowPhoto] = []
        self._anomaly_id = ""
        self._read_only_photos = False

        self.btn_photos = QPushButton("📷 0")
        self.btn_photos.setFixedWidth(EVIDENCE_BULLET_PHOTO_BUTTON_WIDTH)
        self.btn_photos.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_photos.setAccessibleName(f"附加照片 條目 {index}")
        self.btn_photos.setProperty("variant", "secondary")
        self.btn_photos.clicked.connect(self._pick_photos)
        self.layout.insertWidget(2, self.btn_photos)

        self.thumb_row = QWidget()
        self.thumb_layout = QHBoxLayout(self.thumb_row)
        self.thumb_layout.setContentsMargins(28, 0, 0, 0)
        self.thumb_layout.setSpacing(CONTROL_ROW_SPACING)
        self.thumb_row.hide()

        outer = self.parentWidget()
        if outer is not None and outer.layout() is not None:
            # Re-wrap: row widget becomes container with main row + thumbs
            pass

    def attach_thumb_host(self, host_layout: QVBoxLayout) -> None:
        host_layout.addWidget(self.thumb_row)

    def set_anomaly_context(self, anomaly_id: str) -> None:
        self._anomaly_id = str(anomaly_id or "").strip()

    def set_photos_read_only(self, read_only: bool) -> None:
        self._read_only_photos = bool(read_only)
        self.btn_photos.setEnabled(not read_only)

    def photo_count(self) -> int:
        return len(self._photos)

    def photos(self) -> list[_RowPhoto]:
        return list(self._photos)

    def set_photos(self, photos: list[_RowPhoto]) -> None:
        self._photos = list(photos)
        self._refresh_photo_ui()

    def clear_photos(self) -> None:
        self._photos.clear()
        self._refresh_photo_ui()

    def delete_all_photos(self) -> list[str]:
        """Delete stored files and return removed stored filenames."""
        removed_names: list[str] = []
        key = self._anomaly_id
        for photo in list(self._photos):
            if not photo.pending and photo.stored_name and key:
                attachment_manager.delete_anomaly_attachment(key, photo.stored_name)
                removed_names.append(photo.stored_name)
        self._photos.clear()
        if removed_names and key:
            delete_links_for_filenames(key, removed_names)
        self._refresh_photo_ui()
        self.photosChanged.emit()
        return removed_names

    def _pick_photos(self) -> None:
        if self._read_only_photos:
            return
        remaining = EVIDENCE_BULLET_MAX_PHOTOS_PER_ROW - len(self._photos)
        if remaining <= 0:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "選擇現場照片", "", ANOMALY_ATTACHMENT_FILTER
        )
        if not paths:
            return
        existing = {photo.key for photo in self._photos}
        for raw in paths:
            if len(self._photos) >= EVIDENCE_BULLET_MAX_PHOTOS_PER_ROW:
                break
            path = Path(raw)
            if path.suffix.lower() not in attachment_manager.ALLOWED_IMAGE_SUFFIXES:
                continue
            key = str(path)
            if key in existing:
                continue
            self._photos.append(_RowPhoto(path=path, pending=True))
            existing.add(key)
        self._refresh_photo_ui()
        self.photosChanged.emit()

    def _remove_photo(self, photo: _RowPhoto) -> None:
        if photo in self._photos:
            if not photo.pending and photo.stored_name and self._anomaly_id:
                attachment_manager.delete_anomaly_attachment(
                    self._anomaly_id, photo.stored_name
                )
                delete_links_for_filenames(self._anomaly_id, [photo.stored_name])
            self._photos.remove(photo)
            self._refresh_photo_ui()
            self.photosChanged.emit()

    def _refresh_photo_ui(self) -> None:
        self.btn_photos.setText(f"📷 {len(self._photos)}")
        while self.thumb_layout.count():
            item = self.thumb_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not self._photos:
            self.thumb_row.hide()
            return
        self.thumb_row.show()
        for photo in self._photos:
            holder = QWidget()
            holder_layout = QVBoxLayout(holder)
            holder_layout.setContentsMargins(0, 0, 0, 0)
            holder_layout.setSpacing(2)
            thumb = QLabel()
            thumb.setFixedSize(EVIDENCE_BULLET_THUMB_SIZE, EVIDENCE_BULLET_THUMB_SIZE)
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb.setProperty("role", "attachmentThumb")
            pixmap = QPixmap(str(photo.path))
            if not pixmap.isNull():
                thumb.setPixmap(
                    pixmap.scaled(
                        EVIDENCE_BULLET_THUMB_SIZE,
                        EVIDENCE_BULLET_THUMB_SIZE,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            holder_layout.addWidget(thumb)
            if not self._read_only_photos:
                remove_btn = QPushButton("移除")
                remove_btn.setProperty("variant", "dangerOutline")
                remove_btn.setFixedWidth(EVIDENCE_BULLET_THUMB_SIZE)
                remove_btn.clicked.connect(lambda _=False, p=photo: self._remove_photo(p))
                holder_layout.addWidget(remove_btn)
            self.thumb_layout.addWidget(holder)
        self.thumb_layout.addStretch(1)


class EvidenceBulletListWidget(BulletListWidget):
    """Bullet list where each row can own field photos linked by bullet index."""

    def __init__(self, placeholder: str = "新增條目...", parent=None):
        self._anomaly_id = ""
        self._row_hosts: list[QVBoxLayout] = []
        super().__init__(placeholder=placeholder, parent=parent)

    def add_item(self, text: str = "") -> EvidenceBulletListItemRow:
        index = len(self._rows) + 1
        host = QWidget()
        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(2)
        row = EvidenceBulletListItemRow(index=index, text=text, parent=self)
        row.set_anomaly_context(self._anomaly_id)
        row.set_photos_read_only(self._read_only)
        row.photosChanged.connect(self.valueChanged.emit)
        if self._read_only:
            row.line_edit.setReadOnly(True)
            row.btn_delete.setVisible(False)
        row.valueChanged.connect(self._on_row_value_changed)
        row.removeRequested.connect(self._remove_row)
        row.returnPressed.connect(self._on_row_return_pressed)
        row.attach_thumb_host(host_layout)
        host_layout.insertWidget(0, row)
        self._rows.append(row)
        self.items_layout.addWidget(host)
        self._row_hosts.append(host_layout)
        self._update_indices()
        self.items_layout.activate()
        self.items_layout.update()
        self.updateGeometry()
        self.valueChanged.emit()
        return row

    def set_anomaly_context(self, anomaly_id: str) -> None:
        self._anomaly_id = str(anomaly_id or "").strip()
        for row in self._rows:
            if isinstance(row, EvidenceBulletListItemRow):
                row.set_anomaly_context(self._anomaly_id)

    def set_items(self, items: list[str]):
        for row in list(self._rows):
            if isinstance(row, EvidenceBulletListItemRow):
                row.delete_all_photos()
        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows.clear()
        self._row_hosts.clear()

        if not items:
            self.add_item("")
        else:
            for item_text in items:
                self.add_item(item_text)
        self.items_layout.activate()
        self.items_layout.update()
        self.updateGeometry()
        self.valueChanged.emit()

    def _remove_row(self, row: BulletListItemRow):
        if len(self._rows) <= 1:
            if isinstance(row, EvidenceBulletListItemRow):
                row.delete_all_photos()
            row.set_text("")
            self.valueChanged.emit()
            return

        if isinstance(row, EvidenceBulletListItemRow):
            row.delete_all_photos()
        host_index = self._rows.index(row) if row in self._rows else -1
        if row in self._rows:
            self._rows.remove(row)
        if 0 <= host_index < len(self._row_hosts):
            host_layout = self._row_hosts.pop(host_index)
            host_widget = host_layout.parentWidget()
            if host_widget is not None:
                self.items_layout.removeWidget(host_widget)
                host_widget.deleteLater()
        row.deleteLater()
        self._update_indices()
        self.items_layout.activate()
        self.items_layout.update()
        self.updateGeometry()
        self.valueChanged.emit()

    def setReadOnly(self, read_only: bool):
        super().setReadOnly(read_only)
        for row in self._rows:
            if isinstance(row, EvidenceBulletListItemRow):
                row.set_photos_read_only(read_only)

    def load_row_photos(self, anomaly_id: str) -> None:
        key = (anomaly_id or "").strip()
        self.set_anomaly_context(key)
        if not key:
            return
        links = get_problem_photo_links(key)
        captions = attachment_manager.get_anomaly_captions(key)
        files = attachment_manager.list_anomaly_attachments(key)
        by_name = {path.name: path for path in files}
        for row in self._rows:
            if isinstance(row, EvidenceBulletListItemRow):
                row.clear_photos()
        for stored_name, bullet_index in links.items():
            path = by_name.get(stored_name)
            if path is None or not path.is_file():
                continue
            if bullet_index < 1 or bullet_index > len(self._rows):
                continue
            target = self._rows[bullet_index - 1]
            if not isinstance(target, EvidenceBulletListItemRow):
                continue
            target._photos.append(
                _RowPhoto(path=path, stored_name=stored_name, pending=False)
            )
            target._refresh_photo_ui()
        # Legacy photos without links are intentionally not loaded into rows.

    def save_photos_to_anomaly(self, anomaly_id: str) -> dict[str, int]:
        key = (anomaly_id or "").strip()
        if not key:
            return {}
        self.set_anomaly_context(key)
        links: dict[str, int] = {}
        bullet_index = 0
        for row in self._rows:
            if not isinstance(row, EvidenceBulletListItemRow):
                continue
            if not row.text():
                row.delete_all_photos()
                continue
            bullet_index += 1
            for photo in row._photos:
                if photo.pending:
                    stored = attachment_manager.import_single_anomaly_attachment(
                        key, photo.path
                    )
                    if stored is None:
                        continue
                    photo.path = stored
                    photo.stored_name = stored.name
                    photo.pending = False
                stored_name = photo.stored_name or photo.path.name
                links[stored_name] = bullet_index
        set_problem_photo_links(key, links)
        return links

    def get_row_photo_paths(self, index: int) -> list[Path]:
        if index < 1 or index > len(self._rows):
            return []
        row = self._rows[index - 1]
        if not isinstance(row, EvidenceBulletListItemRow):
            return []
        return [photo.path for photo in row.photos()]
