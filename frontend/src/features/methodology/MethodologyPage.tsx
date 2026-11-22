export function MethodologyPage() {
  return (
    <article className="max-w-3xl space-y-4 text-sm leading-6">
      <h2 className="font-display text-3xl">Methods and limitations</h2>
      <p>
        This platform investigates associations between urban land cover and
        air-quality observations. It does not claim that a land-cover class
        causes pollution unless a defensible causal design is implemented.
      </p>
      <h3 className="font-display text-xl">Coordinate reference systems</h3>
      <p>
        Geometries are stored in EPSG:4326. Distances, buffers, and areas use
        Delhi’s projected CRS (EPSG:32643 UTM 43N). City CRS is configuration,
        not hardcoded map math.
      </p>
      <h3 className="font-display text-xl">Air quality</h3>
      <p>
        Default seed data are labeled SAMPLE monthly values at real CPCB-listed
        Delhi CAAQMS coordinates (2000–2026). They are not official CPCB
        measurements; continuous PM2.5 CAAQMS does not cover 2000–2010. Official
        historical records must be imported from CPCB CCR CSV/XLSX or OpenAQ
        when a key is configured. Duplicate (station, pollutant, timestamp,
        source) rows are skipped. Negative and sentinel values (999) are
        rejected.
      </p>
      <h3 className="font-display text-xl">Sparse stations</h3>
      <p>
        City-wide pollution maps and hotspot requests are disabled below eight
        stations. Delhi seed has twelve listed stations: observed means stay on
        the station layer, and other grid cells may show a labeled IDW estimate
        (not a measurement).
      </p>
      <h3 className="font-display text-xl">Remote sensing</h3>
      <p>
        NDVI = (NIR − Red) / (NIR + Red). NDBI = (SWIR − NIR) / (SWIR + NIR)
        after resampling 20 m SWIR. Sentinel-2 bands are not all 10 m. ESA
        WorldCover is the default land-cover product; 2020 and 2021 algorithm
        versions differ, so change maps mix classification differences and
        possible real change.
      </p>
      <h3 className="font-display text-xl">Confounders</h3>
      <p>
        Meteorology, seasonality, traffic, industry, topography, population, and
        monitor siting are not fully controlled in v1. Absence of an OSM
        industrial polygon is not evidence that no industry exists.
      </p>
    </article>
  );
}
