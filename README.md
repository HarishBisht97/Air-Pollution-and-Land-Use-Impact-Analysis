# Air Pollution and Land Use Impact Analysis

Research-oriented geospatial platform for investigating **associations** between urban land cover, vegetation indices, roads, and air-quality **observations**. Study area: **Delhi, NCT of Delhi, India** (EPSG:32643, 1000 m grid, 2000–2026). Another Indian city can be added as a YAML config plus a boundary file — city coordinates are not hardcoded in analysis math.

The first working path is:

**Import labeled sample (or CPCB CSV) observations → validate and store → summarize → FastAPI → map and dashboard → CSV/GeoJSON export.**

This repository does **not** invent station readings or present sample rasters as real Sentinel-2 scenes.

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:5173
- API and OpenAPI: http://localhost:8000/docs
- Health: http://localhost:8000/health

On first API start, Alembic migrates PostGIS and seeds **explicitly labeled SAMPLE** Delhi data (twelve CPCB-listed station coordinates, synthetic monthly series).

## Quick start (local)

Requires Python 3.12, Node 22, and PostgreSQL 16 with PostGIS.

```bash
cp .env.example .env
# Point DATABASE_URL at your PostGIS instance (localhost).
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python -m app.workers.seed
uvicorn app.main:app --reload --port 8000

cd ../frontend
npm install
npm run dev
```

The stack starts **without** Google Earth Engine, Copernicus, or OpenAQ credentials.

## What the seed contains

| Layer | Reality |
| --- | --- |
| Delhi CAAQMS coordinates | Twelve real listed directory locations (e.g. Anand Vihar, R K Puram) |
| Monthly pollutant values | **SAMPLE** series for software testing, not official CPCB measurements |
| City polygon | Approximate NCT envelope, not an official cadastral boundary |
| Roads / parks / industry | Synthetic OSM-like sketches (Ring Road, Yamuna, Ridge, Okhla/Bawana) |
| NDVI / NDBI / WorldCover-like rasters | Tiny GeoTIFFs tagged `SAMPLE — not a satellite observation` |

With ≥8 stations, grid cells without a monitor may store a labeled **IDW estimate** (`data_kind=statistical_estimate`). Delhi seed lists twelve stations, so those estimates are available. Observed means stay on the station layer.

## Tests

```bash
cd backend && pytest
cd frontend && npm test
```

## Importing real air-quality data

1. Download CSV/XLSX from the [CPCB CCR dashboard](https://airquality.cpcb.gov.in/ccr/) (captcha; no official bulk API is used here).
2. Map columns to `station_id, pollutant, concentration, unit, observed_at, latitude, longitude`.
3. Upload via **Datasets** or:

```bash
cd backend
python ../scripts/ingest_air_quality.py ../path/to/file.csv --city delhi --source CPCB_CAAQMS
```

Do not scrape the CCR portal.

## Documentation

- [Architecture](docs/architecture.md)
- [Data sources](docs/data_sources.md)
- [Methodology](docs/methodology.md)
- [Database schema](docs/database_schema.md)
- [API reference](docs/api_reference.md)
- [Setup guide](docs/setup_guide.md)

## License notes

Respect CPCB terms for official observations, OpenStreetMap ODbL for OSM extracts, Copernicus terms for Sentinel-2, and CC-BY 4.0 for ESA WorldCover. Sample fixtures in `data/sample/` are development artifacts only.
# Air-Pollution-and-Land-Use-Impact-Analysis
