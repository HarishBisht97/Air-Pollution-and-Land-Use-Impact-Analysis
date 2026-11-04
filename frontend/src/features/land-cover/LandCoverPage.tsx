import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { useFilters } from "@/hooks/useFilters";
import { Alert, Card } from "@/components/ui/Card";
import { DataKindBadge, SampleBadge } from "@/components/ui/Badge";
import { formatNumber } from "@/lib/format";

export function LandCoverPage() {
  const { filters } = useFilters();
  const stats = useQuery({ queryKey: ["lc-stats", filters.city], queryFn: () => apiGet<any>("/land-cover/statistics", { city: filters.city, year: 2024 }) });
  const change = useQuery({ queryKey: ["lc-change", filters.city], queryFn: () => apiGet<any>("/land-cover/change", { city: filters.city }) });
  const indices = useQuery({ queryKey: ["lc-idx", filters.city], queryFn: () => apiGet<any>("/land-cover/indices", { city: filters.city }) });
  const rasters = useQuery({ queryKey: ["rasters"], queryFn: () => apiGet<any[]>("/rasters") });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <SampleBadge />
        <DataKindBadge kind="classified" />
      </div>
      <Alert tone="info">
        Real Sentinel-2 processing requires Copernicus Data Space or Earth Engine credentials. Until then the UI shows a labeled sample raster, not a fabricated satellite product.
      </Alert>
      <div className="grid gap-3 md:grid-cols-3">
        <Card title="Mean NDVI">{formatNumber(indices.data?.mean_ndvi, 3)} <p className="text-xs text-stone-500">{indices.data?.note}</p></Card>
        <Card title="Mean NDBI">{formatNumber(indices.data?.mean_ndbi, 3)}</Card>
        <Card title="Raster assets">{rasters.data?.length ?? 0}</Card>
      </div>
      <Card title="Class area (sample 2024)">
        <table className="min-w-full text-sm">
          <thead><tr className="text-left text-xs uppercase text-stone-500"><th>Class</th><th>km²</th><th>%</th></tr></thead>
          <tbody>
            {(stats.data?.classes ?? []).map((row: any) => (
              <tr key={row.class_name} className="border-b border-stone-100">
                <td>{row.class_name}</td>
                <td>{formatNumber(row.area_sq_km, 4)}</td>
                <td>{formatNumber(row.percentage)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card title="Change 2020 to 2024">
        <p className="mb-3 text-sm text-stone-600">{change.data?.caveat}</p>
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase text-stone-500">
              <th>Class</th><th>2020 km²</th><th>2024 km²</th><th>Change km²</th><th>pp change</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(change.data?.classes ?? {}).map(([name, row]: any) => (
              <tr key={name} className="border-b border-stone-100">
                <td>{name}</td>
                <td>{formatNumber(row.baseline_sq_km, 4)}</td>
                <td>{formatNumber(row.recent_sq_km, 4)}</td>
                <td>{formatNumber(row.change_sq_km, 4)}</td>
                <td>{formatNumber(row.percentage_point_change)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
