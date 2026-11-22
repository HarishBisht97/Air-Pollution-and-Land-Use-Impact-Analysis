import { useQuery } from "@tanstack/react-query";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, BarChart, Bar } from "recharts";
import { apiGet } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { useFilters } from "@/hooks/useFilters";
import { Alert, Card, EmptyState, Kpi, Skeleton } from "@/components/ui/Card";
import { DataKindBadge, SampleBadge } from "@/components/ui/Badge";
import { NdviBuiltUpChart } from "@/features/dashboard/NdviBuiltUpChart";
import { CpcbSnapshotSummary } from "@/features/air-quality/CpcbSnapshotSummary";

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

  if (dash.isLoading) return <Skeleton className="h-64" />;
  if (dash.isError) return <Alert>Could not load dashboard. Check that the API and database are running, then retry.</Alert>;
  const data = dash.data;
  if (data.empty) {
    return <EmptyState title="No observations yet" body="Import a labeled air-quality CSV on the Datasets page. The app will not invent station readings." />;
  }
  const selected = data.pollutants[filters.pollutant];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <DataKindBadge kind="aggregated" />
      </div>
      <CpcbSnapshotSummary snapshot={cpcb.data} />
      {data.coverage_warning ? <Alert>{data.coverage_warning}</Alert> : null}
      <div className="grid gap-3 md:grid-cols-4">
        <Kpi label="City" value={data.city.name} hint={data.city.state} />
        <Kpi label={`${filters.pollutant} mean`} value={`${formatNumber(selected?.mean)} ${selected?.unit ?? ""}`} hint={selected?.is_sample === false ? "Hour-weighted mean of CPCB station months, XKDR Forum. Concentrations, not AQI." : "Labeled sample series."} />
        <Kpi label="Monitoring stations" value={formatNumber(data.station_count, 0)} hint={selected?.is_sample === false ? "CPCB stations in the XKDR Delhi extract." : undefined} />
        <Kpi label="Vegetation (grid mean)" value={`${formatNumber(data.vegetation_percentage)} %`} hint="ESA WorldCover 2021: tree cover plus grassland." />
        <Kpi label="Built-up (grid mean)" value={`${formatNumber(data.built_up_percentage)} %`} hint="ESA WorldCover 2021, 10 m." />
        <Kpi label="Built-up change" value={`${formatNumber(data.built_up_change_sq_km)} km²`} hint="ESA WorldCover 2020 to 2021. The two editions use different algorithms." />
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
          <ul className="mt-2 grid grid-cols-2 gap-1 text-xs">
            {(land.data?.classes ?? []).map((row: any) => (
              <li key={row.class_name}>{row.class_name}: {formatNumber(row.percentage)}%</li>
            ))}
          </ul>
        </Card>
        <Card title="NDVI versus built-up (grid cells with indices)" action={<DataKindBadge kind="satellite_index" />}>
          <NdviBuiltUpChart points={scatter.data?.points ?? []} />
        </Card>
        <Card title="Dataset freshness">
          <ul className="space-y-2 text-sm">
            {data.datasets.map((d: any) => (
              <li key={d.name} className="flex items-start justify-between gap-2 border-b border-stone-100 pb-2">
                <span>{d.name}</span>
                {d.sample ? <SampleBadge /> : <span className="text-xs text-stone-500">{d.temporal_coverage}</span>}
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
