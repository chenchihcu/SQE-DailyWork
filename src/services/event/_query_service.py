"""Event list, dashboard, monthly stats, trend, Pareto, and range summaries."""

from __future__ import annotations

import logging
from datetime import date

logger = logging.getLogger(__name__)

from database import connection as _connection
from database import repository
from services.date_range import DateRangeFormatError, validate_date_range

from ._helpers import _month_now


def list_events(filters: dict | None = None) -> list[dict]:
    params = filters or {}
    with _connection.get_connection() as conn:
        events = repository.list_events(
            conn,
            event_type=params.get("event_type", "ALL"),
            status=params.get("status", "ALL"),
            supplier_keyword=params.get("supplier", ""),
            yyyymm=params.get("yyyymm"),
            limit=params.get("limit"),
            event_scope=params.get("event_scope"),
            overdue_only=bool(params.get("overdue_only", False)),
        )
        _enrich_events_with_overview(conn, events)
        return events


def _enrich_events_with_overview(
    conn, events: list[dict]
) -> None:
    """Annotate anomaly rows with the workbench overview read model.

    Visits stay unchanged because they don't own an anomaly; only ``ANOMALY``
    rows receive the additional fields so every downstream consumer (list,
    export, dashboard cards) reads the same single source of truth.
    """
    for row in events:
        if row.get("event_type") != "ANOMALY":
            continue
        event_id = str(row.get("event_id") or "").strip()
        if not event_id:
            continue
        try:
            card = repository.get_anomaly_overview_card(conn, event_id)
        except ValueError:
            continue
        row["current_action"] = card.get("current_action")
        row["open_action_count"] = card.get("open_action_count", 0)
        row["overdue"] = bool(card.get("overdue"))
        row["root_cause_status"] = card.get("root_cause_status")
        row["corrective_action_status"] = card.get("corrective_action_status")
        row["verification_result"] = card.get("verification_result")
        row["has_analysis_notes"] = bool(card.get("has_analysis_notes"))
        row["attachment_count"] = int(card.get("attachment_count", 0))


def get_dashboard_summary() -> dict:
    with _connection.get_connection() as conn:
        return repository.get_dashboard_summary(conn)


def get_event_scope_counts() -> dict[str, int]:
    """Per-scope event counts aligned with EVENT_QUERY_SCOPE_TABS filters."""
    scopes = (
        repository.EVENT_SCOPE_ANOMALY_ONLY,
        repository.EVENT_SCOPE_VISIT_WITH_ANOMALY,
        repository.EVENT_SCOPE_VISIT_ONLY,
        repository.EVENT_SCOPE_CLOSED_ONLY,
    )
    with _connection.get_connection() as conn:
        return {
            scope: len(
                repository.list_events(
                    conn,
                    event_type="ALL",
                    status="ALL",
                    event_scope=scope,
                )
            )
            for scope in scopes
        }


def get_monthly_stats(yyyymm: str | None = None) -> dict:
    month = yyyymm or _month_now()
    with _connection.get_connection() as conn:
        return repository.get_monthly_stats(conn, month)


def get_responsible_person_stats(yyyymm: str | None = None) -> list[dict]:
    month = yyyymm or _month_now()
    with _connection.get_connection() as conn:
        return repository.get_responsible_person_stats(conn, month)


