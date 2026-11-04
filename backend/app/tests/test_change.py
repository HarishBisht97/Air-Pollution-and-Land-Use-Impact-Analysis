from app.analytics.change import land_cover_change, transition_matrix


def test_change_reports_area_delta():
    result = land_cover_change(
        {"built_up": 1.0, "tree_cover": 2.0},
        {"built_up": 1.5, "tree_cover": 1.5},
        baseline_year=2020,
        recent_year=2024,
        comparable=False,
        caveat="algorithm change",
    )
    assert result["classes"]["built_up"]["change_sq_km"] == 0.5
    assert result["comparable_classification_scheme"] is False
    assert result["data_kind"] == "classified"


def test_transition_matrix():
    matrix = transition_matrix([("tree_cover", "built_up"), ("tree_cover", "tree_cover")])
    assert matrix["tree_cover"]["built_up"] == 1
