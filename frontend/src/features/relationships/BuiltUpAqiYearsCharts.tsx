import { Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatNumber } from "@/lib/format";
import type { BuiltUpAqiYears, CityTrend, YearStatistics } from "@/features/relationships/builtupAqiYears";

const AXIS_LABEL = { fontSize: 12, fill: "#44403c" };

function GapTooltip({ active, payload }: { active?: boolean; payload?: { payload: YearStatistics }[] }) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <div className="rounded-md border border-stone-200 bg-white px-3 py-2 text-xs shadow-sm">
      <p className="font-medium">{row.year}</p>
      <p>Most built-up nearby ({formatNumber(row.most_built_share, 0)}% built-up): AQI {formatNumber(row.most_built_aqi, 0)}</p>
      <p>Least built-up nearby ({formatNumber(row.least_built_share, 0)}% built-up): AQI {formatNumber(row.least_built_aqi, 0)}</p>
      <p>Gap {formatNumber(row.gap, 0)} AQI · {row.n_each} stations each</p>
      <p>Pearson r = {formatNumber(row.pearson_r, 2)} (p={formatNumber(row.p_value, 3)}, n={row.n})</p>
      <p>{formatNumber(row.aqi_per_10_points, 1)} AQI per 10 points of built-up</p>
    </div>
  );
}

export function BuiltUpTrendChart({ trend, showAqi = true }: { trend: CityTrend[]; showAqi?: boolean }) {
  return (
    <ResponsiveContainer>
      <ComposedChart data={trend} margin={{ top: 8, right: 24, bottom: 24, left: 20 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="year" label={{ value: "Year", position: "bottom", offset: 4, style: AXIS_LABEL }} />
        <YAxis yAxisId="built" width={64} domain={[0, "auto"]} label={{ value: "Built-up inside Delhi (km²)", angle: -90, position: "insideLeft", style: { ...AXIS_LABEL, textAnchor: "middle" } }} />
        {showAqi ? (
          <YAxis yAxisId="aqi" orientation="right" width={52} domain={[0, "auto"]} label={{ value: "Mean station AQI", angle: 90, position: "insideRight", style: { ...AXIS_LABEL, textAnchor: "middle" } }} />
        ) : null}
        <Tooltip />
        <Legend verticalAlign="top" />
        <Bar yAxisId="built" dataKey="built_km2" name="Built-up (km²)" fill="#a8a29e" isAnimationActive={false} />
        {showAqi ? <Line yAxisId="aqi" type="monotone" dataKey="mean_aqi" name="Mean station AQI" stroke="#b91c1c" strokeWidth={2} dot isAnimationActive={false} /> : null}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export function TercileGapChart({ years }: { years: YearStatistics[] }) {
  return (
    <ResponsiveContainer>
      <BarChart data={years} margin={{ top: 8, right: 16, bottom: 24, left: 20 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="year" label={{ value: "Year", position: "bottom", offset: 4, style: AXIS_LABEL }} />
        <YAxis width={52} domain={[0, "auto"]} label={{ value: "Mean annual AQI", angle: -90, position: "insideLeft", style: { ...AXIS_LABEL, textAnchor: "middle" } }} />
        <Tooltip content={<GapTooltip />} />
        <Legend verticalAlign="top" />
        <Bar dataKey="most_built_aqi" name="Most built-up nearby" fill="#b91c1c" isAnimationActive={false} />
        <Bar dataKey="least_built_aqi" name="Least built-up nearby" fill="#3f6b4a" isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function gapSummary(data: BuiltUpAqiYears) {
  const ok = data.years.filter((row) => row.status === "ok");
  const gaps = ok.map((row) => row.gap ?? 0);
  const rs = ok.map((row) => row.pearson_r ?? 0);
  const slopes = ok.map((row) => row.aqi_per_10_points ?? 0);
  return {
    years: ok.length,
    allPositive: ok.length > 0 && gaps.every((gap) => gap > 0),
    minGap: ok.length ? Math.min(...gaps) : null,
    maxGap: ok.length ? Math.max(...gaps) : null,
    minR: ok.length ? Math.min(...rs) : null,
    maxR: ok.length ? Math.max(...rs) : null,
    minSlope: ok.length ? Math.min(...slopes) : null,
    maxSlope: ok.length ? Math.max(...slopes) : null,
  };
}
