from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import mean_absolute_error, mean_squared_error


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
