"""Shared product stage labels (量產／試產) for UI and repository."""

from __future__ import annotations

from typing import Any

PRODUCT_STAGE_MASS_PRODUCTION = "量產"
PRODUCT_STAGE_TRIAL_PRODUCTION = "試產"
PRODUCT_STAGE_OPTIONS: tuple[str, ...] = (
    PRODUCT_STAGE_MASS_PRODUCTION,
    PRODUCT_STAGE_TRIAL_PRODUCTION,
)


def normalize_product_stage_ui(value: Any) -> str:
    text = str(value or "").strip()
    if text in PRODUCT_STAGE_OPTIONS:
        return text
    return PRODUCT_STAGE_MASS_PRODUCTION