def list_events_by_range(start_date: str, end_date: str) -> list[dict]:
    """取得指定日期範圍內的所有異常事件與訪廠事件。"""
    try:
        start_date, end_date = validate_date_range(start_date, end_date)
    except DateRangeFormatError:
        return []
    anomaly_sql = """
        SELECT
            a.id AS event_id,
            a.anomaly_no AS ref_no,
            a.anomaly_date AS event_date,
            'ANOMALY' AS event_type,
            s.supplier_name AS supplier_name,
            a.product_id AS product_id,
            p.product_code AS product_code,
            a.product_name AS product_name,
            a.product_stage AS product_stage,
            a.problem_desc AS content,
            a.status AS status,
            a.category AS category,
            a.process_keywords AS process_keywords,
            a.pending_items AS pending_items,
            a.responsible_person AS responsible_person,
            a.improvement_desc AS improvement_desc,
            a.closed_at AS closed_at,
            a.quality_report_required AS quality_report_required
        FROM anomalies a
        JOIN suppliers s ON s.id = a.supplier_id
        LEFT JOIN products p ON p.id = a.product_id
        WHERE a.anomaly_date BETWEEN ? AND ?
    """
    visit_sql = """
        SELECT
            v.id AS event_id,
            '' AS ref_no,
            v.visit_date AS event_date,
            'VISIT' AS event_type,
            s.supplier_name AS supplier_name,
            v.summary AS content,
            '已完成' AS status,
            '' AS category,
            '' AS improvement_desc,
            v.visitor_name AS responsible_person,
            NULL AS closed_at,
            NULL AS quality_report_required
        FROM visits v
        JOIN suppliers s ON s.id = v.supplier_id
        WHERE v.visit_date BETWEEN ? AND ?
    """
    events = []
    with _connection.get_connection() as conn:
        for row in conn.execute(anomaly_sql, (start_date, end_date)).fetchall():
            events.append(dict(row))
        for row in conn.execute(visit_sql, (start_date, end_date)).fetchall():
            events.append(dict(row))
        _enrich_events_with_overview(conn, events)
    events.sort(key=lambda x: (x["event_date"], x["event_id"]), reverse=True)
    return events


def summarize_range_events(events: list[dict]) -> tuple[dict, list[dict]]:
    """依日期區間明細彙總 (整體 KPI, 供應商排行)。

    口徑：opened-in-range cohort 的「現況」統計（結案數 = 區間內發生且目前
    已結案），與 get_monthly_stats 的固定月份口徑（結案數 = 當月結案，跨
    cohort）刻意不同 — 兩者不可互相替換（audit finding D18：抽成具名純函
    式讓此口徑可獨立測試，而非埋在匯出流程內）。
    """
    from collections import defaultdict

    total_anomalies = len([e for e in events if e['event_type'] == 'ANOMALY'])
    total_visits = len([e for e in events if e['event_type'] == 'VISIT'])
    closed_anomalies = len([e for e in events if e['event_type'] == 'ANOMALY' and e['status'] == '已結案'])
    open_anomalies = len([e for e in events if e['event_type'] == 'ANOMALY' and e['status'] == '待處理'])
    totals = {
        "total_anomalies": total_anomalies,
        "total_visits": total_visits,
        "closed_anomalies": closed_anomalies,
        "open_anomalies": open_anomalies,
        "close_rate": (closed_anomalies / total_anomalies * 100) if total_anomalies > 0 else 0.0,
        "anomaly_visit_ratio": (total_anomalies / total_visits) if total_visits > 0 else 0.0,
        "supplier_coverage": len(set(e['supplier_name'] for e in events if e.get('supplier_name'))),
    }

    supplier_stats = defaultdict(lambda: {"anomaly_count": 0, "visit_count": 0, "closed_count": 0, "open_count": 0})
    for e in events:
        sname = e.get("supplier_name")
        if not sname:
            continue
        if e["event_type"] == "ANOMALY":
            supplier_stats[sname]["anomaly_count"] += 1
            if e["status"] == "已結案":
                supplier_stats[sname]["closed_count"] += 1
            else:
                supplier_stats[sname]["open_count"] += 1
        elif e["event_type"] == "VISIT":
            supplier_stats[sname]["visit_count"] += 1

    ranking_rows = []
    for sname, s in supplier_stats.items():
        tot_anom = s["anomaly_count"]
        cls_anom = s["closed_count"]
        rate = (cls_anom / tot_anom * 100) if tot_anom > 0 else 0.0
        ranking_rows.append({
            "supplier_name": sname,
            "anomaly_count": tot_anom,
            "visit_count": s["visit_count"],
            "closed_anomaly_count": cls_anom,
            "open_anomaly_count": s["open_count"],
            "close_rate_pct": rate
        })
    ranking_rows.sort(key=lambda x: x["anomaly_count"], reverse=True)
    return totals, ranking_rows


def _normalized_anomaly_category(value: object) -> str:
    text = str(value or "").strip()
    return text or "未分類"


