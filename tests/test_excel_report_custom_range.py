from __future__ import annotations

import os
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication
from openpyxl import load_workbook

from ui.widgets.export_range_dialog import ExportRangeDialog
from ncr.services import export_service as ncr_export_service
from services import event_service


class ExcelReportCustomRangeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            cls.app.quit()

    def test_export_range_dialog_defaults(self) -> None:
        dialog = ExportRangeDialog()
        # 預設開始日期是今年 1 月 1 日
        expected_start = QDate(QDate.currentDate().year(), 1, 1).toString("yyyy-MM-dd")
        expected_end = QDate.currentDate().toString("yyyy-MM-dd")
        
        start_val, end_val = dialog.get_date_range()
        self.assertEqual(start_val, expected_start)
        self.assertEqual(end_val, expected_end)
        dialog.close()

    def test_ncr_report_export_success(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            file_path = os.path.join(tmp_dir, "ncr_report.xlsx")
            
            # 建立虛擬不合格品資料
            defects = [
                {
                    "defect_no": "NCR-10001",
                    "event_date": "2026-06-15",
                    "return_slip_type": "廠內退料",
                    "work_order_no": "WO-12345",
                    "internal_work_order_no": "IWO-54321",
                    "transfer_slip_no": "TS-999",
                    "item_no": "ITEM-ABC",
                    "product_name": "虛擬產品A",
                    "qty": 50,
                    "category": "原物料",
                    "supplier_name": "供應商A",
                    "outsource_supplier_name": "N/A",
                    "defect_desc": "表面刮傷",
                    "status": "已結案",
                    "disposition": "報廢",
                    "responsibility": "材損",
                }
            ]
            
            # 呼叫匯出函數，無圖表
            ok, msg = ncr_export_service.export_ncr_excel_report(
                file_path=file_path,
                start_date="2026-06-01",
                end_date="2026-06-30",
                defects=defects,
                temp_chart_paths=None
            )
            
            self.assertTrue(ok)
            self.assertTrue(os.path.exists(file_path))
            self.assertIn("已匯出至", msg)

    @patch("services.event_service.get_anomaly_category_pareto_by_range")
    @patch("services.event_service.list_events_by_range")
    def test_events_report_export_success(self, mock_list_events, mock_pareto) -> None:
        # 柏拉圖表格與頁面圖表、嵌入 PNG 共用同一 SQL 來源(單一實作)
        mock_pareto.return_value = [
            {
                "rank": 1,
                "category": "物料/來料品質異常",
                "count": 1,
                "percent": 100.0,
                "cumulative_percent": 100.0,
            }
        ]
        # Mock 範圍事件列表
        mock_list_events.return_value = [
            {
                "event_id": "EVT-101",
                "ref_no": "AN-2026-001",
                "event_date": "2026-06-10",
                "event_type": "ANOMALY",
                "supplier_name": "供應商A",
                "content": "進料不合格",
                "status": "已結案",
                "category": "進料品質",
                "root_cause_category": "物料/來料品質異常",
                "improvement_desc": "已要求廠商重工",
                "closed_at": "2026-06-12"
            },
            {
                "event_id": "EVT-102",
                "ref_no": "",
                "event_date": "2026-06-15",
                "event_type": "VISIT",
                "supplier_name": "供應商B",
                "content": "例行訪廠交流",
                "status": "已完成",
                "category": "",
                "root_cause_category": "",
                "improvement_desc": "",
                "closed_at": None
            }
        ]

        with TemporaryDirectory() as tmp_dir:
            file_path = os.path.join(tmp_dir, "events_report.xlsx")
            
            ok, msg = event_service.export_events_report(
                file_path=file_path,
                start_date="2026-06-01",
                end_date="2026-06-30",
                temp_chart_paths={"category_pareto": os.path.join(tmp_dir, "missing_pareto.png")}
            )
            
            self.assertTrue(ok)
            self.assertTrue(os.path.exists(file_path))
            self.assertIn("已匯出至", msg)

            workbook = load_workbook(file_path)
            self.assertIn("異常類別柏拉圖", workbook.sheetnames)
            sheet = workbook["異常類別柏拉圖"]
            self.assertEqual(
                ["排名", "異常類別", "件數", "佔比(%)", "累積佔比(%)"],
                [sheet.cell(row=1, column=col).value for col in range(1, 6)],
            )
            self.assertEqual([1, "物料/來料品質異常", 1, 100.0, 100.0], [
                sheet.cell(row=2, column=col).value for col in range(1, 6)
            ])
            # 表格必須以與頁面圖表相同的區間參數取自同一實作
            mock_pareto.assert_called_once_with("2026-06-01", "2026-06-30")
