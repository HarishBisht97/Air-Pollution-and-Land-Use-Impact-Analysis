"""Indian National Ambient Air Quality Standards (CPCB, 18 November 2009).

Comparisons are only valid when the observation averaging period matches
the standard's time-weighted average. A 1-hour reading is never compared
to a 24-hour standard.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class NAAQSLimit:
    pollutant: str
    averaging_period: str
    unit: str
    industrial_residential_rural: float
    ecologically_sensitive: float
    source: str = "CPCB Notification, 18 November 2009"


NAAQS_LIMITS: list[NAAQSLimit] = [
    NAAQSLimit("SO2", "annual", "ug/m3", 50, 20),
    NAAQSLimit("SO2", "24h", "ug/m3", 80, 80),
    NAAQSLimit("NO2", "annual", "ug/m3", 40, 30),
    NAAQSLimit("NO2", "24h", "ug/m3", 80, 80),
    NAAQSLimit("PM10", "annual", "ug/m3", 60, 60),
    NAAQSLimit("PM10", "24h", "ug/m3", 100, 100),
    NAAQSLimit("PM2.5", "annual", "ug/m3", 40, 40),
    NAAQSLimit("PM2.5", "24h", "ug/m3", 60, 60),
    NAAQSLimit("O3", "8h", "ug/m3", 100, 100),
    NAAQSLimit("O3", "1h", "ug/m3", 180, 180),
    NAAQSLimit("CO", "8h", "mg/m3", 2, 2),
    NAAQSLimit("CO", "1h", "mg/m3", 4, 4),
]

COMPATIBLE_PERIODS = {
    "1h": {"1h"},
    "8h": {"8h"},
    "24h": {"24h", "daily"},
    "daily": {"24h", "daily"},
    "weekly": set(),
    "monthly": set(),
    "annual": {"annual", "yearly"},
    "yearly": {"annual", "yearly"},
}


def matching_standard(pollutant: str, averaging_period: str) -> NAAQSLimit | None:
    normalized = averaging_period.lower().replace("-", "").replace("_", "")
    aliases = {
        "24hour": "24h",
        "24hours": "24h",
        "1hour": "1h",
        "8hour": "8h",
        "8hours": "8h",
        "year": "annual",
    }
    period = aliases.get(normalized, averaging_period.lower())
    for limit in NAAQS_LIMITS:
        if limit.pollutant.upper() == pollutant.upper() and period in COMPATIBLE_PERIODS.get(
            limit.averaging_period, {limit.averaging_period}
        ):
            return limit
        if limit.pollutant.upper() == pollutant.upper() and period == limit.averaging_period:
            return limit
    return None


def naaqs_payload() -> list[dict]:
    return [
        {
            "pollutant": item.pollutant,
            "averaging_period": item.averaging_period,
            "unit": item.unit,
            "industrial_residential_rural": item.industrial_residential_rural,
            "ecologically_sensitive": item.ecologically_sensitive,
            "source": item.source,
            "data_kind": "observed",
            "note": "Compare only when the observation averaging period matches this standard.",
        }
        for item in NAAQS_LIMITS
    ]