def _build_category_pareto_rows(category_counts: dict[str, int]) -> list[dict]:
    total = sum(category_counts.values())
    if total <= 0:
        return []

    rows = []
    cumulative_count = 0
    sorted_items = sorted(
        category_counts.items(),
        key=lambda item: (-item[1], item[0] == "未分類", item[0]),
    )
    for rank, (category, count) in enumerate(sorted_items, start=1):
        cumulative_count += count
        rows.append({
            "rank": rank,
            "category": category,
            "count": int(count),
            "percent": round(count / total * 100, 1),
            "cumulative_percent": round(cumulative_count / total * 100, 1),
        })
    rows[-1]["cumulative_percent"] = 100.0
    return rows


def get_anomaly_category_pareto_by_range(start_date: str, end_date: str) -> list[dict]:
    """Return root-cause Pareto rows for anomalies opened in a date range.

    頁面圖表與 Excel 匯出(表格、嵌入 PNG)都必須走這個唯一實作,
    避免兩套彙總口徑(fallback、JOIN 掉列)造成同一份報告內數字不一致。
    """
    from collections import defaultdict

    try:
        start_date, end_date = validate_date_range(start_date, end_date)
    except DateRangeFormatError:
        return []

    sql = """
        SELECT
            COALESCE(
                NULLIF(TRIM(category), ''),
                '未分類'
            ) AS category,
            COUNT(*) AS count
        FROM anomalies
        WHERE anomaly_date BETWEEN ? AND ?
        GROUP BY COALESCE(
            NULLIF(TRIM(category), ''),
            '未分類'
        )
        ORDER BY count DESC, category ASC
    """
    with _connection.get_connection() as conn:
        rows = conn.execute(sql, (start_date, end_date)).fetchall()
    # SQL TRIM 只去 ASCII 空白,Python strip() 另涵蓋全形空白等 Unicode 空白;
    # 兩個 SQL 群組正規化成同一鍵時必須累加,不能讓後者覆蓋前者的計數。
    category_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        category_counts[_normalized_anomaly_category(row["category"])] += int(row["count"] or 0)
    return _build_category_pareto_rows(dict(category_counts))


PROCESS_KEYWORD_PARETO_TOP_N = 15


def _build_process_keyword_pareto_rows(keyword_counts: dict[str, int]) -> list[dict]:
    rows = _build_category_pareto_rows(keyword_counts)
    for row in rows:
        row["keyword"] = row.pop("category")
    return rows


def get_anomaly_process_keyword_pareto_by_range(start_date: str, end_date: str) -> list[dict]:
    """Return SMT process-keyword Pareto rows for anomalies opened in a date range.

    Counts keyword occurrences (multi-tag anomalies contribute to multiple buckets).
    Page charts and Excel export must use this single implementation.
    """
    from collections import defaultdict

    from database.repository import _has_column
    from services.process_keyword_codec import parse_process_keywords

    try:
        start_date, end_date = validate_date_range(start_date, end_date)
    except DateRangeFormatError:
        return []

    with _connection.get_connection() as conn:
        if not _has_column(conn, "anomalies", "process_keywords"):
            return []
        rows = conn.execute(
            """
            SELECT process_keywords
            FROM anomalies
            WHERE anomaly_date BETWEEN ? AND ?
            """,
            (start_date, end_date),
        ).fetchall()

    keyword_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        for keyword in parse_process_keywords(row["process_keywords"]):
            keyword_counts[keyword] += 1
    if not keyword_counts:
        return []

    sorted_items = sorted(
        keyword_counts.items(),
        key=lambda item: (-item[1], item[0]),
    )
    if len(sorted_items) > PROCESS_KEYWORD_PARETO_TOP_N:
        top_items = sorted_items[:PROCESS_KEYWORD_PARETO_TOP_N]
        other_count = sum(count for _, count in sorted_items[PROCESS_KEYWORD_PARETO_TOP_N:])
        collapsed = dict(top_items)
        if other_count:
            collapsed["其他"] = other_count
    else:
        collapsed = dict(sorted_items)
    return _build_process_keyword_pareto_rows(collapsed)


