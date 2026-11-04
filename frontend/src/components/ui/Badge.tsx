import { dataKindLabel } from "@/lib/format";

export function DataKindBadge({ kind }: { kind?: string }) {
  return (
    <span className="inline-flex items-center rounded-full border border-stone-300 bg-white px-2 py-0.5 text-xs font-medium text-stone-700">
      {dataKindLabel(kind)}
    </span>
  );
}

export function SampleBadge() {
  return (
    <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-900">
      SAMPLE — not a real observation
    </span>
  );
}
