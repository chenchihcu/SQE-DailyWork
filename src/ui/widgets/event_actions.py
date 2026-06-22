from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from services import event_service
from ui.popup_i18n import localize_exception, localize_popup_message
from ui.window_sizing import fit_dialog_to_available_screen
from ui.widgets.defect_form_widget import (
    CloseAnomalyDialog,
    NewAnomalyDialog,
    NewVisitDialog,
)
from ui.widgets.common_widgets import apply_clickable_affordance

ACTION_EDIT_ANOMALY = "edit_anomaly"
ACTION_DELETE_ANOMALY = "delete_anomaly"
ACTION_CLOSE_ANOMALY = "close_anomaly"
ACTION_VIEW_LINKED_VISIT = "view_linked_visit"
ACTION_EDIT_VISIT = "edit_visit"
ACTION_DELETE_VISIT = "delete_visit"
ACTION_VIEW_VISIT_DETAIL = "view_visit_detail"
ACTION_PREVIEW_ANOMALY = "preview_anomaly"
ACTION_PREVIEW_VISIT = "preview_visit"
ACTION_REOPEN_ANOMALY = "reopen_anomaly"
ACTION_SEND_LINE = "send_line"


def build_event_action_menu(
    parent: QWidget,
    row: dict,
) -> tuple[QMenu, dict[QAction, str]]:
    menu = QMenu(parent)
    action_map: dict[QAction, str] = {}

    def _add_action(label: str, key: str) -> None:
        action = menu.addAction(label)
        if action is not None:
            action_map[action] = key

    event_type = str(row.get("event_type") or "").strip().upper()
    if event_type == "ANOMALY":
        _add_action("預覽內容", ACTION_PREVIEW_ANOMALY)
        _add_action("編輯異常", ACTION_EDIT_ANOMALY)
        _add_action("刪除異常", ACTION_DELETE_ANOMALY)
        if str(row.get("status") or "").strip() == "待處理":
            _add_action("結案", ACTION_CLOSE_ANOMALY)
        if str(row.get("status") or "").strip() == "已結案":
            _add_action("重新處理", ACTION_REOPEN_ANOMALY)
        if str(row.get("linked_visit_id") or "").strip():
            _add_action("關聯訪廠", ACTION_VIEW_LINKED_VISIT)
        menu.addSeparator()
        _add_action("傳送精簡報告至 LINE", ACTION_SEND_LINE)
        return menu, action_map

    if event_type == "VISIT":
        _add_action("預覽內容", ACTION_PREVIEW_VISIT)
        _add_action("編輯訪廠", ACTION_EDIT_VISIT)
        _add_action("刪除訪廠", ACTION_DELETE_VISIT)
        _add_action("明細", ACTION_VIEW_VISIT_DETAIL)
        menu.addSeparator()
        _add_action("傳送精簡報告至 LINE", ACTION_SEND_LINE)
    return menu, action_map


