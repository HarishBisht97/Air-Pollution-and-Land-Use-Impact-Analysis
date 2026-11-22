from app.ingestion.cpcb_snapshot import aqi_category, stations_from_records


def test_snapshot_uses_subindex_not_concentration():
    features = stations_from_records(
        [
            {
                "station": "Anand Vihar, Delhi - DPCC",
                "latitude": "28.65",
                "longitude": "77.31",
                "pollutant_id": "PM2.5",
                "avg_value": "259",
                "last_update": "22-11-2026 02:00:00",
            },
            {
                "station": "Anand Vihar, Delhi - DPCC",
                "latitude": "28.65",
                "longitude": "77.31",
                "pollutant_id": "PM10",
                "avg_value": "238",
                "last_update": "22-11-2026 02:00:00",
            },
            {
                "station": "Anand Vihar, Delhi - DPCC",
                "latitude": "28.65",
                "longitude": "77.31",
                "pollutant_id": "CO",
                "avg_value": "42",
                "last_update": "22-11-2026 02:00:00",
            },
            {
                "station": "Anand Vihar, Delhi - DPCC",
                "latitude": "28.65",
                "longitude": "77.31",
                "pollutant_id": "PM2.5",
                "avg_value": "259",
                "last_update": "22-11-2026 02:00:00",
            },
        ]
    )
    assert len(features) == 1
    props = features[0]["properties"]
    assert props["aqi"] == 259
    assert props["category"] == "Poor"
    assert props["responsible_pollutant"] == "PM2.5"
    assert props["value_kind"] == "aqi_subindex"
    assert props["subindices"]["CO"] == 42
    assert aqi_category(42) == "Good"
