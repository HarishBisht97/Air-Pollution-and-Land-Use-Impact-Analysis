from datetime import UTC

from app.ingestion.timestamps import parse_observation_timestamp


def test_naive_ist_converts_to_utc():
    utc, original = parse_observation_timestamp("2024-01-15 10:00:00", "Asia/Kolkata")
    assert original == "Asia/Kolkata"
    assert utc.tzinfo is not None
    assert utc.astimezone(UTC).hour == 4


def test_aware_timestamp_preserves_zone_name():
    utc, original = parse_observation_timestamp("2024-01-15T10:00:00+05:30")
    assert utc.hour == 4
    assert original
