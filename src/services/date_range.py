"""Shared strict date-range validation for reports and statistics."""

from __future__ import annotations

from datetime import date


class DateRangeFormatError(ValueError):
    """Raised when a range endpoint is not an ISO calendar date."""


def validate_date_range(start_date: str, end_date: str) -> tuple[str, str]:
    try:
        start = date.fromisoformat(str(start_date or "").strip())
        end = date.fromisoformat(str(end_date or "").strip())
    except ValueError as exc:
        raise DateRangeFormatError("Date range must use YYYY-MM-DD") from exc
    if start > end:
        raise ValueError("Start date cannot be after end date")
    return start.isoformat(), end.isoformat()
