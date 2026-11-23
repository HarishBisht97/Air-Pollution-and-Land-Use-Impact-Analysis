import { useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, TileLayer, GeoJSON, LayersControl, useMap } from "react-leaflet";
import { useQuery } from "@tanstack/react-query";
import L from "leaflet";
import { apiGet } from "@/lib/api";
import { useFilters } from "@/hooks/useFilters";
import { Alert, Card } from "@/components/ui/Card";
import { DataKindBadge } from "@/components/ui/Badge";
import { formatNumber } from "@/lib/format";
import { AQI_COLORS, classFill, partialYearNote, useAnnualAqiBands, useBuiltUpAqiYears } from "@/features/relationships/builtupAqiYears";
import { StationChangeTable } from "@/features/map/StationChangeTable";
import {
  AnnualBandLayer,
  AnnualStationsLayer,
  AqiPanes,
  BUILT_BASELINE,
  BUILT_NEW,
  BuiltUpOverlay,
  CPCB_CATEGORY_COLORS,
  ClassList,
  bandShades,
  type SurfaceMode,
  signed,
  useYearStations,
} from "@/features/map/annualAqiLayers";

const AQI_MISSING = "#78716c";

const GRID_BINS: { label: string; color: string; above: number }[] = [
  { label: "Above 120 µg/m³", color: "#7c2d12", above: 120 },
  { label: "Above 100 to 120 µg/m³", color: "#c2410c", above: 100 },
  { label: "Above 80 to 100 µg/m³", color: "#ea580c", above: 80 },
  { label: "80 µg/m³ or below", color: "#d97706", above: -Infinity },
];
const GRID_EMPTY = "#e7e5e4";

function gridFill(concentration: number | null | undefined) {
  if (concentration == null) return GRID_EMPTY;
  return GRID_BINS.find((bin) => concentration > bin.above)?.color ?? GRID_BINS[GRID_BINS.length - 1].color;
}

function aqiMarker(latlng: L.LatLngExpression, category: string | null) {
  const fill = AQI_COLORS[category ?? ""] ?? "#78716c";
  return L.circleMarker(latlng, { radius: 8, color: "#1c1917", fillColor: fill, fillOpacity: 0.92, weight: 1 });
}

function FlyTo({ bounds }: { bounds: L.LatLngBoundsExpression | null }) {
  const map = useMap();
  const fitted = useRef(false);
  useEffect(() => {
    if (bounds && !fitted.current) {
      map.fitBounds(bounds, { padding: [20, 20] });
      fitted.current = true;
    }
  }, [bounds, map]);
  return null;
}

