"""Smoke test for SQE DailyWork v2 local workflow."""

from __future__ import annotations

import re
import sqlite3
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
for _path in (_PROJECT_ROOT / "src", _PROJECT_ROOT):
    _path_text = str(_path)
    if _path_text not in sys.path:
        sys.path.insert(0, _path_text)

from database import repository  # noqa: E402
from database.connection import get_connection, initialize_database  # noqa: E402
from services import event_service  # noqa: E402


TEST_DATE = "2026-04-15"
TEST_MONTH = "202604"
ANOMALY_NO_PATTERN = re.compile(r"^\d{11}$")


def _get_anomaly_row(anomaly_no: str):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                supplier_id,
                visit_id,
                product_id,
                product_lot_no,
                product_name,
                outsource_work_order,
                batch_qty
            FROM anomalies
            WHERE anomaly_no = ?
            """,
            (anomaly_no,),
        ).fetchone()


def _get_visit_row(visit_id: str):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT supplier_id, product_id, product_name, summary, work_order_no, production_qty
            FROM visits
            WHERE id = ?
            """,
            (visit_id,),
        ).fetchone()


def _assert_raises_value_error(fn, expected_keyword: str):
    try:
        fn()
    except ValueError as exc:
        if expected_keyword and expected_keyword.lower() not in str(exc).lower():
            raise RuntimeError(f"Expected ValueError containing '{expected_keyword}', got: {exc}") from exc
        return
    raise RuntimeError(f"Expected ValueError containing '{expected_keyword}'")


def _assert_anomaly_no_format(anomaly_no: str) -> None:
    if not ANOMALY_NO_PATTERN.fullmatch(anomaly_no):
        raise RuntimeError(f"Unexpected anomaly_no format: {anomaly_no}")


