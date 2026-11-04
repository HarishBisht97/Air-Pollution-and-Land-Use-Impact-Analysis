from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_city, db_session
from app.core.config import get_settings
from app.exports.tabular import methodology_block, to_csv
from app.models.city import City
from app.models.exports import ExportJob
from app.models.pollution import MonitoringStation, PollutionObservation
from app.services.geojson_utils import feature, feature_collection
from geoalchemy2.shape import to_shape

router = APIRouter(prefix="/exports", tags=["exports"])


class ExportRequest(BaseModel):
    export_type: str
    pollutant: str | None = "PM2.5"


@router.post("")
def create_export(body: ExportRequest, city: City = Depends(current_city), db: Session = Depends(db_session)):
    settings = get_settings()
    job = ExportJob(export_type=body.export_type, status="completed", parameters=body.model_dump())
    if body.export_type == "observations_csv":
        rows = []
        stmt = (
            select(PollutionObservation, MonitoringStation)
            .join(MonitoringStation)
            .where(MonitoringStation.city_id == city.id)
        )
        if body.pollutant:
            stmt = stmt.where(PollutionObservation.pollutant == body.pollutant)
        for obs, station in db.execute(stmt.limit(settings.max_export_rows)):
            rows.append(
                {
                    "station_id": station.external_station_id,
                    "station_name": station.name,
                    "pollutant": obs.pollutant,
                    "concentration": float(obs.concentration),
                    "unit": obs.unit,
                    "observed_at": obs.observed_at.isoformat(),
                    "quality_flag": obs.quality_flag,
                    "source": obs.source,
                    "data_kind": obs.data_kind,
                }
            )
        job.row_count = len(rows)
        db.add(job)
        db.commit()
        db.refresh(job)
        return {"id": job.id, "status": job.status, "row_count": job.row_count, "export_type": job.export_type}
    if body.export_type == "stations_geojson":
        job.row_count = db.scalar(
            select(PollutionObservation.id).join(MonitoringStation).where(MonitoringStation.city_id == city.id).exists()
            and 1
        ) or 0
        db.add(job)
        db.commit()
        db.refresh(job)
        return {"id": job.id, "status": "completed", "export_type": body.export_type}
    if body.export_type == "report_json":
        db.add(job)
        db.commit()
        db.refresh(job)
        return {"id": job.id, "status": "completed", "export_type": body.export_type}
    raise HTTPException(400, "Supported export_type: observations_csv, stations_geojson, report_json")


@router.get("/{export_id}")
def download_export(export_id: str, city: City = Depends(current_city), db: Session = Depends(db_session)):
    job = db.get(ExportJob, export_id)
    if job is None:
        raise HTTPException(404, "Export not found")
    if job.export_type == "observations_csv":
        rows = []
        stmt = (
            select(PollutionObservation, MonitoringStation)
            .join(MonitoringStation)
            .where(MonitoringStation.city_id == city.id)
        )
        for obs, station in db.execute(stmt.limit(get_settings().max_export_rows)):
            rows.append(
                {
                    "station_id": station.external_station_id,
                    "station_name": station.name,
                    "pollutant": obs.pollutant,
                    "concentration": float(obs.concentration),
                    "unit": obs.unit,
                    "observed_at": obs.observed_at.isoformat(),
                    "quality_flag": obs.quality_flag,
                    "source": obs.source,
                    "data_kind": obs.data_kind,
                }
            )
        return Response(to_csv(rows), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=observations.csv"})
    if job.export_type == "stations_geojson":
        stations = db.scalars(select(MonitoringStation).where(MonitoringStation.city_id == city.id)).all()
        fc = feature_collection(
            [
                feature(
                    station.location,
                    {
                        "name": station.name,
                        "source": station.source,
                        "external_station_id": station.external_station_id,
                        "data_kind": "observed",
                    },
                )
                for station in stations
            ]
        )
        return Response(
            json_dumps(fc),
            media_type="application/geo+json",
            headers={"Content-Disposition": "attachment; filename=stations.geojson"},
        )
    if job.export_type == "report_json":
        payload = methodology_block(city.name, {"export_id": job.id, "city_slug": city.slug})
        return payload
    raise HTTPException(400, "Unknown export type")


def json_dumps(payload) -> str:
    import json

    return json.dumps(payload)
