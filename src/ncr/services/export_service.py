from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from ncr.models.defect import (
    DETAIL_EXPORT_COLUMNS,
    DETAIL_EXPORT_HEADERS,
    STATS_DIMENSION_COLUMNS,
    STATS_SECTION_DEFINITIONS,
    build_stats_headers,
)


BASE_DIR = Path(__file__).resolve().parents[3] / "Outputs"


def _normalize_rows(rows: Iterable) -> list[dict]:
    normalized: list[dict] = []
    for row in rows:
        if isinstance(row, dict):
            normalized.append(row)
        else:
            normalized.append(dict(row))
    return normalized


def _auto_fit_columns(worksheet) -> None:
    for column_cells in worksheet.columns:
        values = [str(cell.value or "") for cell in column_cells]
        max_length = max((len(value) for value in values), default=0)
        worksheet.column_dimensions[get_column_letter(column_cells[0].column)].width = (
            min(max(max_length + 2, 10), 40)
        )


def export_to_excel(
    defects,
    product_stats,
    supplier_stats,
    outsource_stats,
    file_path: str | None = None,
) -> str:
    defect_rows = _normalize_rows(defects)
    product_rows = _normalize_rows(product_stats)
    supplier_rows = _normalize_rows(supplier_stats)
    outsource_rows = _normalize_rows(outsource_stats)

    workbook = Workbook()
    detail_sheet = workbook.active
    detail_sheet.title = "不良品明細"
    detail_sheet.append(DETAIL_EXPORT_HEADERS)

    for row in defect_rows:
        detail_sheet.append([row.get(field_name, "") for field_name, _ in DETAIL_EXPORT_COLUMNS])
    _auto_fit_columns(detail_sheet)

    stats_sheet = workbook.create_sheet("統計")
    current_row = 1
    rows_by_name = {
        "product_name": product_rows,
        "supplier_name": supplier_rows,
        "outsource_supplier_name": outsource_rows,
    }

    for section_title, name_key in STATS_SECTION_DEFINITIONS:
        rows = rows_by_name[name_key]
        stats_sheet.cell(row=current_row, column=1, value=section_title)
        current_row += 1
        stats_sheet.append(build_stats_headers(name_key))
        current_row += 1
        for row in rows:
            stats_sheet.append(
                [row.get(name_key, "")]
                + [row.get(field_name, 0) for field_name, _ in STATS_DIMENSION_COLUMNS]
            )
            current_row += 1
        current_row += 1

    _auto_fit_columns(stats_sheet)

    if file_path:
        output_path = Path(file_path)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = BASE_DIR / f"defect_report_{timestamp}.xlsx"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)
    return str(output_path)
