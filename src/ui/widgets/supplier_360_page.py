from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QFileDialog,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services import supplier_360_service
from services import supplier_report_service
from ui.list_column_contract import SUPPLIER_360_ANOMALY_COLUMNS
from ui.widgets.common_widgets import EmptyStateWidget, style_table


class SupplierQuarterExportDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("選擇報告季度")
        layout = QFormLayout(self)
        today = date.today()
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2000, 2100)
        self.year_spin.setValue(today.year)
        layout.addRow("年度", self.year_spin)
        self.quarter_combo = QComboBox()
        for quarter, label in enumerate(
            ("Q1（1–3 月）", "Q2（4–6 月）", "Q3（7–9 月）", "Q4（10–12 月）"),
            start=1,
        ):
            self.quarter_combo.addItem(label, quarter)
        current_quarter = (today.month - 1) // 3 + 1
        self.quarter_combo.setCurrentIndex(current_quarter - 1)
        layout.addRow("季度", self.quarter_combo)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def selection(self) -> tuple[str, str, str]:
        year = int(self.year_spin.value())
        quarter = int(self.quarter_combo.currentData())
        quarter_end_days = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
        start_month = (quarter - 1) * 3 + 1
        end_month, end_day = quarter_end_days[quarter]
        start_date = date(year, start_month, 1).isoformat()
        end_date = date(year, end_month, end_day).isoformat()
        return start_date, end_date, f"{year}Q{quarter}"


