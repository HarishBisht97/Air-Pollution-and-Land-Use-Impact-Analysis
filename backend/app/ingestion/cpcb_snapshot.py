"""Read the data.gov.in CPCB real-time snapshot saved under data/raw.

The feed publishes National Air Quality Index sub-indices, not concentrations.
"""

from __future__ import annotations

import json
from pathlib import Path

POLLUTANT_NAMES = {
    "PM2.5": "PM2.5",
    "PM10": "PM10",
    "NO2": "NO2",
    "SO2": "SO2",
    "CO": "CO",
    "OZONE": "O3",
    "O3": "O3",
    "NH3": "NH3",
}

AQI_POLLUTANTS = ("PM2.5", "PM10", "NO2", "SO2", "CO", "O3", "NH3")


def aqi_category(aqi: float) -> str:
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Satisfactory"
    if aqi <= 200:
        return "Moderate"
    if aqi <= 300:
        return "Poor"
    if aqi <= 400:
        return "Very Poor"
    return "Severe"


def _number(value: object) -> float | None:
    text = str(value or "").strip()
    if text in {"", "NA", "None", "null"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def stations_from_records(records: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for record in records:
        name = " ".join(str(record.get("station") or "").split())
        lat = _number(record.get("latitude"))
        lon = _number(record.get("longitude"))
        pollutant = POLLUTANT_NAMES.get(str(record.get("pollutant_id") or "").strip().upper())
        value = _number(record.get("avg_value"))
        if not name or lat is None or lon is None or pollutant is None or value is None:
            continue
        station = grouped.setdefault(
            name,
            {
                "name": name,
                "latitude": lat,
                "longitude": lon,
                "observed_at": str(record.get("last_update") or "").strip(),
                "subindices": {},
            },
        )
        station["subindices"].setdefault(pollutant, value)

    features = []
    for station in grouped.values():
        used = {name: station["subindices"][name] for name in AQI_POLLUTANTS if name in station["subindices"]}
        has_pm = "PM2.5" in used or "PM10" in used
        aqi = max(used.values()) if has_pm and len(used) >= 3 else None
        responsible = max(used, key=used.get) if aqi is not None else None
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [station["longitude"], station["latitude"]]},
                "properties": {
                    "name": station["name"],
                    "observed_at": station["observed_at"],
                    "subindices": used,
                    "aqi": aqi,
                    "category": aqi_category(aqi) if aqi is not None else None,
                    "responsible_pollutant": responsible,
                    "source": "CPCB via data.gov.in",
                    "value_kind": "aqi_subindex",
                    "data_kind": "aggregated",
                },
            }
        )
    features.sort(key=lambda feature: feature["properties"]["name"])
    return features


def load_cpcb_snapshot(path: Path) -> dict:
    if not path.exists():
        return {
            "type": "FeatureCollection",
            "features": [],
            "available": False,
            "message": "No CPCB snapshot file is in data/raw.",
            "data_kind": "aggregated",
        }
    records = json.loads(path.read_text())
    features = stations_from_records(records)
    observed = next((feature["properties"]["observed_at"] for feature in features if feature["properties"]["observed_at"]), None)
    return {
        "type": "FeatureCollection",
        "features": features,
        "available": True,
        "observed_at": observed,
        "station_count": len(features),
        "source": "CPCB via data.gov.in",
        "note": (
            "Marker values are CPCB National Air Quality Index sub-indices for the latest hour "
            "in the open-data feed. They are not concentrations in µg/m³ or mg/m³."
        ),
        "data_kind": "aggregated",
    }
