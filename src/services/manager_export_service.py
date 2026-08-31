"""Excel export for manager summary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ui.list_column_contract import MANAGER_SUMMARY_COLUMNS


def _overdue_label(value: object) -> str:
    return "逾期" if bool(value) else "—"


def _append_contract_sheet(
    sheet: Any,
    columns: tuple,
    rows: list[dict],
    *,
    bold_font: Any,
) -> None:
    sheet.append([column.label for column in columns])
    for cell in sheet[1]:
        cell.font = bold_font
    for row in rows:
        sheet.append(
            [
                row.get(column.field, "")
                if column.field != "overdue"
                else _overdue_label(row.get("overdue"))
                for column in columns
            ]
        )


def export_manager_view_excel(
    file_path: str,
    summary_rows: list[dict],
    queue_rows: list[dict] | None = None,
) -> tuple[bool, str]:
    del queue_rows
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font

        workbook = Workbook()
        summary_sheet = workbook.active
        summary_sheet.title = "案件總覽"
        bold_font = Font(bold=True)
        _append_contract_sheet(
            summary_sheet,
            MANAGER_SUMMARY_COLUMNS,
            summary_rows,
            bold_font=bold_font,
        )

        output_path = Path(file_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(output_path)
        return True, f"已匯出主管檢視報告：{output_path}"
    except Exception as exc:
        return False, f"主管檢視匯出失敗：{exc}"
