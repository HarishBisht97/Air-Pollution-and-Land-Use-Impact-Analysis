from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import mean, median, pstdev

from app.core.naaqs import matching_standard


def summarize_values(values: list[float]) -> dict:
    valid = [float(v) for v in values if v is not None]
    if not valid:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "std": None,
            "missing_percentage": 100.0,
        }
    return {
        "count": len(valid),
        "mean": mean(valid),
        "median": median(valid),
        "min": min(valid),
        "max": max(valid),
        "std": pstdev(valid) if len(valid) > 1 else 0.0,
        "missing_percentage": 0.0,
    }


def compare_to_naaqs(pollutant: str, averaging_period: str, mean_value: float | None, unit: str) -> dict:
    standard = matching_standard(pollutant, averaging_period)
    if standard is None:
        return {
            "comparable": False,
            "reason": (
                f"Averaging period '{averaging_period}' does not match a NAAQS time-weighted average "
                f"for {pollutant}. A mismatch (for example a 1-hour reading vs a 24-hour standard) "
                "is not compared."
            ),
        }
    if mean_value is None:
        return {"comparable": False, "reason": "No valid mean to compare."}
    if unit != standard.unit:
        return {"comparable": False, "reason": f"Unit {unit} does not match standard unit {standard.unit}."}
    return {
        "comparable": True,
        "averaging_period": standard.averaging_period,
        "limit": standard.industrial_residential_rural,
        "unit": standard.unit,
        "exceeds": mean_value > standard.industrial_residential_rural,
        "source": standard.source,
        "data_kind": "aggregated",
    }


def aggregate_by_period(records: list[dict], interval: str) -> list[dict]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for record in records:
        observed_at: datetime = record["observed_at"]
        if interval == "daily":
            key = observed_at.date().isoformat()
        elif interval == "weekly":
            key = f"{observed_at.isocalendar().year}-W{observed_at.isocalendar().week:02d}"
        elif interval == "monthly":
            key = observed_at.strftime("%Y-%m")
        else:
            key = observed_at.isoformat()
        buckets[key].append(float(record["concentration"]))
    return [{"period": period, **summarize_values(vals), "data_kind": "aggregated"} for period, vals in sorted(buckets.items())]
