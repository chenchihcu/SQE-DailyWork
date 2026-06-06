from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from database import repository
from services import event_service


class VisitDefectNotesTests(unittest.TestCase):
    def setUp(self) -> None:
        base_tmp_dir = Path("scratch")
        base_tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = base_tmp_dir / f"sqe_visit_defect_notes_{uuid4().hex}.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def _create_supplier(self, name: str = "Visit Defect Supplier") -> str:
        return repository.create_supplier_record(self.conn, supplier_name=name)

    def _create_product(self, supplier_id: str, code: str, name: str) -> str:
        return repository.create_product_record(
            self.conn,
            product_code=code,
            product_name=name,
            supplier_id=supplier_id,
        )

    def test_create_visit_records_multiple_products_and_defect_notes(self) -> None:
        supplier_id = self._create_supplier()
        product_a = self._create_product(supplier_id, "A-001", "產品A")
        product_b = self._create_product(supplier_id, "B-001", "產品B")

        visit_id = repository.create_visit(
            self.conn,
            visit_date="2026-05-22",
            supplier_id=supplier_id,
            visitor_name="SQE",
            summary="同日訪廠，上午產品A，下午產品B",
            product_sections=[
                {
                    "product_id": product_a,
                    "time_slot": "上午",
                    "work_order_no": "WO-A",
                    "production_qty": 120,
                    "summary": "上午查看產品A",
                    "defect_notes": [
                        {
                            "defect_desc": "生產前沒有依規定全檢材料",
                            "improvement_desc": "已建立 SOP，標準化作業",
                        },
                        {
                            "defect_desc": "沒有收到原物料規格書",
                            "improvement_desc": "",
                            "note": "文件待補",
                        },
                    ],
                },
                {
                    "product_id": product_b,
                    "time_slot": "下午",
                    "work_order_no": "WO-B",
                    "production_qty": 80,
                    "summary": "下午查看產品B",
                    "defect_notes": [
                        {
                            "defect_desc": "包裝區標示未更新",
                            "improvement_desc": "現場已更換標示",
                        }
                    ],
                },
            ],
            defect_notes=[
                {
                    "defect_desc": "共通現場動線需保持暢通",
                    "improvement_desc": "已於現場提醒並整理",
                }
            ],
        )

        detail = repository.get_visit_detail(self.conn, visit_id)
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual("SQE", detail["visitor_name"])
        self.assertEqual("產品A、產品B", detail["product_name"])
        self.assertEqual("A-001、B-001", detail["product_code"])
        self.assertEqual(2, len(detail["product_sections"]))
        self.assertEqual(4, detail["defect_note_count"])
        self.assertEqual(1, detail["pending_improvement_count"])
        self.assertEqual("缺失 4 筆 / 待補改善 1 筆", detail["defect_note_summary"])
        statuses = {note["defect_desc"]: note["status"] for note in detail["defect_notes"]}
        self.assertEqual("已記錄改善", statuses["生產前沒有依規定全檢材料"])
        self.assertEqual("待補改善", statuses["沒有收到原物料規格書"])

        event = repository.list_events(self.conn, event_type="VISIT")[0]
        self.assertEqual("產品A、產品B", event["product_name"])
        self.assertEqual("缺失 4 筆 / 待補改善 1 筆", event["defect_note_summary"])
        self.assertIn("缺失 4 筆 / 待補改善 1 筆", event["content"])

    def test_create_visit_allows_visit_level_defect_without_product_section(self) -> None:
        supplier_id = self._create_supplier("Visit Level Defect Supplier")

        visit_id = repository.create_visit(
            self.conn,
            visit_date="2026-05-22",
            supplier_id=supplier_id,
            summary="共通現場問題",
            defect_notes=[
                {
                    "defect_desc": "現場文件未集中放置",
                    "improvement_desc": "",
                    "note": "下次訪廠補看",
                }
            ],
        )

        detail = repository.get_visit_detail(self.conn, visit_id)
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual([], detail["product_sections"])
        self.assertEqual("", detail["product_name"])
        self.assertEqual(1, detail["defect_note_count"])
        self.assertEqual(1, detail["pending_improvement_count"])
        self.assertEqual("待補改善", detail["defect_notes"][0]["status"])

    def test_update_visit_rewrites_sections_and_defect_notes(self) -> None:
        supplier_id = self._create_supplier("Rewrite Visit Supplier")
        product_a = self._create_product(supplier_id, "RW-A", "重寫前產品")
        product_b = self._create_product(supplier_id, "RW-B", "重寫後產品")
        visit_id = repository.create_visit(
            self.conn,
            visit_date="2026-05-22",
            supplier_id=supplier_id,
            product_sections=[
                {
                    "product_id": product_a,
                    "defect_notes": [{"defect_desc": "舊缺失"}],
                }
            ],
        )

        repository.update_visit(
            self.conn,
            visit_id=visit_id,
            visit_date="2026-05-23",
            supplier_id=supplier_id,
            product_sections=[
                {
                    "product_id": product_b,
                    "defect_notes": [
                        {
                            "defect_desc": "新缺失",
                            "improvement_desc": "已現場改善",
                        }
                    ],
                }
            ],
            defect_notes=[{"defect_desc": "新的共通缺失"}],
        )

        detail = repository.get_visit_detail(self.conn, visit_id)
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual("2026-05-23", detail["visit_date"])
        self.assertEqual("重寫後產品", detail["product_name"])
        descriptions = {note["defect_desc"] for note in detail["defect_notes"]}
        self.assertEqual({"新缺失", "新的共通缺失"}, descriptions)
        self.assertEqual(2, detail["defect_note_count"])

    def test_legacy_single_product_payload_backfills_one_product_section(self) -> None:
        supplier_id = self._create_supplier("Legacy Product Visit Supplier")
        product_id = self._create_product(supplier_id, "LEG-001", "舊欄位產品")

        visit_id = repository.create_visit(
            self.conn,
            visit_date="2026-05-22",
            supplier_id=supplier_id,
            product_id=product_id,
            work_order_no="LEG-WO",
            production_qty=25,
            summary="舊單產品 payload",
        )

        detail = repository.get_visit_detail(self.conn, visit_id)
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(1, len(detail["product_sections"]))
        section = detail["product_sections"][0]
        self.assertEqual(product_id, section["product_id"])
        self.assertEqual("舊欄位產品", section["product_name"])
        self.assertEqual("LEG-WO", section["work_order_no"])
        self.assertEqual(25, section["production_qty"])

    def test_service_allows_visit_level_defect_without_product(self) -> None:
        supplier_id = self._create_supplier("Service Visit Defect Supplier")

        with patch.object(event_service, "get_connection", return_value=self.conn):
            visit_id = event_service.create_visit(
                {
                    "visit_date": "2026-05-22",
                    "supplier_id": supplier_id,
                    "summary": "訪廠層級缺失",
                    "defect_notes": [{"defect_desc": "共通問題"}],
                }
            )

        detail = repository.get_visit_detail(self.conn, visit_id)
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(1, detail["defect_note_count"])
        self.assertEqual("", detail["product_name"])

    def test_confirmed_visit_defect_creates_supplier_anomaly_not_warehouse_defect(
        self,
    ) -> None:
        supplier_id = self._create_supplier("Shared Master Data Supplier")
        product_id = self._create_product(supplier_id, "SHARED-001", "共用公司產品")
        visit_id = repository.create_visit(
            self.conn,
            visit_date="2026-05-22",
            supplier_id=supplier_id,
            product_id=product_id,
            defect_notes=[
                {
                    "defect_desc": "訪廠稽核發現製程檢查表未即時更新",
                    "improvement_desc": "供應商需補齊紀錄",
                }
            ],
        )

        with patch.object(event_service, "get_connection", return_value=self.conn):
            result = event_service.create_anomaly_with_visit_link(
                {
                    "visit_id": visit_id,
                    "sync_visit": False,
                    "anomaly_date": "2026-05-22",
                    "supplier_id": supplier_id,
                    "product_id": product_id,
                    "category": "訪廠/稽核缺失",
                    "problem_desc": "訪廠稽核發現製程檢查表未即時更新",
                    "pending_items": "供應商需補齊紀錄",
                }
            )

        self.assertEqual("linked", result["visit_action"])
        anomaly = self.conn.execute(
            """
            SELECT visit_id, supplier_id, product_id, category, problem_desc
            FROM anomalies
            WHERE anomaly_no = ?
            """,
            (result["anomaly_no"],),
        ).fetchone()
        self.assertIsNotNone(anomaly)
        assert anomaly is not None
        self.assertEqual(visit_id, anomaly["visit_id"])
        self.assertEqual(supplier_id, anomaly["supplier_id"])
        self.assertEqual(product_id, anomaly["product_id"])
        self.assertEqual("訪廠/稽核缺失", anomaly["category"])

        warehouse_defect_count = self.conn.execute(
            "SELECT COUNT(*) FROM defect_records"
        ).fetchone()[0]
        self.assertEqual(0, warehouse_defect_count)

        self.assertIsNotNone(repository.get_supplier(self.conn, supplier_id))
        self.assertIsNotNone(repository.get_product(self.conn, product_id))

    def test_pending_visit_defect_note_can_be_confirmed_once(self) -> None:
        supplier_id = self._create_supplier("Pending Audit Supplier")
        product_id = self._create_product(supplier_id, "PENDING-001", "待確認產品")
        visit_id = repository.create_visit(
            self.conn,
            visit_date="2026-05-23",
            supplier_id=supplier_id,
            product_id=product_id,
            defect_notes=[
                {
                    "defect_desc": "稽核發現製程紀錄未每日簽核",
                    "improvement_desc": "供應商需補簽並建立日檢點",
                }
            ],
        )
        pending = repository.list_pending_visit_defect_notes(self.conn)
        self.assertEqual(1, len(pending))
        self.assertEqual(visit_id, pending[0]["visit_id"])
        self.assertEqual(product_id, pending[0]["product_id"])

        result = repository.confirm_visit_defect_note_as_anomaly(
            self.conn,
            note_id=pending[0]["id"],
            responsible_person="SQE",
            due_date="2026-06-15",
        )

        self.assertEqual("linked", result["visit_action"])
        self.assertEqual(0, len(repository.list_pending_visit_defect_notes(self.conn)))
        detail = repository.get_visit_detail(self.conn, visit_id)
        self.assertIsNotNone(detail)
        assert detail is not None
        confirmed_note = detail["defect_notes"][0]
        self.assertEqual(result["anomaly_id"], confirmed_note["confirmed_anomaly_id"])
        self.assertTrue(confirmed_note["confirmed_at"])
        anomaly = self.conn.execute(
            """
            SELECT visit_id, product_id, category, problem_desc, responsible_person, due_date
            FROM anomalies
            WHERE id = ?
            """,
            (result["anomaly_id"],),
        ).fetchone()
        self.assertIsNotNone(anomaly)
        assert anomaly is not None
        self.assertEqual(visit_id, anomaly["visit_id"])
        self.assertEqual(product_id, anomaly["product_id"])
        self.assertEqual("訪廠/稽核缺失", anomaly["category"])
        self.assertEqual("SQE", anomaly["responsible_person"])
        self.assertEqual("2026-06-15", anomaly["due_date"])
        self.assertEqual(
            0,
            self.conn.execute("SELECT COUNT(*) FROM defect_records").fetchone()[0],
        )
        with self.assertRaises(ValueError):
            repository.confirm_visit_defect_note_as_anomaly(
                self.conn,
                note_id=pending[0]["id"],
            )

    def test_confirmed_visit_defect_notes_block_visit_rewrite(self) -> None:
        supplier_id = self._create_supplier("Confirmed Rewrite Supplier")
        product_id = self._create_product(supplier_id, "CONF-001", "已確認產品")
        visit_id = repository.create_visit(
            self.conn,
            visit_date="2026-05-24",
            supplier_id=supplier_id,
            product_id=product_id,
            defect_notes=[{"defect_desc": "缺失已轉異常"}],
        )
        note = repository.list_pending_visit_defect_notes(self.conn)[0]
        repository.confirm_visit_defect_note_as_anomaly(
            self.conn,
            note_id=note["id"],
        )

        with self.assertRaises(ValueError):
            repository.update_visit(
                self.conn,
                visit_id=visit_id,
                visit_date="2026-05-24",
                supplier_id=supplier_id,
                product_id=product_id,
                defect_notes=[{"defect_desc": "覆寫缺失"}],
            )


if __name__ == "__main__":
    unittest.main()
