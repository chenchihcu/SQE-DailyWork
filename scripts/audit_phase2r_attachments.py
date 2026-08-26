"""Read-only Phase 2R attachment/evidence baseline and reconciliation audit."""

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

from app_paths import data_dir, resolve_db_path  # noqa: E402
from database.backup import sqlite_state_fingerprint  # noqa: E402
from database import repository  # noqa: E402

PHASE2_ITEMS_14_19_MAPPING_DOC = (
    "docs/exec-plans/active/2026-08-26-phase2-items-14-19-mapping.md"
)

PHASE2_ITEMS_14_19: dict[str, Any] = {
    "mapping_type": "design-derived",
    "mapping_doc": PHASE2_ITEMS_14_19_MAPPING_DOC,
    "items": [
        {
            "id": "14",
            "derived_title": "Attachment metadata contract and formal Promotion",
            "status": "complete",
        },
        {
            "id": "15",
            "derived_title": "Nine attachment categories with zh-TW labels",
            "status": "complete",
        },
        {
            "id": "16",
            "derived_title": (
                "Same-anomaly evidence links (analysis note + canonical Action)"
            ),
            "status": "complete",
        },
        {
            "id": "17",
            "derived_title": (
                "Physical storage, suffix allowlist, and legacy projection"
            ),
            "status": "complete",
        },
        {
            "id": "18",
            "derived_title": "Workbench attachments tab write UI",
            "status": "complete",
        },
        {
            "id": "19",
            "derived_title": (
                "Read-model, export, and audit consumer compatibility"
            ),
            "status": "partial-accepted",
        },
    ],
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only Phase 2R attachment baseline audit."
    )
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--attachments-root", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def _readonly_connection(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _physical_manifest(root: Path, anomaly_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    allowed = {
        ".jpg", ".jpeg", ".png", ".csv", ".doc", ".docx", ".json", ".log",
        ".pdf", ".ppt", ".pptx", ".txt", ".xls", ".xlsx", ".yaml", ".yml",
    }
    for anomaly_id in anomaly_ids:
        folder = root / anomaly_id
        entries: list[dict[str, Any]] = []
        if folder.is_dir():
            for path in sorted(folder.iterdir(), key=lambda item: item.name.casefold()):
                if path.is_file() and path.name != "captions.json" and path.suffix.lower() in allowed:
                    entries.append(
                        {"name": path.name, "size": path.stat().st_size}
                    )
        result[anomaly_id] = entries
    return result


def build_report(db_path: Path, attachments_root: Path) -> dict[str, Any]:
    conn = _readonly_connection(db_path)
    try:
        preview = repository.preview_anomaly_attachments_contract_v1(conn)
        anomaly_ids = [
            str(row[0])
            for row in conn.execute("SELECT id FROM anomalies ORDER BY id").fetchall()
        ]
        metadata: dict[str, list[dict[str, Any]]] = {
            anomaly_id: repository.list_anomaly_attachments(conn, anomaly_id)
            for anomaly_id in anomaly_ids
        }
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_keys = [list(row) for row in conn.execute("PRAGMA foreign_key_check").fetchall()]
    finally:
        conn.close()

    physical = _physical_manifest(attachments_root, anomaly_ids)
    reconciliation: dict[str, dict[str, Any]] = {}
    for anomaly_id in anomaly_ids:
        metadata_names = {
            str(row.get("stored_name") or row.get("file_name") or "").strip()
            for row in metadata.get(anomaly_id, [])
            if str(row.get("stored_name") or row.get("file_name") or "").strip()
        }
        physical_names = {str(row["name"]) for row in physical.get(anomaly_id, [])}
        reconciliation[anomaly_id] = {
            "metadata_rows": len(metadata.get(anomaly_id, [])),
            "metadata_names": sorted(metadata_names),
            "physical_names": sorted(physical_names),
            "registered_but_missing": sorted(metadata_names - physical_names),
            "unregistered_physical": sorted(physical_names - metadata_names),
        }

    return {
        "mode": "read-only",
        "db": str(db_path.resolve()),
        "attachments_root": str(attachments_root.resolve()),
        "logical_fingerprint": sqlite_state_fingerprint(db_path),
        "schema_preview": preview,
        "integrity_check": integrity,
        "foreign_key_violations": foreign_keys,
        "metadata": metadata,
        "physical": physical,
        "reconciliation": reconciliation,
        "phase2_items_14_19": dict(PHASE2_ITEMS_14_19),
        "formal_promotion_applied": False,
    }


def main() -> int:
    args = _parse_args()
    db_path = Path(args.db or resolve_db_path()).expanduser().resolve()
    root = Path(args.attachments_root or (data_dir() / "attachments" / "anomaly")).expanduser().resolve()
    if not db_path.is_file():
        raise FileNotFoundError(f"SQLite target does not exist: {db_path}")
    report = build_report(db_path, root)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