def _verify_seed_behavior() -> None:
    with tempfile.TemporaryDirectory(prefix="sqe_seed_") as tmp_dir:
        db_path = Path(tmp_dir) / "seed_test.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            repository.create_schema(conn)
            supplier_id = repository.create_supplier_record(
                conn,
                supplier_name="台達電子-種子資料",
            )
            repository.create_anomaly(
                conn,
                anomaly_date=TEST_DATE,
                supplier_id=supplier_id,
                problem_desc="seed-anomaly-1",
                product_name="Seed Product A",
            )
            repository.create_anomaly(
                conn,
                anomaly_date=TEST_DATE,
                supplier_id=supplier_id,
                problem_desc="seed-anomaly-2",
                product_name="Seed Product A",
            )
            repository.create_anomaly(
                conn,
                anomaly_date=TEST_DATE,
                supplier_id=supplier_id,
                problem_desc="seed-anomaly-3",
                product_name="Seed Product B",
            )

            first = repository.seed_products_from_anomalies(conn)
            if not first["seeded"]:
                raise RuntimeError("Expected first seed run to execute")
            if int(first["created"]) < 2:
                raise RuntimeError("Expected at least 2 products seeded from anomalies")

            product_rows = conn.execute(
                "SELECT product_code FROM products ORDER BY product_code"
            ).fetchall()
            if len(product_rows) < 2:
                raise RuntimeError("Expected seeded products in products table")
            for row in product_rows:
                if not str(row["product_code"]).startswith("AUTO-"):
                    raise RuntimeError("Expected seeded product code to start with AUTO-")

            unresolved = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM anomalies
                WHERE trim(product_name) <> '' AND product_id IS NULL
                """
            ).fetchone()
            if int(unresolved["c"]) != 0:
                raise RuntimeError("Expected seeded anomalies to be backfilled with product_id")

            second = repository.seed_products_from_anomalies(conn)
            if second["seeded"]:
                raise RuntimeError("Expected second seed run to be skipped by migration_meta")
            if int(second["created"]) != 0 or int(second["backfilled"]) != 0:
                raise RuntimeError("Expected no-op result for repeated seed run")
        finally:
            conn.close()


def main() -> int:
    report = initialize_database()
    print("init_migrated", report.get("migrated"))
    print("product_seed", report.get("product_seed"))

    suffix = uuid4().hex[:12]
    supplier_global = f"台達電子-{suffix}"
    supplier_other = f"鴻海精密-{suffix}"

    supplier_a_id = event_service.create_supplier(
        {
            "supplier_name": supplier_global,
            "contact_name": "Alice",
            "phone": "0900000001",
        }
    )
    supplier_b_id = event_service.create_supplier(
        {
            "supplier_name": supplier_other,
            "contact_name": "Bob",
            "phone": "0900000002",
        }
    )
    print("supplier_ids", supplier_a_id, supplier_b_id)

    event_service.update_supplier(
        supplier_a_id,
        {
            "supplier_name": supplier_global,
            "contact_name": "Alice Updated",
            "phone": "0900000011",
        },
    )

    # 無主供應商料號：僅能寫入 DB（create_product 需主／次供應商）；用於驗證 list 含 supplier_id IS NULL 列。
    global_product_id = uuid4().hex
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO products(
                id, product_code, product_name, product_stage, supplier_id, secondary_supplier_id,
                is_active, created_at, updated_at
            ) VALUES (?, ?, ?, '量產', NULL, NULL, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (global_product_id, f"G-{suffix}", "Global Product"),
        )
        conn.commit()
    supplier_a_product_id = event_service.create_product(
        {
            "product_code": f"A-{suffix}",
            "product_name": "Supplier A Product",
            "supplier_id": supplier_a_id,
        }
    )
    supplier_b_product_id = event_service.create_product(
        {
            "product_code": f"B-{suffix}",
            "product_name": "Supplier B Product",
            "supplier_id": supplier_b_id,
        }
    )
    print("product_ids", global_product_id, supplier_a_product_id, supplier_b_product_id)

    active_suppliers = event_service.list_active_suppliers()
    active_supplier_ids = {row["id"] for row in active_suppliers}
    if supplier_a_id not in active_supplier_ids or supplier_b_id not in active_supplier_ids:
        raise RuntimeError("Expected created suppliers in active supplier list")

    products_for_a = event_service.list_active_products_for_supplier(supplier_a_id)
    products_for_a_ids = {row["id"] for row in products_for_a}
    if global_product_id not in products_for_a_ids:
        raise RuntimeError("Expected global product in supplier product options")
    if supplier_a_product_id not in products_for_a_ids:
        raise RuntimeError("Expected supplier-specific product in supplier options")
    if supplier_b_product_id in products_for_a_ids:
        raise RuntimeError("Unexpected other supplier product in supplier options")

    event_service.set_product_active(supplier_b_product_id, False)
    products_for_b = event_service.list_active_products_for_supplier(supplier_b_id)
    products_for_b_ids = {row["id"] for row in products_for_b}
    if supplier_b_product_id in products_for_b_ids:
        raise RuntimeError("Expected inactive product removed from active options")
    event_service.set_product_active(supplier_b_product_id, True)

    preview_same_day = event_service.preview_anomaly_no(TEST_DATE)
    _assert_anomaly_no_format(preview_same_day)
    preview_next_day = event_service.preview_anomaly_no("2026-04-16")
    _assert_anomaly_no_format(preview_next_day)

    linked = event_service.create_anomaly_with_visit_link(
        {
            "anomaly_date": TEST_DATE,
            "supplier_id": supplier_a_id,
            "product_id": supplier_a_product_id,
            "problem_desc": "Smoke anomaly with product",
            "category": "測試",
            "product_lot_no": "LOT-NEW-001",
            "outsource_work_order": "WO-NEW-001",
            "batch_qty": 321,
            "sync_visit": True,
            "visit_summary": "Smoke linked visit",
        }
    )
    print("linked", linked)
    _assert_anomaly_no_format(linked["anomaly_no"])
    if linked["visit_action"] not in {"created", "reused"}:
        raise RuntimeError("Expected linked visit action")

    anomaly_row = _get_anomaly_row(linked["anomaly_no"])
    if anomaly_row is None:
        raise RuntimeError("Expected anomaly row")
    if anomaly_row["supplier_id"] != supplier_a_id:
        raise RuntimeError("Expected anomaly supplier_id to match payload")
    if anomaly_row["product_id"] != supplier_a_product_id:
        raise RuntimeError("Expected anomaly product_id to match payload")
    if anomaly_row["product_name"] != "Supplier A Product":
        raise RuntimeError("Expected anomaly product_name snapshot")
    if int(anomaly_row["batch_qty"]) != 321:
        raise RuntimeError("Expected anomaly batch_qty")

    if linked["visit_id"]:
        visit_row = _get_visit_row(linked["visit_id"])
        if visit_row is None:
            raise RuntimeError("Expected linked visit row")
        if visit_row["product_id"] != supplier_a_product_id:
            raise RuntimeError("Expected linked visit product_id")
        if visit_row["product_name"] != "Supplier A Product":
            raise RuntimeError("Expected linked visit product_name snapshot")

    visit_with_product_id = event_service.create_visit(
        {
            "visit_date": TEST_DATE,
            "supplier_id": supplier_a_id,
            "product_id": supplier_a_product_id,
            "summary": "visit with product",
            "work_order_no": "WO-NOPRODUCT",
            "production_qty": 100,
            "tech_transfer": True,
        }
    )
    visit_with_product_row = _get_visit_row(visit_with_product_id)
    if visit_with_product_row is None:
        raise RuntimeError("Expected visit row")
    if visit_with_product_row["product_id"] != supplier_a_product_id:
        raise RuntimeError("Expected required visit product_id")
    if visit_with_product_row["product_name"] != "Supplier A Product":
        raise RuntimeError("Expected required visit product_name snapshot")

    event_service.set_product_active(supplier_a_product_id, False)
    _assert_raises_value_error(
        lambda: event_service.create_anomaly(
            {
                "anomaly_date": TEST_DATE,
                "supplier_id": supplier_a_id,
                "product_id": supplier_a_product_id,
                "problem_desc": "inactive product should fail",
            }
        ),
        "inactive",
    )
    event_service.set_product_active(supplier_a_product_id, True)

    event_service.set_supplier_active(supplier_a_id, False)
    _assert_raises_value_error(
        lambda: event_service.create_visit(
            {
                "visit_date": TEST_DATE,
                "supplier_id": supplier_a_id,
                "product_id": supplier_a_product_id,
                "summary": "inactive supplier should fail",
            }
        ),
        "inactive",
    )
    event_service.set_supplier_active(supplier_a_id, True)

    delete_free_id = event_service.create_supplier(
        {
            "supplier_name": f"和碩聯合-{suffix}-可刪除",
            "contact_name": "Delete Free Contact",
            "phone": "0900000101",
        }
    )
    delete_blocked_id = event_service.create_supplier(
        {
            "supplier_name": f"仁寶電腦-{suffix}-受保護",
            "contact_name": "Delete Blocked Contact",
            "phone": "0900000102",
        }
    )
    delete_blocked_product_id = event_service.create_product(
        {
            "product_code": f"DB-{suffix}",
            "product_name": "Delete Blocked Product",
            "supplier_id": delete_blocked_id,
        }
    )
    event_service.create_visit(
        {
            "visit_date": TEST_DATE,
            "supplier_id": delete_blocked_id,
            "product_id": delete_blocked_product_id,
            "summary": "delete blocked reference",
        }
    )
    _assert_raises_value_error(
        lambda: event_service.delete_supplier(delete_blocked_id),
        "referenced",
    )
    delete_result = event_service.delete_suppliers([delete_free_id, delete_blocked_id])
    if delete_free_id not in delete_result["deleted"]:
        raise RuntimeError("Expected deletable supplier id in batch deleted list")
    blocked_reasons = [
        str(item.get("reason", ""))
        for item in delete_result["failed"]
        if item.get("id") == delete_blocked_id
    ]
    if not blocked_reasons or not any("referenced" in reason.lower() for reason in blocked_reasons):
        raise RuntimeError("Expected blocked supplier failure reason in batch delete result")
    remaining_supplier_ids = {
        row["id"] for row in event_service.list_suppliers(include_inactive=True)
    }
    if delete_free_id in remaining_supplier_ids:
        raise RuntimeError("Expected deletable supplier removed from supplier list")
    if delete_blocked_id not in remaining_supplier_ids:
        raise RuntimeError("Expected blocked supplier still present after batch delete")

    stats = event_service.get_monthly_stats(TEST_MONTH)
    print("stats", stats)
    output = Path("data/smoke_export.xlsx")
    ok, message = event_service.export_monthly_excel(str(output), TEST_MONTH)
    print("export_ok", ok)
    print("export_msg", message)
    if not ok:
        raise RuntimeError(message)
    if not output.exists():
        raise RuntimeError("Expected exported file")

    _verify_seed_behavior()
    print("seed_behavior_ok")
    print("smoke_test_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
