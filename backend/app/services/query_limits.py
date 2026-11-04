from datetime import date, timedelta

from fastapi import HTTPException

from app.core.config import get_settings


def clamp_limit(limit: int | None) -> int:
    settings = get_settings()
    value = limit or settings.default_page_limit
    if value < 1:
        raise HTTPException(400, "limit must be >= 1")
    return min(value, settings.max_page_limit)


def validate_date_range(start: date | None, end: date | None) -> tuple[date | None, date | None]:
    if start and end and end < start:
        raise HTTPException(400, "end date must be on or after start date")
    if start and end:
        span = (end - start).days
        if span > get_settings().max_date_range_days:
            raise HTTPException(
                400,
                f"Date range exceeds {get_settings().max_date_range_days} days. Narrow the query.",
            )
    return start, end
