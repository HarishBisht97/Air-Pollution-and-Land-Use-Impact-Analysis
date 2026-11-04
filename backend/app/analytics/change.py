from __future__ import annotations

from collections import defaultdict

from app.remote_sensing.worldcover import STUDY_CLASSES


def land_cover_change(
    baseline: dict[str, float],
    recent: dict[str, float],
    *,
    baseline_year: int,
    recent_year: int,
    comparable: bool,
    caveat: str,
) -> dict:
    classes = {}
    for name in STUDY_CLASSES:
        b = float(baseline.get(name, 0.0))
        r = float(recent.get(name, 0.0))
        classes[name] = {
            "baseline_sq_km": b,
            "recent_sq_km": r,
            "change_sq_km": r - b,
            "percentage_point_change": None,
        }
    b_total = sum(item["baseline_sq_km"] for item in classes.values()) or 1.0
    r_total = sum(item["recent_sq_km"] for item in classes.values()) or 1.0
    for name, item in classes.items():
        item["percentage_point_change"] = 100 * item["recent_sq_km"] / r_total - 100 * item["baseline_sq_km"] / b_total
    return {
        "baseline_year": baseline_year,
        "recent_year": recent_year,
        "comparable_classification_scheme": comparable,
        "classes": classes,
        "caveat": caveat,
        "data_kind": "classified",
    }


def transition_matrix(pairs: list[tuple[str, str]]) -> dict:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for before, after in pairs:
        counts[before][after] += 1
    return {a: dict(b) for a, b in counts.items()}
