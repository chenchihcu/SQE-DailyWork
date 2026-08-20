"""Supplier report export with explicit source-separated worksheets."""

from __future__ import annotations

from services import supplier_360_service


def export_supplier_report(
    file_path: str,
    supplier_id: str,
    start_date: str,
    end_date: str,
) -> tuple[bool, str]:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font

        summary = supplier_360_service.get_supplier_summary(supplier_id)
        supplier = summary.get("supplier") or {}
        workbook = Workbook()
        overview = workbook.active
        overview.title = "供應商摘要"
        scorecard = supplier_360_service.get_supplier_scorecard(
            supplier_id, start_date, end_date
        )
        rows = [
            ("供應商", supplier.get("supplier_name", "")),
            ("報告區間", f"{start_date} ～ {end_date}"),
            ("目前評級", scorecard.get("grade", "")),
            ("未結異常", summary.get("open_anomaly_count", 0)),
            ("逾期異常", summary.get("overdue_anomaly_count", 0)),
            ("近 90 日 NCR", summary.get("ncr_90d_count", 0)),
            ("最近訪廠", summary.get("latest_visit_date", "")),
        ]
        for row in rows:
            overview.append(row)
        overview["A1"].font = Font(bold=True)

        _append_table(
            workbook,
            "異常統計",
            supplier_360_service.list_supplier_anomalies(supplier_id),
            ("anomaly_no", "anomaly_date", "problem_desc", "status", "responsible_person", "due_date"),
        )
        _append_table(
            workbook,
            "訪廠紀錄",
            supplier_360_service.list_supplier_visits(supplier_id),
            ("visit_date", "summary", "visitor_name", "status", "work_order_no"),
        )
        _append_table(
            workbook,
            "不合格品統計",
            supplier_360_service.list_supplier_defects(supplier_id),
            ("defect_no", "event_date", "item_no", "product_name", "defect_desc", "status"),
        )
        score_sheet = workbook.create_sheet("評分摘要")
        for key, value in scorecard.items():
            score_sheet.append((key, value))
        workbook.save(file_path)
        return True, f"已輸出供應商報告：{file_path}"
    except Exception as exc:
        return False, f"供應商報告輸出失敗：{exc}"


def _append_table(workbook, title: str, rows: list[dict], keys: tuple[str, ...]) -> None:
    from openpyxl.styles import Font

    sheet = workbook.create_sheet(title)
    sheet.append(keys)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append([row.get(key, "") for key in keys])