def _confirm_and_delete(parent: QWidget, item_type: str, item_name: str, delete_func: Callable[[], None], refresh_func: Callable[[], None]) -> None:
    box = QMessageBox(parent)
    box.setWindowTitle("確認刪除")
    box.setText(localize_popup_message(f"確定要刪除{item_type}「{item_name}」？\n此操作無法復原。"))
    box.setIcon(QMessageBox.Icon.Warning)
    btn_yes = box.addButton("刪除", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(btn_yes)
    box.exec()
    if box.clickedButton() is not btn_yes:
        return
    try:
        delete_func()
        refresh_func()
        QMessageBox.information(parent, "成功", localize_popup_message(f"{item_type}「{item_name}」已刪除"))
    except ValueError as exc:
        QMessageBox.warning(parent, "刪除失敗", localize_exception(exc))
    except Exception as exc:
        logger.exception("刪除%s失敗", item_type)
        QMessageBox.critical(
            parent,
            "錯誤",
            localize_popup_message(f"刪除{item_type}失敗：{localize_exception(exc)}"),
        )



def dispatch_event_action(
    action_key: str,
    row: dict,
    *,
    on_edit_anomaly: Callable[[str], None],
    on_delete_anomaly: Callable[[str, str], None],
    on_close_anomaly: Callable[[str, str], None],
    on_edit_visit: Callable[[str], None],
    on_delete_visit: Callable[[str, str], None],
    on_open_visit_detail: Callable[[str], None],
    on_preview_anomaly: Callable[[str], None] | None = None,
    on_preview_visit: Callable[[str], None] | None = None,
    on_reopen_anomaly: Callable[[str, str], None] | None = None,
    on_send_line: Callable[[dict], None] | None = None,
) -> None:
    event_id = str(row.get("event_id") or "").strip()
    if not event_id:
        return
    if action_key == ACTION_EDIT_ANOMALY:
        on_edit_anomaly(event_id)
        return
    if action_key == ACTION_DELETE_ANOMALY:
        on_delete_anomaly(event_id, str(row.get("ref_no") or ""))
        return
    if action_key == ACTION_CLOSE_ANOMALY:
        on_close_anomaly(event_id, str(row.get("content") or ""))
        return
    if action_key == ACTION_REOPEN_ANOMALY and on_reopen_anomaly:
        on_reopen_anomaly(event_id, str(row.get("ref_no") or ""))
        return
    if action_key == ACTION_VIEW_LINKED_VISIT:
        linked_visit_id = str(row.get("linked_visit_id") or "").strip()
        if linked_visit_id:
            on_open_visit_detail(linked_visit_id)
        return
    if action_key == ACTION_EDIT_VISIT:
        on_edit_visit(event_id)
        return
    if action_key == ACTION_DELETE_VISIT:
        on_delete_visit(event_id, str(row.get("event_date") or ""))
        return
    if action_key == ACTION_VIEW_VISIT_DETAIL:
        on_open_visit_detail(event_id)
        return
    if action_key == ACTION_PREVIEW_ANOMALY and on_preview_anomaly:
        on_preview_anomaly(event_id)
        return
    if action_key == ACTION_PREVIEW_VISIT and on_preview_visit:
        on_preview_visit(event_id)
        return
    if action_key == ACTION_SEND_LINE and on_send_line:
        on_send_line(row)
        return


class VisitDetailDialog(QDialog):
    """Visit-detail popup — fully styled by ui/theme.py via objectName + role props."""

    def __init__(self, visit: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("VisitDetailDialog")
        self.setWindowTitle(localize_popup_message("Visit detail"))
        self.setMinimumWidth(500)
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self._build_ui(visit)
        fit_dialog_to_available_screen(self, preferred_width=640)

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self, v: dict) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())
        body_scroll = QScrollArea()
        body_scroll.setObjectName("VisitDetailBodyScroll")
        body_scroll.setWidgetResizable(True)
        body_scroll.setFrameShape(QFrame.Shape.NoFrame)
        body_scroll.setWidget(self._build_body(v))
        root.addWidget(body_scroll, 1)
        root.addWidget(self._build_footer())

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("VisitDetailHeader")
        header.setFixedHeight(52)
        lay = QHBoxLayout(header)
        lay.setContentsMargins(20, 0, 20, 0)

        lay.addStretch()
        return header

    def _build_body(self, v: dict) -> QFrame:
        body = QFrame()
        body.setObjectName("VisitDetailBody")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(16, 14, 16, 10)
        lay.setSpacing(10)

        lay.addWidget(self._build_basic_info(v))
        lay.addWidget(self._build_tech_section(v))

        summary = (v.get("summary") or "").strip()
        if summary:
            lay.addWidget(self._build_summary_section(summary))
        if v.get("defect_notes") or v.get("product_sections"):
            lay.addWidget(self._build_defect_note_section(v))

        return body

    def _build_basic_info(self, v: dict) -> QFrame:
        """2×2 grid: date / supplier / work-order / production qty."""
        frame = self._card_frame()
        grid = QGridLayout(frame)
        grid.setContentsMargins(16, 12, 16, 12)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(2)

        work_order = (v.get("work_order_no") or "").strip() or "—"
        fields = [
            ("日期",    str(v.get("visit_date") or "—")),
            ("供應商",  str(v.get("supplier_name") or "—")),
            ("工單",    work_order),
            ("數量",    str(v.get("production_qty") or "0")),
        ]
        for i, (lbl_text, val_text) in enumerate(fields):
            row, col = divmod(i, 2)
            grid.addWidget(self._meta_label(lbl_text), row * 2,     col * 3)
            grid.addWidget(self._value_label(val_text), row * 2 + 1, col * 3)
            if col == 0:
                sep = QFrame()
                sep.setProperty("role", "separator")
                sep.setFixedWidth(1)
                grid.addWidget(sep, row * 2, 1, 2, 1)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(2, 0)
        grid.setColumnStretch(3, 1)
        return frame

    def _build_tech_section(self, v: dict) -> QFrame:
        frame = self._card_frame()
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        top_row.addWidget(self._meta_label("技轉狀態"))
        transferred = bool(v.get("tech_transfer", False))
        top_row.addWidget(self._status_badge("已技轉" if transferred else "未技轉", transferred))
        top_row.addStretch()
        lay.addLayout(top_row)

        rule = QFrame()
        rule.setProperty("role", "separator")
        rule.setFixedHeight(1)
        lay.addWidget(rule)

        items_grid = QGridLayout()
        items_grid.setHorizontalSpacing(12)
        items_grid.setVerticalSpacing(4)
        items = [
            ("作業標準書",    "tech_transfer_doc"),
            ("載具要求",      "carrier_requirement"),
            ("Underfill 要求", "dispensing_process"),
            ("電訊測試",      "functional_test"),
            ("包裝規範",      "packaging_requirement"),
        ]
        for i, (label, key) in enumerate(items):
            row, col = divmod(i, 2)
            has_it = bool(v.get(key, False))
            items_grid.addWidget(self._item_row(label, has_it), row, col)
        items_grid.setColumnStretch(0, 1)
        items_grid.setColumnStretch(1, 1)
        lay.addLayout(items_grid)
        return frame

    def _build_summary_section(self, summary: str) -> QFrame:
        frame = self._card_frame()
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(4)
        lay.addWidget(self._meta_label("摘要"))

        text = QLabel(summary)
        text.setWordWrap(True)
        text.setProperty("role", "summary")
        lay.addWidget(text)
        return frame

    def _build_defect_note_section(self, visit: dict) -> QFrame:
        frame = self._card_frame()
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(8)
        lay.addWidget(self._meta_label("缺失 / 改善紀錄"))

        visit_level = [
            item
            for item in list(visit.get("defect_notes") or [])
            if not str(item.get("visit_product_section_id") or "").strip()
        ]
        if visit_level:
            lay.addWidget(self._value_label("訪廠層級"))
            for note in visit_level:
                lay.addWidget(self._defect_note_label(note))

        for section in list(visit.get("product_sections") or []):
            notes = list(section.get("defect_notes") or [])
            if not notes:
                continue
            product_name = str(section.get("product_name") or "未指定產品").strip()
            lay.addWidget(self._value_label(product_name))
            for note in notes:
                lay.addWidget(self._defect_note_label(note))

        return frame

    def _defect_note_label(self, note: dict) -> QLabel:
        defect = str(note.get("defect_desc") or "").strip() or "-"
        improvement = str(note.get("improvement_desc") or "").strip() or "待補改善"
        remark = str(note.get("note") or "").strip()
        text = f"缺失：{defect}\n改善：{improvement}"
        if remark:
            text += f"\n備註：{remark}"
        label = QLabel(text)
        label.setWordWrap(True)
        label.setProperty("role", "summary")
        return label

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("VisitDetailFooter")
        lay = QHBoxLayout(footer)
        lay.setContentsMargins(16, 10, 16, 14)
        lay.addStretch()

        close_btn = QPushButton("關閉")
        close_btn.setMinimumWidth(88)
        close_btn.setProperty("role", "visitDetailClose")
        apply_clickable_affordance(close_btn, tooltip="關閉訪廠明細")
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn)
        return footer

    # ── Widget helpers ─────────────────────────────────────────────────────

    def _card_frame(self) -> QFrame:
        frame = QFrame()
        frame.setProperty("role", "visitDetailCard")
        return frame

    def _meta_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("role", "meta")
        return lbl

    def _value_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setProperty("role", "value")
        return lbl

    def _status_badge(self, text: str, is_positive: bool) -> QLabel:
        badge = QLabel(f"  {text}  ")
        badge.setProperty("role", "statusBadge")
        badge.setProperty("tone", "success" if is_positive else "pending")
        return badge

    def _item_row(self, label: str, has_it: bool) -> QFrame:
        row = QFrame()
        row.setObjectName("vdItemRow")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 3, 8, 3)
        lay.setSpacing(6)

        dot = QLabel("✓" if has_it else "–")
        dot.setFixedWidth(16)
        dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dot.setProperty("role", "techDot")
        if has_it:
            dot.setProperty("state", "on")

        name = QLabel(label)
        name.setProperty("role", "techName")
        if has_it:
            name.setProperty("state", "on")

        val = QLabel("有" if has_it else "沒有")
        val.setProperty("role", "techValue")
        if has_it:
            val.setProperty("state", "on")

        lay.addWidget(dot)
        lay.addWidget(name, stretch=1)
        lay.addWidget(val)
        return row


