from __future__ import annotations

import re

_FIXED_MESSAGE_MAP = {
    "Anomaly id is required": "異常 ID 為必填",
    "Anomaly date cannot be in the future": "異常日期不可晚於今天",
    "Anomaly date must be YYYY-MM-DD": "異常日期格式需為 YYYY-MM-DD",
    "Anomaly not found": "找不到異常資料",
    "Batch quantity cannot be negative": "數量不可為負數",
    "Closed date must be YYYY-MM-DD": "結案日期格式需為 YYYY-MM-DD",
    "Improvement description is required": "改善內容為必填",
    "Month must be YYYYMM or YYYY-MM": "月份格式需為 YYYYMM 或 YYYY-MM",
    "Open anomaly not found": "找不到可結案的異常資料",
    "Problem description is required": "問題描述為必填",
    "Production quantity cannot be negative": "數量不可為負數",
    "Product code already exists": "料號已存在",
    "Product code already exists in this scope": "此範圍內料號已存在",
    "Product code is required": "料號為必填",
    "Product does not belong to selected supplier": "產品不屬於所選供應商",
    "Product id is required": "產品 ID 為必填",
    "Product is inactive": "產品已停用",
    "Product is required": "品名為必填",
    "Product name is required": "品名為必填",
    "Product not found": "找不到產品資料",
    "Secondary supplier is required for active products": "啟用中的產品必須指定 2nd source",
    "Stage change reason is required for mass->trial downgrade": "量產改回試產時需填寫原因",
    "Secondary supplier must be different from primary supplier": "2nd source 不可與主供應商相同",
    "Secondary supplier not found": "找不到 2nd source 供應商",
    "Supplier id is required": "供應商 ID 為必填",
    "Supplier is inactive": "供應商已停用",
    "Supplier is required": "供應商為必填",
    "Supplier name already exists": "供應商名稱已存在",
    "Supplier name is required": "供應商名稱為必填",
    "Supplier not found": "找不到供應商資料",
    "Visit date must be YYYY-MM-DD": "訪廠日期格式需為 YYYY-MM-DD",
    "Visit id is required": "訪廠 ID 為必填",
    "Visit is referenced by anomalies": "訪廠紀錄已被異常資料引用",
    "Visit not found": "找不到訪廠紀錄",
    # Common UI prompts
    "Please select a row first": "請先選取一筆資料",
    "Please select a supplier first": "請先選擇供應商",
    "Please create a supplier first": "需先建立供應商",
    "No supplier available": "目前沒有可用供應商",
    "Visit detail": "訪廠明細",
}

_TABLE_NAME_MAP = {
    "products": "品名",
    "anomalies": "異常",
    "visits": "訪廠紀錄",
}

_ENTITY_MAP = {
    "Supplier": "供應商",
    "Product": "品名",
}

_REFERENCED_BY_PATTERN = re.compile(r"^(Supplier|Product) is referenced by (.+)$")
_EXPORTED_PATTERN = re.compile(r"^Exported to (.+)$")
_EXPORT_FAILED_PATTERN = re.compile(r"^Export failed: (.+)$")
_DETAIL_PATTERN = re.compile(r"^(.*?[：:])\s*(.+)$")


def _translate_reference_tables(text: str) -> str:
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if not parts:
        return text
    translated = [_TABLE_NAME_MAP.get(part, part) for part in parts]
    return "、".join(translated)


def localize_popup_message(text: str) -> str:
    message = str(text or "").strip()
    if not message:
        return message

    fixed = _FIXED_MESSAGE_MAP.get(message)
    if fixed is not None:
        return fixed

    referenced_match = _REFERENCED_BY_PATTERN.fullmatch(message)
    if referenced_match is not None:
        entity = _ENTITY_MAP.get(referenced_match.group(1), referenced_match.group(1))
        table_text = _translate_reference_tables(referenced_match.group(2))
        suffix = "引用" if table_text.endswith("紀錄") else "資料引用"
        return f"{entity}資料已被{table_text}{suffix}"

    exported_match = _EXPORTED_PATTERN.fullmatch(message)
    if exported_match is not None:
        return f"已匯出至：{exported_match.group(1)}"

    export_failed_match = _EXPORT_FAILED_PATTERN.fullmatch(message)
    if export_failed_match is not None:
        detail = export_failed_match.group(1).strip()
        localized_detail = localize_popup_message(detail)
        return f"匯出失敗：{localized_detail}"

    detail_match = _DETAIL_PATTERN.fullmatch(message)
    if detail_match is not None:
        prefix, detail = detail_match.group(1), detail_match.group(2)
        localized_detail = localize_popup_message(detail)
        if localized_detail != detail:
            return f"{prefix}{localized_detail}"

    return message


def localize_exception(exc: Exception) -> str:
    return localize_popup_message(str(exc))
