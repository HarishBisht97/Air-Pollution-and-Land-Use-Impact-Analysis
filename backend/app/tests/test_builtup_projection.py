from app.analytics.builtup_projection import project_builtup_aqi


def _trend():
    rows = []
    for offset, year in enumerate(range(2018, 2027)):
        rows.append(
            {
                "year": year,
                "built_km2": 800 + 10 * offset,
                "mean_aqi": 230 - 2 * offset + (4 if offset % 2 else 0),
                "aqi_source": "cpcb_hourly_index" if year >= 2025 else "concentration_subindex",
                "partial": year == 2026,
            }
        )
    return rows


def test_built_area_extends_and_keeps_the_observed_year():
    result = project_builtup_aqi(_trend())
    built = result["built"]
    assert built["status"] == "ok"
    assert built["n"] == 9
    assert built["per_year"] == 10
    by_year = {row["year"]: row for row in built["projections"]}
    assert by_year[2027]["value"] > by_year[2026]["value"]
    assert by_year[2028]["value"] > by_year[2027]["value"]
    assert by_year[2026]["observed"] == 880
    assert by_year[2027]["observed"] is None
    assert by_year[2026]["low"] <= by_year[2026]["value"] <= by_year[2026]["high"]


def test_aqi_is_read_at_the_projected_built_area():
    result = project_builtup_aqi(_trend())
    aqi = result["aqi"]
    assert aqi["status"] == "ok"
    assert aqi["n"] == 7
    assert aqi["years"] == list(range(2018, 2025))
    assert aqi["per_km2"] < 0
    assert aqi["association_with_built"]["n"] == 7
    assert aqi["association_with_built"]["coefficient"] < 0
    built = {row["year"]: row["value"] for row in result["built"]["projections"]}
    projections = aqi["projections"]
    assert [row["year"] for row in projections] == [2026, 2027, 2028]
    for row in projections:
        assert row["built_km2"] == built[row["year"]]
        assert row["low"] <= row["value"] <= row["high"]
        assert row["outside_observed_built"]
    assert projections[2]["value"] < projections[0]["value"]


def test_hourly_index_years_do_not_enter_the_aqi_line():
    rows = _trend()
    for row in rows:
        if row["year"] >= 2025:
            row["aqi_source"] = "concentration_subindex"
            row["partial"] = False
    result = project_builtup_aqi(rows)
    assert result["aqi"]["n"] == 9
    assert result["aqi"]["projections"][0]["observed"] is not None


def test_too_few_comparable_years_withhold_the_aqi():
    rows = [row for row in _trend() if row["year"] >= 2022]
    result = project_builtup_aqi(rows)
    assert result["aqi"]["status"] == "insufficient_data"
    assert result["aqi"]["projections"] == []
