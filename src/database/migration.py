"""Legacy SQLite (sqe.db) to v2 SQLite (sqe_v2.db) migration helpers."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from database.backup import backup_sqlite_database
from database.product_stage import normalize_product_stage_ui
from database.repo_helpers import _as_int, _table_exists
from database.repository import (
    count_rows,
    create_schema,
    ensure_supplier,
    get_migration_meta,
    rebuild_all_monthly_cache,
    upsert_migration_meta,
)


class LegacyMigrationError(RuntimeError):
    """Raised after an all-or-nothing legacy migration is rolled back."""

    def __init__(self, message: str, report: dict[str, Any]):
        super().__init__(message)
        self.report = report


def _pick(row: sqlite3.Row, *keys: str, default: Any = "") -> Any:
    row_keys = row.keys()
    for key in keys:
        if key in row_keys:
            value = row[key]
            if value is not None and str(value).strip() != "":
                return value
    return default


def _normalize_date(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    return text[:10]


def _as_bool_int(value: Any) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    text = str(value).strip().lower()
    return 1 if text in {"1", "true", "yes", "y"} else 0


def _legacy_visit_product_id(v2_conn: sqlite3.Connection, row: sqlite3.Row) -> str | None:
    raw = _pick(row, "product_id", default="")
    pid = str(raw).strip()
    if not pid:
        return None
    found = v2_conn.execute(
        "SELECT 1 FROM products WHERE id = ? LIMIT 1",
        (pid,),
    ).fetchone()
    return pid if found else None


def _status_to_closed(row: sqlite3.Row) -> bool:
    status = str(_pick(row, "status", default="")).strip().upper()
    if status in {"CLOSED", "已結案"}:
        return True
    if _as_bool_int(_pick(row, "is_closed", default=0)) == 1:
        return True
    close_mark = _pick(row, "closed_at", "close_date", default="")
    return str(close_mark).strip() != ""


def migrate_legacy_data_if_needed(v2_path: Path, legacy_path: Path) -> dict:
    report: dict[str, Any] = {
        "migrated": False,
        "backup_path": "",
        "counts_before": {},
        "counts_after": {},
        "legacy_counts": {},
        "errors": [],
    }
    v2_conn = sqlite3.connect(v2_path)
    try:
        v2_conn.row_factory = sqlite3.Row
        create_schema(v2_conn)
        v2_conn.commit()
        report["counts_before"] = count_rows(v2_conn)
        if get_migration_meta(v2_conn, "legacy_migrated") == "1":
            v2_conn.commit()
            return report

        # 無 legacy 檔時視為沒有需要匯入的來源；標記完成以免每次啟動重試。
        # 若之後才補上 sqe.db，須手動處理或還原 migration_meta 再遷移。
        if not legacy_path.exists():
            upsert_migration_meta(v2_conn, "legacy_migrated", "1")
            report["counts_after"] = count_rows(v2_conn)
            v2_conn.commit()
            return report

        if (
            report["counts_before"]["suppliers"] > 0
            or report["counts_before"].get("products", 0) > 0
            or report["counts_before"]["anomalies"] > 0
            or report["counts_before"]["visits"] > 0
        ):
            upsert_migration_meta(v2_conn, "legacy_migrated", "1")
            report["counts_after"] = count_rows(v2_conn)
            v2_conn.commit()
            return report

        timestamp = datetime.now().strftime("%Y%m%d")
        backup_path = legacy_path.parent / f"sqe_legacy_{timestamp}.db"
        if not backup_path.exists():
            backup_sqlite_database(legacy_path, backup_path)
        report["backup_path"] = str(backup_path)

        v2_conn.execute("BEGIN IMMEDIATE")
        legacy_conn = sqlite3.connect(legacy_path)
        try:
            legacy_conn.row_factory = sqlite3.Row
            _migrate_suppliers(legacy_conn, v2_conn, report)
            _migrate_anomalies(legacy_conn, v2_conn, report)
            _migrate_visits(legacy_conn, v2_conn, report)
        finally:
            legacy_conn.close()

        rebuild_all_monthly_cache(v2_conn, _commit=False)
        if report["errors"]:
            raise ValueError("Legacy migration reconciliation contains row errors")
        upsert_migration_meta(v2_conn, "legacy_migrated", "1")
        report["counts_after"] = count_rows(v2_conn)
        report["migrated"] = True
        v2_conn.commit()
    except Exception as exc:
        v2_conn.rollback()
        if not report["errors"]:
            report["errors"].append(str(exc))
        report["migrated"] = False
        try:
            report["counts_after"] = count_rows(v2_conn)
        except Exception:
            report["counts_after"] = {}
        reconciliation_path = v2_path.with_name(
            f"{v2_path.stem}_migration_VERIFY.json"
        )
        write_migration_report(reconciliation_path, report)
        report["reconciliation_report_path"] = str(reconciliation_path)
        raise LegacyMigrationError(
            "Legacy migration failed and was rolled back; "
            f"see {reconciliation_path}",
            report,
        ) from exc
    finally:
        v2_conn.close()
    return report


def _resolve_and_ensure_supplier(
    v2_conn: sqlite3.Connection,
    row: sqlite3.Row,
) -> str:
    supplier_id = str(_pick(row, "supplier_id", default="")).strip()
    supplier_name = "Unknown Supplier"
    if supplier_id:
        lookup = v2_conn.execute(
            "SELECT supplier_name FROM suppliers WHERE id = ?",
            (supplier_id,),
        ).fetchone()
        if lookup:
            supplier_name = str(lookup["supplier_name"])
    return ensure_supplier(
        v2_conn,
        supplier_name,
        supplier_id=supplier_id or None,
    )


def _migrate_suppliers(
    legacy_conn: sqlite3.Connection,
    v2_conn: sqlite3.Connection,
    report: dict,
) -> None:
    if not _table_exists(legacy_conn, "suppliers"):
        report["legacy_counts"]["suppliers"] = 0
        return
    rows = legacy_conn.execute("SELECT * FROM suppliers").fetchall()
    report["legacy_counts"]["suppliers"] = len(rows)
    for row in rows:
        supplier_name = str(_pick(row, "supplier_name", "name", default="")).strip()
        ensure_supplier(
            v2_conn,
            supplier_name,
            supplier_id=str(_pick(row, "id", default="")).strip() or None,
            contact_name=str(_pick(row, "contact_name", default="")).strip(),
            phone=str(_pick(row, "phone", default="")).strip(),
        )


def _migrate_anomalies(
    legacy_conn: sqlite3.Connection,
    v2_conn: sqlite3.Connection,
    report: dict,
) -> None:
    if not _table_exists(legacy_conn, "issues"):
        report["legacy_counts"]["issues"] = 0
        return
    rows = legacy_conn.execute("SELECT * FROM issues").fetchall()
    report["legacy_counts"]["issues"] = len(rows)
    fallback_seq_by_day: dict[str, int] = {}
    for row in rows:
        try:
            supplier_id = _resolve_and_ensure_supplier(v2_conn, row)

            anomaly_date = _normalize_date(
                _pick(row, "issue_date", "created_at", default=""),
                fallback=date_today(),
            )
            status = "已結案" if _status_to_closed(row) else "待處理"
            closed_at = _normalize_date(
                _pick(row, "closed_at", "close_date", "verification_date", default="")
            )
            if status == "待處理":
                closed_at = ""
            problem_desc = str(
                _pick(row, "problem", "title", "description", default="")
            ).strip()
            if not problem_desc:
                problem_desc = "(empty problem)"
            improvement_desc = str(
                _pick(
                    row,
                    "corrective_action",
                    "action",
                    "verification_note",
                    default="",
                )
            ).strip()
            product_name = str(
                _pick(row, "product_name", "product", "part_name", default="")
            ).strip()
            product_lot_no = str(
                _pick(row, "product_lot_no", "lot_no", "lot", default="")
            ).strip()
            outsource_work_order = str(
                _pick(row, "outsource_work_order", "work_order_no", "work_order", default="")
            ).strip()
            batch_qty = _as_int(_pick(row, "batch_qty", "quantity", "qty", default=0))
            issue_no = str(_pick(row, "issue_no", default="")).strip()
            if not issue_no:
                day_key = anomaly_date.replace("-", "")
                next_seq = fallback_seq_by_day.get(day_key, 0) + 1
                fallback_seq_by_day[day_key] = next_seq
                issue_no = legacy_anomaly_no(anomaly_date, seq=next_seq)

            v2_conn.execute(
                """
                INSERT INTO anomalies(
                    id, anomaly_no, anomaly_date, supplier_id, problem_desc, category,
                    product_lot_no, product_name, outsource_work_order, batch_qty,
                    status, improvement_desc, closed_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    str(_pick(row, "id", default="")).strip() or _new_id(),
                    issue_no,
                    anomaly_date,
                    supplier_id,
                    problem_desc,
                    str(_pick(row, "category", default="")).strip(),
                    product_lot_no,
                    product_name,
                    outsource_work_order,
                    batch_qty,
                    status,
                    improvement_desc,
                    closed_at or None,
                ),
            )
        except Exception as exc:
            message = f"issues.id={_pick(row, 'id', default='?')}: {exc}"
            report["errors"].append(message)
            raise ValueError(message) from exc


