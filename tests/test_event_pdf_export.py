from __future__ import annotations

import os
import unittest
from datetime import datetime
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from services import event_pdf_exporter, event_service


class EventPdfExportTests(unittest.TestCase):
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
            "event_date": "2026-05-07",
            "supplier_name": "振順豐",
        }

    def _visit_detail(self) -> dict:
        return {
            "visit_date": "2026-05-07",
            "supplier_name": "振順豐",
            "product_name": "converter 轉接板 VS80",
            "product_stage": "試產",
            "work_order_no": "5102-260401002",
            "production_qty": 220,
            "status": "已完成",
            "tech_transfer": True,
            "tech_transfer_doc": True,
            "carrier_requirement": False,
            "dispensing_process": True,
            "functional_test": False,
            "packaging_requirement": True,
            "summary": "訪廠確認製程條件與技轉項目。",
        }

    def _anomaly_row(self, *, linked: bool) -> dict:
        return {
            "event_id": "anomaly-001",
            "event_type": "ANOMALY",
            "event_date": "2026-05-07",
            "ref_no": "20260507001",
            "supplier_name": "振順豐",
            "linked_visit_id": "visit-001" if linked else "",
            "linked_visit_date": "2026-05-07" if linked else "",
        }

    def _anomaly_detail(self, *, linked: bool) -> dict:
        return {
            "id": "anomaly-001",
            "anomaly_no": "20260507001",
            "anomaly_date": "2026-05-07",
            "supplier_name": "振順豐",
            "product_name": "converter 轉接板 VS80",
            "product_stage": "試產",
            "outsource_work_order": "5102-260401002",
            "batch_qty": 220,
            "status": "待處理",
            "category": "刮傷",
            "product_lot_no": "LOT-001",
            "problem_desc": "載具刮傷，FPC 對位異常。",
            "visit_id": "visit-001" if linked else "",
            "improvement_desc": "",
            "closed_by": "",
            "root_cause_category": "",
            "closed_at": "",
        }

    def _write_test_image(
        self,
        path: Path,
        *,
        width: int,
        height: int,
        color: str = "#2F80ED",
    ) -> None:
        image = QImage(width, height, QImage.Format.Format_RGB32)
        image.fill(QColor(color))
        self.assertTrue(image.save(str(path)), f"failed to save {path}")

    def test_visit_html_contains_simple_visit_report_fields(self) -> None:
        html = event_pdf_exporter.build_event_pdf_html(
            self._visit_row(),
            self._visit_detail(),
            exported_at=datetime(2026, 5, 7, 10, 30, 0),
        )

        self.assertIn("供應商訪廠紀錄報告", html)
        self.assertIn("Medical Intubation Technology Corporation", html)
        self.assertIn("converter 轉接板 VS80", html)
        self.assertIn("技轉項目", html)
        self.assertIn("2026-05-07 10:30:00", html)

    def test_visit_html_lists_lightweight_defect_notes_by_product_section(self) -> None:
        detail = self._visit_detail()
        detail.update(
            {
                "visitor_name": "SQE",
                "product_sections": [
                    {
                        "id": "section-a",
                        "product_name": "產品A",
                        "time_slot": "上午",
                        "work_order_no": "WO-A",
                        "production_qty": 120,
                        "summary": "上午查看產品A",
                    },
                    {
                        "id": "section-b",
                        "product_name": "產品B",
                        "time_slot": "下午",
                    },
                ],
                "defect_notes": [
                    {
                        "visit_product_section_id": "",
                        "defect_desc": "共通現場動線需保持暢通",
                        "improvement_desc": "已於現場提醒並整理",
                        "note": "",
                    },
                    {
                        "visit_product_section_id": "section-a",
                        "defect_desc": "生產前沒有依規定全檢材料",
                        "improvement_desc": "已建立 SOP，標準化作業",
                        "note": "",
                    },
                    {
                        "visit_product_section_id": "section-b",
                        "defect_desc": "沒有收到原物料規格書",
                        "improvement_desc": "",
                        "note": "下次補看",
                    },
                ],
            }
        )

        html = event_pdf_exporter.build_event_pdf_html(
            self._visit_row(),
            detail,
            exported_at=datetime(2026, 5, 7, 10, 30, 0),
        )

        self.assertIn("缺失與改善紀錄", html)
        self.assertIn("共通現場缺失", html)
        self.assertIn("產品A", html)
        self.assertIn("產品B", html)
        self.assertIn("生產前沒有依規定全檢材料", html)
        self.assertIn("已建立 SOP，標準化作業", html)
        self.assertIn("待補改善", html)
        self.assertNotIn("8D 報告", html)
        self.assertNotIn("CAPA", html)
        self.assertNotIn("稽核簽核", html)

    def test_anomaly_html_distinguishes_linked_and_standalone_titles(self) -> None:
        linked_html = event_pdf_exporter.build_event_pdf_html(
            self._anomaly_row(linked=True),
            self._anomaly_detail(linked=True),
            linked_visit=self._visit_detail(),
        )
        standalone_html = event_pdf_exporter.build_event_pdf_html(
            self._anomaly_row(linked=False),
            self._anomaly_detail(linked=False),
        )

        self.assertIn("訪廠異常追蹤報告", linked_html)
        self.assertIn("關聯訪廠", linked_html)
        self.assertIn("供應商異常處理報告", standalone_html)
        self.assertNotIn("關聯訪廠", standalone_html)

    def test_report_html_embeds_mitcorp_brand_assets(self) -> None:
        html = event_pdf_exporter.build_event_pdf_html(
            self._anomaly_row(linked=False),
            self._anomaly_detail(linked=False),
            exported_at=datetime(2026, 5, 7, 10, 30, 0),
        )

        self.assertIn("data:image/png;base64,", html)
        self.assertIn("#065977", html)
        self.assertIn("#0274BE", html)
        self.assertIn("document-meta-key", html)
        self.assertIn("異常案號", html)
        self.assertIn("列印時間", html)
        self.assertIn("2026-05-07 10:30:00", html)
        self.assertIn("status-chip", html)
        self.assertIn("brand-topline-1", html)
        self.assertIn("brand-topline-2", html)
        self.assertNotIn("Generated by SQETOOL", html)
        self.assertIn("Generated by SQE DailyWork", html)

    def test_problem_description_uses_structured_numbered_paragraphs(self) -> None:
        detail = self._anomaly_detail(linked=True)
        detail["problem_desc"] = (
            "1. 錫膏印刷: 載具2點 + FPC 2點\n"
            "2. 載具開孔*10: 半自動印刷機專用\n"
            "3. 現場發現:\n"
            "3.1 錫膏印刷錫量過低\n"
            "3.2 過 reflow 後發現 Type-C 空焊"
        )

        html = event_pdf_exporter.build_event_pdf_html(
            self._anomaly_row(linked=True),
            detail,
            linked_visit=self._visit_detail(),
            exported_at=datetime(2026, 5, 7, 10, 30, 0),
        )

        self.assertRegex(
            html,
            r'class="[^"]*paragraph-item[^"]*"[^>]*>1\. 錫膏印刷: 載具2點 \+ FPC 2點</div>',
        )
        self.assertRegex(
            html,
            r'class="[^"]*paragraph-subitem[^"]*"[^>]*>3\.1 錫膏印刷錫量過低</div>',
        )
        self.assertIn("3.2 過 reflow 後發現 Type-C 空焊", html)

    def test_default_filename_sanitizes_windows_invalid_chars(self) -> None:
        row = self._anomaly_row(linked=False)
        detail = self._anomaly_detail(linked=False)
        detail["supplier_name"] = "供應商/A:B"

        filename = event_pdf_exporter.default_event_pdf_filename(row, detail)

        self.assertEqual("SQE_異常單_20260507001_供應商_A_B.pdf", filename)

    def test_export_event_pdf_creates_non_empty_pdf(self) -> None:
        output = self.scratch / f"event_pdf_{uuid4().hex}.pdf"
        self.generated_files.append(output)

        ok, msg = event_pdf_exporter.export_event_pdf(
            output,
            self._visit_row(),
            self._visit_detail(),
        )

        self.assertTrue(ok, msg)
        self.assertTrue(output.exists())
        self.assertGreater(output.stat().st_size, 1000)

    def test_closed_anomaly_html_includes_closer_and_root_cause(self) -> None:
        detail = self._anomaly_detail(linked=False)
        detail.update(
            {
                "status": "已結案",
                "improvement_desc": "更換刮傷載具並校驗對位。",
                "closed_by": "Charlie",
                "root_cause_category": "設備/治具異常",
                "closed_at": "2026-05-09",
            }
        )

        html = event_pdf_exporter.build_event_pdf_html(
            self._anomaly_row(linked=False), detail
        )

        self.assertIn("結案資訊", html)
        self.assertIn("結案人員", html)
        self.assertIn("Charlie", html)
        self.assertIn("原因分類", html)
        self.assertIn("設備/治具異常", html)
        self.assertIn("更換刮傷載具並校驗對位。", html)

    def test_closed_anomaly_html_embeds_attachment_image(self) -> None:
        from services import attachment_manager

        anomaly_id = f"anomaly-attach-{uuid4().hex}"
        target_dir = attachment_manager.ANOMALY_ATTACHMENT_ROOT / anomaly_id
        target_dir.mkdir(parents=True, exist_ok=True)
        image_path = target_dir / "renamed_evidence.png"
        # Minimal 1x1 transparent PNG
        image_path.write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f"
            b"\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xcf\xc0\x00\x00"
            b"\x00\x03\x00\x01\x9a\xa3\x9d\xc6\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        attachment_manager.set_anomaly_captions(
            anomaly_id, {image_path.name: "結案前補拍的現場照片"}
        )
        try:
            row = self._anomaly_row(linked=False)
            row["event_id"] = anomaly_id
            detail = self._anomaly_detail(linked=False)
            detail["id"] = anomaly_id
            detail.update(
                {
                    "status": "已結案",
                    "improvement_desc": "附證據照片。",
                    "closed_by": "Dana",
                    "closed_at": "2026-05-09",
                }
            )

            html = event_pdf_exporter.build_event_pdf_html(row, detail)

            self.assertIn("附件照片", html)
            self.assertIn("data:image/png;base64,", html)
            self.assertIn("renamed_evidence.png", html)
            self.assertIn("結案前補拍的現場照片", html)
        finally:
            if image_path.exists():
                image_path.unlink()
            captions_path = target_dir / attachment_manager.CAPTIONS_FILENAME
            if captions_path.exists():
                captions_path.unlink()
            try:
                target_dir.rmdir()
            except OSError:
                pass

    def test_attachment_html_scales_large_and_multiple_images_for_pdf(self) -> None:
        from services import attachment_manager

        anomaly_id = f"anomaly-layout-{uuid4().hex}"
        target_dir = attachment_manager.ANOMALY_ATTACHMENT_ROOT / anomaly_id
        target_dir.mkdir(parents=True, exist_ok=True)
        images = [
            ("large_landscape.jpg", 2397, 1748),
            ("mid_photo.jpg", 733, 624),
            ("portrait_photo.jpg", 900, 1600),
        ]
        images.extend((f"evidence_{idx:02}.jpg", 1024, 768) for idx in range(12))
        try:
            for name, width, height in images:
                self._write_test_image(
                    target_dir / name,
                    width=width,
                    height=height,
                )
            attachment_manager.set_anomaly_captions(
                anomaly_id, {"large_landscape.jpg": "大圖等比例輸出"}
            )

            row = self._anomaly_row(linked=False)
            row["event_id"] = anomaly_id
            detail = self._anomaly_detail(linked=False)
            detail["id"] = anomaly_id

            html = event_pdf_exporter.build_event_pdf_html(row, detail)

            self.assertIn("附件照片", html)
            self.assertEqual(15, html.count("page-break-inside:avoid;width:100%;"))
            self.assertIn('width="660" height="481"', html)
            self.assertIn('width="660" height="562"', html)
            self.assertIn('width="439" height="780"', html)
            self.assertIn("大圖等比例輸出", html)
            self.assertNotIn("max-height:", html)
            self.assertNotIn('width="50%" align="center"', html)
        finally:
            if target_dir.exists():
                for child in target_dir.iterdir():
                    if child.is_file():
                        child.unlink()
                try:
                    target_dir.rmdir()
                except OSError:
                    pass

    def test_event_service_fetches_detail_before_pdf_export(self) -> None:
        row = self._anomaly_row(linked=True)
        detail = self._anomaly_detail(linked=True)
        linked_visit = self._visit_detail()

        calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

        def fake_get_anomaly_detail(event_id: str) -> dict:
            calls.append(("get_anomaly_detail", (event_id,), {}))
            return detail

        def fake_get_visit_detail(visit_id: str) -> dict:
            calls.append(("get_visit_detail", (visit_id,), {}))
            return linked_visit

        def fake_export_event_pdf(*args: object, **kwargs: object) -> tuple[bool, str]:
            calls.append(("export_event_pdf", args, kwargs))
            return True, "已匯出至：x.pdf"

        original_get_anomaly_detail = event_service.get_anomaly_detail
        original_get_visit_detail = event_service.get_visit_detail
        original_export_event_pdf = event_service.event_pdf_exporter.export_event_pdf
        try:
            event_service.get_anomaly_detail = fake_get_anomaly_detail
            event_service.get_visit_detail = fake_get_visit_detail
            event_service.event_pdf_exporter.export_event_pdf = fake_export_event_pdf
            ok, _msg = event_service.export_event_pdf("x.pdf", row)
        finally:
            event_service.get_anomaly_detail = original_get_anomaly_detail
            event_service.get_visit_detail = original_get_visit_detail
            event_service.event_pdf_exporter.export_event_pdf = original_export_event_pdf

        self.assertTrue(ok)
        self.assertEqual(
            [
                ("get_anomaly_detail", ("anomaly-001",), {}),
                ("get_visit_detail", ("visit-001",), {}),
                (
                    "export_event_pdf",
                    ("x.pdf", row, detail),
                    {"linked_visit": linked_visit},
                ),
            ],
            calls,
        )


if __name__ == "__main__":
    unittest.main()
