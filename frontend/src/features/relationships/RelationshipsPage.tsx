import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
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
import { apiGet, apiPost } from "@/lib/api";
import { useFilters } from "@/hooks/useFilters";
import { Alert, Card } from "@/components/ui/Card";
import { DataKindBadge } from "@/components/ui/Badge";
import { formatNumber } from "@/lib/format";
import { NdviBuiltUpChart } from "@/features/dashboard/NdviBuiltUpChart";
import { BuiltUpAqi } from "@/features/relationships/BuiltUpAqi";
import { type BuiltUpAqiYears, type YearStatistics, useBuiltUpAqiYears } from "@/features/relationships/builtupAqiYears";

const AXIS_LABEL = { fontSize: 12, fill: "#44403c" };

function GapTooltip({ active, payload }: { active?: boolean; payload?: { payload: YearStatistics }[] }) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <div className="rounded-md border border-stone-200 bg-white px-3 py-2 text-xs shadow-sm">
      <p className="font-medium">{row.year}</p>
      <p>Most built-up third ({formatNumber(row.most_built_share, 0)}% built-up): AQI {formatNumber(row.most_built_aqi, 0)}</p>
      <p>Least built-up third ({formatNumber(row.least_built_share, 0)}% built-up): AQI {formatNumber(row.least_built_aqi, 0)}</p>
      <p>Gap {formatNumber(row.gap, 0)} AQI · {row.n_each} stations each</p>
      <p>Pearson r = {formatNumber(row.pearson_r, 2)} (p={formatNumber(row.p_value, 3)}, n={row.n})</p>
      <p>{formatNumber(row.aqi_per_10_points, 1)} AQI per 10 points of built-up</p>
    </div>
  );
}

