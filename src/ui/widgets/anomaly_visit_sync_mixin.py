"""異常編輯對話框的訪廠同步邏輯 Mixin。

從 NewAnomalyDialog 提取訪廠關聯、同日期訪廠自動帶入、
同步建立訪廠提示等方法，透過多重繼承注入回原對話框。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QDialog, QMessageBox

from services import event_service
from ui.widgets.common_widgets import set_combo_current_data
from ui.widgets.defect_form_widgets import VisitSelectionDialog, set_tone


class _AnomalyVisitSyncMixin:
    """提供異常對話框的訪廠關聯與同步邏輯。

    透過多重繼承與 NewAnomalyDialog 組合使用：
        class NewAnomalyDialog(QDialog, SupplierProductFormMixin, _AnomalyVisitSyncMixin):
            ...

    方法會透過 self 存取主對話框提供的以下屬性/方法：
    - self._is_edit
    - self._anomaly_id
    - self._initial_data
    - self._same_day_visit_autofill
    - self.date_edit
    - self.sync_visit_check
    - self._sync_visit_hint_label
    - self._same_day_visit_hint_label
    - self._rc_group
    - self._linked_visit_label
    - self.unlink_visit_button
    - self.product_combo
    - self.outsource_work_order_input
    - self.batch_qty_input
    - self.supplier_combo
    - self._update_outsource_row_visibility()
    """

    # ── 同步建立訪廠提示 ─────────────────────────────────

    def _update_sync_visit_hint(self) -> None:
        if self._is_edit:
            return
        if self.sync_visit_check.isChecked():
            visit_date = self.date_edit.date().toString("yyyy-MM-dd")
            self._sync_visit_hint_label.setText(
                f"勾選後將同時建立／重用 {visit_date} 的訪廠紀錄"
            )
            set_tone(self._sync_visit_hint_label, "info")
        else:
            self._sync_visit_hint_label.setText(
                "未勾選：本異常單將不關聯任何訪廠紀錄"
            )
            set_tone(self._sync_visit_hint_label, "warning")

    # ── 同日期訪廠自動帶入 ───────────────────────────────

    def _clear_same_day_visit_defaults_if_owned(self) -> None:
        current_product_id = (self.product_combo.currentData() or "").strip()
        previous_product_id = str(self._same_day_visit_autofill.get("product_id") or "")
        if previous_product_id and current_product_id == previous_product_id:
            self.product_combo.setCurrentIndex(0)

        previous_work_order = str(
            self._same_day_visit_autofill.get("work_order_no") or ""
        )
        current_work_order = self.outsource_work_order_input.text().strip()
        if previous_work_order and current_work_order == previous_work_order:
            self.outsource_work_order_input.clear()

        previous_qty = self._same_day_visit_autofill.get("batch_qty")
        if previous_qty is not None and self.batch_qty_input.text().strip() == str(previous_qty):
            self.batch_qty_input.clear()

        self._same_day_visit_autofill = {
            "product_id": "",
            "work_order_no": "",
            "batch_qty": None,
        }
        self._same_day_visit_hint_label.setText("")
        self._same_day_visit_hint_label.setVisible(False)

    def _apply_same_day_visit_defaults(self) -> None:
        if self._is_edit:
            return
        supplier_id = (self.supplier_combo.currentData() or "").strip()
        visit_date = self.date_edit.date().toString("yyyy-MM-dd")
        if not supplier_id:
            self._clear_same_day_visit_defaults_if_owned()
            return
        try:
            ref = event_service.get_latest_visit_for_supplier_on_date(
                supplier_id,
                visit_date,
            )
        except Exception:
            logger.exception(
                "get_latest_visit_for_supplier_on_date failed for supplier_id=%s date=%s",
                supplier_id,
                visit_date,
            )
            ref = None
        if ref is None:
            self._clear_same_day_visit_defaults_if_owned()
            return

        applied: list[str] = []
        product_id = str(ref.get("product_id") or "").strip()
        current_product_id = (self.product_combo.currentData() or "").strip()
        previous_product_id = str(self._same_day_visit_autofill.get("product_id") or "")
        if product_id and (
            not current_product_id or current_product_id == previous_product_id
        ):
            if set_combo_current_data(self.product_combo, product_id):
                self._same_day_visit_autofill["product_id"] = product_id
                applied.append("品名")

        work_order_no = str(ref.get("work_order_no") or "").strip()
        current_work_order = self.outsource_work_order_input.text().strip()
        previous_work_order = str(
            self._same_day_visit_autofill.get("work_order_no") or ""
        )
        if work_order_no and (
            not current_work_order or current_work_order == previous_work_order
        ):
            self.outsource_work_order_input.setText(work_order_no)
            self._same_day_visit_autofill["work_order_no"] = work_order_no
            applied.append("工單")
            self._update_outsource_row_visibility()

        production_qty = int(ref.get("production_qty") or 0)
        current_qty_text = self.batch_qty_input.text().strip()
        previous_qty = self._same_day_visit_autofill.get("batch_qty")
        if production_qty > 0 and (
            not current_qty_text
            or (previous_qty is not None and current_qty_text == str(previous_qty))
        ):
            self.batch_qty_input.setText(str(production_qty))
            self._same_day_visit_autofill["batch_qty"] = production_qty
            applied.append("數量")

        if applied:
            self._same_day_visit_hint_label.setText(
                f"已沿用 {visit_date} 訪廠資料：{'、'.join(applied)}"
            )
            set_tone(self._same_day_visit_hint_label, "info")
            self._same_day_visit_hint_label.setVisible(True)
        elif not any(self._same_day_visit_autofill.values()):
            self._same_day_visit_hint_label.setText("")
            self._same_day_visit_hint_label.setVisible(False)

    # ── 取消訪廠連結 ─────────────────────────────────────

    def _on_unlink_visit_clicked(self) -> None:
        if not self._is_edit or not self._anomaly_id:
            return
        ans = QMessageBox.question(
            self,
            "取消連結",
            "確定要取消本異常單與訪廠紀錄的連結嗎？\n(本單將變為單獨異常)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return

        try:
            event_service.update_anomaly_link(self._anomaly_id, None)
            self._initial_data["visit_id"] = None
            self._rc_group.setTitle("風險控管調查 (單獨異常 / 無訪廠紀錄適用)")
            self._linked_visit_label.setVisible(False)
            self.unlink_visit_button.setVisible(False)
            QMessageBox.information(self, "成功", "已取消連結訪廠紀錄")
        except Exception as exc:
            logger.exception("Failed to unlink visit")
            QMessageBox.critical(self, "錯誤", f"取消連結失敗：{exc}")

    # ── 關聯訪廠 ─────────────────────────────────────────

    def _on_link_visit_clicked(self) -> None:
        if not self._is_edit:
            return
        supplier_id = (self.supplier_combo.currentData() or "").strip()
        supplier_name = self.supplier_combo.currentText()
        if not supplier_id:
            QMessageBox.warning(self, "提示", "請先選擇供應商")
            return

        dialog = VisitSelectionDialog(supplier_id, supplier_name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            visit_id = dialog.selected_visit_id
            visit_date = dialog.selected_visit_date

            try:
                # 1. Update linkage in DB
                event_service.update_anomaly_link(self._anomaly_id, visit_id)

                # 2. Ask to sync date if different
                current_date = self.date_edit.date().toString("yyyy-MM-dd")
                if visit_date and visit_date != current_date:
                    ans = QMessageBox.question(
                        self,
                        "同步日期",
                        f"所選訪廠日期為 {visit_date}，是否將本異常日期也同步變更？",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    )
                    if ans == QMessageBox.StandardButton.Yes:
                        self.date_edit.setDate(QDate.fromString(visit_date, "yyyy-MM-dd"))

                # 3. Ask to sync product/lot info
                ans_sync = QMessageBox.question(
                    self,
                    "同步資訊",
                    "是否同步沿用該訪廠的產品、工單及批量資訊？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if ans_sync == QMessageBox.StandardButton.Yes:
                    v_detail = event_service.get_visit_detail(visit_id)
                    v_product_id = v_detail.get("product_id")
                    if v_product_id:
                        set_combo_current_data(self.product_combo, v_product_id)
                    v_order = str(v_detail.get("work_order_no") or "").strip()
                    if v_order:
                        self.outsource_work_order_input.setText(v_order)
                    v_qty = int(v_detail.get("production_qty") or 0)
                    if v_qty > 0:
                        self.batch_qty_input.setText(str(v_qty))

                # 4. Manually update UI labels
                self._initial_data["visit_id"] = visit_id
                if visit_id:
                    self.unlink_visit_button.setVisible(True)
                    self._rc_group.setTitle("風險控管調查 (已關聯訪廠)")
                    v_detail = event_service.get_visit_detail(visit_id)
                    v_date = v_detail.get("visit_date") or "?"
                    v_summary = (v_detail.get("summary") or "").strip() or "(無摘要)"
                    self._linked_visit_label.setText(
                        f"【本單已關聯訪廠紀錄】\n日期：{v_date}\n摘要：{v_summary}"
                    )
                    self._linked_visit_label.setVisible(True)
                else:
                    self._rc_group.setTitle("風險控管調查 (單獨異常 / 無訪廠紀錄適用)")
                    self._linked_visit_label.setVisible(False)

                QMessageBox.information(self, "成功", "已成功關聯訪廠紀錄")
            except Exception as exc:
                logger.exception("Failed to update anomaly link")
                QMessageBox.critical(self, "錯誤", f"關聯失敗：{exc}")
