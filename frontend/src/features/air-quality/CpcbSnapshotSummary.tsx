import { formatNumber } from "@/lib/format";
import { Card } from "@/components/ui/Card";

const ORDER = ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"];

type Feature = { properties: { aqi: number | null; category: string | null } };

export function CpcbSnapshotSummary({ snapshot }: { snapshot: { available?: boolean; observed_at?: string; station_count?: number; features?: Feature[]; note?: string } | undefined }) {
  if (!snapshot?.available) return null;
  const features = snapshot.features ?? [];
  const aqis = features.map((feature) => feature.properties.aqi).filter((value): value is number => value != null).sort((a, b) => a - b);
  const mid = Math.floor(aqis.length / 2);
  const median = aqis.length === 0 ? null : aqis.length % 2 ? aqis[mid] : (aqis[mid - 1] + aqis[mid]) / 2;
  const counts = new Map<string, number>();
  for (const feature of features) {
    const category = feature.properties.category ?? "Incomplete";
    counts.set(category, (counts.get(category) ?? 0) + 1);
  }
  const poorOrWorse = ["Poor", "Very Poor", "Severe"].reduce((sum, category) => sum + (counts.get(category) ?? 0), 0);

  return (
    <div className="space-y-3">
      <div className="grid gap-3 md:grid-cols-4">
        <Card title="CPCB stations">{formatNumber(snapshot.station_count, 0)}</Card>
        <Card title="Median station AQI">{formatNumber(median, 0)}</Card>
        <Card title="Poor or worse">{formatNumber(poorOrWorse, 0)} stations</Card>
        <Card title="Reading time">{snapshot.observed_at} IST</Card>
      </div>
      <Card title="CPCB air-quality index by station">
        <ul className="grid grid-cols-2 gap-1 text-sm md:grid-cols-3">
          {ORDER.map((category) => (
            <li key={category}>{category}: {counts.get(category) ?? 0}</li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-stone-500">{snapshot.note}</p>
      </Card>
    </div>
  );
}
