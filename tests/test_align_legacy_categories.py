from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from uuid import uuid4

from database import repository


class AlignLegacyCategoriesTests(unittest.TestCase):
    def setUp(self) -> None:
        base_tmp_dir = Path("scratch")
        base_tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = base_tmp_dir / f"sqe_align_test_{uuid4().hex}.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.supplier_id = repository.create_supplier_record(
            self.conn, supplier_name="Test Supplier"
        )

    def tearDown(self) -> None:
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def test_align_legacy_anomaly_categories(self) -> None:
        # 1. 建立具有各種分類（新舊混合、有空格、無空格）的異常案件
        test_cases = [
            ("文件/SOP 不足", "文件/SOP 不足", "規範文件缺漏"),
            ("文件/SOP不足", "文件/SOP不足", "規範文件缺漏"),
            ("人為操作疏失", "人為操作疏失", "標準作業不落實"),
            ("物料/來料問題", "物料/來料問題", "來料品質不良"),
            ("製程參數異常", "製程參數異常", "製程參數失控"),
            ("設計缺陷", "設計缺陷", "設計匹配不良"),
            # 這些是不應該被更換的合法現有分類
            ("規範文件缺漏", "規範文件缺漏", "規範文件缺漏"),
            ("其他", "其他", "其他"),
            ("", "", ""),
        ]

        anomaly_ids = []
        for idx, (orig_cat, orig_cause, _) in enumerate(test_cases):
            # 建立異常案
            ano_no = repository.create_anomaly(
                self.conn,
                anomaly_date=f"2026-01-{10+idx:02d}",
                supplier_id=self.supplier_id,
                problem_desc=f"Problem {idx}",
                category=orig_cat,
            )
            # 因為 create_anomaly 不會直接塞 root_cause_category，我們手動 update 寫入 root_cause_category 欄位以做為舊資料測試
            self.conn.execute(
                "UPDATE anomalies SET root_cause_category = ? WHERE anomaly_no = ?",
                (orig_cause, ano_no)
            )
            self.conn.commit()
            anomaly_ids.append(ano_no)

        # 2. 執行對齊函數
        updated_count = repository.align_legacy_anomaly_categories(self.conn)
        self.conn.commit()

        # 我們預期會被 update 的個數：
        # 對應 6 個要被更換的項目 (前 6 個)，各包含 category 與 root_cause_category (也就是一共 12 次 update 動作被計算進 rowcount)
        self.assertEqual(12, updated_count)

        # 3. 驗證資料是否已全部轉換為預期的新值
        for idx, (*_, expected_val) in enumerate(test_cases):
            ano_no = anomaly_ids[idx]
            row = self.conn.execute(
                "SELECT category, root_cause_category FROM anomalies WHERE anomaly_no = ?",
                (ano_no,)
            ).fetchone()
            self.assertEqual(expected_val, row["category"])
            self.assertEqual(expected_val, row["root_cause_category"])


if __name__ == "__main__":
    unittest.main()
