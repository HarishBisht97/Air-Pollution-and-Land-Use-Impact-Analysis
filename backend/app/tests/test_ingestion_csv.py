from app.ingestion.air_quality_csv import _map_row


def test_column_aliases():
    mapping = _map_row(["site_id", "parameter", "value", "datetime", "unit"])
    assert mapping["station_id"] == "site_id"
    assert mapping["pollutant"] == "parameter"
    assert mapping["concentration"] == "value"


def test_missing_required_columns():
    try:
        _map_row(["hello"])
        raise AssertionError("should have failed")
    except ValueError as exc:
        assert "station_id" in str(exc)
