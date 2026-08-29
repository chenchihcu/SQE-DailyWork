"""Read-only Phase 3 hypothesis / evidence-chain baseline audit."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for candidate in (SRC_ROOT, REPO_ROOT):
    candidate_text = str(candidate)
    if candidate_text not in sys.path:
        sys.path.insert(0, candidate_text)

from app_paths import resolve_db_path  # noqa: E402
from database.backup import sqlite_state_fingerprint  # noqa: E402
from database import repository  # noqa: E402

PHASE3_ITEMS_20_23_MAPPING_DOC = (
    "docs/exec-plans/active/2026-08-26-phase3-items-20-23-hypothesis-contract.md"
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only Phase 3 hypothesis baseline audit."
    )
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "scratch" / "phase3-hypothesis-audit.json",
    )
    return parser.parse_args()


def _readonly_connection(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _count_rows(connection: sqlite3.Connection, table: str) -> int:
    if not repository._table_exists(connection, table):
        return 0
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def build_report(connection: sqlite3.Connection, *, db_path: Path) -> dict[str, Any]:
    preview = repository.preview_anomaly_hypotheses_v1(connection)
    sample_anomaly_id = connection.execute(
        "SELECT id FROM anomalies ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    evidence_chain: list[dict[str, Any]] = []
    if sample_anomaly_id is not None and preview.get("ready"):
        evidence_chain = repository.list_anomaly_evidence_chain(
            connection, str(sample_anomaly_id[0])
        )
    return {
        "mapping_doc": PHASE3_ITEMS_20_23_MAPPING_DOC,
        "db": str(db_path),
        "fingerprint": sqlite_state_fingerprint(db_path),
        "hypothesis_contract": preview,
        "row_counts": {
            "anomalies": _count_rows(connection, "anomalies"),
            "anomaly_hypotheses": _count_rows(connection, "anomaly_hypotheses"),
            "anomaly_root_causes": _count_rows(connection, "anomaly_root_causes"),
            "anomaly_attachments": _count_rows(connection, "anomaly_attachments"),
        },
        "sample_evidence_chain_nodes": len(evidence_chain),
    }


def main() -> int:
    args = _parse_args()
    target = Path(args.db or resolve_db_path()).expanduser().resolve()
    if not target.is_file():
        raise FileNotFoundError(f"SQLite target does not exist: {target}")

    connection = _readonly_connection(target)
    try:
        report = build_report(connection, db_path=target)
    finally:
        connection.close()

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
