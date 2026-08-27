"""CLI to prepare a disposable verification SQLite database."""

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

from database.verify_prepare import prepare_verify_database


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a verified disposable SQLite database for scripts/verify.ps1. "
            "Missing sources fail unless --allow-schema-only is set."
        )
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--allow-schema-only",
        action="store_true",
        help=(
            "When source is missing, create a scratch schema-only database "
            "and back it up to destination. Never writes data/sqe_v2.db."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        report = prepare_verify_database(
            args.source,
            args.destination,
            allow_schema_only=args.allow_schema_only,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
