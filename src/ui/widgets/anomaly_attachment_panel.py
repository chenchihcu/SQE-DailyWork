"""Evidence upload and metadata workflow for the anomaly workbench."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from database.repo_helpers import (
    ANOMALY_ATTACHMENT_CATEGORIES,
    ANOMALY_ATTACHMENT_CATEGORY_LABELS,
)
from services import attachment_manager
from services.event import _anomaly_workbench_service
from ui.layout_constants import CONTROL_ROW_SPACING, FORM_VERTICAL_SPACING, PANEL_MARGINS
from ui.widgets.common_widgets import EmptyStateWidget, apply_clickable_affordance
from ui.popup_i18n import localize_exception


def _automated_run() -> bool:
    return (
        os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen"
        or os.environ.get("SQE_TESTING", "").strip() == "1"
        or os.environ.get("SQE_PROBE", "").strip() == "1"
    )


class AttachmentMetadataDialog(QDialog):
    """Edit metadata and same-anomaly links without changing stored bytes."""

    def __init__(
        self,
        anomaly_id: str,
        row: dict,
        notes: list[dict],
        actions: list[dict],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("編輯附件資料")
        self.setModal(True)
        root = QVBoxLayout(self)
        root.setContentsMargins(*PANEL_MARGINS)
        root.setSpacing(FORM_VERTICAL_SPACING)

        form = QFormLayout()
        form.setVerticalSpacing(FORM_VERTICAL_SPACING)
        self.category_combo = QComboBox()
        for key in ANOMALY_ATTACHMENT_CATEGORIES:
            self.category_combo.addItem(
                ANOMALY_ATTACHMENT_CATEGORY_LABELS.get(key, key), key
            )
        current_category = str(row.get("category") or "Other")
        index = self.category_combo.findData(current_category)
        self.category_combo.setCurrentIndex(max(index, 0))

        self.description_input = QTextEdit()
        self.description_input.setPlainText(str(row.get("description") or ""))
        self.description_input.setFixedHeight(72)
        self.revision_input = QLineEdit(str(row.get("revision") or ""))

        self.note_combo = QComboBox()
        self.note_combo.addItem("（不關聯）", "")
        for note in notes:
            preview = str(note.get("content") or "").replace("\n", " ").strip()
            self.note_combo.addItem(
                f"{note.get('evidence_label') or note.get('evidence_type') or '紀錄'} — {preview[:30]}",
                str(note.get("id") or ""),
            )
        note_index = self.note_combo.findData(str(row.get("related_note_id") or ""))
        self.note_combo.setCurrentIndex(max(note_index, 0))

        self.action_combo = QComboBox()
        self.action_combo.addItem("（不關聯）", "")
        for action in actions:
            self.action_combo.addItem(
                f"{str(action.get('description') or 'Action')[:30]} — {action.get('execution_status') or '—'}",
                str(action.get("id") or ""),
            )
        action_index = self.action_combo.findData(str(row.get("related_action_id") or ""))
        self.action_combo.setCurrentIndex(max(action_index, 0))

        form.addRow("附件分類", self.category_combo)
        form.addRow("說明", self.description_input)
        form.addRow("版本", self.revision_input)
        form.addRow("關聯分析紀錄", self.note_combo)
        form.addRow("關聯 Action", self.action_combo)
        root.addLayout(form)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Save
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

    def payload(self) -> dict[str, str]:
        return {
            "category": str(self.category_combo.currentData() or "Other"),
            "description": self.description_input.toPlainText().strip(),
            "revision": self.revision_input.text().strip(),
            "related_note_id": str(self.note_combo.currentData() or "") or None,
            "related_action_id": str(self.action_combo.currentData() or "") or None,
        }


class EvidenceAttachmentPanel(QWidget):
    """Complete upload/list/edit/delete UI for registered anomaly evidence."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._anomaly_id = ""
        self._selected_path: Path | None = None
        self._rows: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(FORM_VERTICAL_SPACING)

        upload = QFrame()
        upload.setObjectName("EvidenceAttachmentUpload")
        upload_layout = QVBoxLayout(upload)
        upload_layout.setContentsMargins(*PANEL_MARGINS)
        upload_layout.setSpacing(FORM_VERTICAL_SPACING)

        self.file_button = QPushButton("選擇檔案…")
        self.file_button.setAccessibleName("選擇 Evidence 檔案")
        self.file_button.setProperty("variant", "secondary")
        self.file_button.clicked.connect(self._choose_file)
        self.file_name_label = QLabel("尚未選擇檔案")
        self.file_name_label.setProperty("role", "value")

        self.category_combo = QComboBox()
        for key in ANOMALY_ATTACHMENT_CATEGORIES:
            self.category_combo.addItem(
                ANOMALY_ATTACHMENT_CATEGORY_LABELS.get(key, key), key
            )
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("此附件用途？")
        self.description_input.setFixedHeight(66)
        self.revision_input = QLineEdit()
        self.revision_input.setPlaceholderText("如 Rev A")
        self.note_combo = QComboBox()
        self.action_combo = QComboBox()
        self.upload_button = QPushButton("上傳")
        self.upload_button.setAccessibleName("上傳 Evidence")
        self.upload_button.setProperty("variant", "primary")
        self.upload_button.setEnabled(False)
        self.upload_button.clicked.connect(self._upload)

        form = QFormLayout()
        form.setVerticalSpacing(FORM_VERTICAL_SPACING)
        file_row = QHBoxLayout()
        file_row.setSpacing(CONTROL_ROW_SPACING)
        file_row.addWidget(self.file_button)
        file_row.addWidget(self.file_name_label, 1)
        form.addRow("檔案", file_row)
        form.addRow("附件分類", self.category_combo)
        form.addRow("說明", self.description_input)
        form.addRow("版本", self.revision_input)
        form.addRow("關聯分析紀錄", self.note_combo)
        form.addRow("關聯 Action", self.action_combo)
        upload_layout.addLayout(form)
        upload_layout.addWidget(self.upload_button, 0, Qt.AlignmentFlag.AlignLeft)
        root.addWidget(upload)

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(FORM_VERTICAL_SPACING)
        root.addWidget(self.list_container)
        root.addStretch(1)

        for button in (self.file_button, self.upload_button):
            apply_clickable_affordance(button, tooltip=button.text())

    def set_anomaly(self, anomaly_id: str) -> None:
        self._anomaly_id = str(anomaly_id or "").strip()
        self._selected_path = None
        self.file_name_label.setText("尚未選擇檔案")
        self.upload_button.setEnabled(False)
        self._load_link_options()
        self.refresh()

    def _load_link_options(self) -> None:
        self.note_combo.clear()
        self.note_combo.addItem("（不關聯）", "")
        self.action_combo.clear()
        self.action_combo.addItem("（不關聯）", "")
        if not self._anomaly_id:
            return
        for note in _anomaly_workbench_service.list_attachment_notes(self._anomaly_id):
            preview = str(note.get("content") or "").replace("\n", " ").strip()
            self.note_combo.addItem(
                f"{note.get('evidence_label') or note.get('evidence_type') or '紀錄'} — {preview[:30]}",
                str(note.get("id") or ""),
            )
        for action in _anomaly_workbench_service.list_attachment_actions(self._anomaly_id):
            self.action_combo.addItem(
                f"{str(action.get('description') or 'Action')[:30]} — {action.get('execution_status') or '—'}",
                str(action.get("id") or ""),
            )

    def _choose_file(self) -> None:
        path_text, _ = QFileDialog.getOpenFileName(
            self,
            "選擇 Evidence 檔案",
            "",
            "支援的附件 (*.jpg *.jpeg *.png *.csv *.doc *.docx *.json *.log *.pdf *.ppt *.pptx *.txt *.xls *.xlsx *.yaml *.yml)",
        )
        if not path_text:
            return
        path = Path(path_text)
        if path.suffix.lower() not in attachment_manager.ALLOWED_ATTACHMENT_SUFFIXES:
            QMessageBox.warning(self, "無法上傳附件", "附件格式不受支援。")
            return
        self._selected_path = path
        self.file_name_label.setText(path.name)
        self.file_name_label.setToolTip(str(path))
        self.upload_button.setEnabled(bool(self._anomaly_id))

    def _upload(self) -> None:
        if self._selected_path is None or not self._anomaly_id:
            return
        self.upload_button.setEnabled(False)
        try:
            _anomaly_workbench_service.import_attachment_from_file(
                anomaly_id=self._anomaly_id,
                source_path=self._selected_path,
                category=str(self.category_combo.currentData() or "Other"),
                description=self.description_input.toPlainText().strip(),
                revision=self.revision_input.text().strip(),
                uploaded_by="local_user",
                related_note_id=str(self.note_combo.currentData() or "") or None,
                related_action_id=str(self.action_combo.currentData() or "") or None,
            )
        except Exception as exc:
            self.upload_button.setEnabled(True)
            QMessageBox.warning(self, "附件上傳失敗", localize_exception(exc))
            return
        self._selected_path = None
        self.file_name_label.setText("尚未選擇檔案")
        self.description_input.clear()
        self.revision_input.clear()
        self.refresh()
        self.changed.emit()

    def refresh(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        if not self._anomaly_id:
            return
        self._rows = _anomaly_workbench_service.list_attachments(self._anomaly_id)
        if not self._rows:
            self.list_layout.addWidget(
                EmptyStateWidget("尚未上傳附件", "可從上方選擇 Evidence 檔案。")
            )
            self.list_layout.addStretch(1)
            return
        for row in self._rows:
            self.list_layout.addWidget(self._build_row(row))
        self.list_layout.addStretch(1)

    def _build_row(self, row: dict) -> QWidget:
        card = QFrame()
        card.setObjectName("EvidenceAttachmentRow")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(*PANEL_MARGINS)
        layout.setSpacing(4)
        filename = str(row.get("file_name") or "—")
        title = QLabel(
            f"{filename}　·　{row.get('category_label') or row.get('category') or '其他'}"
        )
        title.setProperty("role", "sectionTitle")
        title.setWordWrap(True)
        layout.addWidget(title)
        state = str(row.get("storage_state") or "present")
        state_text = {
            "present": "儲存狀態：存在",
            "missing": "儲存狀態：檔案遺失",
        }.get(state, f"儲存狀態：{state}")
        if row.get("legacy_physical"):
            state_text = "未登錄實體檔（legacy physical）"
        details = QLabel(
            f"{state_text}　大小：{row.get('file_size') or 0} bytes　"
            f"版本：{row.get('revision') or '—'}\n"
            f"說明：{row.get('description') or '—'}"
        )
        details.setWordWrap(True)
        details.setProperty("role", "value")
        layout.addWidget(details)
        links = []
        if row.get("related_note_id"):
            links.append(f"關聯分析紀錄：{row.get('related_note_id')}")
        if row.get("related_action_id"):
            links.append(f"關聯 Action：{row.get('related_action_id')}")
        if links:
            link_label = QLabel("　".join(links))
            link_label.setWordWrap(True)
            link_label.setProperty("role", "meta")
            layout.addWidget(link_label)

        if not row.get("legacy_physical") and row.get("id"):
            commands = QHBoxLayout()
            edit_button = QPushButton("編輯資料")
            edit_button.setProperty("variant", "secondary")
            edit_button.clicked.connect(lambda _=False, item=dict(row): self._edit(item))
            delete_button = QPushButton("刪除附件")
            delete_button.setProperty("variant", "secondary")
            delete_button.clicked.connect(lambda _=False, item=dict(row): self._delete(item))
            commands.addWidget(edit_button)
            commands.addWidget(delete_button)
            commands.addStretch(1)
            layout.addLayout(commands)
        return card

    def _edit(self, row: dict) -> None:
        dialog = AttachmentMetadataDialog(
            self._anomaly_id,
            row,
            _anomaly_workbench_service.list_attachment_notes(self._anomaly_id),
            _anomaly_workbench_service.list_attachment_actions(self._anomaly_id),
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            _anomaly_workbench_service.update_attachment(
                anomaly_id=self._anomaly_id,
                attachment_id=str(row.get("id") or ""),
                actor_name="local_user",
                **dialog.payload(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "附件資料更新失敗", localize_exception(exc))
            return
        self.refresh()
        self.changed.emit()

    def _delete(self, row: dict) -> None:
        filename = str(row.get("file_name") or "附件")
        if not _automated_run():
            answer = QMessageBox.question(
                self,
                "刪除附件",
                f"確定要刪除『{filename}』嗎？此操作可能無法復原。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            result = _anomaly_workbench_service.delete_attachment(
                anomaly_id=self._anomaly_id,
                attachment_id=str(row.get("id") or ""),
                actor_name="local_user",
            )
        except Exception as exc:
            QMessageBox.warning(self, "附件刪除失敗", localize_exception(exc))
            return
        warnings = list(result.get("warnings") or [])
        if warnings:
            QMessageBox.warning(self, "附件已刪除但有警告", "\n".join(warnings))
        self.refresh()
        self.changed.emit()
