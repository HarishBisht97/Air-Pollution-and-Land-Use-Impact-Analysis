from app.analytics.delhi_land_use import tercile_contrast


def test_tercile_contrast_compares_high_and_low_thirds():
    stations = [{"built": index, "PM2.5": 10 + index} for index in range(9)]
    result = tercile_contrast(stations, "built", "PM2.5")
    assert result["status"] == "ok"
    assert result["n_each"] == 3
    assert result["low_mean"] == 11.0
    assert result["high_mean"] == 17.0
    assert result["percent_difference"] == round(100 * (17 - 11) / 11, 1)


def test_tercile_contrast_refuses_a_short_sample():
    stations = [{"crops": index, "NO2": index} for index in range(5)]
    result = tercile_contrast(stations, "crops", "NO2")
    assert result["status"] == "insufficient_data"
