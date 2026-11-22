from app.analytics.builtup_aqi_years import change_classes, change_samples, city_trend_row, year_statistics


def _rows():
    return [{"built": 20.0 + 6 * i, "aqi": 180.0 + 3 * i + (4 if i % 2 else -4)} for i in range(12)]


def test_year_statistics_reports_gap_and_slope():
    stats = year_statistics(_rows())
    assert stats["status"] == "ok"
    assert stats["n"] == 12
    assert stats["n_each"] == 4
    assert stats["pearson_r"] > 0.9
    assert stats["aqi_per_10_points"] > 0
    assert stats["most_built_aqi"] > stats["least_built_aqi"]
    assert stats["gap"] == round(stats["most_built_aqi"] - stats["least_built_aqi"], 1)


def test_year_statistics_refuses_small_samples():
    stats = year_statistics(_rows()[:6])
    assert stats["status"] == "insufficient_data"
    assert stats["gap"] is None


def test_change_samples_need_both_years():
    features = [
        {"geometry": {"coordinates": [77.1, 28.6]}, "properties": {"years": {"2018": {"aqi": 240.0}, "2024": {"aqi": 210.5}}}},
        {"geometry": {"coordinates": [77.2, 28.7]}, "properties": {"years": {"2024": {"aqi": 230.0}}}},
    ]
    assert change_samples(features, 2018, 2024) == [(77.1, 28.6, -29.5)]


def test_change_classes_have_a_zero_line():
    classes = change_classes()
    assert 0.0 in classes["line_levels"]
    assert classes["line_levels"] == [-40.0, -20.0, 0.0, 20.0, 40.0]


def test_city_trend_row_averages_stations():
    annual = {
        "a": {"aqi": 200.0, "days": 300, "poor_or_worse_days": 150},
        "b": {"aqi": 240.0, "days": 100, "poor_or_worse_days": 70},
    }
    row = city_trend_row(2020, annual, 1234.567)
    assert row == {"year": 2020, "built_km2": 1234.6, "mean_aqi": 220.0, "stations": 2, "poor_or_worse_share": 55.0}
