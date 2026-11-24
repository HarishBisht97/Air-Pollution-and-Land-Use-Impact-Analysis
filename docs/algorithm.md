# Algorithm: air pollution and land-use impact analysis (NCT of Delhi)

This document states the project's algorithm step by step, with the formulas, thresholds, and decision rules used in the code. Every step is drawn in [`GNR605_Algorithm_Flowchart.drawio`](GNR605_Algorithm_Flowchart.drawio). Open it in [diagrams.net](https://app.diagrams.net) or the draw.io VS Code extension. The file has one tab per section:

| Tab | Section in this document |
| --- | --- |
| 0 · Master algorithm | [Master algorithm](#master-algorithm) |
| A2 · Ingest CSV | [A2](#a2--ingest-and-validate-air-quality-observations) |
| A3 · CPCB hourly AQI | [A3](#a3--build-the-cpcb-hourly-aqi-extract-20252026) |
| A4–A5 · Grid and IDW | [A4](#a4--analysis-grid-and-cell-metrics), [A5](#a5--station-in-cell-assignment-and-the-idw-gate) |
| A6 · Annual station AQI | [A6](#a6--annual-aqi-at-each-monitor) |
| A7–A8 · Built-up and projection | [A7](#a7--built-up-land-vs-annual-aqi-year-by-year), [A8](#a8--built-up-area-and-city-aqi-projection) |
| A9 · Neighbourhood questions | [A9](#a9--neighbourhood-questions-at-monitors-2024) |
| A10–A11 · Statistics and screening | [A10](#a10--correlation-regression-and-hotspots), [A11](#a11--land-cover-change-screening-priority-naaqs) |

The project tests **associations** between land use and air quality. It does not estimate causal effects, and it never presents an interpolated or modelled value as a measurement.

---

## 1. Notation and constants

| Symbol / name | Meaning | Value | Defined in |
| --- | --- | --- | --- |
| Geographic CRS | Storage CRS for all geometries | EPSG:4326 | `config/cities/delhi.yaml` |
| Projected CRS | CRS for distances, areas, buffers | EPSG:32643 (UTM 43N) | `delhi.yaml` |
| r | Analysis grid resolution | 1000 m | `delhi.yaml` |
| Buffer distances | Rings around features | 100, 300, 500, 1000 m | `delhi.yaml` |
| S_min | Minimum stations for city-wide maps, IDW, hotspots | 8 | `hotspot_min_stations` |
| H_day | Minimum hourly values for a valid day | 16 | `xkdr_daily.py`, `cpcb_hourly_aqi.py` |
| D_year | Minimum valid days for an annual AQI | 180 | `daily_aqi.py` |
| H_month | Minimum hours for a valid month (local questions) | 336 | `delhi_land_use.py` |
| M_year | Minimum valid months for an annual mean | 6 | `delhi_land_use.py`, `builtup_concentration_change.py` |
| Built-up class | Dynamic World label | 6 | `dynamic_world.py` |
| Vegetation classes | Dynamic World labels (trees, grass, shrub) | 1, 2, 5 | `dynamic_world.py` |
| Window | Square around a monitor for land shares | 1 km × 1 km | `dynamic_world.py` |
| AQI years | Concentration-based index / CPCB hourly index | 2018–2024 / 2025–2026 | `cpcb_hourly_aqi.year_labels` |
| Partial year | 2026 coverage ends | 31 Oct 2026 | `COVERAGE_END` |

### Data-kind labels

Every derived API payload carries a `data_kind` so the reader knows what a number is:

| `data_kind` | Meaning |
| --- | --- |
| `observed` | Raw monitor value |
| `quality_controlled` | Observed value with a valid quality flag |
| `aggregated` | Mean or median of observations (daily, monthly, per cell) |
| `satellite_index` | NDVI / NDBI / NDWI |
| `classified` | Land-cover class or class area |
| `statistical_estimate` | Correlation, regression, IDW fill, z-score |
| `model_prediction` | Projection beyond observed years |
| `screening_score` | Priority index (not a health-risk model) |

---

## 2. Inputs and outputs

**Inputs**

1. City configuration: `config/cities/delhi.yaml` (boundary path, CRS, grid, buffers, pollutants, station list for the SAMPLE seed).
2. Air quality:
   - XKDR extracts of CPCB CAAQMS concentrations: `data/raw/xkdr_daily/*.json` (daily) and `data/raw/xkdr_delhi_*_monthly.json` (monthly), plus `xkdr_delhi_stations.json`.
   - CPCB hourly AQI workbooks for 2025–2026: `cpcb_data_2025_2026/*.xlsx`.
   - Any CPCB CCR CSV uploaded through the Datasets page or `scripts/ingest_air_quality.py`.
3. Land cover and imagery: Dynamic World label rasters `data/raw/dynamicworld/DynamicWorld_label_<year>_delhi.tif` (2018–2026), WorldCover or SAMPLE rasters, Sentinel-2 bands when available.
4. Vector layers: OSM Overpass extract `data/raw/osm/delhi_overpass.json`, FAO GAUL 2015 boundary, station classes `data/raw/stations/cpcb_station_class.csv`, wards `data/raw/wards/delhi_wards.geojson`.

**Outputs**

- PostGIS tables (cities, stations, observations, grid, metrics, land-cover statistics, analysis runs).
- Processed files `data/processed/cpcb_aqi/{hourly/*.csv.gz, daily.json, monthly.json, stations.json}`.
- FastAPI JSON / GeoJSON / PNG responses under `/api/v1`, shown in the React app and exportable as CSV or GeoJSON.

---

## Master algorithm

```text
ALGORITHM DelhiAirLandUse
INPUT  city slug (default "delhi")
OUTPUT labelled analysis products served by /api/v1

 1  cfg ← LoadCityConfig(slug)                                  # CRS, grid r, buffers, S_min
 2  SeedStudyArea(cfg)                                           # A1: boundary, grid, layers, rasters, catalogue
 3  IF research files (XKDR PM2.5 + stations) are absent THEN
 4      GenerateSampleSeries(cfg.stations)                       # labelled SAMPLE, never "observed CPCB"
 5  IngestObservations(uploaded CSV files)                       # A2
 6  BuildHourlyAQIExtract(cpcb_data_2025_2026)                   # A3
 7  grid ← BuildGridMetrics(cfg)                                 # A4
 8  AssignStationsToCells(grid)                                  # A5 part 1
 9  IF number of monitored cells ≥ S_min THEN
10      IDWFill(grid)                                            # A5 part 2, labelled statistical_estimate
11  ELSE
12      leave unmonitored cells null; hotspot requests return "refused"
13  FOR each analysis request DO                                 # each writes an analysis_runs row
14      run one of A6 … A11
15      attach data_kind; return JSON/GeoJSON with run_id
16  END FOR
```

**A1 · Seed the study area** (`backend/app/workers/seed.py`, run on API start, idempotent):

1. Insert or update the city row with its boundary (stored as a MultiPolygon in EPSG:4326).
2. Generate the 1 km grid once (A4).
3. Insert the SAMPLE OSM-like roads, parks, industry, and water sketches.
4. If the XKDR PM2.5 and station files are **not** in `data/raw`, generate the SAMPLE monthly series. For each station, year, month, and pollutant:
   `value = base[pollutant] × month_factor[month] × year_trend(year) × station_factor`
   with ozone using its own seasonal factor. Rows are written with `quality_flag = sample`.
5. Write the SAMPLE GeoTIFFs for 2020 and 2024, register them in `raster_assets`, and compute the cell metrics (A4).
6. Write dataset-catalogue entries, then put the CPCB PM2.5 station means on the grid (A5).

---

## A2 · Ingest and validate air-quality observations

Code: `backend/app/ingestion/air_quality_csv.py`, `units.py`, `timestamps.py`.

```text
PROCEDURE IngestCSV(text, city, default_source, labeled_sample)
 1  header ← first row; map aliases to canonical names
        station_id ← {station_id, external_station_id, site_id, site}
        pollutant  ← {pollutant, parameter, pollutant_name}
        concentration ← {concentration, value, reading, avg}
        observed_at ← {observed_at, datetime, timestamp, from_date, date}
        optional: station_name, unit, latitude, longitude, quality_flag, source, timezone
 2  IF any of {station_id, pollutant, concentration, observed_at} missing THEN raise error
 3  batch ← new IngestionBatch(status = running)
 4  FOR each row DO
 5      processed += 1
 6      pollutant ← Normalise(name)                 # pm25 → PM2.5, ozone → O3; unknown → reject
 7      IF concentration blank THEN skipped += 1; CONTINUE
 8      (value, unit) ← ConvertUnit(pollutant, value, unit)
 9      IF value < 0 OR value ∈ {999, 9999, 99999} THEN rejected += 1; CONTINUE
10      t_utc ← ParseTime(observed_at, timezone or Asia/Kolkata)
11      station ← lookup (city, external id, source)
12      IF station not found THEN
13          IF lat/lon missing THEN rejected += 1; CONTINUE
14          create station POINT(lon, lat) in EPSG:4326
15      IF (station, pollutant, t_utc, source) exists THEN skipped += 1; CONTINUE
16      insert observation (data_kind = observed); inserted += 1
17      ON any exception: rejected += 1 and record the message
18  END FOR
19  batch.status ← completed; store counts; commit; RETURN report
```

**Unit conversion.** Canonical units are µg/m³ for PM2.5, PM10, NO2, SO2, O3 and mg/m³ for CO. If there is no unit column, CO is read as mg/m³ and everything else as µg/m³. Gases in ppm or ppb are converted at 25 °C and 1 atm:

```text
ppm   = value                (unit = ppm)
ppm   = value / 1000         (unit = ppb)
µg/m³ = ppm × MW × 1000 / 24.45
MW: NO2 46.0055, SO2 64.066, CO 28.01, O3 47.998
```

Particulate matter in ppm or ppb cannot be converted and is rejected.

**Idempotency.** The key (station, pollutant, UTC time, source) is unique, so importing the same file twice adds no rows.

---

## A3 · Build the CPCB hourly AQI extract (2025–2026)

Code: `backend/app/ingestion/cpcb_hourly_aqi.py`, run by `scripts/ingest_cpcb_hourly_aqi.py`.

These workbooks hold CPCB's **published hourly AQI index (0–500)**, not concentrations.

```text
PROCEDURE BuildHourlyAQIExtract(source_dir, output_dir, raw_dir)
 1  files ← *.xlsx; drop "name (1).xlsx" when "name.xlsx" exists
 2  by_id, by_name ← coordinate lookups (XKDR station list; CPCB realtime snapshot)
 3  FOR each workbook DO
 4      IF name ≠ AQI_Data_Station_Level_Site_<id>_<name>_Delhi_<agency>_<Month>_<Year>_Hourly
 5          THEN add to unparsed; CONTINUE
 6      read sheet1.xml: row = day, columns 1..24 = hours 00..23 (IST)
 7      FOR each (day, hour) cell DO
 8          IF day ∉ [1, days_in_month] THEN rejected += 1; CONTINUE
 9          IF cell blank (NA, -, NULL, NaN) THEN CONTINUE           # omitted, not zero
10          IF AQI ∉ [0, 500] THEN rejected += 1; CONTINUE
11          hours[site][datetime(y, m, day, hour, IST)] ← AQI
12  FOR each site (numeric order) DO
13      coordinates ← by_id[site] or by_name[normalise(name)] or null
14      write hourly/<site>.csv.gz (observed_at, aqi)
15      daily rows ← for each date: mean, max, n of hourly values; keep only n ≥ 16
16  monthly rows ← mean of daily means per (station, YYYY-MM), with n_days
17  write stations.json, daily.json, monthly.json; RETURN report
```

---

## A4 · Analysis grid and cell metrics

Code: `backend/app/geospatial/grid.py`, `backend/app/workers/seed.py`, `backend/app/remote_sensing/indices.py`, `worldcover.py`.

**Grid generation**

```text
PROCEDURE GenerateGrid(boundary, r, EPSG:32643)
 1  B ← project(boundary); (minx, miny, maxx, maxy) ← bounds(B)
 2  row ← 0; y ← miny
 3  WHILE y < maxy DO
 4      col ← 0; x ← minx
 5      WHILE x < maxx DO
 6          clipped ← square(x, y, x + r, y + r) ∩ B
 7          IF area(clipped) > 0 THEN
 8              store cell "R{row:03}C{col:03}", geometry in EPSG:4326,
 9              area_sq_km = area(clipped in UTM) / 10⁶
10          x ← x + r; col ← col + 1
11      y ← y + r; row ← row + 1
```

Edge cells are clipped to the boundary, so their area can be below 1 km².

**Per-cell metrics.** For each cell:

1. **Spectral indices** (rasters masked to the cell, mean ignoring NaN):
   - NDVI = (B8 − B4) / (B8 + B4)
   - NDBI = (B11 − B8) / (B11 + B8), with B11 resampled from 20 m to 10 m
   - NDWI = (B3 − B8) / (B3 + B8)
   - A zero denominator gives NaN. On real Sentinel-2 composites, SCL classes 3, 8, 9, 10 (cloud and shadow) should be masked first.
2. **Land cover.** Each WorldCover code is mapped to one of seven study classes: 10 → tree cover; 20, 30 → grassland / sparse vegetation; 40 → cropland; 50 → built-up; 60 → bare soil; 80 → water; anything else → other.
   `class % = 100 × pixels of the class / valid pixels`. Built %, vegetation % (tree + grass), and water % are stored on the cell, and one `LandCoverStatistic` row is written per class and year.
3. **Roads and industry** (all in UTM metres):
   `road density (km/km²) = length(major roads ∩ cell) / 1000 / area_sq_km`.
   The distance from the cell centroid to the nearest major road and to the nearest industrial site is also stored.

---

## A5 · Station-in-cell assignment and the IDW gate

Code: `backend/app/ingestion/grid_cpcb.py`, `backend/app/geospatial/idw.py`, `seed.py`.

**Station-in-cell**

1. For each station, compute the hour-weighted mean over its months: `mean = Σ (mean_m × n_m) / Σ n_m`.
2. Find the cells whose polygon covers the station point. If the point lies on a shared edge, choose the cell with the nearer centroid. If no cell covers the point, the station is reported as outside the grid.
3. If a cell holds several stations, combine them by hour-weighted mean; the median is taken over all their monthly means.
4. A cell **with** a station stores mean, median, `observation_count`, and coverage (`data_kind = aggregated`). A cell **without** a station has its pollution fields cleared: `mean = null`, `observation_count = 0`. A null means unmeasured, not low.

**IDW gate** (used for the SAMPLE path)

```text
IF number of monitored cells ≥ S_min (8) THEN
    FOR each cell with observation_count = 0 DO
        (x₀, y₀) ← cell centroid in UTM
        FOR each monitored point i: dᵢ ← ‖(x₀, y₀) − (xᵢ, yᵢ)‖
        IF some dᵢ < 1 m THEN ẑ ← zᵢ
        ELSE ẑ ← Σ wᵢ zᵢ / Σ wᵢ, with wᵢ = 1 / dᵢ²
        store ẑ with pollution_assignment = idw_estimate, data_kind = statistical_estimate
ELSE
    no surface; /analysis/hotspots returns status = refused (the run is still logged)
```

**Buffers** (`backend/app/geospatial/buffers.py`). For distances d₁ < d₂ < … in UTM, `ring_k = buffer(d_k) − buffer(d_{k−1})`. Buffers describe a monitor's neighbourhood; they do not add independent pollution samples.

---

## A6 · Annual AQI at each monitor

Code: `backend/app/analytics/daily_aqi.py`, `backend/app/ingestion/cpcb_hourly_aqi.py` (`annual_index`, `year_labels`).

```text
PROCEDURE AnnualStationAQI(y)
 1  IF y ≤ 2024 THEN                                    # concentration-based index
 2      FOR p ∈ {PM2.5, PM10, NO2, SO2, NH3} load daily rows with n ≥ 16 hours
 3      FOR each (station, day):
 4          Iₚ ← SubIndex(p, Cₚ) for each available pollutant
 5          IF count(Iₚ) ≥ 3 AND (PM2.5 or PM10 present) THEN AQI_day ← max Iₚ
 6          ELSE the day is not rated
 7  ELSE                                                # y ≥ 2025
 8      AQI_day ← daily mean of CPCB hourly AQI (days with ≥ 16 hours, from A3)
 9  FOR each station:
10      IF rated days ≥ 180 THEN
11          AQI_year ← mean(AQI_day); category ← Category(AQI_year)
12          poor_or_worse_days ← #days with AQI_day > 200
```

**Sub-index** (linear interpolation inside the CPCB band that contains C):

```text
C ← max(C, 0)
find the first band with C ≤ C_hi
I = I_lo + (C − C_lo) × (I_hi − I_lo) / (C_hi − C_lo)
if C is above every band, I = 500
```

CPCB breakpoints, 24-hour mean in µg/m³ (CO and O3 are excluded because their AQI uses 8-hour maxima):

| Index band | 0–50 | 51–100 | 101–200 | 201–300 | 301–400 | 401–500 |
| --- | --- | --- | --- | --- | --- | --- |
| PM2.5 | 0–30 | 30–60 | 60–90 | 90–120 | 120–250 | 250–500 |
| PM10 | 0–50 | 50–100 | 100–250 | 250–350 | 350–430 | 430–600 |
| NO2 | 0–40 | 40–80 | 80–180 | 180–280 | 280–400 | 400–800 |
| SO2 | 0–40 | 40–80 | 80–380 | 380–800 | 800–1600 | 1600–2400 |
| NH3 | 0–200 | 200–400 | 400–800 | 800–1200 | 1200–1800 | 1800–2400 |

**Category:** ≤ 50 Good · ≤ 100 Satisfactory · ≤ 200 Moderate · ≤ 300 Poor · ≤ 400 Very Poor · > 400 Severe.

**Series break.** From 2025 the annual value is the mean of CPCB's published hourly index, not the concentration-based index, so a change across 2024 → 2025 mixes a definition change with any real change. 2026 ends on 31 October, before the high-AQI winter months, and every 2026 record carries a `coverage_note`.

---

## A7 · Built-up land vs annual AQI, year by year

Code: `backend/app/analytics/builtup_aqi_years.py`, `backend/app/remote_sensing/dynamic_world.py`, `backend/app/geospatial/contours.py`.

```text
PROCEDURE BuiltUpAQIYears()
 1  monitors ← XKDR stations with coordinates ∪ CPCB 2025–26 stations not already listed
 2  boundary ← FAO GAUL 2015 Delhi polygon
 3  FOR y = 2018 … 2026 DO
 4      annual ← AnnualStationAQI(y)                                   # A6
 5      FOR each monitor m with an annual value:
 6          b_m ← BuiltUpShare(DynamicWorld_y, m)                      # % class 6 in 1 km square
 7      YearStatistics({(b_m, AQI_m)})
 8      CityTrend(y): built_km² inside boundary, mean AQI, poor-or-worse share
 9      Map products for y (classes, IDW surface, isolines, change, overlay)
```

**Built-up share in a 1 km square** (geographic window around a monitor at latitude φ):

```text
Δlat = 0.5 / 111.32 degrees
Δlon = Δlat / cos φ
b = 100 × (pixels with label 6) / (pixels with label ≠ 255)
```

The same window gives vegetation % (labels 1, 2, 5) and crops % (label 4).

**Year statistics** on pairs (b, AQI):

- Pearson r with a Fisher-z 95% confidence interval (see A10).
- OLS `AQI = β₀ + β₁·b`, reported as `10·β₁` (AQI change per 10 built-up points), with R².
- **Tercile gap**: sort monitors by b, t = ⌊n/3⌋, `gap = mean AQI(top t) − mean AQI(bottom t)`.
- `status = ok` only when t ≥ 3 and r is defined; otherwise `insufficient_data`.

**City trend row.** The built-up area inside the boundary sums pixel areas row by row, because a degree of longitude shrinks with latitude:

```text
pixel_km²(row) = (|Δx| × 111.32 × cos(lat_row)) × (|Δy| × 111.32)
built_km² = Σ_rows (class-6 pixels in row) × pixel_km²(row)
poor_or_worse_share = 100 × Σ days with AQI > 200 / Σ rated days
```

**Map products** (all `data_kind = statistical_estimate`):

- **Fixed classes:** 10-point AQI bins that span every station-year, so a colour means the same AQI in every year.
- **IDW surface:** the boundary is projected to UTM and a 500 m grid is laid over its extent. At each node, `ẑ = Σ wᵢzᵢ / Σ wᵢ` with `wᵢ = 1 / max(dᵢ, 1 m)²`. Nodes within 1 m of a station take its value. The filled bands are polygonised and clipped to the boundary.
- **Isolines:** every 20 AQI, traced by marching squares. Each grid square's four corners are compared with the level; crossing points come from linear interpolation along the edges, and the saddle case is resolved by the centre average.
- **Change maps:** `AQI(y) − AQI(base)` for monitors with a valid annual value in both years (base defaults to 2018), in symmetric classes from −50 to +50 in steps of 10, with open-ended outer classes.
- **Quick bands** (`/annual-aqi-bands`): IDW on a 1 km grid, drawn as eight equal bands from that year's own minimum to its maximum, so colours are not comparable between years.
- **Overlay PNG:** pixels built in 2018 are grey, and pixels built since 2018 are red, both inside the boundary.

**A7b · Change 2018 → 2024** (`builtup_concentration_change.py`). For each monitor, compute `Δb = b₂₀₂₄ − b₂₀₁₈` and Δ of the hour-weighted annual mean of PM2.5 and NO2. A year counts for a monitor when it has ≥ 6 months. When n ≥ 8 and Δb takes at least two distinct values, fit OLS `Δconcentration = β₀ + β₁·Δb` and Pearson r.

---

## A8 · Built-up area and city AQI projection

Code: `backend/app/analytics/builtup_projection.py`.

```text
PROCEDURE ProjectBuiltUpAQI(city_trend, targets = {2026, 2027, 2028})
 1  built_rows ← years with a built_km² value
 2  IF |built_rows| < 8 THEN RETURN insufficient_data
 3  Fit OLS  built_km² = a + b·year
 4  FOR t ∈ targets: predict mean and 95% mean CI → (low_t, central_t, high_t)
 5  aqi_rows ← years with aqi_source = concentration_subindex AND not partial
 6  IF |aqi_rows| ≥ 5 THEN
 7      Fit OLS  mean_AQI = c + d·built_km²
 8      FOR t ∈ targets:
 9          evaluate at low_t, central_t, high_t
10          value ← prediction at central_t
11          interval ← [min lower CI, max upper CI] over the three points
12          flag outside_observed_built if central_t ∉ [min, max] observed built_km²
13  ELSE the AQI line is withheld (the built-area line is still returned)
14  report Pearson r(built_km², mean_AQI) over aqi_rows
15  data_kind ← model_prediction
```

The 2025–2026 hourly-index years and the partial 2026 never enter the AQI line. The within-year built-up gap (A7) is **not** converted into a future city average.

---

## A9 · Neighbourhood questions at monitors (2024)

Code: `backend/app/analytics/local_questions.py`, `delhi_land_use.py`.

**Inputs per monitor**

1. 2024 means of PM2.5, NO2, and ozone. A month counts if it has ≥ 336 hours, and a monitor needs ≥ 6 such months. `mean = Σ mean_m·n_m / Σ n_m`.
2. Dynamic World 2024 shares in the 1 km square: built % (label 6) and vegetation % (labels 1, 2, 5).
3. OSM layers from `delhi_overpass.json`:
   - major roads: `highway ∈ {motorway, trunk, primary}`
   - industry: `landuse = industrial`
   - parks: `leisure ∈ {park, garden}` or `landuse = grass`
   - Relations are built as outer rings minus inner rings, and invalid geometries are repaired. Each layer is unioned and projected to EPSG:32643.
4. Metrics, all in metres in UTM:
   - industrial share = 100 × area(1 km square ∩ industry) / area(square), and distance to industry
   - distance to the nearest major road, and major-road length within 300 m
   - park area within 500 m, and distance to the nearest park

**Tercile contrast** (used by several questions):

```text
ranked ← monitors with both values, sorted by the land measure
t ← ⌊|ranked| / 3⌋;  IF t < 3 THEN insufficient_data
low ← first t; high ← last t
% difference = 100 × (mean_high − mean_low) / mean_low
```

**The five questions**

| Question | Method | Withheld when |
| --- | --- | --- |
| Vegetation | Tercile of PM2.5, NO2, ozone by vegetation % | t < 3 |
| Parks | Tercile of PM2.5, NO2 by park area within 500 m | fewer than 3 monitors in the high-park third have any park |
| Major roads | Spearman ρ and Pearson r of NO2 and PM2.5 vs distance; OLS `pollutant = β₀ + β₁·distance + β₂·built %` (β₁ × 1000 = change per km) | OSM roads missing |
| Industry | Tercile of PM2.5 by industrial share + OLS `PM2.5 = β₀ + β₁·industrial % + β₂·built %` | fewer than 3 monitors have industrial share > 0 |
| Residential rank | Residential-class monitors ranked by 2024 PM2.5; ward = polygon that covers the point | class CSV or ward file missing |

**Road reading rule** (ρ < 0 means higher values nearer the road):

```text
IF |ρ_NO2| < 0.2 AND |ρ_PM2.5| < 0.2           → "unclear"
ELSE IF ρ_NO2 < 0 AND ρ_PM2.5 < 0 AND |ρ_NO2| ≤ |ρ_PM2.5| + 0.1 → "both together"
ELSE IF ρ_NO2 < 0 AND |ρ_NO2| > |ρ_PM2.5|     → "NO2 stronger"
ELSE IF ρ_NO2 < 0 AND ρ_PM2.5 < 0              → "both together"
ELSE                                           → "unclear"
```

Polygons are only outlined, and nothing is interpolated onto them. Wards without a residential monitor are counted as unmeasured. The result is cached and recomputed when any input file's modification time changes.

---

## A10 · Correlation, regression, and hotspots

Code: `backend/app/analytics/correlation.py`, `regression.py`, `esda.py`, `backend/app/api/v1/analysis.py`.

**Correlation** (`POST /analysis/correlation`)

```text
pairs ← (xᵢ, yᵢ) with both non-null              # pairwise deletion
IF n < 3 THEN coefficients = null
r, p ← Pearson(x, y)
IF n > 3 AND |r| < 1:
    z = atanh(r);  SE = 1 / √(n − 3);  z* = 1.96 (α = 0.05)
    CI = [tanh(z − z*·SE), tanh(z + z*·SE)]
ρ, p ← Spearman(x, y)
```

Grid-level pollution exists only in monitored cells, so n is small and the result does not generalise to the whole city.

**OLS regression** (`POST /analysis/regression`)

```text
rows ← complete cases of (response, predictors);  k ← #predictors
IF n < max(8, k + 3) THEN insufficient_data
fit y = β₀ + Σ βⱼ xⱼ + ε
report β, p-values, 95% CI, R², adjusted R², RMSE, MAE, residual mean and SD
VIFⱼ = 1 / (1 − R²ⱼ), where R²ⱼ comes from regressing xⱼ on the other predictors
weather_controlled = false; no random hold-out (observations share locations)
```

**Hotspots** (`POST /analysis/hotspots`)

```text
n ← number of stations in the city
IF n < S_min THEN RETURN status = refused (an analysis_run is still recorded)
FOR each station: x ← mean PM2.5 over observations with quality_flag ≠ invalid
μ ← mean(x);  s ← sample SD (n − 1)
z = (x − μ) / s;  hotspot ⇔ z ≥ 1
```

The output is a set of station points, not an interpolated surface and not Getis-Ord Gi\*. A Moran's I helper with row-standardised weights exists in `esda.py`, but no API route calls it yet. The methodology permits it only when n ≥ 8, and local indicators would need an FDR or Bonferroni correction before their significance is mapped.

---

## A11 · Land-cover change, screening priority, NAAQS

**Land-cover change** (`backend/app/analytics/change.py`)

```text
FOR each study class c:
    Δkm²(c) = recent(c) − baseline(c)
    Δpp(c)  = 100·recent(c)/Σ recent − 100·baseline(c)/Σ baseline
comparable_classification_scheme ← both years use the same algorithm
```

WorldCover 2020 (v100) and 2021 (v200) use different algorithms, so for that pair the flag is false and a caveat is attached. `data_kind = classified`.

**Screening priority** (`backend/app/analytics/priority.py`)

```text
norm(v, lo, hi) = clamp((v − lo) / (hi − lo), 0, 1);  norm(null) = 0
severity   = norm(mean, 0, 150) if observation_count > 0 else null
built      = norm(built %, 0, 100)
roads      = norm(road density, 0, 20)
veg_def    = 1 − norm(vegetation %, 0, 100)
confidence = min(1, observation_count / 30)
score      = Σ wᵢ cᵢ / Σ wᵢ   over non-null components
weights    = severity 0.35, built 0.20, roads 0.15, veg_def 0.15, confidence 0.15
```

Cells are sorted by score and the top 200 are returned. Severity, confidence, and score are returned separately. An unobserved cell gets `severity = null`; it is never ranked as safe. `data_kind = screening_score`. This is a planning-support index, not a health-risk model.

**NAAQS comparison** (`backend/app/analytics/summary.py`, `backend/app/core/naaqs.py`)

```text
standard ← NAAQS row whose averaging period matches (24h ≡ daily, annual ≡ yearly)
IF none THEN comparable = false (e.g. a 1-hour value vs a 24-hour standard)
IF mean is null OR unit ≠ standard unit THEN comparable = false
exceeds = mean > industrial/residential/rural limit
```

Examples of limits (CPCB, 18 Nov 2009): PM2.5 40 annual / 60 24-hour; PM10 60 / 100; NO2 40 / 80; SO2 50 / 80 µg/m³; O3 100 (8-hour) / 180 (1-hour) µg/m³; CO 2 (8-hour) / 4 (1-hour) mg/m³.

---

## 3. Complexity

Let G be the number of grid cells, S the number of monitors, P the pixels in a window, and N_x × N_y the nodes of an IDW surface.

| Step | Cost |
| --- | --- |
| Grid generation | O(G) polygon intersections |
| Cell metrics | O(G × pixels per cell) raster reads, plus O(G) geometry operations |
| Station-in-cell | O(S × G) cover tests |
| IDW fill (A5) | O(G × S) |
| Built-up share per monitor-year | O(P) per monitor, P ≈ 10⁴ for a 1 km square at 10 m |
| IDW surface (A7) | O(N_x × N_y × S), vectorised one row at a time |
| Marching squares | O(N_x × N_y) per level |
| OLS / correlation | O(n·k²); n is at most a few dozen monitors |

## 4. Assumptions and limitations

- Results are **associations**. Meteorology, season, traffic, emission controls, stubble burning, topography, population, and monitor siting are not controlled unless supplied as predictors.
- Delhi has a few dozen monitors, so inferential statistics are fragile. Every test reports n and refuses to run below its minimum.
- The AQI series changes definition in 2025, and 2026 is partial.
- OSM can be incomplete. A missing industrial polygon is not evidence that there is no industry.
- The SAMPLE fixtures exist only to exercise the software and are labelled `SAMPLE` everywhere.

## 5. Code map

| Step | Module |
| --- | --- |
| Configuration | `backend/app/core/study_area.py`, `config/cities/delhi.yaml` |
| A1 Seed | `backend/app/workers/seed.py`, `backend/app/ingestion/sample_observations.py` |
| A2 Ingest | `backend/app/ingestion/air_quality_csv.py`, `units.py`, `timestamps.py` |
| A3 Hourly AQI | `backend/app/ingestion/cpcb_hourly_aqi.py`, `scripts/ingest_cpcb_hourly_aqi.py` |
| A4 Grid and metrics | `backend/app/geospatial/grid.py`, `crs.py`, `backend/app/remote_sensing/indices.py`, `worldcover.py` |
| A5 Station-in-cell, IDW, buffers | `backend/app/ingestion/grid_cpcb.py`, `backend/app/geospatial/idw.py`, `buffers.py` |
| A6 Annual AQI | `backend/app/analytics/daily_aqi.py`, `backend/app/ingestion/xkdr_daily.py` |
| A7 Built-up vs AQI | `backend/app/analytics/builtup_aqi_years.py`, `backend/app/remote_sensing/dynamic_world.py`, `backend/app/geospatial/contours.py` |
| A7b Change | `backend/app/analytics/builtup_concentration_change.py` |
| A8 Projection | `backend/app/analytics/builtup_projection.py` |
| A9 Local questions | `backend/app/analytics/local_questions.py`, `delhi_land_use.py` |
| A10 Statistics | `backend/app/analytics/correlation.py`, `regression.py`, `esda.py` |
| A11 Change, priority, NAAQS | `backend/app/analytics/change.py`, `priority.py`, `summary.py`, `backend/app/core/naaqs.py` |
| API | `backend/app/api/v1/*.py` |
| UI | `frontend/src/features/*` |