def _migrate_visits(
    legacy_conn: sqlite3.Connection,
    v2_conn: sqlite3.Connection,
    report: dict,
) -> None:
    if not _table_exists(legacy_conn, "supplier_visits"):
        report["legacy_counts"]["supplier_visits"] = 0
        return
    rows = legacy_conn.execute("SELECT * FROM supplier_visits").fetchall()
    report["legacy_counts"]["supplier_visits"] = len(rows)
    for row in rows:
        try:
            supplier_id = _resolve_and_ensure_supplier(v2_conn, row)

            visit_date = _normalize_date(
                _pick(row, "visit_date", "created_at", default=""),
                fallback=date_today(),
            )
            legacy_product_id = _legacy_visit_product_id(v2_conn, row)
            legacy_product_stage = normalize_product_stage_ui(
                _pick(row, "product_stage", default="")
            )
            v2_conn.execute(
                """
                INSERT INTO visits(
                    id, visit_date, supplier_id, product_id, product_name, product_stage, summary, work_order_no,
                    production_qty, tech_transfer, tech_transfer_doc, carrier_requirement,
                    dispensing_process, functional_test, packaging_requirement,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, '已完成', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    str(_pick(row, "id", default="")).strip() or _new_id(),
                    visit_date,
                    supplier_id,
                    legacy_product_id,
                    str(_pick(row, "product_name", "product", default="")).strip(),
                    legacy_product_stage,
                    str(_pick(row, "audit_note", "summary", "note", default="")).strip(),
                    str(_pick(row, "work_order_no", "work_order", default="")).strip(),
                    _as_int(_pick(row, "production_qty", default=0)),
                    _as_bool_int(
                        _pick(row, "tech_transfer_completed", "tech_transfer_done", default=0)
                    ),
                ),
            )
        except Exception as exc:
            message = (
                f"supplier_visits.id={_pick(row, 'id', default='?')}: {exc}"
            )
            report["errors"].append(message)
            raise ValueError(message) from exc


def write_migration_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(report, ensure_ascii=False, indent=2))


def date_today() -> str:
    return datetime.now().date().isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex


def legacy_anomaly_no(anomaly_date: str, *, seq: int = 1) -> str:
    day = anomaly_date.replace("-", "")
    return f"{day}{seq:03d}"
