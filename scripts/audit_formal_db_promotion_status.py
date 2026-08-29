"""Read-only formal DB promotion status snapshot for release gates."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

MIGRATION_META_KEYS = (
    "case_actions_v1",
    "anomaly_attachments_contract_v1",
    "anomaly_hypotheses_v1",
    "anomaly_repeat_links_v1",
    "product_records_view_is_active_v1",
    "defect_supplier_id_backfill_v1",
)

TABLE_CHECKS = {
    "case_actions": "SELECT COUNT(*) FROM case_actions",
    "anomaly_attachments": "SELECT COUNT(*) FROM anomaly_attachments",
    "anomaly_hypotheses": "SELECT COUNT(*) FROM anomaly_hypotheses",
    "anomaly_repeat_links": "SELECT COUNT(*) FROM anomaly_repeat_links",
}


def build_promotion_status_report(db_path: Path) -> dict[str, Any]:
    """Return a read-only promotion readiness report for the given SQLite DB."""
    report: dict[str, Any] = {
        "db_path": str(db_path.resolve()),
        "exists": db_path.is_file(),
    }
    if not db_path.is_file():
        report["ready"] = False
        report["expected_keys_present"] = {key: False for key in MIGRATION_META_KEYS}
        return report

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        rows = cur.execute("SELECT key, value FROM migration_meta ORDER BY key").fetchall()
        report["migration_meta"] = {str(r["key"]): str(r["value"]) for r in rows}
    except sqlite3.Error as exc:
        report["migration_meta_error"] = str(exc)
        report["migration_meta"] = {}

    report["expected_keys_present"] = {
        key: key in report.get("migration_meta", {}) for key in MIGRATION_META_KEYS
    }

    report["tables"] = {}
    for name, sql in TABLE_CHECKS.items():
        try:
            report["tables"][name] = int(cur.execute(sql).fetchone()[0])
        except sqlite3.Error as exc:
            report["tables"][name] = f"MISSING: {exc}"

    try:
        row = cur.execute(
            "SELECT type, sql FROM sqlite_master WHERE name='product_records'"
        ).fetchone()
        if row:
            sql_text = str(row["sql"] or "")
            report["product_records"] = {
                "type": str(row["type"]),
                "has_is_active_filter": "is_active" in sql_text,
            }
        else:
            report["product_records"] = "missing"
    except sqlite3.Error as exc:
        report["product_records_error"] = str(exc)

    conn.close()

    report["ready"] = all(report["expected_keys_present"].values()) and report.get(
        "product_records", {}
    ) != "missing"
    return report


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Read-only formal DB promotion status")
    parser.add_argument(
        "--db",
        default=str(repo_root / "data" / "sqe_v2.db"),
        help="Formal SQLite database path (read-only).",
    )
    parser.add_argument(
        "--output",
        default=str(repo_root / "scratch" / "formal-db-promotion-status.json"),
        help="JSON output path.",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    output_path = Path(args.output)
    report = build_promotion_status_report(db_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())
