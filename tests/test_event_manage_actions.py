from __future__ import annotations

import sqlite3
import unittest
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from database import repository
from database.product_stage import PRODUCT_STAGE_TRIAL_PRODUCTION


class EventManageActionsTests(unittest.TestCase):
    def setUp(self) -> None:
        base_tmp_dir = Path("scratch")
        base_tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = base_tmp_dir / f"sqe_event_manage_{uuid4().hex}.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def _create_supplier(self, name: str) -> str:
        return repository.create_supplier_record(self.conn, supplier_name=name)

    def _create_product(
        self,
        supplier_id: str,
        *,
        code: str,
        name: str,
        secondary_supplier_id: str | None = None,
        product_stage: str = "量產",
    ) -> str:
        secondary_supplier = secondary_supplier_id or self._create_supplier(
            f"{name}-2nd"
        )
        return repository.create_product_record(
            self.conn,
            product_code=code,
            product_name=name,
            product_stage=product_stage,
            supplier_id=supplier_id,
            secondary_supplier_id=secondary_supplier,
        )

    def _find_anomaly_id(self, anomaly_no: str) -> str:
        row = self.conn.execute(
            "SELECT id FROM anomalies WHERE anomaly_no = ? LIMIT 1",
            (anomaly_no,),
        ).fetchone()
        self.assertIsNotNone(row)
        return str(row["id"])

    def test_anomaly_no_uses_yyyymmdd_sequence(self) -> None:
        supplier_id = self._create_supplier("Anomaly Sequence Supplier")
        first = repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-16",
            supplier_id=supplier_id,
            problem_desc="first",
        )
        second = repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-16",
            supplier_id=supplier_id,
            problem_desc="second",
        )
        next_day = repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-17",
            supplier_id=supplier_id,
            problem_desc="third",
        )
        preview = repository.preview_anomaly_no(self.conn, "2026-04-16")

        self.assertEqual("20260416001", first)
        self.assertEqual("20260416002", second)
        self.assertEqual("20260417001", next_day)
        self.assertEqual("20260416003", preview)

    def test_create_anomaly_rejects_invalid_date_format(self) -> None:
        supplier_id = self._create_supplier("Invalid Date Supplier")
        with self.assertRaises(ValueError) as ctx:
            repository.create_anomaly(
                self.conn,
                anomaly_date="2026/04/16",
                supplier_id=supplier_id,
                problem_desc="invalid date format",
            )
        self.assertIn("YYYY-MM-DD", str(ctx.exception))

    def test_create_anomaly_rejects_future_date(self) -> None:
        supplier_id = self._create_supplier("Future Date Supplier")
        future_date = (date.today() + timedelta(days=1)).isoformat()
        with self.assertRaises(ValueError) as ctx:
            repository.create_anomaly(
                self.conn,
                anomaly_date=future_date,
                supplier_id=supplier_id,
                problem_desc="future anomaly",
            )
        self.assertIn("future", str(ctx.exception).lower())

    def test_create_visit_allows_future_date(self) -> None:
        supplier_id = self._create_supplier("Future Visit Supplier")
        future_date = (date.today() + timedelta(days=1)).isoformat()
        visit_id = repository.create_visit(
            self.conn,
            visit_date=future_date,
            supplier_id=supplier_id,
            summary="future visit is allowed",
        )
        detail = repository.get_visit_detail(self.conn, visit_id)
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(future_date, detail["visit_date"])

    def test_create_anomaly_rejects_negative_batch_qty(self) -> None:
        supplier_id = self._create_supplier("Negative Batch Supplier")
        with self.assertRaises(ValueError) as ctx:
            repository.create_anomaly(
                self.conn,
                anomaly_date="2026-04-16",
                supplier_id=supplier_id,
                problem_desc="negative batch",
                batch_qty=-1,
            )
        self.assertIn("negative", str(ctx.exception).lower())

    def test_create_visit_rejects_negative_production_qty(self) -> None:
        supplier_id = self._create_supplier("Negative Qty Supplier")
        with self.assertRaises(ValueError) as ctx:
            repository.create_visit(
                self.conn,
                visit_date="2026-04-16",
                supplier_id=supplier_id,
                production_qty=-5,
            )
        self.assertIn("negative", str(ctx.exception).lower())

    def test_update_anomaly_success(self) -> None:
        supplier_a = self._create_supplier("Supplier A")
        supplier_b = self._create_supplier("Supplier B")
        product_b = self._create_product(
            supplier_b,
            code="P-B-001",
            name="Product B",
        )
        anomaly_no = repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-16",
            supplier_id=supplier_a,
            problem_desc="before update",
        )
        anomaly_id = self._find_anomaly_id(anomaly_no)

        repository.update_anomaly(
            self.conn,
            anomaly_id=anomaly_id,
            anomaly_date="2026-04-18",
            supplier_id=supplier_b,
            problem_desc="after update",
            category="CAT-A",
            product_lot_no="LOT-001",
            product_id=product_b,
            product_stage="試產",
            outsource_work_order="WO-123",
            batch_qty=88,
        )

        detail = repository.get_anomaly_detail(self.conn, anomaly_id)
        self.assertIsNotNone(detail)
        self.assertEqual("2026-04-18", detail["anomaly_date"])
        self.assertTrue(detail["anomaly_no"].startswith("20260418"))
        self.assertEqual(supplier_b, detail["supplier_id"])
        self.assertEqual("after update", detail["problem_desc"])
        self.assertEqual("CAT-A", detail["category"])
        self.assertEqual("LOT-001", detail["product_lot_no"])
        self.assertEqual("量產", detail["product_stage"])
        self.assertEqual("WO-123", detail["outsource_work_order"])
        self.assertEqual(88, detail["batch_qty"])
        self.assertEqual(product_b, detail["product_id"])

    def test_quality_report_required_preserves_legacy_null_and_round_trips_bool(self) -> None:
        supplier_id = self._create_supplier("Quality Report Supplier")
        product_id = self._create_product(
            supplier_id,
            code="QR-001",
            name="Quality Report Product",
        )
        legacy_no = repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-16",
            supplier_id=supplier_id,
            problem_desc="legacy unset",
            product_id=product_id,
        )
        legacy_id = self._find_anomaly_id(legacy_no)
        self.assertIsNone(
            repository.get_anomaly_detail(self.conn, legacy_id)[
                "quality_report_required"
            ]
        )

        required_no = repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-17",
            supplier_id=supplier_id,
            problem_desc="required yes",
            product_id=product_id,
            quality_report_required=True,
        )
        required_id = self._find_anomaly_id(required_no)
        self.assertIs(
            True,
            repository.get_anomaly_detail(self.conn, required_id)[
                "quality_report_required"
            ],
        )

        repository.update_anomaly(
            self.conn,
            anomaly_id=required_id,
            anomaly_date="2026-04-17",
            supplier_id=supplier_id,
            problem_desc="required no",
            product_id=product_id,
            quality_report_required=False,
        )
        self.assertIs(
            False,
            repository.get_anomaly_detail(self.conn, required_id)[
                "quality_report_required"
            ],
        )

    def test_schema_upgrade_adds_quality_report_required_without_backfill(self) -> None:
        supplier_id = self._create_supplier("Legacy Schema Supplier")
        anomaly_no = repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-16",
            supplier_id=supplier_id,
            problem_desc="legacy row",
        )
        anomaly_id = self._find_anomaly_id(anomaly_no)
        self.conn.execute("ALTER TABLE anomalies DROP COLUMN quality_report_required")
        self.conn.commit()

        repository.create_schema(self.conn)

        columns = {
            str(row["name"])
            for row in self.conn.execute("PRAGMA table_info(anomalies)").fetchall()
        }
        self.assertIn("quality_report_required", columns)
        self.assertIsNone(
            repository.get_anomaly_detail(self.conn, anomaly_id)[
                "quality_report_required"
            ]
        )

    def test_create_anomaly_allows_secondary_source_product_match(self) -> None:
        supplier_primary = self._create_supplier("Primary Supplier")
        supplier_secondary = self._create_supplier("Secondary Supplier")
        product_id = self._create_product(
            supplier_primary,
            code="P-SEC-001",
            name="Secondary Match Product",
            secondary_supplier_id=supplier_secondary,
        )

        anomaly_no = repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-16",
            supplier_id=supplier_secondary,
            product_id=product_id,
            problem_desc="secondary source match",
        )

        anomaly_id = self._find_anomaly_id(anomaly_no)
        detail = repository.get_anomaly_detail(self.conn, anomaly_id)
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(supplier_secondary, detail["supplier_id"])
        self.assertEqual(product_id, detail["product_id"])

    def test_delete_anomaly_removes_event(self) -> None:
        supplier_id = self._create_supplier("Delete Anomaly Supplier")
        anomaly_no = repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-16",
            supplier_id=supplier_id,
            problem_desc="to be deleted",
        )
        anomaly_id = self._find_anomaly_id(anomaly_no)

        repository.delete_anomaly(self.conn, anomaly_id)

        self.assertIsNone(repository.get_anomaly_detail(self.conn, anomaly_id))
        events = repository.list_events(self.conn, event_type="ANOMALY")
        event_ids = {row["event_id"] for row in events}
        self.assertNotIn(anomaly_id, event_ids)

    def test_anomaly_status_flow_uses_zh_values(self) -> None:
        supplier_id = self._create_supplier("Status Supplier")
        anomaly_no = repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-16",
            supplier_id=supplier_id,
            problem_desc="status flow",
        )
        anomaly_id = self._find_anomaly_id(anomaly_no)

        detail_before = repository.get_anomaly_detail(self.conn, anomaly_id)
        self.assertIsNotNone(detail_before)
        assert detail_before is not None
        self.assertEqual("待處理", detail_before["status"])

        repository.close_anomaly(
            self.conn,
            anomaly_id=anomaly_id,
            improvement_desc="fixed",
            closed_by="Alice",
            root_cause_category="製程參數異常",
            closed_at="2026-04-17",
        )

        detail_after = repository.get_anomaly_detail(self.conn, anomaly_id)
        self.assertIsNotNone(detail_after)
        assert detail_after is not None
        self.assertEqual("已結案", detail_after["status"])
        self.assertEqual("2026-04-17", detail_after["closed_at"])
        self.assertEqual("Alice", detail_after["closed_by"])
        self.assertEqual("製程參數異常", detail_after["root_cause_category"])

        summary = repository.get_dashboard_summary(self.conn)
        self.assertEqual(0, summary["open_count"])
        self.assertEqual(1, summary["closed_count"])

    def _create_open_anomaly(self) -> str:
        supplier_id = self._create_supplier("Close Validation Supplier")
        anomaly_no = repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-16",
            supplier_id=supplier_id,
            problem_desc="close validation",
        )
        return self._find_anomaly_id(anomaly_no)

    def test_close_anomaly_rejects_empty_closer(self) -> None:
        anomaly_id = self._create_open_anomaly()
        with self.assertRaises(ValueError) as ctx:
            repository.close_anomaly(
                self.conn,
                anomaly_id=anomaly_id,
                improvement_desc="fixed",
                closed_by="   ",
                closed_at="2026-04-17",
            )
        self.assertIn("Closer", str(ctx.exception))

    def test_close_anomaly_rejects_overlong_improvement(self) -> None:
        anomaly_id = self._create_open_anomaly()
        with self.assertRaises(ValueError) as ctx:
            repository.close_anomaly(
                self.conn,
                anomaly_id=anomaly_id,
                improvement_desc="x" * (repository.IMPROVEMENT_DESC_MAX_LEN + 1),
                closed_by="Bob",
                closed_at="2026-04-17",
            )
        self.assertIn("exceeds", str(ctx.exception))

    def test_close_anomaly_rejects_blank_improvement(self) -> None:
        anomaly_id = self._create_open_anomaly()
        with self.assertRaises(ValueError):
            repository.close_anomaly(
                self.conn,
                anomaly_id=anomaly_id,
                improvement_desc="   ",
                closed_by="Bob",
                closed_at="2026-04-17",
            )

    def test_close_anomaly_rejects_future_closed_date(self) -> None:
        anomaly_id = self._create_open_anomaly()
        with self.assertRaises(ValueError) as ctx:
            repository.close_anomaly(
                self.conn,
                anomaly_id=anomaly_id,
                improvement_desc="fixed",
                closed_by="Bob",
                closed_at=(date.today() + timedelta(days=1)).isoformat(),
            )
        self.assertIn("future", str(ctx.exception))

    def test_close_anomaly_rejects_closed_date_before_anomaly_date(self) -> None:
        anomaly_id = self._create_open_anomaly()
        with self.assertRaises(ValueError) as ctx:
            repository.close_anomaly(
                self.conn,
                anomaly_id=anomaly_id,
                improvement_desc="fixed",
                closed_by="Bob",
                closed_at="2026-04-15",
            )
        self.assertIn("before anomaly date", str(ctx.exception))

    def test_update_anomaly_closed_at_moves_monthly_stats_source(self) -> None:
        supplier_id = self._create_supplier("Closed Date Supplier")
        anomaly_no = repository.create_anomaly(
            self.conn,
            anomaly_date="2026-01-10",
            supplier_id=supplier_id,
            problem_desc="closed date source",
        )
        anomaly_id = self._find_anomaly_id(anomaly_no)
        repository.close_anomaly(
            self.conn,
            anomaly_id=anomaly_id,
            improvement_desc="fixed",
            closed_by="Bob",
            closed_at="2026-03-05",
        )

        self.assertEqual(
            1,
            repository.get_monthly_stats(self.conn, "202603")["closed_anomaly_count"],
        )
        self.assertEqual(
            0,
            repository.get_monthly_stats(self.conn, "202604")["closed_anomaly_count"],
        )

        repository.update_anomaly_closed_at(
            self.conn,
            anomaly_id=anomaly_id,
            closed_at="2026-04-10",
        )

        detail = repository.get_anomaly_detail(self.conn, anomaly_id)
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual("2026-04-10", detail["closed_at"])
        self.assertEqual(
            0,
            repository.get_monthly_stats(self.conn, "202603")["closed_anomaly_count"],
        )
        self.assertEqual(
            1,
            repository.get_monthly_stats(self.conn, "202604")["closed_anomaly_count"],
        )

    def test_update_anomaly_closed_at_rejects_open_anomaly(self) -> None:
        anomaly_id = self._create_open_anomaly()
        with self.assertRaises(ValueError) as ctx:
            repository.update_anomaly_closed_at(
                self.conn,
                anomaly_id=anomaly_id,
                closed_at="2026-04-17",
            )
        self.assertIn("Only closed anomalies", str(ctx.exception))

    def test_update_visit_success(self) -> None:
        supplier_a = self._create_supplier("Visit Supplier A")
        supplier_b = self._create_supplier("Visit Supplier B")
        product_b = self._create_product(
            supplier_b,
            code="P-V-001",
            name="Visit Product",
        )
        visit_id = repository.create_visit(
            self.conn,
            visit_date="2026-04-16",
            supplier_id=supplier_a,
            summary="before update",
        )

        repository.update_visit(
            self.conn,
            visit_id=visit_id,
            visit_date="2026-04-20",
            supplier_id=supplier_b,
            product_id=product_b,
            product_stage="試產",
            summary="after update",
            work_order_no="WO-V-001",
            production_qty=120,
            tech_transfer=True,
        )

        detail = repository.get_visit_detail(self.conn, visit_id)
        self.assertIsNotNone(detail)
        self.assertEqual("2026-04-20", detail["visit_date"])
        self.assertEqual(supplier_b, detail["supplier_id"])
        self.assertEqual(product_b, detail["product_id"])
        self.assertEqual("量產", detail["product_stage"])
        self.assertEqual("after update", detail["summary"])
        self.assertEqual("WO-V-001", detail["work_order_no"])
        self.assertEqual(120, detail["production_qty"])
        self.assertTrue(detail["tech_transfer"])
        self.assertEqual("已完成", detail["status"])

    def test_list_events_includes_product_stage_work_order_and_qty_for_both_types(self) -> None:
        supplier_id = self._create_supplier("List Fields Supplier")
        anomaly_product_id = self._create_product(
            supplier_id,
            code="P-LIST-001",
            name="List Fields Product",
            product_stage=PRODUCT_STAGE_TRIAL_PRODUCTION,
        )
        visit_product_id = self._create_product(
            supplier_id,
            code="P-LIST-002",
            name="List Fields Product V",
            product_stage="量產",
        )
        repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-16",
            supplier_id=supplier_id,
            problem_desc="anomaly with fields",
            product_id=anomaly_product_id,
            product_stage="量產",
            outsource_work_order="AN-WO-001",
            batch_qty=88,
        )
        repository.create_visit(
            self.conn,
            visit_date="2026-04-15",
            supplier_id=supplier_id,
            product_id=visit_product_id,
            product_stage="試產",
            summary="visit with fields",
            work_order_no="V-WO-001",
            production_qty=120,
            tech_transfer=False,
        )

        events = repository.list_events(self.conn, event_type="ALL")
        anomaly_row = next(row for row in events if row["event_type"] == "ANOMALY")
        visit_row = next(row for row in events if row["event_type"] == "VISIT")

        self.assertEqual("List Fields Product", anomaly_row["product_name"])
        self.assertEqual("試產", anomaly_row["product_stage"])
        self.assertEqual("AN-WO-001", anomaly_row["work_order_no"])
        self.assertEqual(88, anomaly_row["production_qty"])
        self.assertEqual("AN-WO-001", anomaly_row["outsource_work_order"])
        self.assertEqual(88, anomaly_row["batch_qty"])

        self.assertEqual("List Fields Product V", visit_row["product_name"])
        self.assertEqual("量產", visit_row["product_stage"])
        self.assertEqual("V-WO-001", visit_row["work_order_no"])
        self.assertEqual(120, visit_row["production_qty"])
        self.assertEqual("", visit_row["outsource_work_order"])
        self.assertEqual(0, visit_row["batch_qty"])

    def test_list_events_splits_query_scopes_without_overlap(self) -> None:
        supplier_id = self._create_supplier("Scoped List Supplier")
        unlinked_visit_id = repository.create_visit(
            self.conn,
            visit_date="2026-04-10",
            supplier_id=supplier_id,
            summary="unlinked visit",
        )
        linked_visit_id = repository.create_visit(
            self.conn,
            visit_date="2026-04-11",
            supplier_id=supplier_id,
            summary="linked visit",
        )
        linked_anomaly_no = repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-12",
            supplier_id=supplier_id,
            problem_desc="linked anomaly",
            visit_id=linked_visit_id,
        )
        pure_anomaly_no = repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-13",
            supplier_id=supplier_id,
            problem_desc="pure anomaly",
        )
        linked_anomaly_id = self._find_anomaly_id(linked_anomaly_no)
        pure_anomaly_id = self._find_anomaly_id(pure_anomaly_no)

        visit_only = repository.list_events(
            self.conn,
            event_scope=repository.EVENT_SCOPE_VISIT_ONLY,
        )
        visit_with_anomaly = repository.list_events(
            self.conn,
            event_scope=repository.EVENT_SCOPE_VISIT_WITH_ANOMALY,
        )
        anomaly_only = repository.list_events(
            self.conn,
            event_scope=repository.EVENT_SCOPE_ANOMALY_ONLY,
        )

        self.assertEqual([unlinked_visit_id], [row["event_id"] for row in visit_only])
        self.assertEqual(["VISIT"], [row["event_type"] for row in visit_only])
        self.assertEqual(
            [linked_anomaly_id],
            [row["event_id"] for row in visit_with_anomaly],
        )
        self.assertEqual(
            ["ANOMALY"],
            [row["event_type"] for row in visit_with_anomaly],
        )
        self.assertEqual(
            [linked_visit_id],
            [row["linked_visit_id"] for row in visit_with_anomaly],
        )
        self.assertEqual([pure_anomaly_id], [row["event_id"] for row in anomaly_only])
        self.assertEqual(["ANOMALY"], [row["event_type"] for row in anomaly_only])
        scoped_ids = [
            row["event_id"]
            for rows in (visit_only, visit_with_anomaly, anomaly_only)
            for row in rows
        ]
        self.assertEqual(len(scoped_ids), len(set(scoped_ids)))

        pending_linked_rows = repository.list_events(
            self.conn,
            status="待處理",
            event_scope=repository.EVENT_SCOPE_VISIT_WITH_ANOMALY,
        )
        self.assertEqual([linked_anomaly_id], [row["event_id"] for row in pending_linked_rows])

    def test_latest_visit_for_supplier_on_date_returns_latest_visit_defaults(self) -> None:
        supplier_id = self._create_supplier("Same Day Visit Supplier")
        product_a = self._create_product(
            supplier_id,
            code="P-SAME-001",
            name="Same Day Product A",
        )
        product_b = self._create_product(
            supplier_id,
            code="P-SAME-002",
            name="Same Day Product B",
            product_stage=PRODUCT_STAGE_TRIAL_PRODUCTION,
        )
        repository.create_visit(
            self.conn,
            visit_date="2026-04-16",
            supplier_id=supplier_id,
            product_id=product_a,
            work_order_no="WO-OLD",
            production_qty=50,
        )
        latest_visit_id = repository.create_visit(
            self.conn,
            visit_date="2026-04-16",
            supplier_id=supplier_id,
            product_id=product_b,
            work_order_no="WO-LATEST",
            production_qty=200,
        )

        defaults = repository.get_latest_visit_for_supplier_on_date(
            self.conn,
            supplier_id=supplier_id,
            visit_date="2026-04-16",
        )

        self.assertIsNotNone(defaults)
        assert defaults is not None
        self.assertEqual(latest_visit_id, defaults["id"])
        self.assertEqual(product_b, defaults["product_id"])
        self.assertEqual("Same Day Product B", defaults["product_name"])
        self.assertEqual(PRODUCT_STAGE_TRIAL_PRODUCTION, defaults["product_stage"])
        self.assertEqual("WO-LATEST", defaults["work_order_no"])
        self.assertEqual(200, defaults["production_qty"])

    def test_product_stage_defaults_to_mass_production(self) -> None:
        supplier_id = self._create_supplier("Stage Default Supplier")
        anomaly_no = repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-16",
            supplier_id=supplier_id,
            problem_desc="stage default anomaly",
        )
        anomaly_id = self._find_anomaly_id(anomaly_no)
        visit_id = repository.create_visit(
            self.conn,
            visit_date="2026-04-16",
            supplier_id=supplier_id,
            summary="stage default visit",
        )

        anomaly_detail = repository.get_anomaly_detail(self.conn, anomaly_id)
        visit_detail = repository.get_visit_detail(self.conn, visit_id)
        self.assertIsNotNone(anomaly_detail)
        self.assertIsNotNone(visit_detail)
        assert anomaly_detail is not None
        assert visit_detail is not None
        self.assertEqual("量產", anomaly_detail["product_stage"])
        self.assertEqual("量產", visit_detail["product_stage"])

    def test_delete_visit_without_reference_success(self) -> None:
        supplier_id = self._create_supplier("Visit Delete Supplier")
        visit_id = repository.create_visit(
            self.conn,
            visit_date="2026-04-16",
            supplier_id=supplier_id,
            summary="no reference",
        )

        repository.delete_visit(self.conn, visit_id)

        self.assertIsNone(repository.get_visit_detail(self.conn, visit_id))

    def test_delete_visit_referenced_by_anomaly_fails(self) -> None:
        supplier_id = self._create_supplier("Visit Ref Supplier")
        visit_id = repository.create_visit(
            self.conn,
            visit_date="2026-04-16",
            supplier_id=supplier_id,
            summary="referenced visit",
        )
        repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-16",
            supplier_id=supplier_id,
            problem_desc="links visit",
            visit_id=visit_id,
        )

        with self.assertRaises(ValueError) as ctx:
            repository.delete_visit(self.conn, visit_id)

        self.assertIn("referenced", str(ctx.exception).lower())
        self.assertIsNotNone(repository.get_visit_detail(self.conn, visit_id))

    def test_delete_product_without_reference_success(self) -> None:
        supplier_id = self._create_supplier("Product Delete Supplier")
        product_id = self._create_product(
            supplier_id,
            code="P-D-001",
            name="Delete Product",
        )

        repository.delete_product_record(self.conn, product_id)

        self.assertIsNone(repository.get_product(self.conn, product_id))

    def test_delete_product_referenced_by_anomaly_fails(self) -> None:
        supplier_id = self._create_supplier("Product Ref Anomaly Supplier")
        product_id = self._create_product(
            supplier_id,
            code="P-RA-001",
            name="Referenced Product A",
        )
        repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-16",
            supplier_id=supplier_id,
            problem_desc="uses product",
            product_id=product_id,
        )

        with self.assertRaises(ValueError) as ctx:
            repository.delete_product_record(self.conn, product_id)

        self.assertIn("anomalies", str(ctx.exception))
        self.assertIsNotNone(repository.get_product(self.conn, product_id))

    def test_delete_product_referenced_by_visit_fails(self) -> None:
        supplier_id = self._create_supplier("Product Ref Visit Supplier")
        product_id = self._create_product(
            supplier_id,
            code="P-RV-001",
            name="Referenced Product V",
        )
        repository.create_visit(
            self.conn,
            visit_date="2026-04-16",
            supplier_id=supplier_id,
            product_id=product_id,
            summary="uses product",
        )

        with self.assertRaises(ValueError) as ctx:
            repository.delete_product_record(self.conn, product_id)

        self.assertIn("visits", str(ctx.exception))
        self.assertIsNotNone(repository.get_product(self.conn, product_id))

    def test_update_product_mass_to_trial_requires_reason(self) -> None:
        supplier_id = self._create_supplier("Downgrade Supplier")
        product_id = self._create_product(
            supplier_id,
            code="P-DOWN-001",
            name="Downgrade Product",
            product_stage="量產",
        )
        with self.assertRaises(ValueError) as ctx:
            repository.update_product_record(
                self.conn,
                product_id=product_id,
                product_code="P-DOWN-001",
                product_name="Downgrade Product",
                product_stage="試產",
                supplier_id=supplier_id,
                secondary_supplier_id=self._create_supplier("Downgrade-2nd"),
                stage_change_reason="",
            )
        self.assertIn("reason", str(ctx.exception).lower())

    def test_update_product_stage_syncs_events_and_writes_log(self) -> None:
        supplier_id = self._create_supplier("Sync Supplier")
        product_id = self._create_product(
            supplier_id,
            code="P-SYNC-001",
            name="Sync Product",
            product_stage=PRODUCT_STAGE_TRIAL_PRODUCTION,
        )
        anomaly_no = repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-16",
            supplier_id=supplier_id,
            product_id=product_id,
            problem_desc="stage sync anomaly",
            product_stage="量產",
        )
        visit_id = repository.create_visit(
            self.conn,
            visit_date="2026-04-16",
            supplier_id=supplier_id,
            product_id=product_id,
            product_stage="量產",
            summary="stage sync visit",
        )
        anomaly_id = self._find_anomaly_id(anomaly_no)

        repository.update_product_record(
            self.conn,
            product_id=product_id,
            product_code="P-SYNC-001",
            product_name="Sync Product",
            product_stage="量產",
            supplier_id=supplier_id,
            secondary_supplier_id=self._create_supplier("Sync-2nd"),
            stage_change_reason="試產結束轉量產",
        )

        anomaly_detail = repository.get_anomaly_detail(self.conn, anomaly_id)
        visit_detail = repository.get_visit_detail(self.conn, visit_id)
        self.assertIsNotNone(anomaly_detail)
        self.assertIsNotNone(visit_detail)
        assert anomaly_detail is not None
        assert visit_detail is not None
        self.assertEqual("量產", anomaly_detail["product_stage"])
        self.assertEqual("量產", visit_detail["product_stage"])
        logs = repository.list_product_stage_change_logs(self.conn, product_id=product_id)
        self.assertEqual(1, len(logs))
        self.assertEqual("試產", logs[0]["from_stage"])
        self.assertEqual("量產", logs[0]["to_stage"])
        self.assertEqual("試產結束轉量產", logs[0]["reason"])
        self.assertGreaterEqual(int(logs[0]["anomalies_updated"]), 0)
        self.assertGreaterEqual(int(logs[0]["visits_updated"]), 0)

    def test_sync_all_product_stages_backfills_unique_product_name_links(self) -> None:
        supplier_id = self._create_supplier("Backfill Supplier")
        product_id = self._create_product(
            supplier_id,
            code="P-BACK-001",
            name="Backfill Product",
            product_stage=PRODUCT_STAGE_TRIAL_PRODUCTION,
        )
        self.conn.execute(
            """
            INSERT INTO anomalies(
                id, anomaly_no, anomaly_date, supplier_id, product_id, problem_desc,
                category, product_lot_no, product_name, product_stage, outsource_work_order,
                batch_qty, status, improvement_desc, closed_at, created_at, updated_at
            ) VALUES (?, '20260416099', '2026-04-16', ?, NULL, 'manual anomaly', '', '',
                      'Backfill Product', '量產', '', 0, '待處理', '', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (uuid4().hex, supplier_id),
        )
        self.conn.execute(
            """
            INSERT INTO visits(
                id, visit_date, supplier_id, product_id, product_name, product_stage, summary,
                work_order_no, production_qty, tech_transfer, tech_transfer_doc, carrier_requirement,
                dispensing_process, functional_test, packaging_requirement, status, created_at, updated_at
            ) VALUES (?, '2026-04-16', ?, NULL, 'Backfill Product', '量產', 'manual visit', '',
                      0, 0, 0, 0, 0, 0, 0, '已完成', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (uuid4().hex, supplier_id),
        )
        self.conn.commit()

        report = repository.sync_all_product_stages_to_events(self.conn)
        self.assertTrue(bool(report.get("applied")))
        anomaly_row = self.conn.execute(
            """
            SELECT product_id, product_stage
            FROM anomalies
            WHERE anomaly_no = '20260416099'
            LIMIT 1
            """
        ).fetchone()
        visit_row = self.conn.execute(
            """
            SELECT product_id, product_stage
            FROM visits
            WHERE summary = 'manual visit'
            LIMIT 1
            """
        ).fetchone()
        self.assertIsNotNone(anomaly_row)
        self.assertIsNotNone(visit_row)
        assert anomaly_row is not None
        assert visit_row is not None
        self.assertEqual(product_id, str(anomaly_row["product_id"]))
        self.assertEqual(product_id, str(visit_row["product_id"]))
        self.assertEqual("試產", str(anomaly_row["product_stage"]))
        self.assertEqual("試產", str(visit_row["product_stage"]))

    def test_reopen_anomaly_success(self) -> None:
        supplier_id = self._create_supplier("Reopen Supplier")
        anomaly_no = repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-16",
            supplier_id=supplier_id,
            problem_desc="to be reopened",
        )
        anomaly_id = self._find_anomaly_id(anomaly_no)

        # Close it first
        repository.close_anomaly(
            self.conn,
            anomaly_id=anomaly_id,
            improvement_desc="fixed",
            closed_by="Alice",
            root_cause_category="製程參數異常",
            closed_at="2026-04-17",
        )

        detail_closed = repository.get_anomaly_detail(self.conn, anomaly_id)
        self.assertEqual("已結案", detail_closed["status"])
        self.assertEqual("fixed", detail_closed["improvement_desc"])

        # Reopen it
        repository.reopen_anomaly(self.conn, anomaly_id)

        detail_reopened = repository.get_anomaly_detail(self.conn, anomaly_id)
        self.assertIsNotNone(detail_reopened)
        assert detail_reopened is not None
        self.assertEqual("待處理", detail_reopened["status"])
        self.assertEqual("", detail_reopened["improvement_desc"])
        self.assertEqual("", detail_reopened["closed_by"])
        self.assertEqual("", detail_reopened["root_cause_category"])
        self.assertIsNone(detail_reopened["closed_at"])

        summary = repository.get_dashboard_summary(self.conn)
        self.assertEqual(1, summary["open_count"])
        self.assertEqual(0, summary["closed_count"])

    def test_get_dashboard_summary_with_standalone_open_count(self) -> None:
        # Create a supplier
        supplier_id = self._create_supplier("Dashboard Badge Supplier")
        
        # 1. Create a standalone open anomaly (visit_id IS NULL)
        repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-16",
            supplier_id=supplier_id,
            problem_desc="standalone open anomaly",
        )
        
        # 2. Create a visit-derived open anomaly (visit_id IS NOT NULL)
        visit_id = repository.create_visit(
            self.conn,
            visit_date="2026-04-16",
            supplier_id=supplier_id,
            summary="visit summary",
        )
        repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-16",
            supplier_id=supplier_id,
            problem_desc="visit derived open anomaly",
            visit_id=visit_id,
        )
        
        # 3. Create a closed anomaly
        anomaly_no_3 = repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-16",
            supplier_id=supplier_id,
            problem_desc="closed anomaly",
        )
        anomaly_id_3 = self._find_anomaly_id(anomaly_no_3)
        repository.close_anomaly(
            self.conn,
            anomaly_id=anomaly_id_3,
            improvement_desc="resolved",
            closed_by="Tester",
            root_cause_category="製程參數異常",
            closed_at="2026-04-17",
        )
        
        # Query dashboard summary and verify
        summary = repository.get_dashboard_summary(self.conn)
        # Total open: standalone (1) + visit-derived (1) = 2
        self.assertEqual(2, summary["open_count"])
        # Total closed: 1
        self.assertEqual(1, summary["closed_count"])
        # Standalone open: 1
        self.assertEqual(1, summary["standalone_open_count"])


if __name__ == "__main__":
    unittest.main()