function BuiltUpAqiYearsCard({ data }: { data: BuiltUpAqiYears }) {
  const trend = data.city_trend;
  const first = trend[0];
  const last = trend[trend.length - 1];
  const ok = data.years.filter((row) => row.status === "ok");
  const gaps = ok.map((row) => row.gap ?? 0);
  const rs = ok.map((row) => row.pearson_r ?? 0);
  const allPositive = ok.length > 0 && gaps.every((gap) => gap > 0);
  return (
    <Card title={`Built-up growth and AQI, ${first.year}–${last.year}`} action={<DataKindBadge kind="statistical_estimate" />}>
      <p className="mb-3 text-sm text-stone-700">
        Built-up land inside Delhi went from {formatNumber(first.built_km2, 0)} km² in {first.year} to {formatNumber(last.built_km2, 0)} km² in {last.year}.
        {allPositive
          ? ` In every year, monitors in the most built-up third had a higher annual AQI than monitors in the least built-up third, by ${formatNumber(Math.min(...gaps), 0)} to ${formatNumber(Math.max(...gaps), 0)} points (Pearson r ${formatNumber(Math.min(...rs), 2)} to ${formatNumber(Math.max(...rs), 2)}).`
          : ""}
        {` The city mean station AQI moved from ${formatNumber(first.mean_aqi, 0)} to ${formatNumber(last.mean_aqi, 0)} over the same years.`}
      </p>
      <div className="grid gap-6 lg:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-medium text-stone-800">Built-up area and city mean AQI</h3>
          <div className="h-80">
            <ResponsiveContainer>
              <ComposedChart data={trend} margin={{ top: 8, right: 24, bottom: 24, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="year" label={{ value: "Year", position: "bottom", offset: 4, style: AXIS_LABEL }} />
                <YAxis yAxisId="built" width={64} domain={[0, "auto"]} label={{ value: "Built-up inside Delhi (km²)", angle: -90, position: "insideLeft", style: { ...AXIS_LABEL, textAnchor: "middle" } }} />
                <YAxis yAxisId="aqi" orientation="right" width={52} domain={[0, "auto"]} label={{ value: "Mean station AQI", angle: 90, position: "insideRight", style: { ...AXIS_LABEL, textAnchor: "middle" } }} />
                <Tooltip />
                <Legend verticalAlign="top" />
                <Bar yAxisId="built" dataKey="built_km2" name="Built-up (km²)" fill="#a8a29e" />
                <Line yAxisId="aqi" type="monotone" dataKey="mean_aqi" name="Mean station AQI" stroke="#b91c1c" strokeWidth={2} dot />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div>
          <h3 className="mb-2 text-sm font-medium text-stone-800">Annual AQI by built-up third of monitors</h3>
          <div className="h-80">
            <ResponsiveContainer>
              <BarChart data={data.years} margin={{ top: 8, right: 16, bottom: 24, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="year" label={{ value: "Year", position: "bottom", offset: 4, style: AXIS_LABEL }} />
                <YAxis width={52} domain={[0, "auto"]} label={{ value: "Mean annual AQI", angle: -90, position: "insideLeft", style: { ...AXIS_LABEL, textAnchor: "middle" } }} />
                <Tooltip content={<GapTooltip />} />
                <Legend verticalAlign="top" />
                <Bar dataKey="most_built_aqi" name="Most built-up third" fill="#b91c1c" />
                <Bar dataKey="least_built_aqi" name="Least built-up third" fill="#3f6b4a" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
      <p className="mt-3 text-sm text-stone-600">
        {data.aqi_method} Built-up is {data.land_cover} within {data.radius_km} km of each monitor; the area total uses the {data.boundary ?? "raster extent"}. Air quality: {data.air_quality}.
      </p>
      <p className="mt-2 text-sm text-stone-600">{data.caveat}</p>
    </Card>
  );
}

type ConcentrationPoint = {
  name: string;
  built_up_change: number;
  concentration_change: number;
  fitted_change: number | null;
};

type ConcentrationFit = {
  pollutant: string;
  unit: string;
  status: string;
  message?: string;
  caveat?: string;
  n?: number;
  r_squared?: number;
  params?: { const?: number; built_up_change?: number };
  pvalues?: { built_up_change?: number };
  pearson?: { coefficient?: number; p_value?: number };
  points?: ConcentrationPoint[];
};

type ConcentrationPayload = {
  baseline_year: number;
  recent_year: number;
  source: string;
  pollutants: ConcentrationFit[];
};

function fittedLine(fit: ConcentrationFit) {
  const intercept = fit.params?.const;
  const slope = fit.params?.built_up_change;
  const points = fit.points ?? [];
  if (intercept == null || slope == null || points.length < 2) return [];
  const changes = points.map((point) => point.built_up_change);
  const min = Math.min(...changes);
  const max = Math.max(...changes);
  return [
    { built_up_change: min, concentration_change: intercept + slope * min },
    { built_up_change: max, concentration_change: intercept + slope * max },
  ];
}

function ConcentrationScatter({ fit, baseline, recent }: { fit: ConcentrationFit; baseline: number; recent: number }) {
  const line = fittedLine(fit);
  return (
    <div>
      <h3 className="mb-2 text-sm font-medium text-stone-800">{fit.pollutant}</h3>
      {fit.status !== "ok" ? <p className="text-sm text-stone-600">{fit.message}</p> : null}
      {fit.status === "ok" ? (
        <>
          <div className="h-80">
            <ResponsiveContainer>
              <ScatterChart margin={{ top: 8, right: 16, bottom: 36, left: 16 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  type="number"
                  dataKey="built_up_change"
                  name={`Built-up change, ${baseline}–${recent} (percentage points)`}
                  unit=" pp"
                  label={{ value: `Built-up change, ${baseline}–${recent} (percentage points)`, position: "bottom", offset: 16, style: { fontSize: 12, fill: "#44403c" } }}
                />
                <YAxis
                  type="number"
                  dataKey="concentration_change"
                  name={`Change in annual ${fit.pollutant} (µg/m³)`}
                  width={64}
                  label={{ value: `Change in annual ${fit.pollutant} (µg/m³)`, angle: -90, position: "insideLeft", style: { fontSize: 12, fill: "#44403c", textAnchor: "middle" } }}
                />
                <Tooltip cursor={{ strokeDasharray: "3 3" }} />
                <Scatter name="Stations" data={fit.points ?? []} fill="#14532d" />
                <Scatter name="Fitted line" data={line} line={{ stroke: "#7f1d1d", strokeWidth: 2 }} shape={() => <g />} legendType="none" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-2 text-sm text-stone-700">
            Pearson r = {formatNumber(fit.pearson?.coefficient, 3)} (p={formatNumber(fit.pearson?.p_value, 3)}).
            Regression R² = {formatNumber(fit.r_squared, 3)} (p={formatNumber(fit.pvalues?.built_up_change, 3)}, n={fit.n}).
            Each additional percentage point of built-up is associated with {formatNumber(fit.params?.built_up_change, 2)} µg/m³.
          </p>
          <p className="mt-2 text-sm text-stone-600">{fit.caveat}</p>
        </>
      ) : null}
    </div>
  );
}

type ChangePoint = { name: string; built_up_change: number; aqi: number; fitted_aqi: number | null };

type ChangeFit = {
  status: string;
  message?: string;
  caveat?: string;
  n?: number;
  r_squared?: number;
  params?: { const?: number; built_up_change?: number };
  pvalues?: { built_up_change?: number };
  pearson?: { coefficient?: number; p_value?: number };
  points?: ChangePoint[];
  baseline_year?: number;
  observed_year?: number;
};

export function RelationshipsPage() {
  const { filters } = useFilters();
  const [showChange, setShowChange] = useState(false);
  const scatter = useQuery({
    queryKey: ["scatter-rel", filters.city],
    queryFn: () => apiGet<any>("/analysis/scatter", { city: filters.city, x: "mean_ndvi", y: "built_up_percentage" }),
  });
  const measured = useQuery({
    queryKey: ["builtup-concentration-change", filters.city],
    queryFn: () => apiGet<ConcentrationPayload>("/analysis/builtup-concentration-change", { city: filters.city }),
  });
  const model = useQuery({
    queryKey: ["builtup-aqi", filters.city],
    queryFn: () => apiPost<{ built_up_change?: ChangeFit }>(`/analysis/builtup-aqi?city=${filters.city}`, {}),
  });
  const builtUpYears = useBuiltUpAqiYears(filters.city);
  const change = model.data?.built_up_change;
  const line = useMemo(() => {
    const intercept = change?.params?.const;
    const slope = change?.params?.built_up_change;
    const points = change?.points ?? [];
    if (intercept == null || slope == null || points.length < 2) return [];
    const changes = points.map((point) => point.built_up_change);
    const min = Math.min(...changes);
    const max = Math.max(...changes);
    return [
      { built_up_change: min, aqi: intercept + slope * min },
      { built_up_change: max, aqi: intercept + slope * max },
    ];
  }, [change]);

  return (
    <div className="space-y-4">
      {builtUpYears.isLoading ? <p className="text-sm text-stone-600">Computing annual AQI and built-up share…</p> : null}
      {builtUpYears.isError ? <Alert>Could not load built-up growth and annual AQI.</Alert> : null}
      {builtUpYears.data?.status === "ok" ? <BuiltUpAqiYearsCard data={builtUpYears.data} /> : null}
      <Card title={`Measured change, ${measured.data?.baseline_year ?? 2018}–${measured.data?.recent_year ?? 2024}`} action={<DataKindBadge kind="statistical_estimate" />}>
        <p className="mb-3 text-sm text-stone-600">
          Each point is one Delhi monitor. Built-up share is Dynamic World class 6 within 1 km. Concentrations are hour-weighted annual means with at least six complete months. {measured.data?.source}
        </p>
        {measured.isLoading ? <p className="text-sm text-stone-600">Comparing station changes…</p> : null}
        {measured.isError ? <Alert>Could not load the measured built-up and concentration changes.</Alert> : null}
        <div className="grid gap-6 lg:grid-cols-2">
          {(measured.data?.pollutants ?? []).map((fit) => (
            <ConcentrationScatter key={fit.pollutant} fit={fit} baseline={measured.data?.baseline_year ?? 2018} recent={measured.data?.recent_year ?? 2024} />
          ))}
        </div>
      </Card>
      <BuiltUpAqi />
      <Alert>
        These plots use grid-cell land-cover and index values. Pollution is assigned only to cells that contain a monitor. Correlation is not causation. Meteorology is not controlled.
      </Alert>
      <Card title="NDVI vs built-up %" action={<DataKindBadge kind="aggregated" />}>
        <NdviBuiltUpChart points={scatter.data?.points ?? []} />
      </Card>
      <div className="flex gap-2">
        <button className="rounded-md bg-ink px-3 py-2 text-sm text-white" onClick={() => setShowChange(true)}>Run correlation</button>
        <button className="rounded-md border border-stone-300 px-3 py-2 text-sm" onClick={() => setShowChange(true)}>Run regression</button>
      </div>
      {showChange ? (
        <Card title="Built-up increase and 2026 AQI" action={<DataKindBadge kind="statistical_estimate" />}>
          {model.isLoading ? <p className="text-sm text-stone-600">Fitting the station relationship…</p> : null}
          {change?.status !== "ok" ? <p className="text-sm">{change?.message ?? "Not enough stations to fit built-up change against AQI."}</p> : null}
          {change?.status === "ok" ? (
            <>
              <div className="h-72">
                <ResponsiveContainer>
                  <ScatterChart margin={{ top: 8, right: 16, bottom: 32, left: 16 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" dataKey="built_up_change" name="Built-up change, 2017–2026 (percentage points)" unit=" pp" label={{ value: "Built-up change, 2017–2026 (percentage points)", position: "bottom", offset: 12, style: { fontSize: 12, fill: "#44403c" } }} />
                    <YAxis type="number" dataKey="aqi" name="Observed AQI, 22 Nov 2026" width={52} label={{ value: "Observed AQI, 22 Nov 2026", angle: -90, position: "insideLeft", style: { fontSize: 12, fill: "#44403c", textAnchor: "middle" } }} />
                    <Tooltip cursor={{ strokeDasharray: "3 3" }} />
                    <Scatter name="Stations" data={change.points ?? []} fill="#14532d" />
                    <Scatter name="Fitted line" data={line} line={{ stroke: "#7f1d1d", strokeWidth: 2 }} shape={() => <g />} legendType="none" />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
              <p className="mt-2 text-sm text-stone-700">
                Pearson r = {formatNumber(change.pearson?.coefficient, 3)} (p={formatNumber(change.pearson?.p_value, 3)}).
                Regression R² = {formatNumber(change.r_squared, 3)} (p={formatNumber(change.pvalues?.built_up_change, 3)}, n={change.n}).
                Each additional percentage point of built-up since {change.baseline_year} is associated with{" "}
                {formatNumber(change.params?.built_up_change, 2)} AQI points in {change.observed_year}.
              </p>
              <p className="mt-2 text-sm text-stone-600">{change.caveat}</p>
            </>
          ) : null}
        </Card>
      ) : null}
    </div>
  );
}
