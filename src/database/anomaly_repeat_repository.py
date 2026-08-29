"""Phase 5 repeat-issue similarity index schema and refresh helpers."""

from __future__ import annotations

import sqlite3
from typing import Any

from database.repo_helpers import (
    ANOMALY_REPEAT_LINKS_MIGRATION_META_KEY,
    ANOMALY_REPEAT_LINKS_SCHEMA_VERSION,
    _gen_id,
    _table_columns,
    _table_exists,
    get_migration_meta,
    upsert_migration_meta,
)
from database.repository_schema_helpers import ensure_index as _ensure_index
from services.repeat_issue_scoring import REPEAT_MIN_SCORE, compute_repeat_similarity

_ANOMALY_REPEAT_LINKS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS anomaly_repeat_links (
    id TEXT PRIMARY KEY,
    anomaly_id TEXT NOT NULL,
    peer_anomaly_id TEXT NOT NULL,
    similarity_score INTEGER NOT NULL CHECK (similarity_score >= 0),
    match_reasons TEXT NOT NULL DEFAULT '',
    indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (anomaly_id, peer_anomaly_id),
    CHECK (anomaly_id <> peer_anomaly_id),
    FOREIGN KEY (anomaly_id) REFERENCES anomalies(id) ON DELETE CASCADE,
    FOREIGN KEY (peer_anomaly_id) REFERENCES anomalies(id) ON DELETE CASCADE
);
"""

_REPEAT_LINK_COLUMNS: tuple[str, ...] = (
    "id",
    "anomaly_id",
    "peer_anomaly_id",
    "similarity_score",
    "match_reasons",
    "indexed_at",
)


def preview_anomaly_repeat_links_v1(conn: sqlite3.Connection) -> dict[str, Any]:
    columns = (
        sorted(_table_columns(conn, "anomaly_repeat_links"))
        if _table_exists(conn, "anomaly_repeat_links")
        else []
    )
    missing_table_columns = [
        name for name in _REPEAT_LINK_COLUMNS if name not in columns
    ]
    ready = (
        _table_exists(conn, "anomaly_repeat_links")
        and not missing_table_columns
        and get_migration_meta(conn, ANOMALY_REPEAT_LINKS_MIGRATION_META_KEY)
        == ANOMALY_REPEAT_LINKS_SCHEMA_VERSION
    )
    row_count = 0
    if _table_exists(conn, "anomaly_repeat_links"):
        row_count = int(
            conn.execute("SELECT COUNT(*) FROM anomaly_repeat_links").fetchone()[0]
        )
    return {
        "ready": ready,
        "missing_table_columns": missing_table_columns,
        "repeat_link_rows": row_count,
    }


def anomaly_repeat_links_schema_ready(conn: sqlite3.Connection) -> bool:
    return bool(preview_anomaly_repeat_links_v1(conn)["ready"])


def _install_repeat_link_indexes(conn: sqlite3.Connection) -> None:
    _ensure_index(
        conn,
        "idx_anomaly_repeat_links_anomaly",
        "anomaly_repeat_links",
        "anomaly_id, similarity_score DESC",
    )
    _ensure_index(
        conn,
        "idx_anomaly_repeat_links_peer",
        "anomaly_repeat_links",
        "peer_anomaly_id",
    )


def _fetch_supplier_anomaly_signals(
    conn: sqlite3.Connection, supplier_id: str
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, category, product_id, product_name, process_keywords, problem_desc
        FROM anomalies
        WHERE supplier_id = ?
        """,
        (str(supplier_id or "").strip(),),
    ).fetchall()
    return [dict(row) for row in rows]


