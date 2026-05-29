"""One-time migration utility: legacy sqe.db -> sqe_v2.db."""

from __future__ import annotations

from pathlib import Path

from database.connection import initialize_database
from database.migration import write_migration_report


def main() -> int:
    report = initialize_database()
    report_path = Path("data") / "migration_report_v2.json"
    write_migration_report(report_path, report)
    print(f"Migration report written to {report_path}")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
