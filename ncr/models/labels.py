from __future__ import annotations

# UI Field Labels
LABEL_DEFECT_NO = "不良單號"
LABEL_EVENT_DATE = "發生日期"
LABEL_RETURN_SLIP_TYPE = "退料單別"
LABEL_WORK_ORDER_NO = "委外製令"
LABEL_INTERNAL_WORK_ORDER_NO = "廠內製令"
LABEL_TRANSFER_SLIP_NO = "轉撥單單號"


LABEL_ITEM_NO = "料號"
LABEL_PRODUCT_NAME = "產品名稱"
LABEL_QTY = "數量"
LABEL_CATEGORY = "類別"
LABEL_RESPONSIBILITY = "責任"
LABEL_SUPPLIER_NAME = "正式供應商"
LABEL_OUTSOURCE_SUPPLIER_NAME = "委外供應商"
LABEL_SUPPLIER_MGMT_NAME = "供應商名稱"
LABEL_DEFECT_DESC = "不良現象紀錄"
LABEL_STATUS = "狀態"
LABEL_DISPOSITION = "處置方式"
LABEL_SUPPLIER_TYPE = "供應商類別"
LABEL_PRODUCT_MGMT = "產品清單"
LABEL_SUPPLIER_MGMT = "供應商清單"

# Table & Column Headers
HEADER_ID = "ID"
HEADER_CREATED_AT = "建立時間"
HEADER_CASE_COUNT = "件數"
HEADER_EVENT_MONTH = "發生月份"
LABEL_DATA_COUNT = "共 {} 筆"
LABEL_OPEN_COUNT = "未結案 {}"
LABEL_CLOSED_COUNT = "已結案 {}"


# Section Titles
SECTION_TITLE_PRODUCT_STATS = "產品統計"
SECTION_TITLE_SUPPLIER_STATS = "供應商統計"
SECTION_TITLE_OUTSOURCE_STATS = "委外供應商統計"
SECTION_TITLE_PRODUCT_MGMT = "產品清單"
SECTION_TITLE_SUPPLIER_MGMT = "供應商清單"

# Placeholders & Hints
PLACEHOLDER_DEFECT_DESC = "請輸入不良現象、異常描述與可追溯補充紀錄。"
PLACEHOLDER_OUTSOURCE_SUPPLIER = "請選擇委外供應商"
HINT_SUPPLIER_LOCKED = "已鎖定正式供應商"
HINT_OUTSOURCE_LOCKED = "已鎖定委外供應商"
HINT_SAVE_SHORTCUT = "快捷鍵：Ctrl+S"
HINT_RESET_FILTER = "重置恢復預設條件"
HINT_OPEN_CASES_SCOPE = "待處理追蹤預設顯示所有未結案 (不限月份)"
HINT_CLOSED_CASES_SCOPE = "已結案/溯源預設全歷史；可勾選月份縮小範圍"
HINT_CLOSED_CASES_MONTH_SCOPE = "已結案/溯源僅顯示 {}"
HINT_EMPTY_RESULT = "目前查詢結果為 0 筆，請先調整條件後再匯出。"

# Validation Messages
VALIDATION_EVENT_DATE_FORMAT = "發生日期格式必須為 YYYY-MM-DD。"
VALIDATION_EVENT_DATE_FUTURE = "發生日期不可晚於今天。"
VALIDATION_REQUIRED = "{}為必填。"
VALIDATION_WORK_ORDER_FORMAT = "委外製令格式不符（須為 14 碼：XXXX-YYMMDDXXX，且前四碼須為 5102、5104、5202，後九碼為有效日期與流水號）。"
VALIDATION_INTERNAL_WORK_ORDER_FORMAT = "廠內製令格式不符（須為 14 碼：XXXX-YYMMDDXXX，且前四碼須為 5101、5103、5201，後九碼為有效日期與流水號）。"
VALIDATION_QTY_INTEGER = "數量必須為整數。"
VALIDATION_QTY_POSITIVE = "數量必須大於 0。"
VALIDATION_OPTION_INVALID = "{}選項不正確。"
VALIDATION_ITEM_NO_NOT_FOUND = "料號未建立於產品清單，請先至基礎資料建立。"
VALIDATION_DUPLICATE_RECORD = (
    "已有相同發生日期、委外製令、廠內製令、轉撥單單號、料號與不良現象紀錄的資料（{}）。"
)

# Status Messages
MSG_SAVING = "儲存中，請稍候..."
MSG_SAVE_SUCCESS = "儲存成功，已建立不良單：{}"
MSG_SAVE_FAILED = "儲存失敗：{}"
MSG_UPDATE_SUCCESS = "資料已更新。"
MSG_DELETE_CONFIRM = "確定要刪除不良單 {} 嗎？"
MSG_DELETE_SUPPLIER_CONFIRM = "確定要刪除供應商 {} 嗎？"
MSG_DELETE_PRODUCT_CONFIRM = "確定要刪除產品 {} 嗎？"
MSG_NO_DATA = "目前無資料"
