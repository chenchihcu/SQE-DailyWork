"""Print a stable read-only SQLite logical-state fingerprint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from database.backup import sqlite_state_fingerprint  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fingerprint SQLite schema and rows without writable access."
    )
    parser.add_argument("database", type=Path)
    parser.add_argument("--digest-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = sqlite_state_fingerprint(args.database)
    if args.digest_only:
        print(report["state_sha256"])
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if (
        report["integrity_check"] == "ok"
        and not report["foreign_key_check"]
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
