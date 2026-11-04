from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.timestamps import parse_observation_timestamp
from app.ingestion.units import convert_concentration, is_invalid_measurement, normalize_pollutant
from app.models.catalog import IngestionBatch
from app.models.pollution import MonitoringStation, PollutionObservation


COLUMN_ALIASES = {
    "station_id": ["station_id", "external_station_id", "site_id", "site"],
    "station_name": ["station_name", "name", "station"],
    "pollutant": ["pollutant", "parameter", "pollutant_name"],
    "concentration": ["concentration", "value", "reading", "avg"],
    "unit": ["unit", "units"],
    "observed_at": ["observed_at", "datetime", "timestamp", "from_date", "date"],
    "latitude": ["latitude", "lat", "y"],
    "longitude": ["longitude", "lon", "lng", "x"],
    "quality_flag": ["quality_flag", "flag", "qc"],
    "source": ["source", "data_source"],
    "timezone": ["timezone", "tz"],
}


@dataclass
class IngestionReport:
    processed: int = 0
    inserted: int = 0
    skipped: int = 0
    rejected: int = 0
    errors: list[str] = field(default_factory=list)
    batch_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "processed": self.processed,
            "inserted": self.inserted,
            "skipped": self.skipped,
            "rejected": self.rejected,
            "errors": self.errors[:50],
            "batch_id": self.batch_id,
        }


def _map_row(fieldnames: list[str]) -> dict[str, str]:
    lowered = {name.lower().strip(): name for name in fieldnames}
    mapping: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lowered:
                mapping[canonical] = lowered[alias]
                break
    required = {"station_id", "pollutant", "concentration", "observed_at"}
    missing = required - mapping.keys()
    if missing:
        raise ValueError(f"CSV missing required columns: {sorted(missing)}")
    return mapping


def ingest_air_quality_csv(
    db: Session,
    content: str,
    *,
    city_id: str,
    filename: str | None = None,
    default_source: str = "manual_csv",
    labeled_sample: bool = False,
) -> IngestionReport:
    report = IngestionReport()
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise ValueError("CSV has no header row")
    mapping = _map_row(list(reader.fieldnames))

    batch = IngestionBatch(
        source=default_source,
        filename=filename,
        status="running",
        extra_metadata={"labeled_sample": labeled_sample},
    )
    db.add(batch)
    db.flush()
    report.batch_id = batch.id

    for row in reader:
        report.processed += 1
        try:
            station_ext = str(row[mapping["station_id"]]).strip()
            pollutant = normalize_pollutant(row[mapping["pollutant"]])
            raw_value = row[mapping["concentration"]].strip()
            if raw_value == "":
                report.skipped += 1
                continue
            value = float(raw_value)
            unit = row[mapping["unit"]] if "unit" in mapping else "ug/m3"
            if pollutant == "CO" and "unit" not in mapping:
                unit = "mg/m3"
            concentration, canonical_unit = convert_concentration(pollutant, value, unit)
            if is_invalid_measurement(concentration):
                report.rejected += 1
                report.errors.append(f"Invalid measurement for {station_ext} {pollutant}: {value}")
                continue
            observed_at, original_tz = parse_observation_timestamp(
                row[mapping["observed_at"]],
                row.get(mapping.get("timezone", ""), None) if "timezone" in mapping else None,
            )
            source = row[mapping["source"]].strip() if "source" in mapping else default_source
            quality_flag = row[mapping["quality_flag"]].strip() if "quality_flag" in mapping else "valid"
            data_kind = "observed"
            if labeled_sample or source.upper().startswith("SAMPLE"):
                data_kind = "observed"
                quality_flag = quality_flag or "sample"

            station = db.scalar(
                select(MonitoringStation).where(
                    MonitoringStation.city_id == city_id,
                    MonitoringStation.external_station_id == station_ext,
                    MonitoringStation.source == source,
                )
            )
            if station is None:
                lat = float(row[mapping["latitude"]]) if "latitude" in mapping else None
                lon = float(row[mapping["longitude"]]) if "longitude" in mapping else None
                if lat is None or lon is None:
                    report.rejected += 1
                    report.errors.append(f"Unknown station {station_ext} without coordinates")
                    continue
                station = MonitoringStation(
                    city_id=city_id,
                    external_station_id=station_ext,
                    name=row.get(mapping.get("station_name", ""), station_ext) or station_ext,
                    source=source,
                    location=from_shape(Point(lon, lat), srid=4326),
                    extra_metadata={"created_from_csv": True, "labeled_sample": labeled_sample},
                )
                db.add(station)
                db.flush()

            exists = db.scalar(
                select(PollutionObservation.id).where(
                    PollutionObservation.station_id == station.id,
                    PollutionObservation.pollutant == pollutant,
                    PollutionObservation.observed_at == observed_at,
                    PollutionObservation.source == source,
                )
            )
            if exists:
                report.skipped += 1
                continue

            db.add(
                PollutionObservation(
                    station_id=station.id,
                    ingestion_batch_id=batch.id,
                    pollutant=pollutant,
                    concentration=concentration,
                    unit=canonical_unit,
                    original_unit=unit,
                    original_timezone=original_tz,
                    observed_at=observed_at,
                    quality_flag=quality_flag,
                    source=source,
                    data_kind=data_kind,
                    notes="SAMPLE labeled dataset" if labeled_sample else None,
                )
            )
            report.inserted += 1
        except Exception as exc:  # noqa: BLE001
            report.rejected += 1
            report.errors.append(str(exc))

    batch.records_processed = report.processed
    batch.records_inserted = report.inserted
    batch.records_skipped = report.skipped
    batch.records_rejected = report.rejected
    batch.status = "completed"
    db.commit()
    return report
