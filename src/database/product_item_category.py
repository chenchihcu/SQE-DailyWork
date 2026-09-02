"""Shared product item-category labels for master data and warehouse alignment."""

from __future__ import annotations

from typing import Any

ITEM_CATEGORY_RAW_MATERIAL = "原物料"
ITEM_CATEGORY_SEMI_FINISHED = "半成品"
ITEM_CATEGORY_FINISHED = "成品"

ITEM_CATEGORY_OPTIONS: tuple[str, ...] = (
    ITEM_CATEGORY_RAW_MATERIAL,
    ITEM_CATEGORY_SEMI_FINISHED,
    ITEM_CATEGORY_FINISHED,
)

MASTER_SEMI_FINISHED_CATEGORIES: tuple[str, ...] = (
    ITEM_CATEGORY_SEMI_FINISHED,
    ITEM_CATEGORY_FINISHED,
)

SUPPLIER_EVENT_PRODUCT_CATEGORIES: tuple[str, ...] = MASTER_SEMI_FINISHED_CATEGORIES

PRODUCT_ITEM_CATEGORY_META_KEY = "product_item_category_v1"
PRODUCT_ITEM_CATEGORY_V2_META_KEY = "product_item_category_v2"


def normalize_item_category(value: Any) -> str:
    text = str(value or "").strip()
    if text in ITEM_CATEGORY_OPTIONS:
        return text
    return ITEM_CATEGORY_SEMI_FINISHED


def infer_item_category_from_product_code(
    product_code: str,
    *,
    current: str = "",
) -> str:
    code = str(product_code or "").strip()
    if code.startswith("0"):
        return ITEM_CATEGORY_RAW_MATERIAL
    normalized_current = normalize_item_category(current)
    if normalized_current in (ITEM_CATEGORY_SEMI_FINISHED, ITEM_CATEGORY_FINISHED):
        return normalized_current
    return ITEM_CATEGORY_SEMI_FINISHED


def item_category_for_defect_record(
    *,
    defect_category: str = "",
    processing_line: str = "",
) -> str:
    normalized_category = str(defect_category or "").strip()
    if normalized_category in ITEM_CATEGORY_OPTIONS:
        return normalized_category
    normalized_line = str(processing_line or "").strip()
    if normalized_line == ITEM_CATEGORY_RAW_MATERIAL:
        return ITEM_CATEGORY_RAW_MATERIAL
    return ITEM_CATEGORY_SEMI_FINISHED
