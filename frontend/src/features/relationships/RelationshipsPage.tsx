import { useMutation, useQuery } from "@tanstack/react-query";
import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { apiGet, apiPost } from "@/lib/api";
import { useFilters } from "@/hooks/useFilters";
import { Alert, Card } from "@/components/ui/Card";
import { DataKindBadge } from "@/components/ui/Badge";
import { formatNumber } from "@/lib/format";
import { useState } from "react";

export function RelationshipsPage() {
  const { filters } = useFilters();
  const scatter = useQuery({
    queryKey: ["scatter-rel", filters.city],
    queryFn: () => apiGet<any>("/analysis/scatter", { city: filters.city, x: "mean_ndvi", y: "built_up_percentage" }),
  });
  const [corr, setCorr] = useState<any>(null);
  const [reg, setReg] = useState<any>(null);
  const corrMut = useMutation({
    mutationFn: () => apiPost("/analysis/correlation", { x: "mean_ndvi", y: "built_up_percentage", pollutant: filters.pollutant }),
    onSuccess: setCorr,
  });
  const regMut = useMutation({
    mutationFn: () => apiPost("/analysis/regression", { response: "built_up_percentage", predictors: ["mean_ndvi", "road_density_km_per_km2"] }),
    onSuccess: setReg,
  });

  return (
    <div className="space-y-4">
      <Alert>
        These plots use grid-cell land-cover and index values. Pollution is assigned only to cells that contain a monitor. Correlation is not causation. Meteorology is not controlled.
      </Alert>
      <Card title="NDVI vs built-up %" action={<DataKindBadge kind="aggregated" />}>
        <div className="h-72">
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
        <p className="text-xs text-stone-500">n = {scatter.data?.n ?? 0}</p>
      </Card>
      <div className="flex gap-2">
        <button className="rounded-md bg-ink px-3 py-2 text-sm text-white" onClick={() => corrMut.mutate()}>Run correlation</button>
        <button className="rounded-md border border-stone-300 px-3 py-2 text-sm" onClick={() => regMut.mutate()}>Run regression</button>
      </div>
      {corr ? (
        <Card title="Correlation" action={<DataKindBadge kind="statistical_estimate" />}>
          <p>Pearson r = {formatNumber(corr.pearson?.coefficient, 3)} (p={formatNumber(corr.pearson?.p_value, 4)}, n={corr.n})</p>
          <p>95% CI: {formatNumber(corr.pearson?.ci_low, 3)} to {formatNumber(corr.pearson?.ci_high, 3)}</p>
          <p>Spearman ρ = {formatNumber(corr.spearman?.coefficient, 3)}</p>
          <p className="mt-2 text-sm text-stone-600">{corr.caveat} {corr.interpretation}</p>
        </Card>
      ) : null}
      {reg ? (
        <Card title="OLS regression" action={<DataKindBadge kind="statistical_estimate" />}>
          <pre className="overflow-auto text-xs">{JSON.stringify(reg, null, 2)}</pre>
        </Card>
      ) : null}
    </div>
  );
}
