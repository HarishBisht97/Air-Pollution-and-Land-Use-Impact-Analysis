type Point = { x: number; y: number };

type Bin = { label: string; min: number; max: number; includeMax?: boolean };

const NDVI_BINS: Bin[] = [
  { label: "< 0", min: -1, max: 0 },
  { label: "0–0.2", min: 0, max: 0.2 },
  { label: "0.2–0.4", min: 0.2, max: 0.4 },
  { label: "0.4–0.6", min: 0.4, max: 0.6 },
  { label: "≥ 0.6", min: 0.6, max: 2, includeMax: true },
];

const BUILT_BINS: Bin[] = [
  { label: "80–100", min: 80, max: 100, includeMax: true },
  { label: "60–80", min: 60, max: 80 },
  { label: "40–60", min: 40, max: 60 },
  { label: "20–40", min: 20, max: 40 },
  { label: "0–20", min: 0, max: 20 },
];

function inBin(value: number, bin: Bin): boolean {
  if (value < bin.min) return false;
  return bin.includeMax ? value <= bin.max : value < bin.max;
}

function mix(t: number): string {
  const start = [231, 229, 228];
  const end = [29, 78, 137];
  const channel = (index: number) => Math.round(start[index] + (end[index] - start[index]) * t);
  return `rgb(${channel(0)}, ${channel(1)}, ${channel(2)})`;
}

export function NdviBuiltUpChart({ points }: { points: Point[] }) {
  const counts = BUILT_BINS.map((built) =>
    NDVI_BINS.map((ndvi) => points.filter((point) => inBin(point.x, ndvi) && inBin(point.y, built)).length),
  );
  const max = Math.max(1, ...counts.flat());

  if (points.length === 0) {
    return <p className="text-sm text-stone-500">No grid cells have both an NDVI and a built-up percentage.</p>;
  }

  return (
    <div>
      <p className="mb-2 text-xs font-medium text-stone-700">X axis: NDVI. Y axis: built-up share (%).</p>
      <div className="grid grid-cols-[4.5rem_repeat(5,minmax(0,1fr))] gap-1 text-center text-[11px] text-stone-600">
        <div />
        {NDVI_BINS.map((bin) => (
          <div key={bin.label} className="pb-1">{bin.label}</div>
        ))}
        {BUILT_BINS.map((built, row) => (
          <div key={built.label} className="contents">
            <div className="flex items-center justify-end pr-1">{built.label}</div>
            {NDVI_BINS.map((ndvi, column) => {
              const count = counts[row][column];
              const tone = count === 0 ? "#f5f5f4" : mix(0.18 + 0.82 * (count / max));
              return (
                <div
                  key={`${built.label}-${ndvi.label}`}
                  className="flex h-9 items-center justify-center rounded-sm font-medium text-stone-900"
                  style={{ backgroundColor: tone, color: count / max > 0.55 ? "#f8fafc" : "#1c1917" }}
                  title={`${count} grid cells. NDVI ${ndvi.label}, built-up ${built.label}%.`}
                >
                  {count > 0 ? count : ""}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      <div className="mt-2 flex items-center justify-between gap-3 text-[11px] text-stone-500">
        <span>X: NDVI →</span>
        <span className="flex items-center gap-2">
          <span>Fewer cells</span>
          <span className="h-2 w-16 rounded-sm" style={{ background: "linear-gradient(90deg, #e7e5e4, #1d4e89)" }} />
          <span>More cells</span>
        </span>
        <span>Y: built-up share (%) ↑</span>
      </div>
      <p className="mt-1 text-xs text-stone-500">Each tile is a count of 1 km cells. n = {points.length}.</p>
    </div>
  );
}
