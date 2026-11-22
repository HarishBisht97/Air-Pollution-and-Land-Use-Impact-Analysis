import { useQuery } from "@tanstack/react-query";
import { apiGet, apiUpload } from "@/lib/api";
import { useFilters } from "@/hooks/useFilters";
import { Alert, Card } from "@/components/ui/Card";
import { SampleBadge } from "@/components/ui/Badge";
import { useState } from "react";

export function DatasetsPage() {
  const { filters } = useFilters();
  const datasets = useQuery({ queryKey: ["datasets"], queryFn: () => apiGet<any[]>("/datasets") });
  const [message, setMessage] = useState("");

  async function onCsv(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("labeled_sample", "false");
    form.append("source", "manual_csv");
    const result = await apiUpload<any>("/ingestion/air-quality/csv", form, { city: filters.city });
    setMessage(`Inserted ${result.inserted}, skipped ${result.skipped}, rejected ${result.rejected}`);
  }

  return (
    <div className="space-y-4">
      <Alert tone="info">
        Delhi charts use monthly CPCB concentrations from the XKDR extract, January 2009 through August 2025. The catalog’s CPCB row is the 22 November 2026 index snapshot, which is separate from those concentrations. A CSV import is for a pollutant or city that extract does not cover. Do not scrape the CPCB portal.
      </Alert>
      <Card title="Import air-quality CSV">
        <input type="file" accept=".csv" onChange={onCsv} />
        {message ? <p className="mt-2 text-sm">{message}</p> : null}
      </Card>
      <Card title="Catalog">
        <ul className="space-y-3">
          {(datasets.data ?? []).map((row) => (
            <li key={row.id} className="border-b border-stone-100 pb-2">
              <div className="flex items-center gap-2">
                <strong>{row.dataset_name}</strong>
                {(row.metadata?.labeled_sample || row.metadata?.label) && <SampleBadge />}
              </div>
              <p className="text-xs text-stone-600">{row.license}</p>
              <p className="text-xs">{row.temporal_coverage} · {row.spatial_coverage}</p>
              {row.source_url ? <a className="text-xs text-moss underline" href={row.source_url}>{row.source_url}</a> : null}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
