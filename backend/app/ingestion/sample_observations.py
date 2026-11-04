"""Generate labeled SAMPLE monthly observations. Not official CPCB measurements."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.timestamps import parse_observation_timestamp
from app.models.pollution import MonitoringStation, PollutionObservation

MONTH_FACTOR = {
    1: 1.45,
    2: 1.28,
    3: 1.08,
    4: 0.95,
    5: 0.88,
    6: 0.70,
    7: 0.52,
    8: 0.55,
    9: 0.72,
    10: 1.05,
    11: 1.32,
    12: 1.48,
}

BASE = {
    "PM2.5": ("ug/m3", 92.0),
    "PM10": ("ug/m3", 168.0),
    "NO2": ("ug/m3", 48.0),
    "SO2": ("ug/m3", 11.0),
    "CO": ("mg/m3", 1.15),
    "O3": ("ug/m3", 42.0),
}

O3_MONTH = {
    1: 0.70,
    2: 0.80,
    3: 1.05,
    4: 1.20,
    5: 1.30,
    6: 1.10,
    7: 0.85,
    8: 0.80,
    9: 0.95,
    10: 1.05,
    11: 0.85,
    12: 0.72,
}


def _year_factor(year: int) -> float:
    trend = 1.0 + 0.01 * max(0, min(year, 2018) - 2000)
    if year >= 2018:
        trend *= 0.985 ** (year - 2018)
    return trend


def sample_concentration(pollutant: str, year: int, month: int, station_factor: float) -> float:
    unit, base = BASE[pollutant]
    seasonal = O3_MONTH[month] if pollutant == "O3" else MONTH_FACTOR[month]
    value = base * seasonal * _year_factor(year) * station_factor
    if pollutant == "CO":
        return round(max(0.1, value), 2)
    return round(max(1.0, value), 1)


def generate_sample_observations(
    db: Session,
    city_id: str,
    stations_cfg: list[dict],
    year_start: int = 2000,
    year_end: int = 2026,
) -> int:
    inserted = 0
    batch: list[PollutionObservation] = []
    for cfg in stations_cfg:
        station = db.scalar(
            select(MonitoringStation).where(
                MonitoringStation.city_id == city_id,
                MonitoringStation.external_station_id == str(cfg["external_station_id"]),
            )
        )
        if station is None:
            station = MonitoringStation(
                city_id=city_id,
                external_station_id=str(cfg["external_station_id"]),
                name=cfg["name"],
                source=cfg.get("source", "SAMPLE_CPCB_STYLE"),
                station_type=cfg.get("station_type", "continuous"),
                location=from_shape(Point(float(cfg["lon"]), float(cfg["lat"])), srid=4326),
                extra_metadata={
                    "labeled_sample": True,
                    "agency": cfg.get("agency"),
                    "directory_note": "Coordinates from CPCB CAAQMS directory; concentrations are SAMPLE.",
                },
            )
            db.add(station)
            db.flush()
        factor = float(cfg.get("factor", 1.0))
        for year in range(year_start, year_end + 1):
            for month in range(1, 13):
                observed_at, tz_name = parse_observation_timestamp(
                    datetime(year, month, 15, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
                )
                for pollutant in BASE:
                    unit = BASE[pollutant][0]
                    batch.append(
                        PollutionObservation(
                            station_id=station.id,
                            pollutant=pollutant,
                            concentration=sample_concentration(pollutant, year, month, factor),
                            unit=unit,
                            original_unit=unit,
                            original_timezone=tz_name,
                            observed_at=observed_at,
                            quality_flag="sample",
                            source=station.source,
                            data_kind="observed",
                            notes="SAMPLE labeled monthly series; not an official CPCB measurement.",
                        )
                    )
                    inserted += 1
                    if len(batch) >= 1000:
                        db.add_all(batch)
                        db.flush()
                        batch.clear()
    if batch:
        db.add_all(batch)
        db.flush()
    db.commit()
    return inserted
