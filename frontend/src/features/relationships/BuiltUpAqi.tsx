import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { GeoJSON, MapContainer, TileLayer } from "react-leaflet";
import {
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import L from "leaflet";
import { apiPost } from "@/lib/api";
import { useFilters } from "@/hooks/useFilters";
import { Alert, Card, Skeleton } from "@/components/ui/Card";
import { DataKindBadge } from "@/components/ui/Badge";
import { formatNumber } from "@/lib/format";

const AQI_COLORS: Record<string, string> = {
  Good: "#14532d",
  Satisfactory: "#4d7c0f",
  Moderate: "#ea580c",
  Poor: "#dc2626",
  "Very Poor": "#b91c1c",
  Severe: "#7f1d1d",
};
const AQI_MISSING = "#78716c";

type YearRow = {
  year: number;
  mean_built_up: number;
  mean_implied_aqi: number;
  observed_year: boolean;
  estimate: boolean;
};

type Shade = { min_aqi: number; max_aqi: number; fill: string };

type Feature = {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: {
    name: string;
    observed_aqi: number;
    observed_category: string;
    built_up: Record<string, number>;
    implied_aqi: Record<string, number>;
    implied_category: Record<string, string>;
  };
};

type ContourCollection = {
  type: "FeatureCollection";
  features: { type: "Feature"; geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon; properties: Shade & { category?: string } }[];
};

type Model = {
  status: string;
  message?: string;
  caveat?: string;
  n?: number;
  r_squared?: number;
  aqi_per_10_built_up_points?: number;
  pvalues?: { built_up_2026?: number };
  params?: { const?: number; built_up_2026?: number };
  observed_year?: number;
  years?: YearRow[];
  features?: Feature[];
  contours?: Record<string, ContourCollection>;
  boundary?: GeoJSON.Feature;
};

export function BuiltUpAqi() {
  const { filters } = useFilters();
  const [year, setYear] = useState(2026);
  const model = useQuery({
    queryKey: ["builtup-aqi", filters.city],
    queryFn: () => apiPost<Model>(`/analysis/builtup-aqi?city=${filters.city}`, {}),
  });

  const data = model.data;
  const points = useMemo(() => {
    return (data?.features ?? []).map((feature) => ({
      name: feature.properties.name,
      builtUp: feature.properties.built_up["2026"],
      aqi: feature.properties.observed_aqi,
      category: feature.properties.observed_category,
    }));
  }, [data]);
  const line = useMemo(() => {
    const intercept = data?.params?.const;
    const slope = data?.params?.built_up_2026;
    if (intercept == null || slope == null || points.length < 2) return [];
    const shares = points.map((point) => point.builtUp);
    const min = Math.min(...shares);
    const max = Math.max(...shares);
    return [
      { builtUp: min, aqi: intercept + slope * min },
      { builtUp: max, aqi: intercept + slope * max },
    ];
  }, [data, points]);
  const mapped = useMemo(() => {
    const key = String(year);
    const observed = year === (data?.observed_year ?? 2026);
    return {
      type: "FeatureCollection" as const,
      features: (data?.features ?? []).map((feature) => ({
        ...feature,
        properties: {
          ...feature.properties,
          year,
          built_up_selected: feature.properties.built_up[key],
          aqi_selected: observed ? feature.properties.observed_aqi : feature.properties.implied_aqi[key],
          category_selected: observed ? feature.properties.observed_category : feature.properties.implied_category[key],
          kind: observed ? "Observed CPCB AQI" : "Implied from the 2026 built-up slope",
        },
      })),
    };
  }, [data, year]);
  const shades = useMemo(() => {
    return [...(data?.contours?.[String(year)]?.features ?? [])]
      .map((feature) => feature.properties)
      .filter((properties, index, all) => all.findIndex((item) => item.min_aqi === properties.min_aqi) === index)
      .sort((left, right) => left.min_aqi - right.min_aqi);
  }, [data, year]);

  if (model.isLoading) return <Skeleton className="h-80" />;
  if (model.isError) return <Alert>Could not fit built-up area against AQI. Check that the API is running, then reload.</Alert>;
  if (!data || data.status !== "ok") {
    return <Alert>{data?.message ?? "Not enough stations with both an AQI and a built-up share."}</Alert>;
  }

  const observedYear = data.observed_year ?? 2026;
  const showingEstimate = year !== observedYear;

  return (
    <div className="space-y-4">
      <Alert>{data.caveat}</Alert>
      <Card title="Built-up share and AQI, 2026" action={<DataKindBadge kind="statistical_estimate" />}>
        <div className="h-80">
          <ResponsiveContainer>
            <ScatterChart margin={{ top: 8, right: 16, bottom: 28, left: 16 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" dataKey="builtUp" name="Built-up share within 1 km, 2026 (%)" unit="%" domain={["dataMin - 2", "dataMax + 2"]} label={{ value: "Built-up share within 1 km, 2026 (%)", position: "bottom", offset: 8, style: { fontSize: 12, fill: "#44403c" } }} />
              <YAxis type="number" dataKey="aqi" name="Observed AQI, 22 Nov 2026" domain={["dataMin - 10", "dataMax + 10"]} width={52} label={{ value: "Observed AQI, 22 Nov 2026", angle: -90, position: "insideLeft", style: { fontSize: 12, fill: "#44403c", textAnchor: "middle" } }} />
              <Tooltip cursor={{ strokeDasharray: "3 3" }} />
              <Scatter name="Stations" data={points}>
                {points.map((point) => (
                  <Cell key={point.name} fill={AQI_COLORS[point.category] ?? AQI_MISSING} />
                ))}
              </Scatter>
              <Scatter name="Fitted line" data={line} line={{ stroke: "#1c1917", strokeWidth: 2 }} shape={() => <g />} legendType="none" />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-2 text-sm text-stone-700">
          Each additional 10 percentage points of built-up area is associated with{" "}
          <strong>{formatNumber(data.aqi_per_10_built_up_points, 1)} AQI points</strong>
          {" "}(p={formatNumber(data.pvalues?.built_up_2026, 3)}, R²={formatNumber(data.r_squared, 3)}, n={data.n}).
        </p>
      </Card>
      <Card title="Built-up and implied AQI, 2017–2026" action={<DataKindBadge kind="statistical_estimate" />}>
        <div className="h-80">
          <ResponsiveContainer>
            <ComposedChart data={data.years ?? []} margin={{ top: 28, right: 24, bottom: 24, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="year" label={{ value: "Year", position: "bottom", offset: 4, style: { fontSize: 12, fill: "#44403c" } }} />
              <YAxis yAxisId="built" unit="%" domain={[0, 100]} width={56} label={{ value: "Mean built-up share (%)", angle: -90, position: "insideLeft", style: { fontSize: 12, fill: "#44403c", textAnchor: "middle" } }} />
              <YAxis yAxisId="aqi" orientation="right" width={48} label={{ value: "Implied mean AQI", angle: 90, position: "insideRight", style: { fontSize: 12, fill: "#44403c", textAnchor: "middle" } }} />
              <Tooltip />
              <Legend verticalAlign="top" />
              <Line yAxisId="built" type="monotone" dataKey="mean_built_up" name="Mean built-up %" stroke="#57534e" strokeWidth={2} dot />
              <Line
                yAxisId="aqi"
                type="monotone"
                dataKey="mean_implied_aqi"
                name="Implied mean AQI"
                stroke="#b45309"
                strokeWidth={2}
                dot={(props: { cx?: number; cy?: number; payload?: YearRow }) => {
                  const { cx, cy, payload } = props;
                  if (cx == null || cy == null) return <g />;
                  const observed = payload?.observed_year;
                  return <circle cx={cx} cy={cy} r={observed ? 6 : 3} fill={observed ? "#1c1917" : "#b45309"} />;
                }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-2 text-sm text-stone-600">
          The dark point is {observedYear}, the year with observed AQI. Earlier points apply that slope to the built-up share measured that year.
        </p>
      </Card>
      <Card title={`Station AQI in ${year}`} action={<DataKindBadge kind={showingEstimate ? "statistical_estimate" : "aggregated"} />}>
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <label className="text-sm text-stone-700" htmlFor="builtup-year">Year</label>
          <input
            id="builtup-year"
            type="range"
            min={2017}
            max={2026}
            step={1}
            value={year}
            onChange={(event) => setYear(Number(event.target.value))}
            className="w-56"
          />
          <span className="text-sm font-medium">{year}</span>
          <span className="text-sm text-stone-600">
            {showingEstimate
              ? "Shaded areas use the AQI implied by the built-up slope."
              : "Shaded areas use the observed CPCB AQI."}
          </span>
        </div>
        <div className="h-[28rem] overflow-hidden rounded-xl border border-stone-200">
          <MapContainer center={[28.6139, 77.209]} zoom={11} scrollWheelZoom className="h-full w-full">
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {data.contours?.[String(year)] ? (
              <GeoJSON
                key={`contour-${year}`}
                data={data.contours[String(year)]}
                style={(feature) => ({
                  color: "#1c1917",
                  weight: 0.6,
                  opacity: 0.45,
                  fillColor: feature?.properties?.fill ?? AQI_MISSING,
                  fillOpacity: 0.72,
                })}
                onEachFeature={(feature, layer) => {
                  const upper = feature.properties?.max_aqi;
                  const range = upper == null ? `${feature.properties?.min_aqi}+` : `${feature.properties?.min_aqi}–${upper}`;
                  layer.bindTooltip(`AQI ${range}`, { sticky: true });
                }}
              />
            ) : null}
            {data.boundary ? (
              <GeoJSON data={data.boundary} style={{ color: "#1c1917", weight: 1.5, fillOpacity: 0 }} />
            ) : null}
            <GeoJSON
              key={year}
              data={mapped}
              pointToLayer={(feature, latlng) => {
                const fill = AQI_COLORS[feature.properties?.category_selected] ?? AQI_MISSING;
                return L.circleMarker(latlng, { radius: 8, color: "#1c1917", weight: 1, fillColor: fill, fillOpacity: 0.92 });
              }}
              onEachFeature={(feature, layer) => {
                const p = feature.properties;
                layer.bindPopup(
                  `<strong>${p.name}</strong><br/>${year} built-up: ${formatNumber(p.built_up_selected, 1)}%<br/>Observed 2026 AQI: ${formatNumber(p.observed_aqi, 0)} (${p.observed_category})<br/>Implied AQI: ${formatNumber(p.aqi_selected, 0)} (${p.category_selected})<br/>${p.kind}`,
                );
              }}
            />
          </MapContainer>
        </div>
        <ul className="mt-3 flex flex-wrap gap-3 text-xs text-stone-700">
          {shades.map((shade) => (
            <li key={shade.min_aqi}>
              <span className="mr-1 inline-block h-3 w-3" style={{ backgroundColor: shade.fill }} />
              {shade.min_aqi}–{shade.max_aqi}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
