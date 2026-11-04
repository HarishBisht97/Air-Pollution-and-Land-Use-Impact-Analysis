# Testing instructions

## Backend unit tests

From `backend/`:

```bash
pytest
```

Covered without a live database:

- Pollutant aliases and unit conversion
- IST timestamp conversion
- NDVI / NDBI / NDWI numeric examples
- WorldCover class mapping
- NAAQS averaging-period matching
- CRS area and buffer distance in EPSG:32643
- Correlation n, r, p
- Regression insufficient-n guard
- Hotspot refusal under the station threshold
- Priority score does not treat unobserved cells as safe
- Land-cover change area deltas
- Health and NAAQS HTTP endpoints

## Backend integration (PostGIS)

With Docker Compose up:

```bash
docker compose exec api pytest
```

This exercises migrations (already applied at container start), seed data, and SQLAlchemy models.

## Frontend

```bash
cd frontend
npm test
```

Covers URL filter round-trip and empty-state rendering.

## Manual smoke (acceptance)

1. `docker compose up --build`
2. Open http://localhost:5173 — dashboard shows SAMPLE KPIs, not blanks with invented numbers.
3. Map explorer: station popup, grid popup with `observation_count`.
4. Datasets: catalog lists the seeded SAMPLE Delhi air-quality entry.
5. Reports: create observations CSV export and download.
6. Priority: hotspot request returns a labeled statistical estimate when station count is at least eight.
7. Confirm SAMPLE badges remain visible.
