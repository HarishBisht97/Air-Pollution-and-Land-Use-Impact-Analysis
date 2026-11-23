"""Extend Delhi's mapped built area, and read the city mean AQI off that path.

Built area is fit on the year over every Dynamic World year on hand. The city
mean AQI is fit on built area over the concentration-based index years,
2018–2024, and then evaluated at the projected built area for each target year.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import statsmodels.api as sm

from app.analytics.correlation import pearson_with_ci

MIN_YEARS = 8
MIN_AQI_YEARS = 5
TARGET_YEARS = (2026, 2027, 2028)
COMPARABLE_AQI = "concentration_subindex"


def _finite(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _round(value, digits: int = 1) -> float | None:
    number = _finite(value)
    if number is None:
        return None
    return round(number, digits)


def _fit_line(rows: list[dict], predictor: str, response: str, minimum: int) -> dict[str, Any]:
    frame = pd.DataFrame(rows, columns=[predictor, response]).dropna()
    frame = frame[frame[predictor].map(_finite).notna() & frame[response].map(_finite).notna()]
    n = len(frame)
    if n < minimum:
        return {
            "status": "insufficient_data",
            "n": n,
            "minimum_years": minimum,
            "message": f"{n} years are below the {minimum} years required for this line.",
        }
    y = frame[response].astype(float)
    x = sm.add_constant(frame[predictor].astype(float), has_constant="add")
    model = sm.OLS(y, x).fit()
    return {
        "status": "ok",
        "n": n,
        "minimum_years": minimum,
        "slope": _round(model.params[predictor], 3),
        "p_value": _round(model.pvalues[predictor], 4),
        "r_squared": _round(model.rsquared, 3),
        "intercept": _round(model.params["const"], 2),
        "_model": model,
        "_predictor": predictor,
    }


def _predict(fit: dict[str, Any], values: list[float]) -> pd.DataFrame:
    future = pd.DataFrame({"const": 1.0, fit["_predictor"]: values})
    return fit["_model"].get_prediction(future).summary_frame(alpha=0.05)


def _project(fit: dict[str, Any], years: tuple[int, ...], observed: dict[int, float]) -> list[dict[str, Any]]:
    if fit.get("status") != "ok":
        return []
    summary = _predict(fit, [float(year) for year in years])
    rows = []
    for year, mean, low, high in zip(
        years,
        summary["mean"],
        summary["mean_ci_lower"],
        summary["mean_ci_upper"],
        strict=True,
    ):
        rows.append(
            {
                "year": int(year),
                "value": _round(mean, 1),
                "low": _round(low, 1),
                "high": _round(high, 1),
                "observed": _round(observed.get(int(year)), 1),
            }
        )
    return rows


def _project_aqi(
    fit: dict[str, Any],
    built_projections: list[dict[str, Any]],
    observed: dict[int, float],
    built_range: tuple[float, float] | None,
) -> list[dict[str, Any]]:
    """Evaluate the AQI-on-built line at each projected built area.

    The interval spans the AQI line's 95% band at the low, central, and high
    built-area values, so it carries the uncertainty of both lines.
    """
    if fit.get("status") != "ok":
        return []
    rows = []
    for built in built_projections:
        points = [_finite(built.get(key)) for key in ("low", "value", "high")]
        if any(point is None for point in points):
            continue
        summary = _predict(fit, points)
        central = summary["mean"].iloc[1]
        rows.append(
            {
                "year": int(built["year"]),
                "value": _round(central, 1),
                "low": _round(summary["mean_ci_lower"].min(), 1),
                "high": _round(summary["mean_ci_upper"].max(), 1),
                "built_km2": _round(built["value"], 1),
                "outside_observed_built": bool(
                    built_range and not (built_range[0] <= points[1] <= built_range[1])
                ),
                "observed": _round(observed.get(int(built["year"])), 1),
            }
        )
    return rows


def _public_fit(fit: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in fit.items() if not key.startswith("_")}


def project_builtup_aqi(city_trend: list[dict], targets: tuple[int, ...] = TARGET_YEARS) -> dict[str, Any]:
    """Project built area from the mapped years, then read the city mean AQI at that built area."""
    built_rows = [row for row in city_trend if _finite(row.get("built_km2")) is not None and _finite(row.get("year")) is not None]
    aqi_rows = [
        row
        for row in city_trend
        if row.get("aqi_source") == COMPARABLE_AQI
        and not row.get("partial")
        and _finite(row.get("mean_aqi")) is not None
        and _finite(row.get("built_km2")) is not None
        and _finite(row.get("year")) is not None
    ]
    built_fit = _fit_line(built_rows, "year", "built_km2", MIN_YEARS)
    aqi_fit = _fit_line(aqi_rows, "built_km2", "mean_aqi", MIN_AQI_YEARS)
    built_observed = {int(row["year"]): float(row["built_km2"]) for row in built_rows}
    aqi_observed = {int(row["year"]): float(row["mean_aqi"]) for row in aqi_rows}
    paired_x = [float(row["built_km2"]) for row in aqi_rows]
    paired_y = [float(row["mean_aqi"]) for row in aqi_rows]
    association = pearson_with_ci(pd.Series(paired_x).to_numpy(), pd.Series(paired_y).to_numpy()) if paired_x else {"n": 0}
    built_range = (min(paired_x), max(paired_x)) if paired_x else None
    built_projections = _project(built_fit, targets, built_observed)
    aqi_projections = _project_aqi(aqi_fit, built_projections, aqi_observed, built_range)
    fitted_built = {
        row["year"]: row["value"]
        for row in _project(built_fit, tuple(int(row["year"]) for row in built_rows), built_observed)
    }
    fitted_aqi = (
        [_round(value, 1) for value in _predict(aqi_fit, paired_x)["mean"]]
        if aqi_fit["status"] == "ok"
        else [None] * len(aqi_rows)
    )
    built_public = _public_fit(built_fit)
    if "slope" in built_public:
        built_public["per_year"] = _round(built_public.pop("slope"), 2)
    aqi_public = _public_fit(aqi_fit)
    if "slope" in aqi_public:
        aqi_public["per_km2"] = aqi_public.pop("slope")
    return {
        "status": "ok" if built_fit["status"] == "ok" else "insufficient_data",
        "targets": list(targets),
        "built": {
            **built_public,
            "unit": "km²",
            "years": [int(row["year"]) for row in built_rows],
            "series": [
                {
                    "year": int(row["year"]),
                    "built_km2": _round(row["built_km2"], 1),
                    "fitted": fitted_built.get(int(row["year"])),
                }
                for row in built_rows
            ],
            "projections": built_projections,
            "caveat": (
                "The line is the change in Dynamic World built area inside the Delhi boundary. "
                "The band is the 95% interval for that line. It is not a guarantee of next year's map."
            ),
        },
        "aqi": {
            **aqi_public,
            "source": COMPARABLE_AQI,
            "unit": "AQI",
            "years": [int(row["year"]) for row in aqi_rows],
            "observed_built_range": [_round(value, 1) for value in built_range] if built_range else None,
            "observed": [
                {
                    "year": int(row["year"]),
                    "mean_aqi": _round(row["mean_aqi"], 1),
                    "built_km2": _round(row.get("built_km2"), 1),
                    "fitted": fitted,
                }
                for row, fitted in zip(aqi_rows, fitted_aqi, strict=True)
            ],
            "projections": aqi_projections,
            "association_with_built": {
                "coefficient": _round(association.get("coefficient"), 3),
                "p_value": _round(association.get("p_value"), 4),
                "n": association.get("n", 0),
            },
            "caveat": (
                "The city mean AQI is fit on built area over 2018–2024, the years with the concentration-based annual index, "
                "and read at the projected built area for each year. "
                "2025 and 2026 use CPCB's published hourly index, and 2026 ends on 31 October, so they are not in the fit. "
                "The interval covers the 95% band of both the built-area line and the AQI line. "
                "Weather, emission controls, and stubble burning move the yearly mean too, and are not in this model."
            ),
        },
        "data_kind": "model_prediction" if built_fit["status"] == "ok" else "statistical_estimate",
    }
