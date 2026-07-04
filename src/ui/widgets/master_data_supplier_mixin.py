"""供應商基礎資料管理 Mixin。

從 MasterDataWidget 中提取所有供應商專屬的方法，
透過多重繼承注入回原 widget。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QMenu,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services import event_service
from ui.popup_i18n import localize_exception, localize_popup_message
from ui.widgets.common_widgets import (
    apply_table_action_affordance,
    create_status_item,
    safe_ui_operation,
    style_table,
    text_table_item,
)
from ui.widgets.supplier_form_dialog import SupplierFormDialog
from ui.widgets.pagination_bar import PaginationBar


class _MasterDataSupplierMixin:
    """提供供應商管理的 UI 建構與 CRUD 操作。

    透過多重繼承與 MasterDataWidget 組合使用：
        class MasterDataWidget(QWidget, _MasterDataSupplierMixin, _MasterDataProductMixin):
            ...

    方法會透過 self 存取主 Widget 提供的以下屬性/方法：
    - self.main_window              (set in __init__)
    - self._supplier_rows           (set by refresh_data)
    - self._selected_supplier_id    (set by _on_supplier_selected)
    - self._supplier_page / _supplier_page_size
    - self._find_supplier_row()     (shared method in core)
    - self._selected_table_ids()    (shared method in core)
    - self._table_menu_pos()        (shared method in core)
    - self._select_single_row()     (shared method in core)
    - self._create_toolbar_button() (shared method in core)
    - self._set_toggle_button_state() (shared method in core)
    - self._focus_master_query()    (shared method in core)
    """

    # ── UI 建構 ──────────────────────────────────────────

    def _build_supplier_actions_row(self) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        self.btn_supplier_create = self._create_toolbar_button(
            "新增",
            tooltip="新增供應商",
            variant="toolbarPrimary",
            on_click=self._create_supplier,
        )
        self.btn_supplier_update = self._create_toolbar_button(
            "更新",
            tooltip="更新供應商",
            variant="toolbarSecondary",
            on_click=self._update_supplier,
        )
        self.btn_supplier_toggle = self._create_toolbar_button(
            "停用",
            tooltip="停用供應商",
            variant="toolbarSecondary",
            on_click=self._toggle_supplier_active,
        )
        self.btn_supplier_delete = self._create_toolbar_button(
            "刪除",
            tooltip="刪除供應商",
            variant="toolbarSecondary",
            on_click=self._delete_supplier,
        )
        self.btn_supplier_delete_selected = self._create_toolbar_button(
            "刪選",
            tooltip="刪除選取供應商",
            variant="toolbarSecondary",
            on_click=self._delete_selected_suppliers,
        )
        self.btn_supplier_filter = self._create_toolbar_button(
            "篩選",
            tooltip="聚焦關鍵字篩選欄",
            variant="toolbarSecondary",
            on_click=self._focus_master_query,
        )
        self.btn_supplier_clear = self._create_toolbar_button(
            "清空",
            tooltip="清空供應商選取",
            variant="toolbarGhost",
            on_click=self._clear_supplier_form,
        )

        row_layout.addWidget(self.btn_supplier_create)
        row_layout.addWidget(self.btn_supplier_update)
        row_layout.addWidget(self.btn_supplier_toggle)
        row_layout.addWidget(self.btn_supplier_delete)
        row_layout.addWidget(self.btn_supplier_delete_selected)
        row_layout.addWidget(self.btn_supplier_filter)
        row_layout.addSpacing(16)
        row_layout.addWidget(self.btn_supplier_clear)
        return row

    def _build_supplier_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        from ui.layout_constants import TAB_CONTENT_TOP_MARGIN
        layout.setContentsMargins(0, TAB_CONTENT_TOP_MARGIN, 0, 0)
        layout.setSpacing(8)

        self.supplier_table = QTableWidget()
        self.supplier_table.setColumnCount(6)
        self.supplier_table.setHorizontalHeaderLabels(
            ["供應商", "聯絡人", "部門", "電子郵件", "電話/行動", "狀態"]
        )
        style_table(self.supplier_table, single_selection=False)
        _sup_header = self.supplier_table.horizontalHeader()
        _sup_header.setStretchLastSection(False)
        _sup_header.setSectionResizeMode(0, _sup_header.ResizeMode.Stretch)
        _sup_header.setSectionResizeMode(5, _sup_header.ResizeMode.ResizeToContents)
        apply_table_action_affordance(
            self.supplier_table,
            "點擊供應商列開啟管理動作；Ctrl/Shift 可多選後批次刪除",
        )
        self.supplier_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.supplier_table.itemSelectionChanged.connect(self._on_supplier_selected)
        self.supplier_table.cellClicked.connect(self._on_supplier_table_clicked)
        layout.addWidget(self.supplier_table, 1)

        self.supplier_pagination = PaginationBar(
            on_page_changed=self._on_supplier_page_changed,
            on_page_size_changed=self._on_supplier_page_size_changed,
            default_page_size=self._supplier_page_size,
        )
        layout.addWidget(self.supplier_pagination)
        return panel

    # ── Toggle 按鈕狀態 ──────────────────────────────────

    def _set_supplier_toggle_button_state(self, *, is_active: bool) -> None:
        self._set_toggle_button_state(
            self.btn_supplier_toggle, is_active=is_active, entity="供應商"
        )

    # ── 標籤輔助 ──────────────────────────────────────────

    def _supplier_label(self, supplier_id: str) -> str:
        row = self._find_supplier_row(supplier_id)
        if row is not None:
            return str(row.get("supplier_name") or supplier_id)
        return supplier_id or "（空白ID）"

    # ── 表格操作與渲染 ────────────────────────────────────

    def _render_supplier_table(self):
        selected_supplier_id = self._selected_supplier_id
        visible_rows = self._filtered_supplier_rows()
        total_items = len(visible_rows)

        start = (self._supplier_page - 1) * self._supplier_page_size
        end = start + self._supplier_page_size
        page_rows = visible_rows[start:end]

        self.supplier_table.setRowCount(0)
        selected_row_index: int | None = None
        for idx, row in enumerate(page_rows):
            self.supplier_table.insertRow(idx)
            status_text = "啟用" if row["is_active"] else "停用"
            self.supplier_table.setItem(idx, 0, text_table_item(row["supplier_name"], empty=""))
            self.supplier_table.setItem(idx, 1, text_table_item(row.get("contact_name", ""), empty=""))
            self.supplier_table.setItem(idx, 2, text_table_item(row.get("department", ""), empty=""))
            self.supplier_table.setItem(idx, 3, text_table_item(row.get("contact_email", ""), empty=""))
            self.supplier_table.setItem(idx, 4, QTableWidgetItem(row.get("phone", "")))
            status_item = create_status_item(status_text)
            self.supplier_table.setItem(idx, 5, status_item)
            self.supplier_table.item(idx, 0).setData(Qt.ItemDataRole.UserRole, row["id"])
            if row["id"] == selected_supplier_id:
                selected_row_index = idx

        self.supplier_pagination.set_state(
            total_items=total_items,
            current_page=self._supplier_page,
            page_size=self._supplier_page_size,
        )

        if selected_supplier_id and selected_row_index is None:
            self.supplier_table.clearSelection()
            self._set_supplier_toggle_button_state(is_active=True)
        elif selected_row_index is not None:
            self._select_single_row(self.supplier_table, selected_row_index)

    # ── 分頁事件 ──────────────────────────────────────────

    def _on_supplier_page_changed(self, page_no: int):
        self._supplier_page = page_no
        self._render_supplier_table()

    def _on_supplier_page_size_changed(self, page_size: int):
        self._supplier_page_size = page_size
        self._supplier_page = 1
        self._render_supplier_table()

    # ── 表格選取 / 右鍵選單 ──────────────────────────────

    def _on_supplier_selected(self):
        selected_ids = self._selected_table_ids(self.supplier_table)
        self._selected_supplier_id = selected_ids[0] if selected_ids else None
        row = (
            self._find_supplier_row(self._selected_supplier_id)
            if len(selected_ids) == 1
            else None
        )
        if row is not None:
            self._set_supplier_toggle_button_state(is_active=bool(row["is_active"]))
        else:
            self._set_supplier_toggle_button_state(is_active=True)
        self._sync_action_buttons()

    def _on_supplier_table_clicked(self, row_idx: int, _column_idx: int):
        from PySide6.QtWidgets import QApplication
        modifiers = QApplication.keyboardModifiers()
        if modifiers & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ):
            return
        item = self.supplier_table.item(row_idx, 0)
        if item is None:
            return
        supplier_id = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        row = self._find_supplier_row(supplier_id)
        if row is None:
            return
        self._select_single_row(self.supplier_table, row_idx)

        menu = QMenu(self)
        action_edit = menu.addAction("編輯")
        action_toggle = menu.addAction("停用" if row["is_active"] else "啟用")
        action_delete = menu.addAction("刪除")
        selected = menu.exec(self._table_menu_pos(self.supplier_table, row_idx))
        if selected is action_edit:
            self._update_supplier()
        elif selected is action_toggle:
            self._toggle_supplier_active()
        elif selected is action_delete:
            self._delete_supplier()

    # ── 表單操作 ──────────────────────────────────────────

    def _clear_supplier_form(self):
        self._selected_supplier_id = None
        self.supplier_table.clearSelection()
        self._set_supplier_toggle_button_state(is_active=True)
        self._sync_action_buttons()

    def _open_supplier_dialog(
        self, *, initial_data: dict | None, is_edit: bool
    ) -> dict | None:
        dialog = SupplierFormDialog(self, initial_data=initial_data, is_edit=is_edit)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.payload()

    # ── CRUD ──────────────────────────────────────────────

    def _create_supplier(self):
        payload = self._open_supplier_dialog(initial_data=None, is_edit=False)
        if payload is None:
            return
        safe_ui_operation(
            self,
            lambda: (
                event_service.create_supplier(payload),
                self.main_window.refresh_all_views(),
                self._clear_supplier_form(),
            ),
            success_msg="供應商已建立",
            logger_msg="建立供應商失敗",
        )

    def _update_supplier(self):
        if not self._selected_supplier_id:
            QMessageBox.warning(self, "提示", localize_popup_message("請先選擇供應商"))
            return
        row = self._find_supplier_row(self._selected_supplier_id)
        if row is None:
            QMessageBox.warning(self, "提示", localize_popup_message("請先選擇供應商"))
            return

        payload = self._open_supplier_dialog(initial_data=row, is_edit=True)
        if payload is None:
            return
        safe_ui_operation(
            self,
            lambda: (
                event_service.update_supplier(self._selected_supplier_id, payload),
                self.main_window.refresh_all_views(),
            ),
            success_msg="供應商已更新",
            logger_msg="更新供應商失敗",
        )

    def _toggle_supplier_active(self):
        row = self._find_supplier_row(self._selected_supplier_id)
        if not row:
            QMessageBox.warning(self, "提示", localize_popup_message("請先選擇供應商"))
            return
        target_active = not bool(row.get("is_active"))
        action_text = "啟用" if target_active else "停用"
        supplier_label = self._supplier_label(str(row.get("id") or ""))
        confirm = QMessageBox.question(
            self,
            f"確認{action_text}",
            localize_popup_message(f"確定要{action_text}供應商「{supplier_label}」？"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        safe_ui_operation(
            self,
            lambda: (
                event_service.set_supplier_active(row["id"], target_active),
                self.main_window.refresh_all_views(),
            ),
            success_msg=f"供應商已{action_text}",
            logger_msg=f"{action_text}供應商失敗",
        )

    def _delete_supplier(self):
        selected_ids = self._selected_table_ids(self.supplier_table)
        if not selected_ids:
            QMessageBox.warning(self, "提示", localize_popup_message("請先選擇供應商"))
            return
        supplier_id = selected_ids[0]
        supplier_label = self._supplier_label(supplier_id)
        confirm = QMessageBox.question(
            self,
            "確認刪除",
            localize_popup_message(f"確定要刪除供應商「{supplier_label}」？\n此操作無法復原。"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        safe_ui_operation(
            self,
            lambda: (
                event_service.delete_supplier(supplier_id),
                self.main_window.refresh_all_views(),
                self._clear_supplier_form(),
            ),
            success_msg=f"供應商「{supplier_label}」已刪除",
            logger_msg="刪除供應商失敗",
        )

    def _delete_selected_suppliers(self):
        selected_ids = self._selected_table_ids(self.supplier_table)
        if not selected_ids:
            QMessageBox.warning(self, "提示", localize_popup_message("請先選擇供應商"))
            return
        preview_labels = [self._supplier_label(item_id) for item_id in selected_ids[:5]]
        preview_text = "、".join(preview_labels)
        if len(selected_ids) > 5:
            preview_text = f"{preview_text} ... 等 {len(selected_ids)} 筆"
        confirm = QMessageBox.question(
            self,
            "確認刪除",
            localize_popup_message(
                f"確定要刪除選取的 {len(selected_ids)} 筆供應商？\n{preview_text}\n此操作無法復原。"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        keyword, ok = QInputDialog.getText(
            self,
            "二次確認",
            localize_popup_message(
                f"刪除摘要：共 {len(selected_ids)} 筆\n{preview_text}\n\n請輸入 DELETE 以確認刪除。"
            ),
        )
        if not ok:
            return
        if keyword.strip().upper() != "DELETE":
            QMessageBox.warning(
                self,
                "已取消",
                localize_popup_message("未輸入 DELETE，已取消批次刪除。"),
            )
            return
        try:
            result = event_service.delete_suppliers(selected_ids)
            deleted = list(result.get("deleted", []))
            failed = list(result.get("failed", []))
            self.main_window.refresh_all_views()
            self._clear_supplier_form()

            if failed:
                failed_lines: list[str] = []
                for item in failed[:10]:
                    failed_id = str(item.get("id") or "")
                    failed_reason = localize_popup_message(str(item.get("reason") or ""))
                    failed_lines.append(
                        f"- {self._supplier_label(failed_id)}：{failed_reason}"
                    )
                if len(failed) > 10:
                    failed_lines.append(f"... 尚有 {len(failed) - 10} 筆未列出")
                detail = "\n".join(failed_lines)
                if deleted:
                    QMessageBox.warning(
                        self,
                        "部分成功",
                        localize_popup_message(
                            f"已刪除 {len(deleted)} 筆，{len(failed)} 筆刪除失敗。\n\n{detail}"
                        ),
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "刪除失敗",
                        localize_popup_message(f"共 {len(failed)} 筆刪除失敗。\n\n{detail}"),
                    )
            else:
                QMessageBox.information(
                    self,
                    "成功",
                    localize_popup_message(f"已刪除 {len(deleted)} 筆供應商"),
                )
        except Exception as exc:
            logger.exception("批次刪除供應商失敗")
            QMessageBox.critical(
                self,
                "錯誤",
                localize_popup_message(f"批次刪除供應商失敗：{localize_exception(exc)}"),
            )
