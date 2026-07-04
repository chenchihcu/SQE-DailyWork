"""產品基礎資料管理 Mixin。

從 MasterDataWidget 中提取所有產品專屬的方法，
透過多重繼承注入回原 widget。
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMenu,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.connection import get_connection
from database.product_stage import normalize_product_stage_ui
from services import event_service, master_import_service
from ui.popup_i18n import localize_exception, localize_popup_message
from ui.widgets.common_widgets import (
    apply_table_action_affordance,
    create_status_item,
    safe_ui_operation,
    style_table,
    text_table_item,
)
from ui.widgets.product_form_dialog import ProductFormDialog
from ui.widgets.product_stage_log_dialog import ProductStageLogDialog
from ui.widgets.pagination_bar import PaginationBar


class _MasterDataProductMixin:
    """提供產品管理的 UI 建構與 CRUD 操作。

    透過多重繼承與 MasterDataWidget 組合使用：
        class MasterDataWidget(QWidget, _MasterDataSupplierMixin, _MasterDataProductMixin):
            ...

    方法會透過 self 存取主 Widget 提供的以下屬性/方法：
    - self.main_window              (set in __init__)
    - self._product_rows            (set by refresh_data)
    - self._selected_product_id     (set by _on_product_selected)
    - self._product_page / _product_page_size
    - self._find_product_row()      (shared method in core)
    - self._selected_table_id()     (shared method in core)
    - self._table_menu_pos()        (shared method in core)
    - self._select_single_row()     (shared method in core)
    - self._create_toolbar_button() (shared method in core)
    - self._set_toggle_button_state() (shared method in core)
    - self._focus_master_query()    (shared method in core)
    - self._supplier_rows           (for dialog supplier list)
    """

    # ── UI 建構 ──────────────────────────────────────────

    def _build_product_actions_row(self) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        self.btn_product_create = self._create_toolbar_button(
            "新增",
            tooltip="新增產品",
            variant="toolbarPrimary",
            on_click=self._create_product,
        )
        self.btn_product_update = self._create_toolbar_button(
            "更新",
            tooltip="更新產品",
            variant="toolbarSecondary",
            on_click=self._update_product,
        )
        self.btn_product_toggle = self._create_toolbar_button(
            "停用",
            tooltip="停用產品",
            variant="toolbarSecondary",
            on_click=self._toggle_product_active,
        )
        self.btn_product_delete = self._create_toolbar_button(
            "刪除",
            tooltip="刪除產品",
            variant="toolbarSecondary",
            on_click=self._delete_product,
        )
        self.btn_product_stage_logs = self._create_toolbar_button(
            "紀錄",
            tooltip="查詢產品階段異動紀錄",
            variant="toolbarSecondary",
            on_click=self._show_product_stage_logs,
        )
        self.btn_product_import = self._create_toolbar_button(
            "匯入",
            tooltip="從 Excel / ERP 匯出檔匯入共用產品與供應商主檔",
            variant="toolbarSecondary",
            on_click=self._import_products_from_excel,
        )
        self.btn_product_filter = self._create_toolbar_button(
            "篩選",
            tooltip="聚焦關鍵字篩選欄",
            variant="toolbarSecondary",
            on_click=self._focus_master_query,
        )
        self.btn_product_clear = self._create_toolbar_button(
            "清空",
            tooltip="清空產品選取",
            variant="toolbarGhost",
            on_click=self._clear_product_form,
        )

        row_layout.addWidget(self.btn_product_create)
        row_layout.addWidget(self.btn_product_update)
        row_layout.addWidget(self.btn_product_toggle)
        row_layout.addWidget(self.btn_product_delete)
        row_layout.addWidget(self.btn_product_stage_logs)
        row_layout.addWidget(self.btn_product_import)
        row_layout.addWidget(self.btn_product_filter)
        row_layout.addSpacing(16)
        row_layout.addWidget(self.btn_product_clear)
        return row

    def _build_product_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        from ui.layout_constants import TAB_CONTENT_TOP_MARGIN
        layout.setContentsMargins(0, TAB_CONTENT_TOP_MARGIN, 0, 0)
        layout.setSpacing(8)

        self.product_table = QTableWidget()
        self.product_table.setColumnCount(6)
        self.product_table.setHorizontalHeaderLabels(
            ["料號", "品名", "階段", "主供應商", "次要供應商", "狀態"]
        )
        style_table(self.product_table)
        _prod_header = self.product_table.horizontalHeader()
        _prod_header.setStretchLastSection(False)
        _prod_header.setSectionResizeMode(1, _prod_header.ResizeMode.Stretch)
        _prod_header.setSectionResizeMode(5, _prod_header.ResizeMode.ResizeToContents)
        apply_table_action_affordance(
            self.product_table,
            "點擊產品列開啟編輯、停用、刪除或階段紀錄動作",
        )
        self.product_table.itemSelectionChanged.connect(self._on_product_selected)
        self.product_table.cellClicked.connect(self._on_product_table_clicked)
        layout.addWidget(self.product_table, 1)

        self.product_pagination = PaginationBar(
            on_page_changed=self._on_product_page_changed,
            on_page_size_changed=self._on_product_page_size_changed,
            default_page_size=self._product_page_size,
        )
        layout.addWidget(self.product_pagination)
        return panel

    # ── Toggle 按鈕狀態 ──────────────────────────────────

    def _set_product_toggle_button_state(self, *, is_active: bool) -> None:
        self._set_toggle_button_state(
            self.btn_product_toggle, is_active=is_active, entity="產品"
        )

    # ── 標籤輔助 ──────────────────────────────────────────

    def _product_label(self, product_id: str) -> str:
        row = self._find_product_row(product_id)
        if row is not None:
            code = str(row.get("product_code") or "").strip()
            name = str(row.get("product_name") or "").strip()
            if code and name:
                return f"[{code}] {name}"
            return name or code or product_id
        return product_id or "（空白ID）"

    # ── 表格渲染 ──────────────────────────────────────────

    def _render_product_table(self):
        selected_product_id = self._selected_product_id
        visible_rows = self._filtered_product_rows()
        total_items = len(visible_rows)

        start = (self._product_page - 1) * self._product_page_size
        end = start + self._product_page_size
        page_rows = visible_rows[start:end]

        self.product_table.setRowCount(0)
        selected_row_index: int | None = None
        for idx, row in enumerate(page_rows):
            self.product_table.insertRow(idx)
            status_text = "啟用" if row["is_active"] else "停用"
            product_stage = normalize_product_stage_ui(row.get("product_stage"))
            primary_supplier_text = row.get("supplier_name") or "（未指定）"
            secondary_supplier_text = row.get("secondary_supplier_name") or "（未指定）"
            self.product_table.setItem(idx, 0, QTableWidgetItem(row["product_code"]))
            self.product_table.setItem(idx, 1, text_table_item(row["product_name"]))
            self.product_table.setItem(idx, 2, QTableWidgetItem(product_stage))
            self.product_table.setItem(idx, 3, text_table_item(primary_supplier_text))
            self.product_table.setItem(idx, 4, text_table_item(secondary_supplier_text))
            status_item = create_status_item(status_text)
            self.product_table.setItem(idx, 5, status_item)
            self.product_table.item(idx, 0).setData(Qt.ItemDataRole.UserRole, row["id"])
            if row["id"] == selected_product_id:
                selected_row_index = idx

        self.product_pagination.set_state(
            total_items=total_items,
            current_page=self._product_page,
            page_size=self._product_page_size,
        )

        if selected_product_id and selected_row_index is None:
            self.product_table.clearSelection()
        elif selected_row_index is not None:
            self._select_single_row(self.product_table, selected_row_index)

    # ── 分頁事件 ──────────────────────────────────────────

    def _on_product_page_changed(self, page_no: int):
        self._product_page = page_no
        self._render_product_table()

    def _on_product_page_size_changed(self, page_size: int):
        self._product_page_size = page_size
        self._product_page = 1
        self._render_product_table()

    # ── 表格選取 / 右鍵選單 ──────────────────────────────

    def _on_product_selected(self):
        self._selected_product_id = self._selected_table_id(self.product_table)
        row = self._find_product_row(self._selected_product_id)
        if row:
            self._set_product_toggle_button_state(is_active=bool(row["is_active"]))
        else:
            self._set_product_toggle_button_state(is_active=True)
        self._sync_action_buttons()

    def _on_product_table_clicked(self, row_idx: int, _column_idx: int):
        from PySide6.QtWidgets import QApplication
        modifiers = QApplication.keyboardModifiers()
        if modifiers & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ):
            return
        item = self.product_table.item(row_idx, 0)
        if item is None:
            return
        product_id = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        row = self._find_product_row(product_id)
        if row is None:
            return
        self._select_single_row(self.product_table, row_idx)

        menu = QMenu(self)
        action_edit = menu.addAction("編輯")
        action_toggle = menu.addAction("停用" if row["is_active"] else "啟用")
        action_delete = menu.addAction("刪除")
        action_logs = menu.addAction("階段紀錄")
        selected = menu.exec(self._table_menu_pos(self.product_table, row_idx))
        if selected is action_edit:
            self._update_product()
        elif selected is action_toggle:
            self._toggle_product_active()
        elif selected is action_delete:
            self._delete_product()
        elif selected is action_logs:
            self._show_product_stage_logs()

    # ── 表單操作 ──────────────────────────────────────────

    def _clear_product_form(self):
        self._selected_product_id = None
        self.product_table.clearSelection()
        self._set_product_toggle_button_state(is_active=True)
        self._sync_action_buttons()

    def _open_product_dialog(
        self, *, initial_data: dict | None, is_edit: bool
    ) -> dict | None:
        dialog = ProductFormDialog(
            self._supplier_rows,
            self,
            initial_data=initial_data,
            is_edit=is_edit,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.payload()

    # ── CRUD ──────────────────────────────────────────────

    def _create_product(self):
        payload = self._open_product_dialog(initial_data=None, is_edit=False)
        if payload is None:
            return
        safe_ui_operation(
            self,
            lambda: (
                event_service.create_product(payload),
                self.main_window.refresh_all_views(),
                self._clear_product_form(),
            ),
            success_msg="產品已建立",
            logger_msg="建立產品失敗",
        )

    def _update_product(self):
        if not self._selected_product_id:
            QMessageBox.warning(self, "提示", localize_popup_message("請先選擇產品"))
            return
        row = self._find_product_row(self._selected_product_id)
        if row is None:
            QMessageBox.warning(self, "提示", localize_popup_message("請先選擇產品"))
            return
        payload = self._open_product_dialog(initial_data=row, is_edit=True)
        if payload is None:
            return
        safe_ui_operation(
            self,
            lambda: (
                event_service.update_product(self._selected_product_id, payload),
                self.main_window.refresh_all_views(),
            ),
            success_msg="產品已更新",
            logger_msg="更新產品失敗",
        )

    def _toggle_product_active(self):
        row = self._find_product_row(self._selected_product_id)
        if not row:
            QMessageBox.warning(self, "提示", localize_popup_message("請先選擇產品"))
            return
        target_active = not bool(row.get("is_active"))
        action_text = "啟用" if target_active else "停用"
        product_label = self._product_label(str(row.get("id") or ""))
        confirm = QMessageBox.question(
            self,
            f"確認{action_text}",
            localize_popup_message(f"確定要{action_text}產品「{product_label}」？"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        safe_ui_operation(
            self,
            lambda: (
                event_service.set_product_active(row["id"], target_active),
                self.main_window.refresh_all_views(),
            ),
            success_msg=f"產品已{action_text}",
            logger_msg=f"{action_text}產品失敗",
        )

    def _delete_product(self):
        product_id = self._selected_product_id
        if not product_id:
            QMessageBox.warning(self, "提示", localize_popup_message("請先選擇產品"))
            return
        product_label = self._product_label(product_id)
        confirm = QMessageBox.question(
            self,
            "確認刪除",
            localize_popup_message(f"確定要刪除產品「{product_label}」？\n此操作無法復原。"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        safe_ui_operation(
            self,
            lambda: (
                event_service.delete_product(product_id),
                self.main_window.refresh_all_views(),
                self._clear_product_form(),
            ),
            success_msg=f"產品「{product_label}」已刪除",
            logger_msg="刪除產品失敗",
        )

    # ── 產品階段紀錄 ──────────────────────────────────────

    def _show_product_stage_logs(self):
        product_id = self._selected_product_id
        if not product_id:
            QMessageBox.warning(self, "提示", localize_popup_message("請先選擇產品"))
            return
        try:
            logs = event_service.list_product_stage_change_logs(product_id=product_id, limit=200)
            dialog = ProductStageLogDialog(self._product_label(product_id), logs, self)
            dialog.exec()
        except Exception as exc:
            logger.exception("載入階段異動紀錄失敗")
            QMessageBox.critical(
                self,
                "錯誤",
                localize_popup_message(f"載入階段異動紀錄失敗：{localize_exception(exc)}"),
            )

    # ── 從 Excel 匯入 ─────────────────────────────────────

    def _import_products_from_excel(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "匯入共用產品主檔",
            "",
            "Excel Files (*.xlsx)",
        )
        if not file_path:
            return
        try:
            with get_connection() as conn:
                preview = master_import_service.preview_product_master_import(
                    conn,
                    Path(file_path),
                )
                if preview.error_count:
                    batch_id = master_import_service.record_product_master_import_rejection(
                        conn,
                        preview,
                        source_file=Path(file_path),
                    )
                    error_lines = list(preview.file_errors)
                    error_lines.extend(
                        f"第 {row.row_number} 列：{row.message}"
                        for row in preview.rows
                        if row.is_error
                    )
                    if len(error_lines) > 10:
                        error_lines = [
                            *error_lines[:10],
                            f"... 尚有 {preview.error_count - 10} 項錯誤未列出",
                        ]
                    QMessageBox.warning(
                        self,
                        "匯入預覽失敗",
                        localize_popup_message(
                            "\n".join(
                                [
                                    f"批次：{batch_id}",
                                    "未寫入 suppliers/products、事件或倉庫不合格品資料。",
                                    "",
                                    *error_lines,
                                ]
                            )
                        ),
                    )
                    return
                if not preview.has_writes:
                    result = master_import_service.apply_product_master_import(
                        conn,
                        preview,
                        source_file=Path(file_path),
                    )
                    QMessageBox.information(
                        self,
                        "匯入預覽",
                        localize_popup_message(
                            "共用產品與供應商主檔已一致，沒有需要匯入的資料。\n"
                            f"批次：{result.batch_id}"
                        ),
                    )
                    return

                message = (
                    f"新增產品：{preview.add_count} 筆\n"
                    f"更新產品：{preview.update_count} 筆\n"
                    f"新增供應商：{preview.supplier_create_count} 筆\n"
                    f"略過：{preview.skipped_count} 筆\n\n"
                    "本匯入只寫入 suppliers/products 共用主檔，"
                    "不寫入訪廠缺失、正式異常或倉庫不合格品資料。\n\n"
                    "確認匯入？"
                )
                confirm = QMessageBox.question(
                    self,
                    "確認匯入",
                    localize_popup_message(message),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if confirm != QMessageBox.StandardButton.Yes:
                    return
                result = master_import_service.apply_product_master_import(
                    conn,
                    preview,
                    source_file=Path(file_path),
                )

            self.refresh_data()
            self.main_window.refresh_all_views()
            backup_text = (
                f"\n備份：{result.backup_path}"
                if result.backup_path is not None
                else ""
            )
            QMessageBox.information(
                self,
                "匯入完成",
                localize_popup_message(
                    f"新增產品：{result.added_count} 筆\n"
                    f"更新產品：{result.updated_count} 筆\n"
                    f"新增供應商：{result.supplier_created_count} 筆\n"
                    f"略過：{result.skipped_count} 筆"
                    f"{backup_text}\n"
                    f"批次：{result.batch_id}"
                ),
            )
        except (ValueError, master_import_service.MasterImportError) as exc:
            QMessageBox.warning(self, "匯入失敗", localize_exception(exc))
        except Exception as exc:
            logger.exception("匯入產品主檔失敗")
            QMessageBox.critical(
                self,
                "錯誤",
                localize_popup_message(f"匯入產品主檔失敗：{localize_exception(exc)}"),
            )
