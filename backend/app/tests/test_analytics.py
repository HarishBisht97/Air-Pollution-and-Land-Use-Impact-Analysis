import pandas as pd

from app.analytics.correlation import correlate
from app.analytics.esda import require_station_threshold
from app.analytics.priority import score_cell
from app.analytics.regression import builtup_aqi_effect, fit_ols


def test_correlation_reports_n_and_p():
    x = list(range(10))
    y = [2 * v + 0.1 for v in x]
    result = correlate(x, y, "ndvi", "pm")
    assert result["n"] == 10
    assert result["pearson"]["p_value"] < 0.05
    assert result["data_kind"] == "statistical_estimate"


def test_hotspots_refused_when_sparse():
    refused = require_station_threshold(1, 8)
    assert refused is not None
    assert refused["status"] == "refused"


def test_priority_does_not_mark_unobserved_as_safe():
    scored = score_cell(
        {
            "observation_count": 0,
            "mean_concentration": None,
            "built_up_percentage": 80,
            "road_density_km_per_km2": 10,
            "vegetation_percentage": 5,
        }
    )
    assert scored["severity"] is None
    assert scored["confidence"] == 0
    assert scored["data_kind"] == "screening_score"


def test_regression_insufficient_rows():
    frame = pd.DataFrame({"y": [1, 2], "x": [3, 4]})
    result = fit_ols(frame, "y", ["x"])
    assert result["status"] == "insufficient_data"


def _stations(n: int) -> list[dict]:
    rows = []
    for index in range(n):
        built_2026 = 20.0 + index * 7.0
        rows.append(
            {
                "name": f"Station {index}",
                "longitude": 77.0 + index * 0.01,
                "latitude": 28.5,
                "aqi": 40.0 + 2.0 * built_2026,
                "built_up": {2017: built_2026 - 10.0, 2026: built_2026},
            }
        )
    return rows


def test_builtup_aqi_recovers_slope_and_projects_earlier_year():
    result = builtup_aqi_effect(_stations(10))
    assert result["status"] == "ok"
    assert abs(result["params"]["built_up_2026"] - 2.0) < 0.01
    station = result["stations"][0]
    intercept = result["params"]["const"]
    slope = result["params"]["built_up_2026"]
    expected = intercept + slope * station["built_up"]["2017"]
    assert abs(station["implied_aqi"]["2017"] - expected) < 0.01
    assert result["years"][0]["estimate"] is True
    assert result["years"][-1]["observed_year"] is True


def test_aqi_on_built_up_change_recovers_slope():
    rows = []
    for index in range(10):
        change = float(index)
        rows.append(
            {
                "name": f"S{index}",
                "longitude": 77.0,
                "latitude": 28.5,
                "aqi": 100.0 + 3.0 * change,
                "built_up": {2017: 30.0, 2026: 30.0 + change},
            }
        )
    result = builtup_aqi_effect(rows)
    change = result["built_up_change"]
    assert change["status"] == "ok"
    assert abs(change["params"]["built_up_change"] - 3.0) < 0.01
    assert abs(change["pearson"]["coefficient"] - 1.0) < 0.01
    assert len(change["points"]) == 10


def test_builtup_aqi_requires_eight_stations():
    result = builtup_aqi_effect(_stations(7))
    assert result["status"] == "insufficient_data"
    assert result["n"] == 7
