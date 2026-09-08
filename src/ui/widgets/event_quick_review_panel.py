"""Quick Review side panel for the consolidated event query page."""

from __future__ import annotations

import logging
from pathlib import Path
from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from services import attachment_manager
from services.event import _anomaly_service, _anomaly_workbench_service
from ui.layout_constants import (
    CONTROL_ROW_SPACING,
    EVENT_LIST_PREVIEW_THUMB_SIZE,
    FORM_VERTICAL_SPACING,
    PANEL_MARGINS,
)
from ui.widgets.common_widgets import (
    CaseStageStepper,
    EmptyStateWidget,
    apply_clickable_affordance,
    create_section_card,
    create_status_item,
)
from ui.widgets.event_next_action import (
    HANDLER_OPEN_FULL,
    NextActionSpec,
    resolve_next_action,
)

logger = logging.getLogger(__name__)


def _parse_due_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    if "T" in text:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def format_due_countdown(due_value: object, *, now: datetime | None = None) -> str:
    due_dt = _parse_due_datetime(due_value)
    if due_dt is None:
        return ""
    current = now or datetime.now()
    delta = due_dt - current
    total_minutes = int(delta.total_seconds() // 60)
    if total_minutes >= 0:
        hours, minutes = divmod(total_minutes, 60)
        if hours:
            return f"剩餘 {hours} 小時 {minutes} 分"
        return f"剩餘 {minutes} 分"
    overdue_minutes = abs(total_minutes)
    hours, minutes = divmod(overdue_minutes, 60)
    if hours:
        return f"已逾期 {hours} 小時 {minutes} 分"
    return f"已逾期 {minutes} 分"


class EventQuickReviewPanel(QWidget):
    """Read-only preview for a selected supplier-event anomaly row."""

    primary_action_requested = Signal(str, dict)
    open_full_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("EventQuickReviewPanel")
        self._row: dict[str, Any] = {}
        self._overview: dict[str, Any] = {}
        self._detail: dict[str, Any] = {}
        self._next_action = NextActionSpec("開啟完整案件", HANDLER_OPEN_FULL)
        self._due_value: object = None
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(60_000)
        self._countdown_timer.timeout.connect(self._refresh_countdown_text)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(CONTROL_ROW_SPACING)

        title = QLabel("快速審閱")
        title.setProperty("role", "sectionTitle")
        root.addWidget(title)

        self._empty_state = EmptyStateWidget(
            "請選取一筆異常",
            "右側將顯示案件摘要、階段進度與下一步建議。",
            parent=self,
        )
        root.addWidget(self._empty_state)

        self._content_scroll = QScrollArea()
        self._content_scroll.setObjectName("EventQuickReviewScroll")
        self._content_scroll.setWidgetResizable(True)
        self._content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._content_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._content_body = QWidget()
        self._content_body.setObjectName("EventQuickReviewBody")
        body = QVBoxLayout(self._content_body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(FORM_VERTICAL_SPACING)

        self._header_card = create_section_card(self._content_body)
        header_layout = self._header_card.layout()
        assert header_layout is not None
        header_layout.setContentsMargins(*PANEL_MARGINS)
        self._ref_label = QLabel()
        self._ref_label.setProperty("role", "title")
        self._ref_label.setWordWrap(True)
        header_layout.addWidget(self._ref_label)
        badge_row = QHBoxLayout()
        badge_row.setSpacing(CONTROL_ROW_SPACING)
        self._status_host = QWidget()
        self._status_layout = QHBoxLayout(self._status_host)
        self._status_layout.setContentsMargins(0, 0, 0, 0)
        self._status_layout.setSpacing(CONTROL_ROW_SPACING)
        badge_row.addWidget(self._status_host)
        badge_row.addStretch(1)
        header_layout.addLayout(badge_row)
        self._meta_label = QLabel()
        self._meta_label.setProperty("role", "value")
        self._meta_label.setWordWrap(True)
        header_layout.addWidget(self._meta_label)
        body.addWidget(self._header_card)

        self.stage_stepper = CaseStageStepper(self._content_body)
        body.addWidget(self.stage_stepper)

        self._action_card = create_section_card(self._content_body)
        action_layout = self._action_card.layout()
        assert action_layout is not None
        action_layout.setContentsMargins(*PANEL_MARGINS)
        action_title = QLabel("下一步處置")
        action_title.setProperty("role", "sectionTitle")
        action_layout.addWidget(action_title)
        self._action_desc = QLabel()
        self._action_desc.setProperty("role", "value")
        self._action_desc.setWordWrap(True)
        action_layout.addWidget(self._action_desc)
        self._due_label = QLabel()
        self._due_label.setProperty("role", "helperText")
        self._due_label.setWordWrap(True)
        action_layout.addWidget(self._due_label)
        self._countdown_frame = QFrame()
        self._countdown_frame.setObjectName("EventQuickReviewCountdown")
        self._countdown_frame.setProperty("role", "pendingBanner")
        countdown_layout = QVBoxLayout(self._countdown_frame)
        countdown_layout.setContentsMargins(8, 6, 8, 6)
        self._countdown_label = QLabel()
        self._countdown_label.setProperty("role", "value")
        self._countdown_label.setWordWrap(True)
        countdown_layout.addWidget(self._countdown_label)
        action_layout.addWidget(self._countdown_frame)
        body.addWidget(self._action_card)

        self._evidence_card = create_section_card(self._content_body)
        evidence_layout = self._evidence_card.layout()
        assert evidence_layout is not None
        evidence_layout.setContentsMargins(*PANEL_MARGINS)
        self._evidence_title = QLabel("現場證據")
        self._evidence_title.setProperty("role", "sectionTitle")
        evidence_layout.addWidget(self._evidence_title)
        self._thumb_row = QHBoxLayout()
        self._thumb_row.setSpacing(CONTROL_ROW_SPACING)
        self._thumb_labels: list[QLabel] = []
        for _index in range(3):
            thumb = QLabel()
            thumb.setFixedSize(EVENT_LIST_PREVIEW_THUMB_SIZE, EVENT_LIST_PREVIEW_THUMB_SIZE)
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb.setProperty("role", "attachmentThumb")
            thumb.setScaledContents(True)
            thumb.hide()
            self._thumb_labels.append(thumb)
            self._thumb_row.addWidget(thumb)
        self._thumb_row.addStretch(1)
        evidence_layout.addLayout(self._thumb_row)
        self._evidence_empty = QLabel("尚無附件")
        self._evidence_empty.setProperty("role", "muted")
        evidence_layout.addWidget(self._evidence_empty)
        body.addWidget(self._evidence_card)

        body.addStretch(1)
        self._content_scroll.setWidget(self._content_body)
        root.addWidget(self._content_scroll, 1)

        command_row = QHBoxLayout()
        command_row.setSpacing(CONTROL_ROW_SPACING)
        command_row.addStretch(1)
        self.open_full_button = QPushButton("開啟完整案件")
        self.open_full_button.setAccessibleName("開啟完整案件")
        self.open_full_button.setProperty("variant", "secondary")
        apply_clickable_affordance(
            self.open_full_button,
            tooltip="開啟完整案件管理頁",
        )
        self.open_full_button.clicked.connect(self._emit_open_full)
        self.primary_button = QPushButton("開啟完整案件")
        self.primary_button.setAccessibleName("快速審閱主操作")
        self.primary_button.setProperty("variant", "primary")
        apply_clickable_affordance(self.primary_button, tooltip="執行建議的下一步操作")
        self.primary_button.clicked.connect(self._emit_primary_action)
        command_row.addWidget(self.open_full_button)
        command_row.addWidget(self.primary_button)
        root.addLayout(command_row)

        self._content_scroll.hide()
        self.open_full_button.hide()
        self.primary_button.hide()

    def clear(self) -> None:
        self._row = {}
        self._overview = {}
        self._detail = {}
        self._due_value = None
        self._countdown_timer.stop()
        self._empty_state.show()
        self._content_scroll.hide()
        self.open_full_button.hide()
        self.primary_button.hide()

    def load_from_row(self, row: dict | None) -> None:
        if not row:
            self.clear()
            return
        event_type = str(row.get("event_type") or "").strip().upper()
        anomaly_id = str(row.get("event_id") or row.get("id") or "").strip()
        if event_type != "ANOMALY" or not anomaly_id:
            self.clear()
            return

        self._row = dict(row)
        self._overview = self._build_overview_from_row(row)
        try:
            self._detail = _anomaly_service.get_anomaly_detail(anomaly_id)
            self._overview = _anomaly_workbench_service.get_overview_card(anomaly_id)
        except Exception:
            logger.exception("Quick Review 載入案件資料失敗")
            self._detail = dict(row)
        self._render()

    def refresh(self) -> None:
        if not self._row:
            return
        self.load_from_row(self._row)

    def set_preview_collapsed(self, collapsed: bool) -> None:
        if collapsed:
            self._content_scroll.hide()
            self._empty_state.hide()
            self.open_full_button.hide()
            self.primary_button.hide()
        elif self._row:
            self._render()
        else:
            self.clear()

    def _build_overview_from_row(self, row: dict) -> dict[str, Any]:
        return {
            "overdue": bool(row.get("overdue")),
            "current_action": row.get("current_action"),
            "open_action_count": int(row.get("open_action_count") or 0),
            "root_cause_status": row.get("root_cause_status"),
            "corrective_action_status": row.get("corrective_action_status"),
            "verification_result": row.get("verification_result"),
            "attachment_count": int(row.get("attachment_count") or 0),
        }

    def _render(self) -> None:
        row = self._row
        overview = self._overview
        detail = self._detail
        anomaly_id = str(row.get("event_id") or row.get("id") or "").strip()

        self._empty_state.hide()
        self._content_scroll.show()
        self.open_full_button.show()
        self.primary_button.show()

        ref_no = str(row.get("ref_no") or detail.get("anomaly_no") or anomaly_id)
        self._ref_label.setText(ref_no)
        supplier = str(row.get("supplier_name") or detail.get("supplier_name") or "—")
        product_code = str(row.get("product_code") or detail.get("product_code") or "—")
        stage = str(row.get("product_stage") or detail.get("product_stage") or "—")
        category = str(row.get("category") or detail.get("category") or "—")
        self._meta_label.setText(f"{supplier} · {product_code} · {stage}\n類別：{category}")

        while self._status_layout.count():
            item = self._status_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        status = str(row.get("status") or detail.get("status") or "—")
        status_label = QLabel(status)
        status_label.setProperty("role", "statusBadge")
        palette_item = create_status_item(status)
        status_label.setStyleSheet(
            f"color: {palette_item.foreground().color().name()};"
            f"background-color: {palette_item.background().color().name()};"
            "padding: 2px 8px; border-radius: 4px;"
        )
        self._status_layout.addWidget(status_label)
        if bool(overview.get("overdue")) and status == "待處理":
            overdue_label = QLabel("逾期")
            overdue_label.setProperty("role", "statusBadge")
            overdue_palette = create_status_item("逾期")
            overdue_label.setStyleSheet(
                f"color: {overdue_palette.foreground().color().name()};"
                f"background-color: {overdue_palette.background().color().name()};"
                "padding: 2px 8px; border-radius: 4px;"
            )
            self._status_layout.addWidget(overdue_label)

        self.stage_stepper.set_case_state(detail, overview)

        current = overview.get("current_action") or {}
        action_text = str(
            current.get("description")
            or detail.get("pending_items")
            or row.get("content")
            or "—"
        )
        self._action_desc.setText(action_text)
        due_date = current.get("due_date") or ""
        self._due_value = due_date
        if due_date:
            self._due_label.setText(f"到期：{due_date}")
            self._due_label.show()
        else:
            self._due_label.hide()
        self._refresh_countdown_text()
        if due_date:
            self._countdown_timer.start()
        else:
            self._countdown_timer.stop()

        self._render_thumbnails(anomaly_id, int(overview.get("attachment_count") or 0))

        self._next_action = resolve_next_action(overview, detail)
        self.primary_button.setText(self._next_action.label)
        self.primary_button.setAccessibleName(self._next_action.label)

    def _render_thumbnails(self, anomaly_id: str, attachment_count: int) -> None:
        for label in self._thumb_labels:
            label.hide()
            label.clear()
        if attachment_count <= 0:
            self._evidence_title.setText("現場證據")
            self._evidence_empty.setText("尚無附件")
            self._evidence_empty.show()
            return
        self._evidence_empty.hide()
        self._evidence_title.setText(f"現場證據 ({attachment_count})")
        try:
            attachments = _anomaly_workbench_service.list_attachments(anomaly_id)
        except Exception:
            logger.exception("Quick Review 讀取附件失敗")
            attachments = []
        shown = 0
        for attachment in attachments:
            if shown >= len(self._thumb_labels):
                break
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
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                continue
            label = self._thumb_labels[shown]
            label.setPixmap(
                pixmap.scaled(
                    EVENT_LIST_PREVIEW_THUMB_SIZE,
                    EVENT_LIST_PREVIEW_THUMB_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            label.setToolTip(stored_name)
            label.show()
            shown += 1
        if shown == 0:
            self._evidence_empty.setText(
                f"附件 {attachment_count} 筆（無可預覽圖片）"
            )
            self._evidence_empty.show()

    def _refresh_countdown_text(self) -> None:
        if not self._due_value:
            self._countdown_frame.hide()
            return
        text = format_due_countdown(self._due_value)
        if not text:
            self._countdown_frame.hide()
            return
        self._countdown_label.setText(text)
        self._countdown_frame.show()

    def _emit_open_full(self) -> None:
        anomaly_id = str(self._row.get("event_id") or self._row.get("id") or "").strip()
        if anomaly_id:
            self.open_full_requested.emit(anomaly_id)

    def _emit_primary_action(self) -> None:
        if not self._row:
            return
        self.primary_action_requested.emit(self._next_action.handler_key, dict(self._row))
