from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from dateutil import parser as date_parser

DEFAULT_SOURCE_TZ = "Asia/Kolkata"


def parse_observation_timestamp(
    value: str | datetime,
    source_timezone: str | None = None,
) -> tuple[datetime, str]:
    """Parse a timestamp and return (UTC datetime, original timezone name)."""
    tz_name = source_timezone or DEFAULT_SOURCE_TZ
    if isinstance(value, datetime):
        dt = value
    else:
        dt = date_parser.parse(str(value))

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(tz_name))
        original_tz = tz_name
    else:
        original_tz = str(dt.tzinfo)

    return dt.astimezone(UTC), original_tz
