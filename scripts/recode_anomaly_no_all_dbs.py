"""Batch recode anomaly/issue numbers in SQLite databases."""

from __future__ import annotations

import argparse
import glob
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from database import repository


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recode anomaly numbers to YYYYMMDDNNN for all SQLite DBs."
    )
    parser.add_argument(
        "--pattern",
        default="data/*.db",
        help="Glob pattern for database files (default: data/*.db)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. Default mode is dry-run.",
    )
    return parser.parse_args()


def _backup_db(path: Path, *, stamp: str) -> Path:
    backup_path = path.with_name(
        f"{path.stem}.backup_before_recode_{stamp}{path.suffix}.bak"
    )
    shutil.copy2(path, backup_path)
    return backup_path


def _run_single_db(path: Path, *, apply: bool) -> dict:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        report = repository.recode_anomaly_numbers(
            conn,
            apply=apply,
            rewrite_text=True,
            migration_meta_key=None,
        )
    finally:
        conn.close()
    return report


def main() -> int:
    args = _parse_args()
    db_paths = sorted(Path(p) for p in glob.glob(args.pattern))
    if not db_paths:
        print(f"No database files matched pattern: {args.pattern}")
        return 1

    apply = bool(args.apply)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"mode={'apply' if apply else 'dry-run'}")
    print(f"targets={[str(p) for p in db_paths]}")

    all_results: list[dict] = []
    has_error = False
    for path in db_paths:
        backup_path: str | None = None
        if apply:
            backup_path = str(_backup_db(path, stamp=stamp))
        try:
            report = _run_single_db(path, apply=apply)
            result = {
                "db": str(path),
                "ok": True,
                "backup": backup_path,
                "report": report,
            }
        except Exception as exc:
            has_error = True
            result = {
                "db": str(path),
                "ok": False,
                "backup": backup_path,
                "error": str(exc),
            }
        all_results.append(result)
        print(json.dumps(result, ensure_ascii=False))

    summary = {
        "total": len(all_results),
        "success": sum(1 for item in all_results if item.get("ok")),
        "failed": sum(1 for item in all_results if not item.get("ok")),
        "mode": "apply" if apply else "dry-run",
    }
    print(json.dumps({"summary": summary}, ensure_ascii=False))
    return 1 if has_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