def get_responsible_person_stats_by_range(start_date: str, end_date: str) -> list[dict]:
    """計算指定日期範圍內各責任人的異常件數與平均處理時效。"""
    start_date, end_date = validate_date_range(start_date, end_date)
    sql = """
        SELECT
            COALESCE(NULLIF(TRIM(responsible_person), ''), '未指定') AS person,
            COUNT(*) AS total_count,
            COUNT(CASE WHEN status = '已結案' THEN 1 END) AS closed_count,
            COUNT(CASE WHEN status = '待處理' THEN 1 END) AS open_count,
            AVG(julianday(COALESCE(NULLIF(closed_at, ''), date('now', 'localtime'))) - julianday(anomaly_date)) AS avg_days
        FROM anomalies
        WHERE anomaly_date BETWEEN ? AND ?
        GROUP BY person
        ORDER BY total_count DESC, person ASC
    """
    with _connection.get_connection() as conn:
        rows = conn.execute(sql, (start_date, end_date)).fetchall()

        # 未結案最早/最晚日期必須與 open_count 同一區間口徑(圖表長條、tooltip、
        # 洞察文字皆以區間內事件為準),否則日期會指向不在計數內的案件。
        unclosed_sql = """
            SELECT
                COALESCE(NULLIF(TRIM(responsible_person), ''), '未指定') AS person,
                MIN(anomaly_date) AS min_date,
                MAX(anomaly_date) AS max_date
            FROM anomalies
            WHERE status = '待處理' AND anomaly_date BETWEEN ? AND ?
            GROUP BY person
        """
        unclosed_rows = conn.execute(unclosed_sql, (start_date, end_date)).fetchall()
        unclosed_dates = {r["person"]: (r["min_date"], r["max_date"]) for r in unclosed_rows}

    results = []
    for row in rows:
        person = row["person"]
        min_date, max_date = unclosed_dates.get(person, (None, None))
        results.append({
            "responsible_person": person,
            "total_count": int(row["total_count"]),
            "closed_count": int(row["closed_count"]),
            "open_count": int(row["open_count"]),
            "avg_resolution_time": round(float(row["avg_days"] or 0), 1),
            "min_open_date": min_date,
            "max_open_date": max_date,
        })
    return results


