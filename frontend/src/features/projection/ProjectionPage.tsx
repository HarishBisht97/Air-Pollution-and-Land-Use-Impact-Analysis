import { useQuery } from "@tanstack/react-query";
import { Area, CartesianGrid, ComposedChart, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Alert, Card, Kpi, Skeleton } from "@/components/ui/Card";
import { useFilters } from "@/hooks/useFilters";
import { apiGet } from "@/lib/api";
import { formatNumber } from "@/lib/format";

type Point = { year: number; value: number | null; low: number | null; high: number | null; observed: number | null };

type Projection = {
  status: string;
  aqi_method?: string;
  land_cover?: string;
  boundary?: string | null;
  built: {
    status: string;
    n?: number;
    per_year?: number | null;
    p_value?: number | null;
    r_squared?: number | null;
    message?: string;
    unit: string;
    series: { year: number; built_km2: number | null; fitted: number | null }[];
    projections: Point[];
    caveat: string;
  };
  aqi: {
    status: string;
    n?: number;
    minimum_years?: number;
    message?: string;
    per_km2?: number | null;
    p_value?: number | null;
    r_squared?: number | null;
    observed_built_range?: [number, number] | null;
    observed: { year: number; mean_aqi: number | null; built_km2: number | null; fitted: number | null }[];
    projections: (Point & { built_km2: number | null; outside_observed_built: boolean })[];
    association_with_built: { coefficient: number | null; p_value: number | null; n: number };
    caveat: string;
  };
};

function range(start: number, end: number) {
  return Array.from({ length: end - start + 1 }, (_, index) => start + index);
}

