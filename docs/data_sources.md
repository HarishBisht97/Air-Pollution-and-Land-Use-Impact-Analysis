# Data sources

| Dataset | Access in this project | License / attribution | Limitation |
| --- | --- | --- | --- |
| CPCB CAAQMS / CCR | Manual CSV import only | Government public data; portal ToS | No official bulk API; captcha dashboard. **Not scraped.** |
| OpenAQ v3 | Optional if `OPENAQ_API_KEY` is set | Respect originating licenses | May be incomplete vs CPCB |
| Sentinel-2 L2A | Optional CDSE or GEE; local rasters | Copernicus open use + attribution | Cloud, season, and missing years |
| ESA WorldCover 10 m | Intended default LULC product | CC-BY 4.0 | 2020 vs 2021 algorithm change |
| OpenStreetMap | Intended for roads, parks, industry | ODbL | Industry/park incompleteness |
| NAAQS 2009 | Embedded standards table | CPCB notification | Averaging period must match |
| Sample fixtures | Seeded on startup | Development only | **Not measurements** |

## Delhi air quality

The Delhi config lists twelve CPCB CAAQMS directory locations (for example Anand Vihar, R K Puram, Mandir Marg). Seeded monthly values at those coordinates are labeled `SAMPLE_CPCB_STYLE` and are not official measurements. Continuous PM2.5 CAAQMS does not cover 2000–2010.

## How to obtain official observations

1. Open https://airquality.cpcb.gov.in/ccr/
2. Use Data Repository / station report for Delhi and the station you need.
3. Export CSV/XLSX for the averaging period you need (hourly or 24-hour).
4. Import through the Datasets page, or `scripts/ingest_air_quality.py --city delhi`.

## Satellite setup (optional)

- Copernicus Data Space: create an OAuth client; set `CDSE_CLIENT_ID` / `CDSE_CLIENT_SECRET`.
- Google Earth Engine: set `GEE_SERVICE_ACCOUNT` to a service-account JSON path.
- Without credentials, use `data/sample/rasters/` (generated at seed, tagged SAMPLE).
