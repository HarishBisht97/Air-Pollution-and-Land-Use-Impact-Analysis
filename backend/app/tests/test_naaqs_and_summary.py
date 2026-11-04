from app.analytics.summary import compare_to_naaqs, summarize_values
from app.core.naaqs import matching_standard


def test_24h_pm25_matches():
    limit = matching_standard("PM2.5", "24h")
    assert limit is not None
    assert limit.industrial_residential_rural == 60


def test_hourly_not_compared_to_daily():
    result = compare_to_naaqs("PM2.5", "1h", 90, "ug/m3")
    assert result["comparable"] is False


def test_summary_empty():
    stats = summarize_values([])
    assert stats["count"] == 0
    assert stats["missing_percentage"] == 100
