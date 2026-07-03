"""迴歸測試:責任人統計的未結案日期必須與 open_count 同一區間口徑。

Bug(修復前):get_responsible_person_stats_by_range 的 open_count 以
anomaly_date BETWEEN 篩選,但 min_open_date/max_open_date 來自不設日期
條件的全期查詢 — 洞察文字「區間內有 N 件未結案,最早累計自 YYYY/MM」
的日期可能指向不在 N 件之內(區間外)的案件,與圖表長條口徑矛盾。
"""

from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from database import repository
from services import event_service


class ResponsiblePersonStatsRangeTests(unittest.TestCase):
    def setUp(self) -> None:
        base_tmp_dir = Path("scratch")
        base_tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = base_tmp_dir / f"sqe_resp_stats_{uuid4().hex}.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.supplier_id = repository.create_supplier_record(
            self.conn, supplier_name="Range Supplier"
        )

    def tearDown(self) -> None:
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def _create_open_anomaly(self, anomaly_date: str, person: str) -> None:
        repository.create_anomaly(
            self.conn,
            anomaly_date=anomaly_date,
            supplier_id=self.supplier_id,
            problem_desc=f"Problem {anomaly_date}",
            category="其他",
            responsible_person=person,
        )
        self.conn.commit()

    def test_min_open_date_is_scoped_to_the_same_range_as_open_count(self) -> None:
        # 區間外(2026-01)與區間內(2026-03)各一件未結案
        self._create_open_anomaly("2026-01-10", "張三")
        self._create_open_anomaly("2026-03-05", "張三")

        with patch.object(event_service, "get_connection", return_value=self.conn):
            rows = event_service.get_responsible_person_stats_by_range(
                "2026-02-01", "2026-07-31"
            )

        row = next(r for r in rows if r["responsible_person"] == "張三")
        # open_count 是區間內計數;min/max_open_date 必須也落在同一區間,
        # 不能指向 2026-01-10 那件不在計數內的案件。
        self.assertEqual(1, row["open_count"])
        self.assertEqual("2026-03-05", row["min_open_date"])
        self.assertEqual("2026-03-05", row["max_open_date"])


if __name__ == "__main__":
    unittest.main()