class Supplier360Page(QWidget):
    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self.supplier_id = ""
        self._supplier_name = QLabel()
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.addWidget(self._supplier_name, 1)
        self.summary_label = QLabel()
        header.addWidget(self.summary_label)
        anomaly_button = QPushButton("新增異常")
        anomaly_button.setProperty("variant", "primary")
        anomaly_button.clicked.connect(self._open_anomaly)
        header.addWidget(anomaly_button)
        visit_button = QPushButton("安排訪廠")
        visit_button.setProperty("variant", "secondary")
        visit_button.clicked.connect(self._open_visit)
        header.addWidget(visit_button)
        report_button = QPushButton("匯出報告")
        report_button.setProperty("variant", "secondary")
        report_button.clicked.connect(self._export_report)
        header.addWidget(report_button)
        root.addLayout(header)

        self.tabs = QTabWidget()
        self.timeline_table = self._table(
            ["日期", "來源", "單號", "內容", "狀態"]
        )
        self.anomaly_table = self._table(
            [column.label for column in SUPPLIER_360_ANOMALY_COLUMNS]
        )
        self.visit_table = self._table(
            ["日期", "摘要", "訪廠人員", "狀態", "工單"]
        )
        self.defect_table = self._table(
            ["不良單號", "日期", "料號", "品名", "不良描述", "狀態"]
        )
        self.contact_table = self._table(
            ["姓名", "部門", "電話", "Email", "主要聯絡人"]
        )
        self.contact_empty = EmptyStateWidget(
            "尚無聯絡人資料",
            "請至基礎資料維護供應商聯絡人。",
            parent=self,
        )
        self.contact_empty.setVisible(False)
        contact_tab = QWidget()
        contact_layout = QVBoxLayout(contact_tab)
        contact_layout.setContentsMargins(0, 0, 0, 0)
        contact_layout.addWidget(self.contact_table)
        contact_layout.addWidget(self.contact_empty)
        self.scorecard_label = QLabel()
        self.scorecard_label.setWordWrap(True)
        self.tabs.addTab(self.timeline_table, "概況")
        self.tabs.addTab(self.anomaly_table, "異常案件")
        self.tabs.addTab(self.visit_table, "訪廠紀錄")
        self.tabs.addTab(self.defect_table, "不合格品")
        self.tabs.addTab(contact_tab, "聯絡人")
        self.tabs.addTab(self.scorecard_label, "評分")
        root.addWidget(self.tabs, 1)

    def _table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        style_table(table)
        return table

    def load_supplier(self, supplier_id: str) -> None:
        self.supplier_id = str(supplier_id or "")
        summary = supplier_360_service.get_supplier_summary(self.supplier_id)
        supplier = summary.get("supplier") or {}
        name = supplier.get("supplier_name") or "供應商"
        self._supplier_name.setText(f"{name}（供應商檔案）")
        self.summary_label.setText(
            f"未結異常 {summary.get('open_anomaly_count', 0)}　"
            f"逾期 {summary.get('overdue_anomaly_count', 0)}　"
            f"近90日 NCR {summary.get('ncr_90d_count', 0)}　"
            f"最近訪廠 {summary.get('latest_visit_date') or '—'}"
        )
        today = date.today()
        scorecard = supplier_360_service.get_supplier_scorecard(
            self.supplier_id,
            f"{today.year}-01-01",
            today.isoformat(),
        )
        self.scorecard_label.setText(
            f"目前評級：{scorecard.get('grade', '—')}\n"
            f"區間：{scorecard.get('start_date')} ～ {scorecard.get('end_date')}\n"
            f"異常 {scorecard.get('anomaly_count', 0)} 件，"
            f"準時結案率 {scorecard.get('on_time_rate', 0) * 100:.1f}%；"
            f"NCR {scorecard.get('ncr_count', 0)} 件；"
            f"訪廠 {scorecard.get('visit_count', 0)} 次。"
        )
        self._render_timeline(supplier_360_service.list_supplier_timeline(self.supplier_id))
        self._render_rows(
            self.anomaly_table,
            supplier_360_service.list_supplier_anomalies(self.supplier_id),
            tuple(column.field for column in SUPPLIER_360_ANOMALY_COLUMNS),
        )
        self._render_rows(
            self.visit_table,
            supplier_360_service.list_supplier_visits(self.supplier_id),
            ("visit_date", "summary", "visitor_name", "status", "work_order_no"),
        )
        self._render_rows(
            self.defect_table,
            supplier_360_service.list_supplier_defects(self.supplier_id),
            ("defect_no", "event_date", "item_no", "product_name", "defect_desc", "status"),
        )
        self._render_contacts(supplier_360_service.list_supplier_contacts(self.supplier_id))

    def refresh_data(self) -> None:
        """Refresh the currently selected supplier from the database."""
        if self.supplier_id:
            self.load_supplier(self.supplier_id)

    def _render_timeline(self, rows: list[dict]) -> None:
        self.timeline_table.setRowCount(0)
        for row in rows:
            index = self.timeline_table.rowCount()
            self.timeline_table.insertRow(index)
            values = (
                row.get("event_date") or "—",
                row.get("source") or "—",
                row.get("ref_no") or "—",
                row.get("title") or "—",
                row.get("status") or "—",
            )
            for column, value in enumerate(values):
                self.timeline_table.setItem(index, column, QTableWidgetItem(str(value)))

    def _render_rows(
        self,
        table: QTableWidget,
        rows: list[dict],
        keys: tuple[str, ...],
    ) -> None:
        table.setRowCount(0)
        for row in rows:
            index = table.rowCount()
            table.insertRow(index)
            for column, key in enumerate(keys):
                table.setItem(index, column, QTableWidgetItem(str(row.get(key) or "—")))

    def _render_contacts(self, rows: list[dict]) -> None:
        has_rows = bool(rows)
        self.contact_table.setVisible(has_rows)
        self.contact_empty.setVisible(not has_rows)
        self.contact_table.setRowCount(0)
        for row in rows:
            index = self.contact_table.rowCount()
            self.contact_table.insertRow(index)
            values = (
                row.get("contact_name") or "—",
                row.get("department") or "—",
                row.get("phone") or "—",
                row.get("email") or "—",
                "是" if row.get("is_primary") else "否",
            )
            for column, value in enumerate(values):
                self.contact_table.setItem(
                    index, column, QTableWidgetItem(str(value))
                )

    def _supplier_prefill(self) -> dict:
        summary = supplier_360_service.get_supplier_summary(self.supplier_id)
        supplier = summary.get("supplier") or {}
        return {
            "supplier_id": self.supplier_id,
            "supplier_name": supplier.get("supplier_name") or "",
        }

    def _open_anomaly(self) -> None:
        if hasattr(self.main_window, "open_new_anomaly_create_page"):
            self.main_window.open_new_anomaly_create_page(self._supplier_prefill())

    def _open_visit(self) -> None:
        if hasattr(self.main_window, "open_new_visit_create_page"):
            self.main_window.open_new_visit_create_page(self._supplier_prefill())

    def _export_report(self) -> None:
        dialog = SupplierQuarterExportDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        start_date, end_date, quarter_label = dialog.selection()
        default_name = f"supplier-quality-report-{quarter_label}.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "匯出供應商季度報告",
            default_name,
            "Excel (*.xlsx)",
        )
        if not path:
            return
        ok, message = supplier_report_service.export_supplier_report(
            path,
            self.supplier_id,
            start_date,
            end_date,
        )
        if ok:
            QMessageBox.information(self, "匯出完成", message)
        else:
            QMessageBox.warning(self, "匯出失敗", message)
