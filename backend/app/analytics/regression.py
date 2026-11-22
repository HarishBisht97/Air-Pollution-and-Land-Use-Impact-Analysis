from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import mean_absolute_error, mean_squared_error

from app.analytics.correlation import correlate
from app.ingestion.cpcb_snapshot import aqi_category

BUILTUP_AQI_CAVEAT = (
    "The slope is an observational association from the 22 November 2026 CPCB snapshot. "
    "AQI values for 2017–2025 apply that slope to each year's built-up share; they are not measured AQI. "
    "Weather is not controlled, and the coefficient is not a causal effect."
)


def fit_ols(frame: pd.DataFrame, response: str, predictors: list[str]) -> dict[str, Any]:
    clean = frame[[response, *predictors]].dropna()
    n = len(clean)
    if n < max(8, len(predictors) + 3):
        return {
            "status": "insufficient_data",
            "n": n,
            "message": "Not enough complete rows for a stable regression.",
            "data_kind": "statistical_estimate",
        }
    y = clean[response]
    x = sm.add_constant(clean[predictors])
    model = sm.OLS(y, x).fit()
    fitted = model.fittedvalues
    rmse = float(np.sqrt(mean_squared_error(y, fitted)))
    mae = float(mean_absolute_error(y, fitted))
    vif = {}
    for i, name in enumerate(x.columns):
        if name == "const":
            continue
        others = x.drop(columns=[name])
        r2 = sm.OLS(x[name], others).fit().rsquared
        vif[name] = float(1 / (1 - r2)) if r2 < 1 else float("inf")
    return {
        "status": "ok",
        "n": n,
        "response": response,
        "predictors": predictors,
        "params": {k: float(v) for k, v in model.params.items()},
        "pvalues": {k: float(v) for k, v in model.pvalues.items()},
        "conf_int": {
            k: [float(low), float(high)] for k, (low, high) in model.conf_int().iterrows()
        },
        "r_squared": float(model.rsquared),
        "adj_r_squared": float(model.rsquared_adj),
        "rmse": rmse,
        "mae": mae,
        "vif": vif,
        "residuals_summary": {
            "mean": float(model.resid.mean()),
            "std": float(model.resid.std()),
        },
        "weather_controlled": False,
        "caveat": (
            "This is an observational association model. It does not control for meteorology "
            "unless weather predictors are supplied. Coefficients are not causal effects."
        ),
        "data_kind": "statistical_estimate",
    }


def _built_up_by_year(raw: dict[Any, Any]) -> dict[int, float]:
    parsed: dict[int, float] = {}
    for key, value in raw.items():
        if value is None:
            continue
        parsed[int(key)] = float(value)
    return parsed


def builtup_aqi_effect(stations: list[dict[str, Any]], *, observed_year: int = 2026) -> dict[str, Any]:
    """Fit station AQI on built-up share and apply that slope to every year."""
    rows: list[dict[str, Any]] = []
    for station in stations:
        aqi = station.get("aqi")
        built = _built_up_by_year(station.get("built_up") or {})
        if aqi is None or observed_year not in built:
            continue
        rows.append(
            {
                "name": station.get("name") or "",
                "longitude": float(station["longitude"]),
                "latitude": float(station["latitude"]),
                "aqi": float(aqi),
                "built_up": built,
            }
        )
    frame = pd.DataFrame(
        [{"aqi": row["aqi"], "built_up_2026": row["built_up"][observed_year]} for row in rows]
    )
    fit = fit_ols(frame, "aqi", ["built_up_2026"]) if not frame.empty else {
        "status": "insufficient_data",
        "n": 0,
        "message": "Not enough complete rows for a stable regression.",
        "data_kind": "statistical_estimate",
    }
    fit["caveat"] = BUILTUP_AQI_CAVEAT
    fit["observed_year"] = observed_year
    if fit["status"] != "ok":
        return fit

    intercept = fit["params"]["const"]
    slope = fit["params"]["built_up_2026"]
    fit["aqi_per_10_built_up_points"] = slope * 10.0
    station_payload = []
    for row in rows:
        implied = {str(year): intercept + slope * share for year, share in sorted(row["built_up"].items())}
        fitted = implied[str(observed_year)]
        station_payload.append(
            {
                "name": row["name"],
                "longitude": row["longitude"],
                "latitude": row["latitude"],
                "observed_aqi": row["aqi"],
                "observed_category": aqi_category(row["aqi"]),
                "built_up": {str(year): share for year, share in sorted(row["built_up"].items())},
                "implied_aqi": implied,
                "implied_category": {year: aqi_category(value) for year, value in implied.items()},
                "fitted_aqi": fitted,
                "residual": row["aqi"] - fitted,
            }
        )
    year_rows = []
    years = sorted({year for row in rows for year in row["built_up"]})
    for year in years:
        shares = [row["built_up"][year] for row in rows if year in row["built_up"]]
        implied_values = [intercept + slope * share for share in shares]
        mean_implied = float(np.mean(implied_values))
        year_rows.append(
            {
                "year": year,
                "mean_built_up": float(np.mean(shares)),
                "mean_implied_aqi": mean_implied,
                "mean_implied_category": aqi_category(mean_implied),
                "observed_year": year == observed_year,
                "estimate": year != observed_year,
            }
        )
    fit["years"] = year_rows
    fit["stations"] = station_payload
    fit["built_up_change"] = _aqi_on_built_up_change(rows, baseline_year=2017, observed_year=observed_year)
    return fit


def _aqi_on_built_up_change(rows: list[dict[str, Any]], *, baseline_year: int, observed_year: int) -> dict[str, Any]:
    """Associate the 2026 AQI with how much built-up share grew since the baseline year."""
    usable = []
    for row in rows:
        if baseline_year not in row["built_up"] or observed_year not in row["built_up"]:
            continue
        usable.append(
            {
                "name": row["name"],
                "built_up_change": row["built_up"][observed_year] - row["built_up"][baseline_year],
                "aqi": row["aqi"],
            }
        )
    empty = {
        "status": "insufficient_data",
        "baseline_year": baseline_year,
        "observed_year": observed_year,
        "n": len(usable),
        "points": usable,
        "message": "Not enough stations with built-up in both years.",
        "data_kind": "statistical_estimate",
    }
    if len(usable) < 8 or len({point["built_up_change"] for point in usable}) < 2:
        return empty
    frame = pd.DataFrame(usable)
    fit = fit_ols(frame, "aqi", ["built_up_change"])
    paired = correlate(
        frame["built_up_change"].tolist(),
        frame["aqi"].tolist(),
        "built_up_change",
        "aqi",
    )
    intercept = fit.get("params", {}).get("const")
    slope = fit.get("params", {}).get("built_up_change")
    points = []
    for point in usable:
        fitted = None if intercept is None or slope is None else intercept + slope * point["built_up_change"]
        points.append({**point, "fitted_aqi": fitted})
    return {
        "status": fit["status"],
        "baseline_year": baseline_year,
        "observed_year": observed_year,
        "n": fit.get("n", len(usable)),
        "params": fit.get("params"),
        "pvalues": fit.get("pvalues"),
        "r_squared": fit.get("r_squared"),
        "pearson": paired["pearson"],
        "points": points,
        "caveat": (
            f"The vertical axis is the measured AQI on 22 November {observed_year}. "
            f"The horizontal axis is the change in built-up share from {baseline_year} to {observed_year}. "
            "This is an association between how much a place built up and how high its 2026 index is. "
            "It is not a measured decline in AQI, and weather is not controlled."
        ),
        "data_kind": "statistical_estimate",
    }
