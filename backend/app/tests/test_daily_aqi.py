import pytest

from app.analytics.daily_aqi import annual_from_daily, daily_station_aqi, station_day_aqi, sub_index


@pytest.mark.parametrize(
    ("pollutant", "concentration", "expected"),
    [
        ("PM2.5", 0, 0),
        ("PM2.5", 30, 50),
        ("PM2.5", 60, 100),
        ("PM2.5", 75, 150),
        ("PM2.5", 250, 400),
        ("PM2.5", 900, 500),
        ("PM10", 100, 100),
        ("NO2", 180, 200),
        ("SO2", 80, 100),
        ("NH3", 400, 100),
        ("PM2.5", -5, 0),
    ],
)
def test_sub_index_breakpoints(pollutant, concentration, expected):
    assert sub_index(pollutant, concentration) == pytest.approx(expected)


def test_station_day_needs_three_pollutants_with_pm():
    assert station_day_aqi({"PM2.5": 120, "NO2": 80}) is None
    assert station_day_aqi({"NO2": 80, "SO2": 40, "NH3": 30}) is None
    assert station_day_aqi({"PM10": 150, "NO2": 80, "SO2": 40}) == 150


def test_daily_aqi_takes_the_highest_sub_index():
    rows = {
        "PM2.5": [{"station_id": "a", "day": "2024-01-01", "mean": 75.0}],
        "NO2": [{"station_id": "a", "day": "2024-01-01", "mean": 40.0}],
        "SO2": [{"station_id": "a", "day": "2024-01-01", "mean": 10.0}],
        "PM10": [{"station_id": "b", "day": "2024-01-01", "mean": 100.0}],
    }
    daily = daily_station_aqi(rows)
    assert daily == {"a": {"2024-01-01": pytest.approx(150)}}


def test_annual_aqi_drops_stations_with_too_few_days():
    daily = {
        "full": {f"d{i}": 250.0 if i % 2 else 150.0 for i in range(200)},
        "short": {f"d{i}": 100.0 for i in range(50)},
    }
    annual = annual_from_daily(daily, min_days=180)
    assert set(annual) == {"full"}
    assert annual["full"]["aqi"] == 200.0
    assert annual["full"]["days"] == 200
    assert annual["full"]["poor_or_worse_days"] == 100
    assert annual["full"]["category"] == "Moderate"
