import { useQuery } from "@tanstack/react-query";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, BarChart, Bar } from "recharts";
import { apiGet } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { useFilters } from "@/hooks/useFilters";
import { Alert, Card, EmptyState, Kpi, Skeleton } from "@/components/ui/Card";
import { DataKindBadge, SampleBadge } from "@/components/ui/Badge";

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
    queryFn: () => apiGet<any>("/land-cover/statistics", { city: filters.city, year: 2024 }),
  });
  const scatter = useQuery({
    queryKey: ["scatter", filters.city],
    queryFn: () => apiGet<any>("/analysis/scatter", { city: filters.city, x: "mean_ndvi", y: "built_up_percentage" }),
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
        <SampleBadge />
      </div>
      {data.coverage_warning ? <Alert>{data.coverage_warning}</Alert> : null}
      <div className="grid gap-3 md:grid-cols-4">
        <Kpi label="City" value={data.city.name} hint={data.city.state} />
        <Kpi label="Monitoring stations" value={String(data.station_count)} hint="Listed / imported stations only" />
        <Kpi label={`${filters.pollutant} mean`} value={`${formatNumber(selected?.mean)} ${selected?.unit ?? ""}`} hint={`${selected?.count ?? 0} valid observations`} />
        <Kpi label="Observations" value={formatNumber(data.observation_count, 0)} />
        <Kpi label="Vegetation (grid mean)" value={`${formatNumber(data.vegetation_percentage)} %`} hint="From SAMPLE land-cover raster unless replaced" />
        <Kpi label="Built-up (grid mean)" value={`${formatNumber(data.built_up_percentage)} %`} />
        <Kpi label="Built-up change" value={`${formatNumber(data.built_up_change_sq_km)} km²`} hint="SAMPLE 2020 vs 2024 rasters (illustrated expansion, not ESA WorldCover)" />
        <Kpi label="Datasets loaded" value={String(data.datasets.length)} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title={`${filters.pollutant} monthly mean`} action={<DataKindBadge kind="aggregated" />}>
          <div className="h-64">
            <ResponsiveContainer>
              <LineChart data={series.data?.series ?? []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="period" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="mean" stroke="#b45309" name="Mean" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="Land-cover composition" action={<DataKindBadge kind="classified" />}>
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={land.data?.classes ?? []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="class_name" hide />
                <YAxis />
                <Tooltip />
                <Bar dataKey="percentage" fill="#3f6b4a" name="% of mapped area" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <ul className="mt-2 grid grid-cols-2 gap-1 text-xs">
            {(land.data?.classes ?? []).map((row: any) => (
              <li key={row.class_name}>{row.class_name}: {formatNumber(row.percentage)}%</li>
            ))}
          </ul>
        </Card>
        <Card title="NDVI versus built-up (grid cells with indices)" action={<DataKindBadge kind="aggregated" />}>
          <div className="h-64">
            <ResponsiveContainer>
              <ScatterChart>
                <CartesianGrid />
                <XAxis dataKey="x" name="NDVI" />
                <YAxis dataKey="y" name="Built-up %" />
                <Tooltip />
                <Scatter data={scatter.data?.points ?? []} fill="#1d4e89" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
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
