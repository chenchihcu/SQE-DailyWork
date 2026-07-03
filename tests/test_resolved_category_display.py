from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from uuid import uuid4

from database import repository


class ResolvedCategoryDisplayTests(unittest.TestCase):
    def setUp(self) -> None:
        base_tmp_dir = Path("scratch")
        base_tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = base_tmp_dir / f"sqe_resolved_cat_test_{uuid4().hex}.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.supplier_id = repository.create_supplier_record(
            self.conn, supplier_name="Test Supplier"
        )
        self.product_id = repository.create_product_record(
            self.conn,
            product_code="P-TEST",
            product_name="Test Product",
            product_stage="量產",
            supplier_id=self.supplier_id,
        )

    def tearDown(self) -> None:
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def test_resolved_category_lifecycle(self) -> None:
        # 1. 建立一個待處理的異常案件
        anomaly_no = repository.create_anomaly(
            self.conn,
            anomaly_date="2026-07-03",
            supplier_id=self.supplier_id,
            product_id=self.product_id,
            problem_desc="測試問題描述",
            category="製程參數失控",
        )
        self.conn.commit()

        # 查詢取得 UUID id
        row = self.conn.execute("SELECT id FROM anomalies WHERE anomaly_no = ?", (anomaly_no,)).fetchone()
        self.assertIsNotNone(row)
        anomaly_id = row["id"]

        # 2. 驗證待處理狀態下，清單與詳情傳回的均為原始類別 "製程參數失控"
        detail = repository.get_anomaly_detail(self.conn, anomaly_id)
        self.assertIsNotNone(detail)
        self.assertEqual("製程參數失控", detail["category"])

        events = repository.list_events(self.conn, event_type="ANOMALY")
        self.assertEqual(1, len(events))
        self.assertEqual("製程參數失控", events[0]["category"])

        # 3. 結案該異常案件，設定原因分類為 "其他"
        repository.close_anomaly(
            self.conn,
            anomaly_id=anomaly_id,
            improvement_desc="已完成改善",
            closed_by="SQE Auditor",
            root_cause_category="其他",
            closed_at="2026-07-03",
        )
        self.conn.commit()

        # 4. 驗證已結案狀態下，清單與詳情傳回的 category 均為原因分類 "其他"
        detail_closed = repository.get_anomaly_detail(self.conn, anomaly_id)
        self.assertIsNotNone(detail_closed)
        self.assertEqual("其他", detail_closed["category"])
        self.assertEqual("其他", detail_closed["root_cause_category"])

        events_closed = repository.list_events(self.conn, event_type="ANOMALY", event_scope="CLOSED_ONLY")
        self.assertEqual(1, len(events_closed))
        self.assertEqual("其他", events_closed[0]["category"])

        # 5. 重新開啟該異常案件
        repository.reopen_anomaly(self.conn, anomaly_id)
        self.conn.commit()

        # 6. 驗證重新開啟後，傳回的 category 還原為原始類別 "製程參數失控"
        detail_reopened = repository.get_anomaly_detail(self.conn, anomaly_id)
        self.assertIsNotNone(detail_reopened)
        self.assertEqual("製程參數失控", detail_reopened["category"])
        self.assertEqual("", detail_reopened["root_cause_category"])

        events_reopened = repository.list_events(self.conn, event_type="ANOMALY")
        self.assertEqual(1, len(events_reopened))
        self.assertEqual("製程參數失控", events_reopened[0]["category"])


if __name__ == "__main__":
    unittest.main()
