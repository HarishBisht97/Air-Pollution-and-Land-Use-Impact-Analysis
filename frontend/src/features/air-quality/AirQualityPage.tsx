import { useQuery } from "@tanstack/react-query";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { apiGet } from "@/lib/api";
import { useFilters } from "@/hooks/useFilters";
import { Alert, Card, EmptyState, Skeleton } from "@/components/ui/Card";
import { DataKindBadge } from "@/components/ui/Badge";
import { formatNumber } from "@/lib/format";

export function AirQualityPage() {
  const { filters } = useFilters();
  const summary = useQuery({
    queryKey: ["summary", filters],
    queryFn: () => apiGet<any>("/air-quality/summary", { city: filters.city, pollutant: filters.pollutant, start: filters.from, end: filters.to, averaging_period: "monthly" }),
  });
  const daily = useQuery({
    queryKey: ["ts-daily", filters],
    queryFn: () => apiGet<any>("/air-quality/timeseries", { city: filters.city, pollutant: filters.pollutant, start: filters.from, end: filters.to, interval: "monthly" }),
  });
  const stations = useQuery({
    queryKey: ["obs", filters],
    queryFn: () => apiGet<any>("/air-quality/observations", { city: filters.city, pollutant: filters.pollutant, start: filters.from, end: filters.to, limit: 200 }),
  });

  if (summary.isLoading) return <Skeleton className="h-48" />;
  if (summary.isError) return <Alert>Air-quality API request failed.</Alert>;
  if (!summary.data?.observation_count) {
    return <EmptyState title="No observations in this filter" body="Widen the date range or import a CSV. Missing data is not interpolated." />;
  }

  const pollutant = summary.data.pollutants.find((p: any) => p.pollutant === filters.pollutant) ?? summary.data.pollutants[0];

  return (
    <div className="space-y-4">
      {summary.data.coverage_warning ? <Alert>{summary.data.coverage_warning}</Alert> : null}
      <div className="grid gap-3 md:grid-cols-4">
        <Card title="Mean">{formatNumber(pollutant?.mean)} {pollutant?.unit}</Card>
        <Card title="Median">{formatNumber(pollutant?.median)}</Card>
        <Card title="Min / max">{formatNumber(pollutant?.min)} / {formatNumber(pollutant?.max)}</Card>
        <Card title="Valid n">{formatNumber(pollutant?.count, 0)}</Card>
      </div>
      <Card title="NAAQS comparison" action={<DataKindBadge kind="aggregated" />}>
        {pollutant?.naaqs?.comparable ? (
          <p>
            {filters.pollutant} {pollutant.naaqs.averaging_period} limit is {pollutant.naaqs.limit} {pollutant.naaqs.unit}.
            Observed mean {pollutant.naaqs.exceeds ? "exceeds" : "does not exceed"} that limit. Source: {pollutant.naaqs.source}.
          </p>
        ) : (
          <p>{pollutant?.naaqs?.reason}</p>
        )}
      </Card>
      <Card title="Monthly series" action={<DataKindBadge kind="aggregated" />}>
        <div className="h-72">
          <ResponsiveContainer>
            <LineChart data={daily.data?.series ?? []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="period" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line dataKey="mean" name="Mean" stroke="#b45309" />
              <Line dataKey="min" name="Min" stroke="#a8a29e" />
              <Line dataKey="max" name="Max" stroke="#7c2d12" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>
      <Card title="Observation table (paginated)">
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead>
              <tr className="border-b text-xs uppercase text-stone-500">
                <th className="py-2">Time (UTC)</th>
                <th>Station</th>
                <th>Value</th>
                <th>Flag</th>
                <th>Kind</th>
              </tr>
            </thead>
            <tbody>
              {(stations.data?.items ?? []).map((row: any) => (
                <tr key={row.id} className="border-b border-stone-100">
                  <td className="py-2">{row.observed_at}</td>
                  <td>{row.station_name}</td>
                  <td>{row.concentration} {row.unit}</td>
                  <td>{row.quality_flag}</td>
                  <td>{row.data_kind}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
