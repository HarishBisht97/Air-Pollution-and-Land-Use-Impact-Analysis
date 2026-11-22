import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { apiGet, apiPost } from "@/lib/api";
import { useFilters } from "@/hooks/useFilters";
import { Alert, Card } from "@/components/ui/Card";
import { DataKindBadge } from "@/components/ui/Badge";
import { formatNumber } from "@/lib/format";
import { NdviBuiltUpChart } from "@/features/dashboard/NdviBuiltUpChart";
import { BuiltUpAqi } from "@/features/relationships/BuiltUpAqi";

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
  const model = useQuery({
    queryKey: ["builtup-aqi", filters.city],
    queryFn: () => apiPost<{ built_up_change?: ChangeFit }>(`/analysis/builtup-aqi?city=${filters.city}`, {}),
  });
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
