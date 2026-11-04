import { useMutation } from "@tanstack/react-query";
import { apiPost } from "@/lib/api";
import { Alert, Card } from "@/components/ui/Card";
import { DataKindBadge } from "@/components/ui/Badge";
import { formatNumber } from "@/lib/format";
import { useState } from "react";

export function PriorityPage() {
  const [weights, setWeights] = useState({
    pollution_severity: 0.35,
    built_up: 0.2,
    road_density: 0.15,
    vegetation_deficit: 0.15,
    evidence_confidence: 0.15,
  });
  const [result, setResult] = useState<any>(null);
  const hot = useMutation({ mutationFn: () => apiPost<any>("/analysis/hotspots", {}), onSuccess: setResult });
  const pri = useMutation({ mutationFn: () => apiPost<any>("/analysis/priority", { weights }), onSuccess: setResult });
  const buf = useMutation({ mutationFn: () => apiPost<any>("/analysis/buffers", { target: "stations" }), onSuccess: setResult });

  return (
    <div className="space-y-4">
      <Alert>
        Hotspot maps of pollution are refused when fewer than eight stations are available. The screening index separates severity, confidence, and priority. It is not a health-risk assessment.
      </Alert>
      <Card title="Weights">
        <div className="grid gap-3 md:grid-cols-5">
          {Object.entries(weights).map(([key, value]) => (
            <label key={key} className="text-xs">
              {key}
              <input
                type="number"
                step="0.05"
                className="mt-1 w-full rounded border px-2 py-1"
                value={value}
                onChange={(e) => setWeights({ ...weights, [key]: Number(e.target.value) })}
              />
            </label>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <button className="rounded-md bg-ink px-3 py-2 text-sm text-white" onClick={() => pri.mutate()}>Compute screening scores</button>
          <button className="rounded-md border px-3 py-2 text-sm" onClick={() => hot.mutate()}>Request pollution hotspots</button>
          <button className="rounded-md border px-3 py-2 text-sm" onClick={() => buf.mutate()}>Station buffers</button>
        </div>
      </Card>
      {result?.status === "refused" ? <Alert>{result.message}</Alert> : null}
      {result?.cells ? (
        <Card title="Ranked grid cells" action={<DataKindBadge kind="screening_score" />}>
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-stone-500">
                <th>Grid</th><th>Severity</th><th>Confidence</th><th>Priority</th><th>Obs</th>
              </tr>
            </thead>
            <tbody>
              {result.cells.slice(0, 25).map((row: any) => (
                <tr key={row.grid_id} className="border-b border-stone-100">
                  <td>{row.grid_code}</td>
                  <td>{row.severity == null ? "unobserved" : formatNumber(row.severity, 2)}</td>
                  <td>{formatNumber(row.confidence, 2)}</td>
                  <td>{formatNumber(row.screening_priority, 2)}</td>
                  <td>{row.observation_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs">{result.note}</p>
        </Card>
      ) : null}
      {result?.limitation ? <Card title="Buffer limitation">{result.limitation}</Card> : null}
    </div>
  );
}
