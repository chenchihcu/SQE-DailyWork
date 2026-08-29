"""Read-only audit for product_records VIEW is_active filter promotion."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for candidate in (SRC_ROOT, REPO_ROOT):
    candidate_text = str(candidate)
    if candidate_text not in sys.path:
        sys.path.insert(0, candidate_text)

from database.repository import preview_product_records_view_is_active_v1  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit product_records VIEW is_active filter readiness."
    )
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    target = args.db.expanduser().resolve()
    if not target.is_file():
        raise FileNotFoundError(f"SQLite target does not exist: {target}")

    uri = f"file:{target.as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    try:
        report = {
            "db": str(target),
            **preview_product_records_view_is_active_v1(connection),
            "integrity_check": str(
                connection.execute("PRAGMA integrity_check").fetchone()[0]
            ),
        }
    finally:
        connection.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote audit report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