def refresh_supplier_repeat_links(
    conn: sqlite3.Connection,
    supplier_id: str,
) -> dict[str, int]:
    """Rebuild directed repeat links for all anomalies under one supplier."""
    sid = str(supplier_id or "").strip()
    if not sid:
        return {"deleted": 0, "inserted": 0}
    anomalies = _fetch_supplier_anomaly_signals(conn, sid)
    anomaly_ids = [str(row["id"]) for row in anomalies]
    if not anomaly_ids:
        return {"deleted": 0, "inserted": 0}
    placeholders = ",".join("?" for _ in anomaly_ids)
    deleted = conn.execute(
        f"""
        DELETE FROM anomaly_repeat_links
        WHERE anomaly_id IN ({placeholders})
           OR peer_anomaly_id IN ({placeholders})
        """,
        anomaly_ids + anomaly_ids,
    ).rowcount
    inserted = 0
    for current in anomalies:
        for peer in anomalies:
            if current["id"] == peer["id"]:
                continue
            score, reasons = compute_repeat_similarity(current, peer)
            if score < REPEAT_MIN_SCORE:
                continue
            conn.execute(
                """
                INSERT INTO anomaly_repeat_links(
                    id, anomaly_id, peer_anomaly_id, similarity_score, match_reasons
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    _gen_id(),
                    str(current["id"]),
                    str(peer["id"]),
                    int(score),
                    "\n".join(reasons),
                ),
            )
            inserted += 1
    return {"deleted": int(deleted or 0), "inserted": inserted}


def backfill_all_repeat_links(conn: sqlite3.Connection) -> dict[str, int]:
    supplier_ids = [
        str(row["supplier_id"])
        for row in conn.execute(
            "SELECT DISTINCT supplier_id FROM anomalies"
        ).fetchall()
    ]
    totals = {"deleted": 0, "inserted": 0, "suppliers": 0}
    conn.execute("DELETE FROM anomaly_repeat_links")
    for supplier_id in supplier_ids:
        report = refresh_supplier_repeat_links(conn, supplier_id)
        totals["deleted"] += report["deleted"]
        totals["inserted"] += report["inserted"]
        totals["suppliers"] += 1
    return totals


def list_repeat_links_for_anomaly(
    conn: sqlite3.Connection,
    anomaly_id: str,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    aid = str(anomaly_id or "").strip()
    if not aid:
        return []
    rows = conn.execute(
        """
        SELECT
            l.peer_anomaly_id,
            l.similarity_score,
            l.match_reasons,
            a.anomaly_no,
            a.anomaly_date,
            a.category,
            a.status,
            a.problem_desc
        FROM anomaly_repeat_links AS l
        JOIN anomalies AS a ON a.id = l.peer_anomaly_id
        WHERE l.anomaly_id = ?
        ORDER BY l.similarity_score DESC, a.anomaly_date DESC, a.anomaly_no DESC
        LIMIT ?
        """,
        (aid, max(1, int(limit))),
    ).fetchall()
    return [dict(row) for row in rows]


def count_repeat_links_for_anomaly(
    conn: sqlite3.Connection, anomaly_id: str
) -> int:
    aid = str(anomaly_id or "").strip()
    if not aid or not _table_exists(conn, "anomaly_repeat_links"):
        return 0
    row = conn.execute(
        "SELECT COUNT(*) AS count FROM anomaly_repeat_links WHERE anomaly_id = ?",
        (aid,),
    ).fetchone()
    return int(row["count"] or 0) if row else 0


def count_supplier_repeat_flagged_anomalies(
    conn: sqlite3.Connection, supplier_id: str
) -> int:
    sid = str(supplier_id or "").strip()
    if not sid or not _table_exists(conn, "anomaly_repeat_links"):
        return 0
    row = conn.execute(
        """
        SELECT COUNT(DISTINCT l.anomaly_id) AS count
        FROM anomaly_repeat_links AS l
        JOIN anomalies AS a ON a.id = l.anomaly_id
        WHERE a.supplier_id = ?
        """,
        (sid,),
    ).fetchone()
    return int(row["count"] or 0) if row else 0


def _ensure_anomaly_repeat_links_v1(
    conn: sqlite3.Connection,
    *,
    commit_meta: bool = True,
) -> dict[str, Any]:
    conn.executescript(_ANOMALY_REPEAT_LINKS_TABLE_DDL)
    _install_repeat_link_indexes(conn)
    backfill = backfill_all_repeat_links(conn)
    if commit_meta:
        upsert_migration_meta(
            conn,
            ANOMALY_REPEAT_LINKS_MIGRATION_META_KEY,
            ANOMALY_REPEAT_LINKS_SCHEMA_VERSION,
        )
    else:
        conn.execute(
            """
            INSERT INTO migration_meta(key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (
                ANOMALY_REPEAT_LINKS_MIGRATION_META_KEY,
                ANOMALY_REPEAT_LINKS_SCHEMA_VERSION,
            ),
        )
    report = preview_anomaly_repeat_links_v1(conn)
    report["backfill"] = backfill
    return report


def migrate_anomaly_repeat_links_v1(
    conn: sqlite3.Connection,
    *,
    apply: bool = False,
) -> dict[str, Any]:
    preview = preview_anomaly_repeat_links_v1(conn)
    if not apply:
        return {**preview, "applied": False, "skipped": preview["ready"]}
    if preview["ready"]:
        return {**preview, "applied": False, "skipped": True}
    report = _ensure_anomaly_repeat_links_v1(conn, commit_meta=True)
    if report["missing_table_columns"]:
        raise RuntimeError(
            "Repeat-issue contract migration did not install all objects: "
            + ", ".join(report["missing_table_columns"])
        )
    return {**report, "applied": True, "skipped": False}
