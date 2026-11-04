# Setup guide

## Prerequisites

- Docker Desktop or Python 3.12 + Node 22 + PostGIS 16
- 8 GB RAM recommended for the API image (GDAL/rasterio)

## Environment

Copy `.env.example` to `.env`. Defaults work for Docker Compose. Never commit secrets.

Optional variables:

- `OPENAQ_API_KEY`
- `CDSE_CLIENT_ID` / `CDSE_CLIENT_SECRET`
- `GEE_SERVICE_ACCOUNT` / `GEE_PROJECT`

## First run

`docker compose up --build` applies migrations and runs `python -m app.workers.seed`.

If seed fails because of volume paths, confirm `./data` and `./config` are mounted (see `docker-compose.yml`).

## Replacing sample data

1. Official city boundary GeoJSON → `POST /ingestion/spatial-file` is for layers; city boundary is seeded from YAML `boundary_geojson`.
2. CPCB CSV → Datasets upload or `scripts/ingest_air_quality.py`.
3. OSM extract → `scripts/ingest_spatial_data.py --layer roads`.
4. WorldCover COG / Sentinel bands → place under `data/raw` and run `scripts/process_satellite_imagery.py`.

## Tests

```bash
cd backend && pytest
cd frontend && npm test
```

Integration tests that need PostGIS expect `DATABASE_URL`. Unit tests for NDVI, units, NAAQS, correlation, and CRS do not need a database.

## Known gaps / future work

- Official CPCB live client (still no scraping)
- Authenticated Copernicus/GEE composite pipeline wired to the UI
- Custom Random Forest land-cover classifier with an independent validation set
- Weather covariates
- Vector tiles if another megacity grid exceeds GeoJSON comfort
- User authentication (v1 is a local research tool)
