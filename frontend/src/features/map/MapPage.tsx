import { useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, TileLayer, GeoJSON, ImageOverlay, LayerGroup, LayersControl, useMap } from "react-leaflet";
import { useQuery } from "@tanstack/react-query";
import L from "leaflet";
import { apiGet, downloadUrl } from "@/lib/api";
import { useFilters } from "@/hooks/useFilters";
import { Alert, Card } from "@/components/ui/Card";
import { DataKindBadge } from "@/components/ui/Badge";
import { formatNumber } from "@/lib/format";
import { useBuiltUpAqiYears } from "@/features/relationships/builtupAqiYears";

const AQI_COLORS: Record<string, string> = {
  Good: "#3f6b4a",
  Satisfactory: "#65a30d",
  Moderate: "#ca8a04",
  Poor: "#ea580c",
  "Very Poor": "#b91c1c",
  Severe: "#7f1d1d",
};
const AQI_MISSING = "#78716c";
const BUILT_BASELINE = "rgba(120, 113, 108, 0.6)";
const BUILT_NEW = "rgba(220, 38, 38, 0.82)";

const GRID_BINS: { label: string; color: string; above: number }[] = [
  { label: "Above 100 µg/m³", color: "#7c2d12", above: 100 },
  { label: "Above 80 to 100 µg/m³", color: "#c2410c", above: 80 },
  { label: "Above 60 to 80 µg/m³", color: "#ea580c", above: 60 },
  { label: "60 µg/m³ or below", color: "#d97706", above: -Infinity },
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
  const [year, setYear] = useState<number | null>(null);
  const selectedYear = year ?? years[years.length - 1]?.year ?? null;
  const yearStats = years.find((item) => item.year === selectedYear);
  const yearCity = builtUp.data?.city_trend.find((item) => item.year === selectedYear);
  const baselineCity = builtUp.data?.city_trend[0];
  const yearStations = useMemo(() => {
    if (!builtUp.data || selectedYear == null) return null;
    const key = String(selectedYear);
    return {
      type: "FeatureCollection" as const,
      features: builtUp.data.features
        .filter((feature) => feature.properties.years[key])
        .map((feature) => ({ ...feature, properties: { name: feature.properties.name, ...feature.properties.years[key] } })),
    };
  }, [builtUp.data, selectedYear]);

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
            <LayersControl position="topright">
              <LayersControl.Overlay checked name="City boundary">
                {city.data?.boundary ? <GeoJSON data={city.data.boundary} style={{ color: "#1c1917", weight: 2, fillOpacity: 0.04 }} /> : null}
              </LayersControl.Overlay>
              <LayersControl.Overlay checked name="Built-up and annual AQI">
                <LayerGroup>
                  {builtUp.data && selectedYear != null ? (
                    <ImageOverlay
                      url={downloadUrl(`/analysis/builtup-overlay/${selectedYear}`, { city: filters.city })}
                      bounds={builtUp.data.overlay_bounds}
                      opacity={0.85}
                    />
                  ) : null}
                  {yearStations ? (
                    <GeoJSON
                      key={`annual-aqi-${selectedYear}`}
                      data={yearStations as any}
                      pointToLayer={(feature, latlng) => aqiMarker(latlng, feature.properties?.category)}
                      onEachFeature={(feature, layer) => {
                        const p = feature.properties;
                        layer.bindPopup(
                          `<strong>${p.name}</strong><br/>Annual AQI ${selectedYear}: ${p.aqi} · ${p.category}<br/>Built-up within 1 km: ${p.built ?? "—"}%<br/>${p.days} valid days, ${p.poor_or_worse_days} at Poor or worse<br/>${builtUp.data?.aqi_method ?? ""}`,
                        );
                      }}
                    />
                  ) : null}
                </LayerGroup>
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
                      const estimateNote = p.pollution_assignment === "idw_estimate" ? "IDW estimate, not a measurement" : p.pollution_assignment;
                      layer.bindPopup(
                        `<strong>${p.grid_code}</strong><br/>obs count: ${p.observation_count}<br/>mean conc: ${p.mean_concentration ?? "—"}<br/>NDVI: ${p.mean_ndvi ?? "—"}<br/>built-up %: ${p.built_up_percentage ?? "—"}<br/>${estimateNote}`,
                      );
                    }}
                  />
                ) : null}
              </LayersControl.Overlay>
              <LayersControl.Overlay checked name="Major roads">
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
              <p className="text-xs font-medium text-stone-700">Built-up and annual AQI, {selectedYear}</p>
              <input
                className="w-full"
                type="range"
                min={years[0].year}
                max={years[years.length - 1].year}
                step={1}
                value={selectedYear}
                onChange={(e) => setYear(Number(e.target.value))}
                aria-label="Year"
              />
              <div className="flex justify-between text-[10px] text-stone-500">
                <span>{years[0].year}</span>
                <span>{years[years.length - 1].year}</span>
              </div>
              <ul className="mt-2 space-y-1 text-sm">
                <li><span className="mr-2 inline-block h-3 w-3" style={{ backgroundColor: BUILT_BASELINE }} /> Built-up in {builtUp.data.baseline_year}</li>
                <li><span className="mr-2 inline-block h-3 w-3" style={{ backgroundColor: BUILT_NEW }} /> Built-up since {builtUp.data.baseline_year}</li>
              </ul>
              <dl className="mt-2 space-y-1 text-xs text-stone-700">
                <div className="flex justify-between">
                  <dt>Built-up inside Delhi</dt>
                  <dd>
                    {formatNumber(yearCity?.built_km2, 0)} km²
                    {baselineCity?.built_km2 != null && yearCity?.built_km2 != null && selectedYear !== baselineCity.year
                      ? ` (${yearCity.built_km2 >= baselineCity.built_km2 ? "+" : ""}${formatNumber(yearCity.built_km2 - baselineCity.built_km2, 0)} since ${baselineCity.year})`
                      : ""}
                  </dd>
                </div>
                <div className="flex justify-between"><dt>Mean station AQI</dt><dd>{formatNumber(yearCity?.mean_aqi, 0)} ({yearCity?.stations} stations)</dd></div>
                <div className="flex justify-between"><dt>Most built-up third</dt><dd>AQI {formatNumber(yearStats?.most_built_aqi, 0)}</dd></div>
                <div className="flex justify-between"><dt>Least built-up third</dt><dd>AQI {formatNumber(yearStats?.least_built_aqi, 0)}</dd></div>
                <div className="flex justify-between"><dt>Pearson r</dt><dd>{formatNumber(yearStats?.pearson_r, 2)}</dd></div>
              </dl>
              {yearStats?.gap != null ? (
                <p className="mt-2 text-xs text-stone-600">
                  In {selectedYear}, monitors in the most built-up third (about {formatNumber(yearStats.most_built_share, 0)}% built-up within 1 km) averaged {formatNumber(yearStats.gap, 0)} AQI points more than monitors in the least built-up third (about {formatNumber(yearStats.least_built_share, 0)}%). Station circles use the CPCB category of the annual mean AQI. This is an association, not a measured effect.
                </p>
              ) : null}
            </div>
          ) : null}
          {builtUp.isError ? <p className="mb-3 text-xs text-stone-600">Built-up and annual AQI are not available for this city.</p> : null}
          <label className="text-xs">
            Grid opacity
            <input className="w-full" type="range" min={0.15} max={0.9} step={0.05} value={opacity} onChange={(e) => setOpacity(Number(e.target.value))} />
          </label>
          <p className="mt-3 text-xs font-medium text-stone-700">Station AQI category (annual and snapshot layers)</p>
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
            Annual station circles are the mean daily CPCB index computed from XKDR daily concentrations. The snapshot layer is the CPCB index for one hour. Built-up is Dynamic World class 6 inside the GAUL Delhi boundary. Grid colour is the XKDR PM2.5 mean, in µg/m³, only for a cell that contains a monitor. Cells without a monitor are left empty. Roads, parks, and industrial sites are OpenStreetMap. {industry.data?.disclaimer}
          </p>
          <p className="mt-2 text-xs">CPCB index stations: {formatNumber(cpcb.data?.station_count, 0)}. Concentration stations: {formatNumber(stations.data?.features?.length, 0)}.</p>
        </Card>
      </div>
    </div>
  );
}
