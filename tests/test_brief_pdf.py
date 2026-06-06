from __future__ import annotations

import os
import unittest
from datetime import datetime
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from services import event_pdf_exporter, event_service, line_service


class BriefPdfExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.scratch = Path("scratch")
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.generated_files: list[Path] = []

    def tearDown(self) -> None:
        for path in self.generated_files:
            if path.exists():
                path.unlink()

    def _visit_row(self) -> dict:
        return {
            "event_id": "visit-001",
            "event_type": "VISIT",
            "event_date": "2026-05-30",
            "supplier_name": "振順豐",
        }

    def _visit_detail(self) -> dict:
        return {
            "visit_date": "2026-05-30",
            "supplier_name": "振順豐",
            "product_name": "converter 轉接板 VS80",
            "visitor_name": "SQE_張三",
            "summary": "本次訪廠主要確認試產階段的製程穩定性，現場缺失已於對話框標記。",
            "status": "已完成",
        }

    def _anomaly_row(self) -> dict:
        return {
            "event_id": "anomaly-001",
            "event_type": "ANOMALY",
            "event_date": "2026-05-30",
            "ref_no": "20260530001",
            "supplier_name": "振順豐",
        }

    def _anomaly_detail(self) -> dict:
        return {
            "id": "anomaly-001",
            "anomaly_no": "20260530001",
            "anomaly_date": "2026-05-30",
            "supplier_name": "振順豐",
            "product_name": "converter 轉接板 VS80",
            "responsible_person": "李四",
            "due_date": "2026-06-05",
            "status": "待處理",
            "problem_desc": "電測不良，外觀有些微刮傷。",
            "improvement_desc": "",
        }

    def test_brief_visit_html_contains_basic_fields(self) -> None:
        html = event_pdf_exporter.build_brief_event_pdf_html(
            self._visit_row(),
            self._visit_detail(),
            exported_at=datetime(2026, 5, 30, 10, 30, 0),
        )

        self.assertIn("供應商訪廠精簡報告", html)
        self.assertIn("振順豐", html)
        self.assertIn("SQE_張三", html)
        self.assertNotIn("技轉項目", html)  # 確保技轉明細表格在精簡版中被移除

    def test_brief_anomaly_html_contains_basic_fields(self) -> None:
        html = event_pdf_exporter.build_brief_event_pdf_html(
            self._anomaly_row(),
            self._anomaly_detail(),
            exported_at=datetime(2026, 5, 30, 10, 30, 0),
        )

        self.assertIn("供應商異常處理精簡報告", html)
        self.assertIn("李四", html)
        self.assertIn("電測不良，外觀有些微刮傷。", html)
        self.assertNotIn("附件照片", html)  # 確保照片在精簡版中被移除

    def test_export_brief_event_pdf_creates_file(self) -> None:
        output = self.scratch / f"brief_event_{uuid4().hex}.pdf"
        self.generated_files.append(output)

        ok, msg = event_pdf_exporter.export_brief_event_pdf(
            output,
            self._anomaly_row(),
            self._anomaly_detail(),
        )

        self.assertTrue(ok, msg)
        self.assertTrue(output.exists())
        self.assertGreater(output.stat().st_size, 1000)

    def test_export_brief_pdf_wrapper_in_service(self) -> None:
        row = self._anomaly_row()
        detail = self._anomaly_detail()

        calls = []

        def fake_get_anomaly_detail(event_id: str) -> dict:
            return detail

        def fake_export_brief_event_pdf(*args, **kwargs) -> tuple[bool, str]:
            calls.append(("export_brief_event_pdf", args, kwargs))
            return True, "已匯出精簡版至：x.pdf"

        original_get_anomaly_detail = event_service.get_anomaly_detail
        original_export_brief_event_pdf = event_service.event_pdf_exporter.export_brief_event_pdf
        try:
            event_service.get_anomaly_detail = fake_get_anomaly_detail
            event_service.event_pdf_exporter.export_brief_event_pdf = fake_export_brief_event_pdf
            ok, _msg = event_service.export_brief_event_pdf("x.pdf", row)
        finally:
            event_service.get_anomaly_detail = original_get_anomaly_detail
            event_service.event_pdf_exporter.export_brief_event_pdf = original_export_brief_event_pdf

        self.assertTrue(ok)
        self.assertEqual(len(calls), 1)

    def test_render_brief_event_to_image_returns_qimage(self) -> None:
        from PySide6.QtGui import QImage

        image = event_pdf_exporter.render_brief_event_to_image(
            self._anomaly_row(),
            self._anomaly_detail(),
        )
        self.assertIsNotNone(image)
        self.assertIsInstance(image, QImage)
        self.assertGreater(image.width(), 0)
        self.assertGreater(image.height(), 0)

    def test_line_service_copy_image_to_clipboard_does_not_crash(self) -> None:
        from PySide6.QtGui import QImage

        # Create a small test image
        image = QImage(100, 100, QImage.Format.Format_ARGB32)
        image.fill(0xFFFF0000)

        # 呼叫複製到剪貼簿，確保能安全執行不崩潰
        res = line_service.copy_image_to_clipboard(image)
        # 在沒有真實顯示卡的 Offscreen 模式下，有時 clipboard 會回傳 False，
        # 但我們主要驗證執行時不會丟出錯誤
        self.assertIsInstance(res, bool)


if __name__ == "__main__":
    unittest.main()
