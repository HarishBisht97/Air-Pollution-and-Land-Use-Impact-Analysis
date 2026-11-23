import { useState } from "react";
import { GeoJSON, MapContainer, TileLayer } from "react-leaflet";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { apiGet } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { useFilters } from "@/hooks/useFilters";
import { Alert, Card, EmptyState, Kpi, Skeleton } from "@/components/ui/Card";
import { DataKindBadge, SampleBadge } from "@/components/ui/Badge";
import { NdviBuiltUpChart } from "@/features/dashboard/NdviBuiltUpChart";
import { CpcbSnapshotSummary } from "@/features/air-quality/CpcbSnapshotSummary";
import { gapSummary } from "@/features/relationships/BuiltUpAqiYearsCharts";
import { classFill, partialYearNote, useAnnualAqiBands, useBuiltUpAqiYears } from "@/features/relationships/builtupAqiYears";
import { BuiltUpAqiYearsCard, MeasuredConcentrationChange } from "@/features/relationships/RelationshipsPage";
import { LandUseContrastChart, useLandUseContrasts } from "@/features/scenarios/LandUseScenariosPage";
import { StationChangeTable } from "@/features/map/StationChangeTable";
import {
  AnnualBandLayer,
  AnnualStationsLayer,
  AqiPanes,
  bandShades,
  BUILT_BASELINE,
  BUILT_NEW,
  BuiltUpOverlay,
  CPCB_CATEGORY_COLORS,
  type SurfaceMode,
  signed,
  useYearStations,
} from "@/features/map/annualAqiLayers";

function AnnualMap({ city }: { city: string }) {
  const builtUp = useBuiltUpAqiYears(city);
  const boundary = useQuery({ queryKey: ["city", city], queryFn: () => apiGet<any>("/cities/slug/current", { city }) });
  const data = builtUp.data;
  const years = data?.city_trend.map((row) => row.year) ?? [];
  const [mode, setMode] = useState<SurfaceMode>("change");
  const [year, setYear] = useState<number | null>(null);
  const [showBuilt, setShowBuilt] = useState(false);
  const first = years[0] ?? null;
  const last = years[years.length - 1] ?? null;
  const minYear = mode === "change" && first != null ? first + 1 : first;
  const selected = year == null ? last : minYear != null ? Math.max(year, minYear) : year;
  const surface = useAnnualAqiBands(city, selected, first, mode);
  const shades = bandShades(surface.data);
  const classes = shades.map((shade) => ({ ...shade, label: `${shade.min_aqi}–${shade.max_aqi}`, category: "" }));
  const stations = useYearStations(data, selected, first, mode);
  if (!data || selected == null || first == null) return null;
  const yearCity = data.city_trend.find((row) => row.year === selected);
  const baseCity = data.city_trend.find((row) => row.year === first);
  return (
    <>
    <Card title="Annual AQI across Delhi" action={<DataKindBadge kind="statistical_estimate" />}>
      <div className="mb-3 flex flex-wrap items-end gap-4">
        <div className="flex overflow-hidden rounded-md border border-stone-300 text-sm">
          {(["change", "level"] as SurfaceMode[]).map((item) => (
            <button key={item} type="button" className={`px-3 py-1.5 ${mode === item ? "bg-ink text-white" : "bg-white text-stone-700"}`} onClick={() => setMode(item)}>
              {item === "change" ? `Change since ${first}` : "AQI level"}
            </button>
          ))}
        </div>
        <label className="min-w-48 flex-1 text-sm text-stone-700">
          Year: <strong>{selected}</strong>
          <input className="w-full" type="range" min={minYear ?? first} max={last ?? selected} step={1} value={selected} onChange={(event) => setYear(Number(event.target.value))} />
        </label>
        <label className="flex items-center gap-2 text-sm text-stone-700">
          <input type="checkbox" checked={showBuilt} onChange={(event) => setShowBuilt(event.target.checked)} />
          Built-up growth
        </label>
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_16rem]">
        <div className="h-[52vh] overflow-hidden rounded-xl border border-stone-200">
          <MapContainer bounds={data.overlay_bounds} scrollWheelZoom={false}>
            <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            <AqiPanes />
            {surface.data ? <AnnualBandLayer bands={surface.data} /> : null}
            {showBuilt ? <BuiltUpOverlay city={city} year={selected} bounds={data.overlay_bounds} /> : null}
            {boundary.data?.boundary ? <GeoJSON data={boundary.data.boundary} style={{ color: "#1c1917", weight: 2, fillOpacity: 0 }} /> : null}
            {stations ? (
              <AnnualStationsLayer
                stations={stations}
                classes={classes}
                year={selected}
                base={first}
                mode={mode}
                method={data.aqi_method}
                fillFor={(properties) =>
                  mode === "level"
                    ? CPCB_CATEGORY_COLORS[properties.category ?? ""] ?? "#78716c"
                    : classFill(properties.value, classes)
                }
              />
            ) : null}
          </MapContainer>
        </div>
        <div className="space-y-2 text-sm text-stone-700">
          <ul className="mt-2 flex flex-col gap-1 text-[11px] text-stone-700">
            {shades.map((shade) => (
              <li key={shade.min_aqi}>
                <span className="mr-1 inline-block h-3 w-3 border border-stone-300" style={{ backgroundColor: shade.fill }} />
                {shade.min_aqi}–{shade.max_aqi}
              </li>
            ))}
          </ul>
          <p className="text-xs text-stone-600">
            {mode === "change"
              ? "Green is the lowest change in this comparison. Dark red is the highest. The bands are drawn the same way as Station AQI in 2026."
              : "Green is this year’s lowest estimated AQI. Dark red is the highest. The bands are drawn the same way as Station AQI in 2026."}
          </p>
          {mode === "change" && surface.data?.mode === "change" ? (
            <p>
              {first} to {selected}: <strong>{surface.data.improved}</strong> monitors improved, <strong>{surface.data.worsened}</strong> got worse, median change <strong>{signed(surface.data.median_change ?? 0)}</strong>.
            </p>
          ) : (
            <p>
              Mean station AQI in {selected}: <strong>{formatNumber(yearCity?.mean_aqi, 0)}</strong> across {yearCity?.stations} monitors.
            </p>
          )}
          {partialYearNote(yearCity) ? <p className="text-xs text-stone-600">{partialYearNote(yearCity)}</p> : null}
          <p>
            Built-up inside Delhi: <strong>{formatNumber(yearCity?.built_km2, 0)} km²</strong>
            {baseCity?.built_km2 != null && yearCity?.built_km2 != null && selected !== first ? ` (${signed(yearCity.built_km2 - baseCity.built_km2)} since ${first})` : ""}.
          </p>
          {showBuilt ? (
            <ul className="space-y-1 text-xs">
              <li><span className="mr-2 inline-block h-3 w-3" style={{ backgroundColor: BUILT_BASELINE }} /> Built-up in {data.baseline_year}</li>
              <li><span className="mr-2 inline-block h-3 w-3" style={{ backgroundColor: BUILT_NEW }} /> Built-up since {data.baseline_year}</li>
            </ul>
          ) : null}
          <p className="text-xs text-stone-500">{data.aqi_method}</p>
        </div>
      </div>
    </Card>
    <StationChangeTable data={data} selectedYear={selected} />
    </>
  );
}

