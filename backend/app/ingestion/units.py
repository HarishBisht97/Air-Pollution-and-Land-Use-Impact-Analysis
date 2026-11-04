"""Normalize pollutant names and concentration units."""

from __future__ import annotations

POLLUTANT_ALIASES = {
    "pm2.5": "PM2.5",
    "pm25": "PM2.5",
    "pm_2_5": "PM2.5",
    "fine particulate matter": "PM2.5",
    "pm10": "PM10",
    "pm_10": "PM10",
    "no2": "NO2",
    "no₂": "NO2",
    "nitrogen dioxide": "NO2",
    "so2": "SO2",
    "sulphur dioxide": "SO2",
    "sulfur dioxide": "SO2",
    "co": "CO",
    "carbon monoxide": "CO",
    "o3": "O3",
    "ozone": "O3",
}

CANONICAL_UNITS = {
    "PM2.5": "ug/m3",
    "PM10": "ug/m3",
    "NO2": "ug/m3",
    "SO2": "ug/m3",
    "O3": "ug/m3",
    "CO": "mg/m3",
}

UNIT_ALIASES = {
    "ug/m3": "ug/m3",
    "µg/m3": "ug/m3",
    "ug/m³": "ug/m3",
    "µg/m³": "ug/m3",
    "micrograms per cubic meter": "ug/m3",
    "mg/m3": "mg/m3",
    "mg/m³": "mg/m3",
    "ppm": "ppm",
    "ppb": "ppb",
}


class UnitConversionError(ValueError):
    pass


def normalize_pollutant(name: str) -> str:
    key = str(name).strip().lower()
    if key not in POLLUTANT_ALIASES:
        raise UnitConversionError(f"Unsupported pollutant: {name}")
    return POLLUTANT_ALIASES[key]


def normalize_unit_label(unit: str) -> str:
    key = str(unit).strip().lower()
    if key not in UNIT_ALIASES:
        raise UnitConversionError(f"Unsupported unit: {unit}")
    return UNIT_ALIASES[key]


def convert_concentration(pollutant: str, value: float, unit: str) -> tuple[float, str]:
    pollutant = normalize_pollutant(pollutant)
    unit = normalize_unit_label(unit)
    target = CANONICAL_UNITS[pollutant]

    if unit == target:
        return float(value), target

    # Approximate conversions at 25 C, 1 atm for gases only.
    molecular_weights = {"NO2": 46.0055, "SO2": 64.066, "CO": 28.01, "O3": 47.998}
    if pollutant in molecular_weights and unit in {"ppm", "ppb"}:
        mw = molecular_weights[pollutant]
        ppm = value if unit == "ppm" else value / 1000.0
        ug_m3 = ppm * mw * (1000 / 24.45)
        if target == "mg/m3":
            return ug_m3 / 1000.0, target
        return ug_m3, target

    if pollutant in {"PM2.5", "PM10"} and unit in {"ppm", "ppb"}:
        raise UnitConversionError("Particulate matter cannot be converted from ppm/ppb")

    if unit == "ug/m3" and target == "mg/m3":
        return float(value) / 1000.0, target
    if unit == "mg/m3" and target == "ug/m3":
        return float(value) * 1000.0, target

    raise UnitConversionError(f"Cannot convert {pollutant} from {unit} to {target}")


def is_invalid_measurement(value: float | None) -> bool:
    if value is None:
        return True
    if value < 0:
        return True
    if value in {999, 9999, 99999}:
        return True
    return False
