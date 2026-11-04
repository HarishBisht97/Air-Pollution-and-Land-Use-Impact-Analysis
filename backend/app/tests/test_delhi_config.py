from app.core.config import get_settings
from app.core.study_area import default_study_area, load_city_config
from app.ingestion.sample_observations import sample_concentration
from app.analytics.esda import require_station_threshold, station_zscore_hotspots


def test_default_city_is_delhi():
    assert get_settings().default_city_slug == "delhi"
    area = default_study_area()
    assert area.slug == "delhi"
    assert area.projected_srid == 32643
    assert area.grid_resolution_m == 1000
    assert area.date_start == "2000-01-01"
    assert area.date_end == "2026-12-31"


def test_delhi_has_twelve_listed_stations():
    area = load_city_config("delhi")
    stations = area.data["stations"]
    assert len(stations) >= 12
    ids = {row["external_station_id"] for row in stations}
    assert "site_301" in ids
    assert "site_113" in ids


def test_sample_concentrations_are_seasonal():
    winter = sample_concentration("PM2.5", 2024, 12, 1.0)
    monsoon = sample_concentration("PM2.5", 2024, 7, 1.0)
    assert winter > monsoon
    traffic = sample_concentration("PM2.5", 2024, 1, 1.22)
    ridge = sample_concentration("PM2.5", 2024, 1, 0.82)
    assert traffic > ridge


def test_hotspots_allowed_for_dense_station_means():
    assert require_station_threshold(12, 8) is None
    result = station_zscore_hotspots(
        [
            {"id": "a", "name": "A", "lon": 77.1, "lat": 28.6, "mean": 80, "n": 10},
            {"id": "b", "name": "B", "lon": 77.2, "lat": 28.7, "mean": 90, "n": 10},
            {"id": "c", "name": "C", "lon": 77.3, "lat": 28.5, "mean": 140, "n": 10},
        ]
    )
    assert result["status"] == "ok"
    assert result["data_kind"] == "statistical_estimate"
    assert any(feature["properties"]["hotspot"] for feature in result["features"])