def get_anomaly_closure_activity_by_range(start_date: str, end_date: str) -> int:
    """Count anomalies closed in the range, regardless of creation cohort."""
    start_date, end_date = validate_date_range(start_date, end_date)
    with _connection.get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM anomalies
            WHERE status = '已結案' AND closed_at BETWEEN ? AND ?
            """,
            (start_date, end_date),
        ).fetchone()
    return int(row["count"] or 0)


def _enumerate_month_keys(start_date: str, end_date: str) -> list[str]:
    """Return YYYY-MM keys from start through end, capped at the last 12 months."""
    from datetime import datetime

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    months_list: list[str] = []
    curr_y, curr_m = start_dt.year, start_dt.month
    end_y, end_m = end_dt.year, end_dt.month

    while (curr_y < end_y) or (curr_y == end_y and curr_m <= end_m):
        months_list.append(f"{curr_y:04d}-{curr_m:02d}")
        curr_m += 1
        if curr_m > 12:
            curr_m = 1
            curr_y += 1

    if len(months_list) > 12:
        months_list = months_list[-12:]
    return months_list


def get_visit_trend_by_range(start_date: str, end_date: str) -> list[dict]:
    """計算指定日期範圍內各月份的訪廠數與訪廠發現的異常數（最多限制 12 個月）。"""
    try:
        start_date, end_date = validate_date_range(start_date, end_date)
    except DateRangeFormatError:
        return []
    months_list = _enumerate_month_keys(start_date, end_date)

    with _connection.get_connection() as conn:
        visit_rows = conn.execute(
            """
            SELECT substr(visit_date, 1, 7) AS yyyymm, COUNT(*) AS visit_count
            FROM visits
            WHERE visit_date BETWEEN ? AND ?
            GROUP BY yyyymm
            """,
            (start_date, end_date)
        ).fetchall()
        visits_by_month = {r["yyyymm"]: int(r["visit_count"] or 0) for r in visit_rows}

        anomaly_rows = conn.execute(
            """
            SELECT substr(anomaly_date, 1, 7) AS yyyymm, COUNT(*) AS anomaly_count
            FROM anomalies
            WHERE NULLIF(visit_id, '') IS NOT NULL AND anomaly_date BETWEEN ? AND ?
            GROUP BY yyyymm
            """,
            (start_date, end_date)
        ).fetchall()
        anomalies_by_month = {r["yyyymm"]: int(r["anomaly_count"] or 0) for r in anomaly_rows}

    results = []
    for yyyymm in months_list:
        results.append({
            "yyyymm": yyyymm,
            "visit_count": visits_by_month.get(yyyymm, 0),
            "visit_anomaly_count": anomalies_by_month.get(yyyymm, 0)
        })
    return results


def get_anomaly_trend_by_range(start_date: str, end_date: str) -> list[dict]:
    """計算指定日期範圍內各月份的異常數、結案數、逾期數及累計積壓趨勢（最多限制 12 個月）。"""
    import calendar

    try:
        start_date, end_date = validate_date_range(start_date, end_date)
    except DateRangeFormatError:
        return []
    months_list = _enumerate_month_keys(start_date, end_date)

    def _month_end_date(yyyymm: str) -> str:
        year, month = int(yyyymm[:4]), int(yyyymm[5:])
        last_day = calendar.monthrange(year, month)[1]
        return f"{year:04d}-{month:02d}-{last_day:02d}"

    with _connection.get_connection() as conn:
        # total + overdue per month in one grouped query (both keyed off
        # anomaly_date; overdue's "now" cutoff doesn't depend on the month
        # being reported, so it groups cleanly alongside total). Keep the
        # date predicate exact so custom export ranges do not include
        # same-month rows outside the selected start/end dates.
        total_overdue_rows = conn.execute(
            """
            SELECT
                substr(anomaly_date, 1, 7) AS yyyymm,
                COUNT(*) AS total_count,
                SUM(
                    CASE WHEN status = '待處理' AND due_date <> ''
                              AND due_date < date('now', 'localtime')
                         THEN 1 ELSE 0 END
                ) AS overdue_count
            FROM anomalies
            WHERE anomaly_date BETWEEN ? AND ?
            GROUP BY yyyymm
            """,
            (start_date, end_date),
        ).fetchall()
        total_by_month = {r["yyyymm"]: int(r["total_count"] or 0) for r in total_overdue_rows}
        overdue_by_month = {r["yyyymm"]: int(r["overdue_count"] or 0) for r in total_overdue_rows}

        # closed per month, grouped by closed_at (a different column than
        # anomaly_date, so it needs its own query).
        closed_rows = conn.execute(
            """
            SELECT substr(closed_at, 1, 7) AS yyyymm, COUNT(*) AS closed_count
            FROM anomalies
            WHERE closed_at <> '' AND closed_at BETWEEN ? AND ?
            GROUP BY yyyymm
            """,
            (start_date, end_date),
        ).fetchall()
        closed_by_month = {r["yyyymm"]: int(r["closed_count"] or 0) for r in closed_rows}

        # backlog: whether a row counts as "still open as of yyyymm" depends
        # on yyyymm itself (not a fixed cutoff), so it can't be grouped in
        # one pass -- fetch every candidate row once and re-apply the
        # original per-month condition in Python instead of re-scanning the
        # table once per month (was up to 12 additional full-table scans).
        all_rows = conn.execute(
            "SELECT anomaly_date, status, closed_at FROM anomalies "
            "WHERE anomaly_date <= ?",
            (end_date,),
        ).fetchall()

    results = []
    for yyyymm in months_list:
        cutoff_date = min(_month_end_date(yyyymm), end_date)
        backlog_count = 0
        for row in all_rows:
            row_date = str(row["anomaly_date"] or "")
            if row_date > cutoff_date:
                continue
            status = row["status"]
            closed_at = row["closed_at"] or ""
            is_open_as_of_month = (
                status != "已結案"
                or (closed_at != "" and closed_at > cutoff_date)
            )
            if is_open_as_of_month:
                backlog_count += 1
        results.append({
            "yyyymm": yyyymm,
            "total_count": total_by_month.get(yyyymm, 0),
            "closed_count": closed_by_month.get(yyyymm, 0),
            "overdue_count": overdue_by_month.get(yyyymm, 0),
            "backlog_count": backlog_count,
        })
    return results
