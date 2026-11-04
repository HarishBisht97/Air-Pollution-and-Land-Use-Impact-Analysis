import pandas as pd

from app.analytics.correlation import correlate
from app.analytics.esda import require_station_threshold
from app.analytics.priority import score_cell
from app.analytics.regression import fit_ols


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
