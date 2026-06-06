"""Dry-run or apply the legacy NCR defect.db migration into sqe_v2.db."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
for path in (SRC_ROOT, ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from database.connection import DB_PATH, PROJECT_ROOT, get_connection  # noqa: E402
from database.ncr_migration import migrate_ncr_data_once  # noqa: E402
from database.repository import create_schema  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate SQETOOL/ncr/data/defect.db into SQETOOL/data/sqe_v2.db."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Inspect only; do not write.")
    mode.add_argument("--apply", action="store_true", help="Apply migration and archive source DB.")
    parser.add_argument(
        "--source",
        type=Path,
        default=PROJECT_ROOT / "ncr" / "data" / "defect.db",
        help="Legacy NCR defect.db path.",
    )
    parser.add_argument(
        "--no-archive",
        action="store_true",
        help="Apply migration without renaming the source DB.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with get_connection(DB_PATH) as conn:
        create_schema(conn)
        report = migrate_ncr_data_once(
            conn,
            args.source,
            dry_run=args.dry_run,
            archive=not args.no_archive,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if report.get("errors"):
        return 1
    if args.apply and not report.get("migrated") and report.get("source_exists"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
