from __future__ import annotations

from ncr.models.labels import (
    HEADER_CASE_COUNT,
    HEADER_EVENT_MONTH,
    HEADER_ID,
    LABEL_CATEGORY,
    LABEL_RESPONSIBILITY,
    LABEL_DEFECT_DESC,
    LABEL_DEFECT_NO,
    LABEL_DISPOSITION,
    LABEL_EVENT_DATE,
    LABEL_INTERNAL_WORK_ORDER_NO,
    LABEL_RETURN_SLIP_TYPE,
    LABEL_TRANSFER_SLIP_NO,
    LABEL_ITEM_NO,
    LABEL_OUTSOURCE_SUPPLIER_NAME,
    LABEL_PRODUCT_NAME,
    LABEL_QTY,
    LABEL_STATUS,
    LABEL_SUPPLIER_NAME,
    LABEL_WORK_ORDER_NO,
    SECTION_TITLE_OUTSOURCE_STATS,
    SECTION_TITLE_PRODUCT_STATS,
    SECTION_TITLE_SUPPLIER_STATS,
)

CATEGORY_OPTIONS = ["原物料", "半成品", "成品", "委外加工品"]
RESPONSIBILITY_OPTIONS = ["材損", "製損", "不確定"]
STATUS_OPTIONS = ["處理中", "已結案"]
DISPOSITION_OPTIONS = ["重工", "報廢"]
RETURN_SLIP_TYPE_OPTIONS = ["廠內退料", "託外退料"]
SUPPLIER_CATEGORY_OPTIONS = ["正式供應商", "委外供應商"]

DETAIL_EXPORT_COLUMNS = [
    ("defect_no", LABEL_DEFECT_NO),
    ("event_date", LABEL_EVENT_DATE),
    ("return_slip_type", LABEL_RETURN_SLIP_TYPE),
    ("work_order_no", LABEL_WORK_ORDER_NO),
    ("internal_work_order_no", LABEL_INTERNAL_WORK_ORDER_NO),
    ("transfer_slip_no", LABEL_TRANSFER_SLIP_NO),
    ("item_no", LABEL_ITEM_NO),
    ("product_name", LABEL_PRODUCT_NAME),
    ("qty", LABEL_QTY),
    ("category", LABEL_CATEGORY),
    ("supplier_name", LABEL_SUPPLIER_NAME),
    ("outsource_supplier_name", LABEL_OUTSOURCE_SUPPLIER_NAME),
    ("defect_desc", LABEL_DEFECT_DESC),
    ("status", LABEL_STATUS),
    ("disposition", LABEL_DISPOSITION),
    ("responsibility", LABEL_RESPONSIBILITY),
]
FIELD_LABEL_BY_NAME = {"id": HEADER_ID, **dict(DETAIL_EXPORT_COLUMNS)}

STATS_DIMENSION_COLUMNS = [
    ("disposition", LABEL_DISPOSITION),
    ("category", LABEL_CATEGORY),
    ("event_month", HEADER_EVENT_MONTH),
    ("status", LABEL_STATUS),
    ("case_count", HEADER_CASE_COUNT),
    ("total_qty", LABEL_QTY),
]

STATS_NAME_LABELS = {
    "product_name": LABEL_PRODUCT_NAME,
    "supplier_name": LABEL_SUPPLIER_NAME,
    "outsource_supplier_name": LABEL_OUTSOURCE_SUPPLIER_NAME,
}

STATS_SECTION_DEFINITIONS = [
    (SECTION_TITLE_PRODUCT_STATS, "product_name"),
    (SECTION_TITLE_SUPPLIER_STATS, "supplier_name"),
    (SECTION_TITLE_OUTSOURCE_STATS, "outsource_supplier_name"),
]

LIST_HEADERS = [
    LABEL_DEFECT_NO,
    LABEL_EVENT_DATE,
    LABEL_RETURN_SLIP_TYPE,
    LABEL_WORK_ORDER_NO,
    LABEL_INTERNAL_WORK_ORDER_NO,
    LABEL_TRANSFER_SLIP_NO,
    LABEL_ITEM_NO,
    LABEL_PRODUCT_NAME,
    LABEL_QTY,
    LABEL_CATEGORY,
    LABEL_SUPPLIER_NAME,
    LABEL_OUTSOURCE_SUPPLIER_NAME,
    LABEL_DEFECT_DESC,
    LABEL_STATUS,
    LABEL_DISPOSITION,
    LABEL_RESPONSIBILITY,
]

DETAIL_EXPORT_HEADERS = [label for _, label in DETAIL_EXPORT_COLUMNS]
STATS_DIMENSION_HEADERS = [label for _, label in STATS_DIMENSION_COLUMNS]

LIST_FIELD_ORDER = [
    "defect_no",
    "event_date",
    "return_slip_type",
    "work_order_no",
    "internal_work_order_no",
    "transfer_slip_no",
    "item_no",
    "product_name",
    "qty",
    "category",
    "supplier_name",
    "outsource_supplier_name",
    "defect_desc",
    "status",
    "disposition",
    "responsibility",
]


def labels_for_fields(field_names: list[str]) -> list[str]:
    return [FIELD_LABEL_BY_NAME[field_name] for field_name in field_names]


DETAIL_PREVIEW_FIELDS = [
    "defect_no",
    "event_date",
    "return_slip_type",
    "work_order_no",
    "item_no",
    "product_name",
    "qty",
    "status",
    "disposition",
    "defect_desc",
]
DETAIL_PREVIEW_HEADERS = labels_for_fields(DETAIL_PREVIEW_FIELDS)

STATUS_TOTAL_PREVIEW_FIELDS = [
    *DETAIL_PREVIEW_FIELDS,
    "supplier_name",
    "outsource_supplier_name",
]
STATUS_TOTAL_PREVIEW_HEADERS = labels_for_fields(STATUS_TOTAL_PREVIEW_FIELDS)

OUTSOURCE_PROCESSING_PREVIEW_FIELDS = [
    *DETAIL_PREVIEW_FIELDS,
    "outsource_supplier_name",
]
OUTSOURCE_PROCESSING_PREVIEW_HEADERS = labels_for_fields(OUTSOURCE_PROCESSING_PREVIEW_FIELDS)

SUPPLIER_PROCESSING_PREVIEW_FIELDS = [*DETAIL_PREVIEW_FIELDS, "supplier_name"]
SUPPLIER_PROCESSING_PREVIEW_HEADERS = labels_for_fields(SUPPLIER_PROCESSING_PREVIEW_FIELDS)

OUTSOURCE_SCRAP_PREVIEW_FIELDS = [
    *DETAIL_PREVIEW_FIELDS,
    "outsource_supplier_name",
]
OUTSOURCE_SCRAP_PREVIEW_HEADERS = labels_for_fields(OUTSOURCE_SCRAP_PREVIEW_FIELDS)


def build_stats_headers(name_key: str) -> list[str]:
    return [STATS_NAME_LABELS[name_key], *STATS_DIMENSION_HEADERS]
