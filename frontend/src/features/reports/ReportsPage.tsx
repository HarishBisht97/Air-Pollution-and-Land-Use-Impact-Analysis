import { useMutation } from "@tanstack/react-query";
import { apiPost, downloadUrl } from "@/lib/api";
import { useFilters } from "@/hooks/useFilters";
import { Card } from "@/components/ui/Card";
import { useState } from "react";

export function ReportsPage() {
  const { filters } = useFilters();
  const [job, setJob] = useState<any>(null);
  const create = useMutation({
    mutationFn: (export_type: string) => apiPost("/exports", { export_type, pollutant: filters.pollutant }),
    onSuccess: setJob,
  });

  return (
    <div className="space-y-4">
      <Card title="Create export">
        <div className="flex flex-wrap gap-2">
          <button className="rounded-md bg-ink px-3 py-2 text-sm text-white" onClick={() => create.mutate("observations_csv")}>Observations CSV</button>
          <button className="rounded-md border px-3 py-2 text-sm" onClick={() => create.mutate("stations_geojson")}>Stations GeoJSON</button>
          <button className="rounded-md border px-3 py-2 text-sm" onClick={() => create.mutate("report_json")}>Research summary JSON</button>
        </div>
      </Card>
      {job ? (
        <Card title="Download">
          <p className="text-sm">Export {job.id} ({job.export_type}) status {job.status}.</p>
          <a className="mt-2 inline-block text-moss underline" href={downloadUrl(`/exports/${job.id}`, { city: filters.city })}>
            Download file
          </a>
        </Card>
      ) : null}
      <Card title="Printable methods note">
        <article className="prose prose-stone max-w-none text-sm">
          <p><strong>Study area:</strong> {filters.city}</p>
          <p><strong>Period:</strong> {filters.from} to {filters.to}</p>
          <p><strong>Pollutant:</strong> {filters.pollutant}</p>
          <p>Observations are stored as station measurements. Grid cells without a monitor do not inherit the station reading. NAAQS lines appear only when averaging periods match. Satellite indices in the default seed are labeled SAMPLE.</p>
        </article>
      </Card>
    </div>
  );
}
