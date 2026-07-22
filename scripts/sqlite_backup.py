"""CLI for verified SQLite online backups."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for candidate in (SRC_ROOT, REPO_ROOT):
    text = str(candidate)
    if text not in sys.path:
        sys.path.insert(0, text)

from database.backup import backup_sqlite_database


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a verified SQLite online backup (WAL-safe)."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--no-verify", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = backup_sqlite_database(
        args.source,
        args.destination,
        verify=not args.no_verify,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
