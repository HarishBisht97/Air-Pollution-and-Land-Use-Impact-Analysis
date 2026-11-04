from __future__ import annotations

from typing import Any


def station_zscore_hotspots(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Hotspots from station means. Not a continuous surface and not Getis-Ord Gi*."""
    values = [float(row["mean"]) for row in records]
    n = len(values)
    if n < 2:
        return {
            "status": "insufficient_data",
            "n_stations": n,
            "message": "Need at least two station means to compute z-scores.",
            "data_kind": "statistical_estimate",
            "features": [],
        }
    mu = sum(values) / n
    variance = sum((value - mu) ** 2 for value in values) / (n - 1)
    sigma = variance**0.5
    features = []
    for row in records:
        z = 0.0 if sigma == 0 else (float(row["mean"]) - mu) / sigma
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
                "properties": {
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "mean": row["mean"],
                    "n": row.get("n"),
                    "z_score": z,
                    "hotspot": z >= 1.0,
                    "data_kind": "statistical_estimate",
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "features": features,
        "status": "ok",
        "method": "station_z_score",
        "n_stations": n,
        "n_hotspots": sum(1 for feature in features if feature["properties"]["hotspot"]),
        "note": "Hotspots are z-scores of station means. Not interpolated and not Getis-Ord Gi*.",
        "data_kind": "statistical_estimate",
    }


def require_station_threshold(n_stations: int, minimum: int) -> dict[str, Any] | None:
    if n_stations < minimum:
        return {
            "status": "refused",
            "n_stations": n_stations,
            "minimum": minimum,
            "message": (
                "Pollution hotspot / spatial-cluster maps are disabled because the number of "
                "monitoring stations is below the configured threshold. Interpolating a continuous "
                "pollution surface from sparse stations would be presented as measured data."
            ),
            "data_kind": "statistical_estimate",
        }
    return None


def morans_i_from_values(values: list[float], weights: list[list[float]]) -> dict[str, Any]:
    try:
        from esda.moran import Moran
        from libpysal.weights import W
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("libpysal/esda are required for spatial autocorrelation") from exc

    w = W.from_adjacency_list(
        [(i, j, weights[i][j]) for i in range(len(weights)) for j in range(len(weights[i])) if weights[i][j] and i != j]
    )
    w.transform = "r"
    moran = Moran(values, w)
    return {
        "I": float(moran.I),
        "p_norm": float(moran.p_norm),
        "z_norm": float(moran.z_norm),
        "expected_I": float(moran.EI),
        "n": len(values),
        "data_kind": "statistical_estimate",
        "weights": "row-standardized adjacency",
        "multiple_testing_note": "Local indicators require FDR or Bonferroni adjustment before mapping significance.",
    }
