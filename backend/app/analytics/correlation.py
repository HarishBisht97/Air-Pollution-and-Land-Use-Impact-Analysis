from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import stats


def _clean_pairs(x: list[float], y: list[float]) -> tuple[np.ndarray, np.ndarray]:
    pairs = [(float(a), float(b)) for a, b in zip(x, y, strict=False) if a is not None and b is not None]
    if not pairs:
        return np.array([]), np.array([])
    arr = np.array(pairs, dtype=float)
    return arr[:, 0], arr[:, 1]


def pearson_with_ci(x: np.ndarray, y: np.ndarray, alpha: float = 0.05) -> dict[str, Any]:
    n = len(x)
    if n < 3:
        return {"coefficient": None, "p_value": None, "ci_low": None, "ci_high": None, "n": n}
    r, p = stats.pearsonr(x, y)
    if n == 3 or abs(r) >= 1:
        return {"coefficient": float(r), "p_value": float(p), "ci_low": None, "ci_high": None, "n": n}
    # Fisher z confidence interval
    z = np.arctanh(r)
    se = 1 / math.sqrt(n - 3)
    z_crit = stats.norm.ppf(1 - alpha / 2)
    ci = np.tanh([z - z_crit * se, z + z_crit * se])
    return {
        "coefficient": float(r),
        "p_value": float(p),
        "ci_low": float(ci[0]),
        "ci_high": float(ci[1]),
        "n": n,
    }


def spearman_stats(x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    n = len(x)
    if n < 3:
        return {"coefficient": None, "p_value": None, "n": n}
    rho, p = stats.spearmanr(x, y)
    return {"coefficient": float(rho), "p_value": float(p), "n": n}


def correlate(x: list[float], y: list[float], x_name: str, y_name: str) -> dict[str, Any]:
    xa, ya = _clean_pairs(x, y)
    result = {
        "x": x_name,
        "y": y_name,
        "n": int(len(xa)),
        "missing_data_treatment": "pairwise deletion of nulls",
        "pearson": pearson_with_ci(xa, ya),
        "spearman": spearman_stats(xa, ya),
        "data_kind": "statistical_estimate",
        "caveat": (
            "Correlation describes association, not causation. Meteorology, traffic, "
            "topography, and station placement are uncontrolled confounders."
        ),
    }
    return result