class EventActionsController:
    def __init__(self, parent: QWidget, main_window) -> None:
        self._parent = parent
        self._main_window = main_window

    def _refresh_all_views(self) -> None:
        refresh = getattr(self._main_window, "refresh_all_views", None)
        if callable(refresh):
            refresh()

    def open_close_dialog(self, anomaly_id: str, problem_desc: str) -> None:
        dialog = CloseAnomalyDialog(anomaly_id, problem_desc, self._parent)
        if not dialog.exec():
            return
        self._refresh_all_views()

    def open_edit_anomaly_dialog(self, anomaly_id: str) -> None:
        try:
            detail = event_service.get_anomaly_detail(anomaly_id)
            dialog = NewAnomalyDialog(
                self._parent,
                anomaly_id=anomaly_id,
                initial_data=detail,
            )
            if dialog.exec():
                self._refresh_all_views()
        except ValueError as exc:
            QMessageBox.warning(self._parent, "編輯失敗", localize_exception(exc))
        except Exception as exc:
            logger.exception("編輯異常失敗")
            QMessageBox.critical(
                self._parent,
                "錯誤",
                localize_popup_message(f"開啟異常編輯失敗：{localize_exception(exc)}"),
            )

    def delete_anomaly(self, anomaly_id: str, ref_no: str) -> None:
        ref_text = ref_no.strip() or anomaly_id
        _confirm_and_delete(
            self._parent, "異常單", ref_text,
            lambda: event_service.delete_anomaly(anomaly_id),
            self._refresh_all_views,
        )

    def open_edit_visit_dialog(self, visit_id: str) -> None:
        try:
            detail = event_service.get_visit_detail(visit_id)
            dialog = NewVisitDialog(
                self._parent,
                visit_id=visit_id,
                initial_data=detail,
            )
            if dialog.exec():
                self._refresh_all_views()
        except ValueError as exc:
            QMessageBox.warning(self._parent, "編輯失敗", localize_exception(exc))
        except Exception as exc:
            logger.exception("編輯訪廠失敗")
            QMessageBox.critical(
                self._parent,
                "錯誤",
                localize_popup_message(f"開啟訪廠編輯失敗：{localize_exception(exc)}"),
            )

    def delete_visit(self, visit_id: str, visit_date: str) -> None:
        date_text = visit_date.strip() or visit_id
        _confirm_and_delete(
            self._parent, "訪廠紀錄", date_text,
            lambda: event_service.delete_visit(visit_id),
            self._refresh_all_views,
        )

    def open_visit_detail(self, visit_id: str) -> None:
        try:
            visit = event_service.get_visit_detail(visit_id)
            dlg = VisitDetailDialog(visit, self._parent)
            dlg.exec()
        except ValueError as exc:
            QMessageBox.warning(self._parent, "查詢失敗", localize_exception(exc))
        except Exception as exc:
            logger.exception("讀取訪廠失敗")
            QMessageBox.critical(
                self._parent,
                "錯誤",
                localize_popup_message(f"讀取訪廠失敗：{localize_exception(exc)}"),
            )

    def open_preview_anomaly_dialog(self, anomaly_id: str) -> None:
        """Open the anomaly form in read-only mode."""
        try:
            detail = event_service.get_anomaly_detail(anomaly_id)
            dialog = NewAnomalyDialog(
                self._parent,
                anomaly_id=anomaly_id,
                initial_data=detail,
                read_only=True,
            )
            dialog.exec()
        except Exception as exc:
            logger.exception("開啟異常預覽失敗")
            QMessageBox.critical(
                self._parent,
                "錯誤",
                localize_popup_message(f"開啟預覽失敗：{localize_exception(exc)}"),
            )

    def open_preview_visit_dialog(self, visit_id: str) -> None:
        """Open the visit form in read-only mode."""
        try:
            detail = event_service.get_visit_detail(visit_id)
            dialog = NewVisitDialog(
                self._parent,
                visit_id=visit_id,
                initial_data=detail,
                read_only=True,
            )
            dialog.exec()
        except Exception as exc:
            logger.exception("開啟訪廠預覽失敗")
            QMessageBox.critical(
                self._parent,
                "錯誤",
                localize_popup_message(f"開啟預覽失敗：{localize_exception(exc)}"),
            )

    def reopen_anomaly(self, anomaly_id: str, ref_no: str) -> None:
        ref_text = ref_no.strip() or anomaly_id
        confirm = QMessageBox.question(
            self._parent,
            "確認重新處理",
            localize_popup_message(f"確定要將異常單「{ref_text}」設為「待處理」？\n原有的結案對策與日期將會被清除。"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            event_service.reopen_anomaly(anomaly_id)
            self._refresh_all_views()
            QMessageBox.information(
                self._parent,
                "成功",
                localize_popup_message(f"異常單「{ref_text}」已變更為待處理狀態"),
            )
        except ValueError as exc:
            QMessageBox.warning(self._parent, "操作失敗", localize_exception(exc))
        except Exception as exc:
            logger.exception("重新處理異常失敗")
            QMessageBox.critical(
                self._parent,
                "錯誤",
                localize_popup_message(f"重新處理失敗：{localize_exception(exc)}"),
            )
