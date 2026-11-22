from app.analytics.builtup_concentration_change import annual_station_means, fit_concentration_change


def test_annual_mean_requires_six_months_and_weights_by_hours():
    rows = []
    for month in range(1, 7):
        hours = 400 if month == 1 else 300
        rows.append(
            {
                "station_id": "s1",
                "period_start": f"2018-{month:02d}-01",
                "mean": 10.0 if month == 1 else 20.0,
                "n": hours,
            }
        )
    rows.append({"station_id": "s2", "period_start": "2018-01-01", "mean": 50.0, "n": 400})
    means = annual_station_means(rows, 2018)
    assert "s2" not in means
    expected = (10 * 400 + 20 * 300 * 5) / (400 + 300 * 5)
    assert abs(means["s1"] - expected) < 0.01


def test_concentration_change_recovers_slope():
    rows = []
    for index in range(10):
        change = float(index)
        rows.append(
            {
                "name": f"S{index}",
                "built_up_change": change,
                "concentration_change": -5.0 + 2.0 * change,
            }
        )
    result = fit_concentration_change(rows, pollutant="PM2.5", unit="ug/m3")
    assert result["status"] == "ok"
    assert abs(result["params"]["built_up_change"] - 2.0) < 0.01
    assert abs(result["pearson"]["coefficient"] - 1.0) < 0.01
    assert len(result["points"]) == 10
    assert abs(result["points"][0]["fitted_change"] - result["points"][0]["concentration_change"]) < 0.01


def test_concentration_change_refuses_a_short_sample():
    rows = [{"name": "S", "built_up_change": 1.0, "concentration_change": 1.0} for _ in range(5)]
    result = fit_concentration_change(rows, pollutant="NO2", unit="ug/m3")
    assert result["status"] == "insufficient_data"