export function DashboardPage() {
  const { filters } = useFilters();
  const dash = useQuery({
    queryKey: ["dashboard", filters.city],
    queryFn: () => apiGet<any>("/dashboard", { city: filters.city }),
  });
  const series = useQuery({
    queryKey: ["timeseries", filters],
    queryFn: () => apiGet<any>("/air-quality/timeseries", { city: filters.city, pollutant: filters.pollutant, start: filters.from, end: filters.to, interval: "monthly" }),
  });
  const land = useQuery({
    queryKey: ["lulc", filters.city],
    queryFn: () => apiGet<any>("/land-cover/statistics", { city: filters.city, year: 2021 }),
  });
  const scatter = useQuery({
    queryKey: ["scatter", filters.city],
    queryFn: () => apiGet<any>("/analysis/scatter", { city: filters.city, x: "mean_ndvi", y: "built_up_percentage" }),
  });
  const cpcb = useQuery({
    queryKey: ["cpcb-snapshot", filters.city],
    queryFn: () => apiGet<any>("/air-quality/cpcb-snapshot", { city: filters.city }),
  });
  const builtUp = useBuiltUpAqiYears(filters.city);
  const landUse = useLandUseContrasts();

  if (dash.isLoading) return <Skeleton className="h-64" />;
  if (dash.isError) return <Alert>Could not load dashboard. Check that the API and database are running, then retry.</Alert>;
  const data = dash.data;
  if (data.empty) {
    return <EmptyState title="No observations yet" body="Import a labeled air-quality CSV on the Datasets page. The app will not invent station readings." />;
  }
  const selected = data.pollutants[filters.pollutant];
  const trend = builtUp.data?.city_trend ?? [];
  const first = trend[0];
  const last = trend[trend.length - 1];
  const summary = builtUp.data ? gapSummary(builtUp.data) : null;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-display text-3xl leading-tight text-stone-900">Does urbanization go with worse air in Delhi?</h2>
        <p className="mt-1 max-w-3xl text-sm text-stone-600">
          Annual CPCB AQI at each monitor, set beside Dynamic World built-up land within 1 km. The association is observed. It is not a measured effect of construction.
        </p>
      </div>
      {builtUp.data?.status === "ok" && first && last && summary ? (
        <div className="grid gap-3 md:grid-cols-4">
          <Kpi label="Years" value={`${first.year}–${last.year}`} hint={`${summary.years} years with a valid annual AQI`} />
          <Kpi label="Built-up inside Delhi" value={`${formatNumber(first.built_km2, 0)} → ${formatNumber(last.built_km2, 0)}`} hint="km², Dynamic World class 6" />
          <Kpi label="City mean AQI" value={`${formatNumber(first.mean_aqi, 0)} → ${formatNumber(last.mean_aqi, 0)}`} hint={last.partial ? `Mean of station annual values. ${partialYearNote(last)}` : "Mean of station annual values"} />
          <Kpi
            label="Built-up AQI gap"
            value={`${formatNumber(summary.minGap, 0)}–${formatNumber(summary.maxGap, 0)}`}
            hint="AQI points higher where the surroundings are most built-up"
          />
        </div>
      ) : null}
      {builtUp.isError ? <Alert>Built-up and annual AQI could not be loaded.</Alert> : null}
      {builtUp.data?.status === "ok" ? <AnnualMap city={filters.city} /> : null}
      {builtUp.data?.status === "ok" ? <BuiltUpAqiYearsCard data={builtUp.data} /> : null}
      <Card title={`Land cover within 1 km and ${landUse.data?.year ?? 2024} concentrations`} action={<DataKindBadge kind="statistical_estimate" />}>
        <p className="mb-3 text-sm text-stone-600">
          Monitors are split into three equal groups by how much of that land cover is within 1 km. Each bar compares the group with the most of it nearby with the group with the least. A bar below zero means the group with more of that land cover had lower pollution.
        </p>
        {landUse.isError ? <Alert>Land-use contrasts could not be loaded.</Alert> : null}
        <div className="h-80">
          <LandUseContrastChart data={landUse.data} />
        </div>
        {landUse.data ? <p className="mt-2 text-xs text-stone-500">{landUse.data.note}</p> : null}
      </Card>
      <MeasuredConcentrationChange />
      <div className="grid gap-3 md:grid-cols-4">
        <Kpi label={`${filters.pollutant} mean`} value={`${formatNumber(selected?.mean)} ${selected?.unit ?? ""}`} hint={selected?.is_sample === false ? "Hour-weighted CPCB station months. Concentrations, not AQI." : "Labeled sample series."} />
        <Kpi label="Monitoring stations" value={formatNumber(data.station_count, 0)} hint={selected?.is_sample === false ? "CPCB stations in the XKDR Delhi extract." : undefined} />
        <Kpi label="Vegetation (grid mean)" value={`${formatNumber(data.vegetation_percentage)} %`} hint="ESA WorldCover 2021: tree cover plus grassland." />
        <Kpi label="Built-up (grid mean)" value={`${formatNumber(data.built_up_percentage)} %`} hint="ESA WorldCover 2021, 10 m." />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card
          title={`${filters.pollutant} monthly mean`}
          action={series.data?.is_sample === false ? <DataKindBadge kind="aggregated" /> : <SampleBadge />}
        >
          <div className="h-72">
            <ResponsiveContainer>
              <LineChart data={series.data?.series ?? []} margin={{ top: 8, right: 12, bottom: 24, left: 16 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="period" minTickGap={24} label={{ value: "Month", position: "bottom", offset: 4, style: { fontSize: 12, fill: "#44403c" } }} />
                <YAxis width={64} label={{ value: `${filters.pollutant} (${series.data?.unit === "mg/m3" ? "mg/m³" : "µg/m³"})`, angle: -90, position: "insideLeft", style: { fontSize: 12, fill: "#44403c", textAnchor: "middle" } }} />
                <Tooltip />
                <Line type="monotone" dataKey="mean" stroke="#b45309" name="City monthly mean" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          {series.data?.is_sample === false ? (
            <p className="mt-2 text-xs text-stone-600">{series.data.note} {series.data.source}. {series.data.coverage}.</p>
          ) : null}
        </Card>
        <Card title="Land-cover composition" action={<DataKindBadge kind="classified" />}>
          <div className="h-80">
            <ResponsiveContainer>
              <BarChart data={land.data?.classes ?? []} margin={{ top: 8, right: 12, bottom: 48, left: 16 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="class_name" interval={0} angle={-30} textAnchor="end" height={64} label={{ value: "Land-cover class", position: "bottom", offset: 28, style: { fontSize: 12, fill: "#44403c" } }} />
                <YAxis width={56} label={{ value: "Share of mapped area (%)", angle: -90, position: "insideLeft", style: { fontSize: 12, fill: "#44403c", textAnchor: "middle" } }} />
                <Tooltip />
                <Bar dataKey="percentage" fill="#3f6b4a" name="Share of mapped area (%)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="NDVI versus built-up (grid cells with indices)" action={<DataKindBadge kind="satellite_index" />}>
          <NdviBuiltUpChart points={scatter.data?.points ?? []} />
        </Card>
        <div>
          <CpcbSnapshotSummary snapshot={cpcb.data} />
          {data.coverage_warning ? <Alert>{data.coverage_warning}</Alert> : null}
        </div>
      </div>
      {builtUp.data?.caveat ? <Alert tone="info">{builtUp.data.caveat}</Alert> : null}
    </div>
  );
}
