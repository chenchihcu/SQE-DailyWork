from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMenu,
    QMessageBox,
    QWidget,
)

from services.event import _anomaly_service, _visit_service
from ui.popup_i18n import localize_exception, localize_popup_message
from ui.widgets.defect_form_shim import CloseAnomalyDialog
from ui.widgets.reopen_anomaly_dialog import ReopenAnomalyDialog
from ui.widgets.new_anomaly_dialog import NewAnomalyDialog
from ui.widgets.new_visit_dialog import NewVisitDialog
from ui.widgets.common_widgets import safe_ui_operation
from ui.widgets.visit_detail_dialog import VisitDetailDialog

ACTION_EDIT_ANOMALY = "edit_anomaly"
ACTION_DELETE_ANOMALY = "delete_anomaly"
ACTION_CLOSE_ANOMALY = "close_anomaly"
ACTION_VIEW_LINKED_VISIT = "view_linked_visit"
ACTION_EDIT_VISIT = "edit_visit"
ACTION_DELETE_VISIT = "delete_visit"
ACTION_VIEW_VISIT_DETAIL = "view_visit_detail"
ACTION_VIEW_ANOMALY_DETAILS = "view_anomaly_details"
ACTION_PREVIEW_VISIT = "preview_visit"
ACTION_REOPEN_ANOMALY = "reopen_anomaly"
ACTION_UPDATE_CLOSED_AT = "update_closed_at"
ACTION_SEND_LINE = "send_line"


def build_event_action_menu(
    parent: QWidget,
    row: dict,
) -> tuple[QMenu, dict[QAction, str]]:
    menu = QMenu(parent)
    action_map: dict[QAction, str] = {}

    def _add_action(label: str, key: str) -> None:
        action_map[menu.addAction(label)] = key

    event_type = str(row.get("event_type") or "").strip().upper()
    if event_type == "ANOMALY":
        _add_action("案件詳情", ACTION_VIEW_ANOMALY_DETAILS)
        _add_action("編輯異常", ACTION_EDIT_ANOMALY)
        _add_action("刪除異常", ACTION_DELETE_ANOMALY)
        if str(row.get("status") or "").strip() == "待處理":
            _add_action("結案", ACTION_CLOSE_ANOMALY)
        if str(row.get("status") or "").strip() == "已結案":
            _add_action("調整結案日期", ACTION_UPDATE_CLOSED_AT)
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


def _confirm_and_delete(
    parent: QWidget,
    item_type: str,
    item_name: str,
    delete_func: Callable[[], None],
    refresh_func: Callable[[], None],
) -> None:
    try:
        from services.appearance_preferences_service import load_application_preferences
        prefs = load_application_preferences()
        require_confirm = prefs.confirm_on_delete
    except Exception:
        require_confirm = True

    if require_confirm:
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
    on_view_anomaly_details: Callable[[str], None] | None = None,
    on_preview_visit: Callable[[str], None] | None = None,
    on_reopen_anomaly: Callable[[str, str], None] | None = None,
    on_update_closed_at: Callable[[str, str], None] | None = None,
    on_send_line: Callable[[dict], None] | None = None,
) -> None:
    event_id = str(row.get("event_id") or "").strip()
    if not event_id:
        return
    if action_key == ACTION_VIEW_ANOMALY_DETAILS and on_view_anomaly_details:
        on_view_anomaly_details(event_id)
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
    if action_key == ACTION_UPDATE_CLOSED_AT and on_update_closed_at:
        on_update_closed_at(event_id, str(row.get("content") or ""))
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
    if action_key == ACTION_PREVIEW_VISIT and on_preview_visit:
        on_preview_visit(event_id)
        return
    if action_key == ACTION_SEND_LINE and on_send_line:
        on_send_line(row)
        return


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

    def open_update_closed_at_dialog(self, anomaly_id: str, problem_desc: str) -> None:
        dialog = CloseAnomalyDialog(
            anomaly_id,
            problem_desc,
            self._parent,
            date_adjustment_only=True,
        )
        if not dialog.exec():
            return
        self._refresh_all_views()

    def open_edit_anomaly_dialog(self, anomaly_id: str) -> None:
        open_management = getattr(self._main_window, "open_anomaly_management", None)
        if callable(open_management):
            open_management(anomaly_id, edit=True)
            return
        def _op() -> None:
            detail = _anomaly_service.get_anomaly_detail(anomaly_id)
            dialog = NewAnomalyDialog(
                self._parent,
                anomaly_id=anomaly_id,
                initial_data=detail,
            )
            if dialog.exec():
                self._refresh_all_views()
        safe_ui_operation(
            self._parent,
            _op,
            warning_title="編輯失敗",
            logger_msg="編輯異常失敗",
            error_msg="開啟異常編輯失敗：",
        )

    def open_anomaly_details(self, anomaly_id: str, *, edit: bool = False) -> None:
        """Open the single anomaly workbench route."""
        open_management = getattr(self._main_window, "open_anomaly_management", None)
        if callable(open_management):
            open_management(anomaly_id, edit=edit)
            return
        QMessageBox.warning(
            self._parent,
            "無法開啟案件詳情",
            "目前視窗未提供異常案件管理頁。",
        )

    def delete_anomaly(self, anomaly_id: str, ref_no: str) -> None:
        ref_text = ref_no.strip() or anomaly_id
        _confirm_and_delete(
            self._parent, "異常單", ref_text,
            lambda: _anomaly_service.delete_anomaly(anomaly_id),
            self._refresh_all_views,
        )

    def open_edit_visit_dialog(self, visit_id: str) -> None:
        def _op() -> None:
            detail = _visit_service.get_visit_detail(visit_id)
            dialog = NewVisitDialog(
                self._parent,
                visit_id=visit_id,
                initial_data=detail,
            )
            if dialog.exec():
                self._refresh_all_views()
        safe_ui_operation(
            self._parent,
            _op,
            warning_title="編輯失敗",
            logger_msg="編輯訪廠失敗",
            error_msg="開啟訪廠編輯失敗：",
        )

    def delete_visit(self, visit_id: str, visit_date: str) -> None:
        date_text = visit_date.strip() or visit_id
        _confirm_and_delete(
            self._parent, "訪廠紀錄", date_text,
            lambda: _visit_service.delete_visit(visit_id),
            self._refresh_all_views,
        )

    def open_visit_detail(self, visit_id: str) -> None:
        def _op() -> None:
            visit = _visit_service.get_visit_detail(visit_id)
            dlg = VisitDetailDialog(visit, self._parent)
            dlg.exec()
        safe_ui_operation(
            self._parent, _op,
            warning_title="查詢失敗",
            logger_msg="讀取訪廠失敗",
            error_msg="讀取訪廠失敗：",
        )

    def open_preview_visit_dialog(self, visit_id: str) -> None:
        """Open the visit form in read-only mode."""
        try:
            detail = _visit_service.get_visit_detail(visit_id)
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
        dialog = ReopenAnomalyDialog(anomaly_id, ref_no, self._parent)
        if not dialog.exec():
            return
        self._refresh_all_views()
