"""統一訊息文案來源 — 確保所有頁面成功/錯誤/提醒/確認的標題與內文一致。

格式約定:
- 成功內文一律「{實體}已{動作}」(例:「供應商已建立」、「異常單已刪除」)
- 標題短而明確,使用 TITLES 字典
- 提示句不加句號(與既有 popup_i18n 風格一致)
"""

from __future__ import annotations

# ── 對話框標題 ─────────────────────────────────────────────────────────
TITLES = {
    "success": "成功",
    "warning": "提醒",
    "error": "錯誤",
    "info": "提示",
    "confirm": "確認",
    "confirm_delete": "確認刪除",
}


# ── 成功訊息產生器 ─────────────────────────────────────────────────────
def created(entity: str, *, ref: str | None = None) -> str:
    """例: created('供應商') -> '供應商已建立';
    created('異常單', ref='A-001') -> '異常單「A-001」已建立'。"""
    if ref:
        return f"{entity}「{ref}」已建立"
    return f"{entity}已建立"


def updated(entity: str, *, ref: str | None = None) -> str:
    if ref:
        return f"{entity}「{ref}」已更新"
    return f"{entity}已更新"


def deleted(entity: str, *, ref: str | None = None) -> str:
    if ref:
        return f"{entity}「{ref}」已刪除"
    return f"{entity}已刪除"


def closed(entity: str, *, ref: str | None = None) -> str:
    if ref:
        return f"{entity}「{ref}」已結案"
    return f"{entity}已結案"


def saved(entity: str) -> str:
    return f"{entity}已儲存"


# ── 常用提示文字 ───────────────────────────────────────────────────────
SELECT_ROW_FIRST = "請先選取一筆資料"
SELECT_SUPPLIER_FIRST = "請先選擇供應商"
NEED_SUPPLIER_FIRST = "需先建立供應商"
NO_SUPPLIER_AVAILABLE = "目前沒有可用供應商"
EMPTY_TABLE_HINT = "目前無資料,請使用上方按鈕新增"
LOADING = "載入中…"