export function ProjectionPage() {
  const { filters } = useFilters();
  const query = useQuery({
    queryKey: ["builtup-projection", filters.city],
    queryFn: () => apiGet<Projection>("/analysis/builtup-projection", { city: filters.city }),
  });

  if (query.isLoading) return <Skeleton className="h-80" />;
  if (query.isError || !query.data) return <Alert>The built-up projection could not be loaded.</Alert>;

  const data = query.data;
  const built = data.built;
  const aqi = data.aqi;
  const chart = built.series.map((row) => ({ year: row.year, mapped: row.built_km2, line: row.fitted }));
  for (const row of built.projections) {
    if (!chart.some((item) => item.year === row.year)) {
      chart.push({ year: row.year, mapped: row.observed, line: row.value });
    }
  }
  type AqiRow = {
    year: number;
    observed: number | null;
    model: number | null;
    projected: number | null;
    band: [number, number] | null;
    built: number | null;
  };
  const aqiChart: AqiRow[] = aqi.observed.map((row) => ({
    year: row.year,
    observed: row.mean_aqi,
    model: row.fitted,
    projected: null,
    band: null,
    built: row.built_km2,
  }));
  for (const row of aqi.projections) {
    aqiChart.push({
      year: row.year,
      observed: null,
      model: row.value,
      projected: row.value,
      band: row.low != null && row.high != null ? [row.low, row.high] : null,
      built: row.built_km2,
    });
  }
  aqiChart.sort((a, b) => a.year - b.year);
  const first = aqi.observed[0];
  const last = aqi.observed[aqi.observed.length - 1];
  const association = aqi.association_with_built;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-3xl text-stone-900">If the built-up pace continues</h2>
        <p className="mt-2 max-w-3xl text-stone-700">
          The mapped built area is extended to 2026, 2027, and 2028, and the citywide average AQI is read at that built area.
          {built.status === "ok" && built.per_year != null
            ? ` From ${built.series[0]?.year} to ${built.series[built.series.length - 1]?.year}, built area changed by ${formatNumber(built.per_year, 1)} km² per year (p ${formatNumber(built.p_value, 3)}, r² ${formatNumber(built.r_squared, 2)}, n ${built.n}).`
            : ""}
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {built.projections.map((row) => (
          <Kpi
            key={row.year}
            label={`${row.year} built area`}
            value={`${formatNumber(row.value, 0)} km²`}
            hint={
              row.observed != null
                ? `Mapped that year: ${formatNumber(row.observed, 0)} km². Line interval ${formatNumber(row.low, 0)}–${formatNumber(row.high, 0)}.`
                : `Line interval ${formatNumber(row.low, 0)}–${formatNumber(row.high, 0)} km².`
            }
          />
        ))}
      </div>

      <Card title="Mapped built area and the fitted line">
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chart} margin={{ top: 8, right: 12, bottom: 24, left: 16 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="year" />
              <YAxis unit=" km²" width={72} />
              <Tooltip />
              <Line dataKey="mapped" name="Mapped" stroke="#1c1917" strokeWidth={2} dot />
              <Line dataKey="line" name="Fitted line" stroke="#9a3412" strokeWidth={2} dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-3 text-sm text-stone-600">{built.caveat}</p>
      </Card>

      <Card title="Average AQI for 2026, 2027, and 2028">
        {aqi.status === "ok" && aqi.projections.length ? (
          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-3">
              {aqi.projections.map((row) => (
                <Kpi
                  key={row.year}
                  label={`${row.year} city mean AQI`}
                  value={formatNumber(row.value, 0)}
                  hint={`At ${formatNumber(row.built_km2, 0)} km² built. Interval ${formatNumber(row.low, 0)}–${formatNumber(row.high, 0)}.`}
                />
              ))}
            </div>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={aqiChart} margin={{ top: 8, right: 12, bottom: 24, left: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="year"
                    type="number"
                    domain={["dataMin", "dataMax"]}
                    ticks={aqiChart.length ? range(aqiChart[0].year, aqiChart[aqiChart.length - 1].year) : []}
                  />
                  <YAxis width={56} domain={["auto", "auto"]} />
                  <Tooltip
                    labelFormatter={(year) => {
                      const row = aqiChart.find((item) => item.year === year);
                      return row?.built != null ? `${year} · ${formatNumber(row.built, 0)} km² built` : `${year}`;
                    }}
                    formatter={(value, name) =>
                      Array.isArray(value)
                        ? [`${formatNumber(Number(value[0]), 0)}–${formatNumber(Number(value[1]), 0)}`, name]
                        : [formatNumber(value as number, 0), name]
                    }
                  />
                  <Legend verticalAlign="top" height={28} />
                  <Area
                    dataKey="band"
                    name="95% interval"
                    stroke="none"
                    fill="#9a3412"
                    fillOpacity={0.15}
                    isAnimationActive={false}
                  />
                  <Line
                    dataKey="model"
                    name="Model at built area"
                    stroke="#a8a29e"
                    strokeDasharray="5 4"
                    strokeWidth={2}
                    dot={false}
                    connectNulls
                    isAnimationActive={false}
                  />
                  <Line
                    dataKey="observed"
                    name="Observed city mean"
                    stroke="#1c1917"
                    strokeWidth={2}
                    dot
                    isAnimationActive={false}
                  />
                  <Line
                    dataKey="projected"
                    name="Projected"
                    stroke="#9a3412"
                    strokeWidth={2}
                    dot={{ r: 4 }}
                    connectNulls
                    isAnimationActive={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <Alert tone="info">
              Fit on {aqi.n} years ({first?.year}–{last?.year}): the city mean changes by{" "}
              {formatNumber(aqi.per_km2 != null ? aqi.per_km2 * 10 : null, 1)} AQI per 10 km² of built area (p{" "}
              {formatNumber(aqi.p_value, 3)}, r² {formatNumber(aqi.r_squared, 2)}).
              {aqi.p_value != null && aqi.p_value >= 0.05
                ? " That slope is not statistically different from zero, so the three values sit close to the 2018–2024 average and the interval is the honest answer."
                : ""}
              {aqi.projections.some((row) => row.outside_observed_built) && aqi.observed_built_range
                ? ` Projected built area is beyond the ${formatNumber(aqi.observed_built_range[0], 0)}–${formatNumber(aqi.observed_built_range[1], 0)} km² seen in those years, so the line is extended past its data.`
                : ""}
            </Alert>
          </div>
        ) : (
          <Alert tone="info">
            No average AQI is estimated. {aqi.message} The comparable index has {aqi.n} years
            {first && last
              ? `, from ${formatNumber(first.mean_aqi, 0)} in ${first.year} at ${formatNumber(first.built_km2, 0)} km² built to ${formatNumber(last.mean_aqi, 0)} in ${last.year} at ${formatNumber(last.built_km2, 0)} km² built`
              : ""}
            . Pearson r between built area and the city mean is {formatNumber(association.coefficient, 2)}
            {association.p_value != null ? ` (p ${formatNumber(association.p_value, 3)}, n ${association.n})` : ""}.
          </Alert>
        )}
        <p className="mt-3 text-sm text-stone-600">{aqi.caveat}</p>
        {data.aqi_method ? <p className="mt-2 text-sm text-stone-600">{data.aqi_method}</p> : null}
      </Card>
    </div>
  );
}
