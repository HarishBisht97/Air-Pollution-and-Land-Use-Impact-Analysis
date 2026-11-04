from __future__ import annotations

from typing import Any


DEFAULT_WEIGHTS = {
    "pollution_severity": 0.35,
    "built_up": 0.20,
    "road_density": 0.15,
    "vegetation_deficit": 0.15,
    "evidence_confidence": 0.15,
}


def _norm(value: float | None, lo: float, hi: float) -> float:
    if value is None:
        return 0.0
    if hi == lo:
        return 0.0
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def score_cell(row: dict[str, Any], weights: dict[str, float] | None = None) -> dict[str, Any]:
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    obs = int(row.get("observation_count") or 0)
    severity = _norm(row.get("mean_concentration"), 0, 150) if obs > 0 else None
    built = _norm(row.get("built_up_percentage"), 0, 100)
    roads = _norm(row.get("road_density_km_per_km2"), 0, 20)
    veg = 1 - _norm(row.get("vegetation_percentage"), 0, 100)
    confidence = 0.0 if obs == 0 else min(1.0, obs / 30)

    components = {
        "pollution_severity": severity,
        "built_up": built,
        "road_density": roads,
        "vegetation_deficit": veg,
        "evidence_confidence": confidence,
    }
    # Screening priority uses only known components; missing severity does not imply safety.
    screening = 0.0
    weight_sum = 0.0
    for key, weight in weights.items():
        value = components[key]
        if value is None:
            continue
        screening += weight * value
        weight_sum += weight
    screening = screening / weight_sum if weight_sum else 0.0
    return {
        "severity": severity,
        "confidence": confidence,
        "screening_priority": screening,
        "components": components,
        "weights": weights,
        "observation_count": obs,
        "data_kind": "screening_score",
        "note": (
            "Screening and planning-support index only. Not a validated health-risk assessment. "
            "Cells without observations are not ranked as safe."
        ),
    }