export function MapPage() {
  const { filters } = useFilters();
  const [opacity, setOpacity] = useState(0.55);
  const city = useQuery({ queryKey: ["city", filters.city], queryFn: () => apiGet<any>("/cities/slug/current", { city: filters.city }) });
  const stations = useQuery({ queryKey: ["stations", filters.city], queryFn: () => apiGet<any>("/air-quality/stations", { city: filters.city }) });
  const spatial = useQuery({
    queryKey: ["spatial", filters],
    queryFn: () => apiGet<any>("/air-quality/spatial-distribution", { city: filters.city, pollutant: filters.pollutant, start: filters.from, end: filters.to }),
  });
  const roads = useQuery({ queryKey: ["roads", filters.city], queryFn: () => apiGet<any>("/roads", { city: filters.city, major_only: "true" }) });
  const parks = useQuery({ queryKey: ["parks", filters.city], queryFn: () => apiGet<any>("/green-spaces", { city: filters.city }) });
  const industry = useQuery({ queryKey: ["industry", filters.city], queryFn: () => apiGet<any>("/industrial", { city: filters.city }) });
  const grid = useQuery({ queryKey: ["grid", filters.city], queryFn: () => apiGet<any>("/grid", { city: filters.city, limit: 5000 }) });
  const cpcb = useQuery({ queryKey: ["cpcb-snapshot", filters.city], queryFn: () => apiGet<any>("/air-quality/cpcb-snapshot", { city: filters.city }) });
  const builtUp = useBuiltUpAqiYears(filters.city);
  const years = builtUp.data?.years ?? [];
  const [mode, setMode] = useState<SurfaceMode>("change");
  const [year, setYear] = useState<number | null>(null);
  const [baseChoice, setBaseChoice] = useState<number | null>(null);
  const firstYear = years[0]?.year ?? null;
  const lastYear = years[years.length - 1]?.year ?? null;
  const base = baseChoice ?? firstYear;
  const minYear = mode === "change" && base != null ? base + 1 : firstYear;
  const selectedYear = year == null ? lastYear : minYear != null ? Math.max(year, minYear) : year;
  const yearStats = years.find((item) => item.year === selectedYear);
  const yearCity = builtUp.data?.city_trend.find((item) => item.year === selectedYear);
  const baseCity = builtUp.data?.city_trend.find((item) => item.year === base);
  const previousCity = builtUp.data?.city_trend.find((item) => selectedYear != null && item.year === selectedYear - 1);
  const surface = useAnnualAqiBands(filters.city, selectedYear, base, mode);
  const classes = bandShades(surface.data).map((shade) => ({ ...shade, label: `${shade.min_aqi}–${shade.max_aqi}`, category: "" }));
  const yearStations = useYearStations(builtUp.data, selectedYear, base, mode);

  const cityBounds = useMemo(() => {
    const geometry = city.data?.boundary?.geometry;
    if (!geometry) return null;
    const rings = geometry.type === "MultiPolygon" ? geometry.coordinates.flat() : geometry.coordinates;
    const latlngs = (rings || []).flat().map((c: number[]) => [c[1], c[0]] as [number, number]);
    if (!latlngs.length) return null;
    return L.latLngBounds(latlngs);
  }, [city.data]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <DataKindBadge kind="aggregated" />
        {cpcb.data?.available ? (
          <Alert tone="info">
            The "CPCB stations" layer (off by default) is the air-quality index for {cpcb.data.observed_at} IST ({cpcb.data.station_count} stations, data.gov.in). {cpcb.data.note}
          </Alert>
        ) : null}
        {cpcb.isError || (cpcb.isSuccess && !cpcb.data?.available) ? (
          <Alert>{cpcb.data?.message ?? "CPCB snapshot is not loaded."}</Alert>
        ) : null}
      </div>
      <div className="grid gap-3 lg:grid-cols-[1fr_16rem]">
        <div className="h-[70vh] overflow-hidden rounded-xl border border-stone-200">
          <MapContainer center={[28.6139, 77.209]} zoom={11} scrollWheelZoom>
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <AqiPanes />
            <LayersControl position="topright">
              <LayersControl.Overlay checked name="City boundary">
                {city.data?.boundary ? <GeoJSON data={city.data.boundary} style={{ color: "#1c1917", weight: 2, fillOpacity: 0.04 }} /> : null}
              </LayersControl.Overlay>
              <LayersControl.Overlay checked name="AQI bands">
                {surface.data ? <AnnualBandLayer bands={surface.data} fillOpacity={opacity} /> : null}
              </LayersControl.Overlay>
              <LayersControl.Overlay checked name="Annual AQI stations">
                {yearStations && selectedYear != null ? (
                  <AnnualStationsLayer
                    stations={yearStations}
                    classes={classes}
                    year={selectedYear}
                    base={base}
                    mode={mode}
                    method={builtUp.data?.aqi_method ?? ""}
                    fillFor={(properties) =>
                      mode === "level"
                        ? CPCB_CATEGORY_COLORS[properties.category ?? ""] ?? AQI_MISSING
                        : classFill(properties.value, classes)
                    }
                  />
                ) : null}
              </LayersControl.Overlay>
              <LayersControl.Overlay name="Built-up growth (Dynamic World)">
                {builtUp.data && selectedYear != null ? <BuiltUpOverlay city={filters.city} year={selectedYear} bounds={builtUp.data.overlay_bounds} /> : null}
              </LayersControl.Overlay>
              <LayersControl.Overlay name="CPCB stations">
                {cpcb.data?.features?.length ? (
                  <GeoJSON
                    data={cpcb.data}
                    pointToLayer={(feature, latlng) => aqiMarker(latlng, feature.properties?.category)}
                    onEachFeature={(feature, layer) => {
                      const p = feature.properties;
                      const lines = Object.entries(p.subindices ?? {})
                        .map(([name, value]) => `${name} sub-index ${value}`)
                        .join("<br/>");
                      layer.bindPopup(
                        `<strong>${p.name}</strong><br/>AQI ${p.aqi ?? "—"} · ${p.category ?? "not enough pollutants"}<br/>Set by ${p.responsible_pollutant ?? "—"}<br/>${lines}<br/>${p.observed_at} IST<br/>${p.source}. Sub-indices, not concentrations.`,
                      );
                    }}
                  />
                ) : null}
              </LayersControl.Overlay>
              <LayersControl.Overlay name="Station concentration means">
                {spatial.data ? (
                  <GeoJSON
                    data={spatial.data}
                    pointToLayer={(_f, latlng) => L.circleMarker(latlng, { radius: 9, color: "#7c2d12", fillColor: "#b45309", fillOpacity: 0.9, weight: 2 })}
                    onEachFeature={(feature, layer) => {
                      const p = feature.properties;
                      layer.bindPopup(
                        `<strong>${p.name}</strong><br/>${p.pollutant}: ${p.mean ?? "—"} ${p.unit ?? ""}<br/>n=${p.count}<br/>source: station aggregate<br/>kind: ${p.data_kind}`,
                      );
                    }}
                  />
                ) : null}
              </LayersControl.Overlay>
              <LayersControl.Overlay name="Analysis grid">
                {grid.data ? (
                  <GeoJSON
                    data={grid.data}
                    style={(feature) => ({
                      color: "#57534e",
                      weight: 0.4,
                      fillColor: gridFill(feature?.properties?.mean_concentration),
                      fillOpacity: opacity,
                    })}
                    onEachFeature={(feature, layer) => {
                      const p = feature.properties;
                      const concentration =
                        p.mean_concentration == null
                          ? "No CPCB monitor in this cell"
                          : `PM2.5 ${formatNumber(p.mean_concentration)} µg/m³<br/>${(p.station_names ?? []).join(", ")}<br/>${p.observation_count} station-months<br/>${p.coverage ?? ""}<br/>${p.pollution_source ?? "CPCB"}`;
                      layer.bindPopup(
                        `<strong>${p.grid_code}</strong><br/>${concentration}<br/>NDVI: ${p.mean_ndvi ?? "—"}<br/>built-up %: ${p.built_up_percentage ?? "—"}`,
                      );
                    }}
                  />
                ) : null}
              </LayersControl.Overlay>
              <LayersControl.Overlay name="Major roads">
                {roads.data ? <GeoJSON data={roads.data} style={{ color: "#44403c", weight: 2 }} /> : null}
              </LayersControl.Overlay>
              <LayersControl.Overlay name="Green spaces">
                {parks.data ? <GeoJSON data={parks.data} style={{ color: "#166534", fillColor: "#3f6b4a", fillOpacity: 0.35 }} /> : null}
              </LayersControl.Overlay>
              <LayersControl.Overlay name="Industrial (mapped only)">
                {industry.data ? <GeoJSON data={industry.data} style={{ color: "#7c2d12", fillColor: "#b45309", fillOpacity: 0.4 }} /> : null}
              </LayersControl.Overlay>
            </LayersControl>
            <FlyTo bounds={cityBounds} />
          </MapContainer>
        </div>
        <Card title="Legend and layers">
          {builtUp.data && selectedYear != null ? (
            <div className="mb-4 border-b border-stone-200 pb-3">
              <div className="mb-2 flex overflow-hidden rounded-md border border-stone-300 text-xs">
                {(["change", "level"] as SurfaceMode[]).map((item) => (
                  <button
                    key={item}
                    type="button"
                    className={`flex-1 px-2 py-1 ${mode === item ? "bg-ink text-white" : "bg-white text-stone-700"}`}
                    onClick={() => setMode(item)}
                  >
                    {item === "change" ? "Change in AQI" : "AQI level"}
                  </button>
                ))}
              </div>
              {mode === "change" ? (
                <label className="mb-1 flex items-center justify-between text-xs text-stone-700">
                  Compared with
                  <select
                    className="rounded border border-stone-300 px-1 py-0.5"
                    value={base ?? ""}
                    onChange={(e) => setBaseChoice(Number(e.target.value))}
                  >
                    {years.slice(0, -1).map((item) => (
                      <option key={item.year} value={item.year}>{item.year}</option>
                    ))}
                  </select>
                </label>
              ) : null}
              <p className="text-xs font-medium text-stone-700">
                {mode === "change" ? `Change in annual AQI, ${base} to ${selectedYear}` : `Annual AQI, ${selectedYear}`}
              </p>
              {partialYearNote(yearCity) ? <p className="text-xs text-stone-600">{partialYearNote(yearCity)}</p> : null}
              <input
                className="w-full"
                type="range"
                min={minYear ?? years[0].year}
                max={years[years.length - 1].year}
                step={1}
                value={selectedYear}
                onChange={(e) => setYear(Number(e.target.value))}
                aria-label="Year"
              />
              <div className="flex justify-between text-[10px] text-stone-500">
                <span>{minYear ?? years[0].year}</span>
                <span>{years[years.length - 1].year}</span>
              </div>
              <ClassList classes={classes} />
              <p className="mt-1 text-[11px] text-stone-600">
                {mode === "change"
                  ? "Green is the lowest change in this comparison. Dark red is the highest. Eight filled bands, drawn the same way as Station AQI in 2026."
                  : "Green is this year’s lowest estimated AQI. Dark red is the highest. Eight filled bands, drawn the same way as Station AQI in 2026."}
              </p>
              <dl className="mt-2 space-y-1 text-xs text-stone-700">
                {mode === "change" && surface.data?.mode === "change" ? (
                  <div className="flex justify-between">
                    <dt>Monitors improved / worsened</dt>
                    <dd>
                      {surface.data.improved} / {surface.data.worsened} (median {signed(surface.data.median_change ?? 0)})
                    </dd>
                  </div>
                ) : null}
                <div className="flex justify-between">
                  <dt>Change in mean AQI</dt>
                  <dd>
                    {mode === "change" && baseCity?.mean_aqi != null && yearCity?.mean_aqi != null
                      ? `${signed(yearCity.mean_aqi - baseCity.mean_aqi)} vs ${baseCity.year}`
                      : previousCity?.mean_aqi != null && yearCity?.mean_aqi != null
                        ? `${signed(yearCity.mean_aqi - previousCity.mean_aqi)} vs ${previousCity.year}`
                        : "—"}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt>Built-up inside Delhi</dt>
                  <dd>
                    {formatNumber(yearCity?.built_km2, 0)} km²
                    {baseCity?.built_km2 != null && yearCity?.built_km2 != null && selectedYear !== baseCity.year
                      ? ` (${signed(yearCity.built_km2 - baseCity.built_km2)} since ${baseCity.year})`
                      : ""}
                  </dd>
                </div>
                <div className="flex justify-between"><dt>Mean station AQI</dt><dd>{formatNumber(yearCity?.mean_aqi, 0)} ({yearCity?.stations} stations)</dd></div>
                <div className="flex justify-between"><dt>Most built-up nearby</dt><dd>AQI {formatNumber(yearStats?.most_built_aqi, 0)}</dd></div>
                <div className="flex justify-between"><dt>Least built-up nearby</dt><dd>AQI {formatNumber(yearStats?.least_built_aqi, 0)}</dd></div>
                <div className="flex justify-between"><dt>Pearson r</dt><dd>{formatNumber(yearStats?.pearson_r, 2)}</dd></div>
              </dl>
              {yearStats?.gap != null ? (
                <p className="mt-2 text-xs text-stone-600">
                  In {selectedYear}, monitors with the most built-up land nearby (about {formatNumber(yearStats.most_built_share, 0)}% within 1 km) averaged {formatNumber(yearStats.gap, 0)} AQI points more than monitors with the least (about {formatNumber(yearStats.least_built_share, 0)}%). This is an association, not a measured effect.
                </p>
              ) : null}
              <p className="mt-2 text-[11px] text-stone-600">
                {surface.data?.method} {surface.data ? `${surface.data.stations} monitors in ${surface.data.year}.` : ""}
              </p>
              <p className="mt-3 text-xs font-medium text-stone-700">Built-up growth layer (off by default)</p>
              <ul className="mt-1 space-y-1 text-sm">
                <li><span className="mr-2 inline-block h-3 w-3" style={{ backgroundColor: BUILT_BASELINE }} /> Built-up in {builtUp.data.baseline_year}</li>
                <li><span className="mr-2 inline-block h-3 w-3" style={{ backgroundColor: BUILT_NEW }} /> Built-up since {builtUp.data.baseline_year}</li>
              </ul>
            </div>
          ) : null}
          {builtUp.isError ? <p className="mb-3 text-xs text-stone-600">Built-up and annual AQI are not available for this city.</p> : null}
          <label className="text-xs">
            Fill opacity (AQI bands and grid)
            <input className="w-full" type="range" min={0.15} max={0.9} step={0.05} value={opacity} onChange={(e) => setOpacity(Number(e.target.value))} />
          </label>
          <p className="mt-3 text-xs font-medium text-stone-700">CPCB snapshot station category</p>
          <ul className="mt-1 space-y-1 text-sm">
            {Object.entries(AQI_COLORS).map(([label, color]) => (
              <li key={label}><span className="mr-2 inline-block h-3 w-3 rounded-full" style={{ backgroundColor: color }} /> {label}</li>
            ))}
            <li><span className="mr-2 inline-block h-3 w-3 rounded-full" style={{ backgroundColor: AQI_MISSING }} /> Not enough pollutants</li>
          </ul>
          <p className="mt-3 text-xs font-medium text-stone-700">PM2.5 in cells with a monitor</p>
          <ul className="mt-1 space-y-1 text-sm">
            {GRID_BINS.map((bin) => (
              <li key={bin.label}><span className="mr-2 inline-block h-3 w-3" style={{ backgroundColor: bin.color }} /> {bin.label}</li>
            ))}
            <li><span className="mr-2 inline-block h-3 w-3 border border-stone-300" style={{ backgroundColor: GRID_EMPTY }} /> No value</li>
          </ul>
          <p className="mt-3 text-xs font-medium text-stone-700">Other layers</p>
          <ul className="mt-1 space-y-1 text-sm">
            <li><span className="mr-2 inline-block h-0.5 w-3 bg-stone-700 align-middle" /> Major roads</li>
            <li><span className="mr-2 inline-block h-3 w-3" style={{ backgroundColor: "#3f6b4a" }} /> Green spaces</li>
            <li><span className="mr-2 inline-block h-3 w-3" style={{ backgroundColor: "#b45309" }} /> Industrial sites</li>
            <li><span className="mr-2 inline-block h-3 w-3 rounded-full border-2" style={{ backgroundColor: "#b45309", borderColor: "#7c2d12" }} /> Station concentration mean</li>
            <li><span className="mr-2 inline-block h-0.5 w-3 bg-stone-900 align-middle" /> City boundary</li>
            <li>Basemap: OpenStreetMap</li>
          </ul>
          <p className="mt-3 text-xs text-stone-600">
            Annual station circles are the mean daily CPCB index computed from XKDR daily concentrations. The snapshot layer is the CPCB index for one hour. Built-up is Dynamic World class 6 inside the GAUL Delhi boundary. Grid colour is the hour-weighted CPCB PM2.5 mean from the XKDR extract{grid.data?.coverage ? ` (${grid.data.coverage})` : ""}, in µg/m³, for {formatNumber(grid.data?.cells_with_monitor, 0)} cells that contain a monitor. Cells without a monitor are empty. Roads, parks, and industrial sites are OpenStreetMap. {industry.data?.disclaimer}
          </p>
          <p className="mt-2 text-xs">CPCB index stations: {formatNumber(cpcb.data?.station_count, 0)}. Concentration stations: {formatNumber(stations.data?.features?.length, 0)}.</p>
        </Card>
      </div>
      {builtUp.data ? <StationChangeTable data={builtUp.data} selectedYear={selectedYear} /> : null}
    </div>
  );
}
