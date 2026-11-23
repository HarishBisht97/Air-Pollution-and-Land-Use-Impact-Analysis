import { Fragment } from "react";
import { Card } from "@/components/ui/Card";
import { DataKindBadge } from "@/components/ui/Badge";
import { formatNumber } from "@/lib/format";
import { AQI_COLORS, type BuiltUpAqiYears, type StationFeature, partialYearNote } from "@/features/relationships/builtupAqiYears";

const CATEGORY_ORDER = ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"];
const MISSING_FILL = "#e7e5e4";

export const BANDS: { label: string; below: number }[] = [
  { label: "Under 30% built-up", below: 30 },
  { label: "30–70% built-up", below: 70 },
  { label: "70–90% built-up", below: 90 },
  { label: "90% built-up and over", below: Infinity },
];
const UNKNOWN_BAND = "Built-up share unknown";

export type ChangeCell = { aqi: number; category: string; built: number | null };
type YearCell = ChangeCell & { year: number };

export type StationChangeRow = {
  stationId: string;
  label: string;
  band: string;
  cells: (ChangeCell | null)[];
  first: YearCell;
  last: YearCell;
  builtChange: number | null;
  aqiChange: number;
  categoryChange: "worse" | "same" | "better";
};

function bandFor(built: number | null) {
  if (built == null) return UNKNOWN_BAND;
  return BANDS.find((band) => built < band.below)!.label;
}

function bandRank(band: string) {
  const index = BANDS.findIndex((item) => item.label === band);
  return index === -1 ? BANDS.length : index;
}

function categoryRank(category: string) {
  return CATEGORY_ORDER.indexOf(category);
}

export function stationChangeRows(features: StationFeature[], years: number[]): StationChangeRow[] {
  const nameCounts = new Map<string, number>();
  for (const feature of features) nameCounts.set(feature.properties.name, (nameCounts.get(feature.properties.name) ?? 0) + 1);
  const rows: StationChangeRow[] = [];
  for (const feature of features) {
    const { name, station_id, years: byYear } = feature.properties;
    const cells = years.map((year) => {
      const entry = byYear[String(year)];
      return entry ? { aqi: entry.aqi, category: entry.category, built: entry.built } : null;
    });
    const present = years.flatMap((year, index) => (cells[index] ? [{ ...cells[index]!, year }] : []));
    if (!present.length) continue;
    const first = present[0];
    const last = present[present.length - 1];
    const rankChange = categoryRank(last.category) - categoryRank(first.category);
    rows.push({
      stationId: station_id,
      label: (nameCounts.get(name) ?? 0) > 1 ? `${name} (${station_id})` : name,
      band: bandFor(first.built),
      cells,
      first,
      last,
      builtChange: first.built != null && last.built != null ? Math.round((last.built - first.built) * 10) / 10 : null,
      aqiChange: Math.round((last.aqi - first.aqi) * 10) / 10,
      categoryChange: rankChange > 0 ? "worse" : rankChange < 0 ? "better" : "same",
    });
  }
  return rows.sort((a, b) => bandRank(a.band) - bandRank(b.band) || (a.first.built ?? Infinity) - (b.first.built ?? Infinity));
}

function signed(value: number, digits = 0) {
  return `${value > 0 ? "+" : ""}${formatNumber(value, digits)}`;
}

function median(values: number[]) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

const CHANGE_TEXT: Record<StationChangeRow["categoryChange"], string> = {
  worse: "text-red-700",
  same: "text-stone-600",
  better: "text-green-700",
};

export function StationChangeTable({ data, selectedYear }: { data: BuiltUpAqiYears; selectedYear: number | null }) {
  const years = data.years.map((item) => item.year);
  const rows = stationChangeRows(data.features, years);
  if (!rows.length) return null;
  const firstYear = years[0];
  const lastYear = years[years.length - 1];
  const lastIndex = years.length - 1;
  const counts = { worse: 0, same: 0, better: 0 };
  for (const row of rows) counts[row.categoryChange] += 1;
  const bands = [...new Set(rows.map((row) => row.band))];

  return (
    <Card title={`Station AQI category and built-up share, ${firstYear}–${lastYear}`} action={<DataKindBadge kind="statistical_estimate" />}>
      <p className="mb-3 text-sm text-stone-700">
        Since their first year with data, {counts.worse} monitors moved to a worse AQI category, {counts.better} to a better one, and{" "}
        {counts.same} stayed in the same category. Rows run from the least built-up surroundings to the most, using each monitor's
        first-year built-up share within {data.radius_km} km.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-0.5 text-xs">
          <thead>
            <tr className="text-left text-stone-600">
              <th className="sticky left-0 z-10 bg-white px-2 py-1 font-medium">Station</th>
              {years.map((year) => (
                <th key={year} className={`px-2 py-1 text-center font-medium ${year === selectedYear ? "bg-stone-200 text-stone-900" : ""}`}>
                  {year}
                </th>
              ))}
              <th className="px-2 py-1 font-medium">First to last year</th>
            </tr>
          </thead>
          <tbody>
            {bands.map((band) => {
              const bandRows = rows.filter((row) => row.band === band);
              const bandMedian = median(bandRows.flatMap((row) => (row.cells[lastIndex] ? [row.cells[lastIndex]!.aqi] : [])));
              return (
                <Fragment key={band}>
                  <tr>
                    <td colSpan={years.length + 2} className="bg-stone-100 px-2 py-1 font-medium text-stone-800">
                      {band} · {bandRows.length} monitors · median AQI in {lastYear}: {formatNumber(bandMedian, 0)}
                    </td>
                  </tr>
                  {bandRows.map((row) => (
                    <tr key={row.stationId}>
                      <td className="sticky left-0 z-10 whitespace-nowrap bg-white px-2 py-1 text-stone-800">{row.label}</td>
                      {row.cells.map((cell, index) => (
                        <td
                          key={years[index]}
                          className={`min-w-[3.75rem] px-1.5 py-1 text-center ${years[index] === selectedYear ? "outline outline-2 outline-stone-900" : ""}`}
                          style={{ backgroundColor: cell ? AQI_COLORS[cell.category] ?? MISSING_FILL : MISSING_FILL }}
                          title={cell ? `${row.label}, ${years[index]}: AQI ${cell.aqi} (${cell.category}), ${cell.built ?? "—"}% built-up` : `${row.label}, ${years[index]}: no valid annual AQI`}
                        >
                          {cell ? (
                            <span className="text-white">
                              <span className="block font-medium">{formatNumber(cell.aqi, 0)}</span>
                              <span className="block text-[10px] opacity-90">{formatNumber(cell.built, 0)}%</span>
                            </span>
                          ) : (
                            <span className="text-stone-500">—</span>
                          )}
                        </td>
                      ))}
                      <td className="whitespace-nowrap px-2 py-1 text-stone-700">
                        <span className={`font-medium ${CHANGE_TEXT[row.categoryChange]}`}>
                          {row.first.category === row.last.category ? `${row.first.category} throughout` : `${row.first.category} to ${row.last.category}`}
                        </span>
                        <span className="block text-[11px] text-stone-500">
                          {row.first.year}–{row.last.year}: built-up {row.builtChange == null ? "—" : `${signed(row.builtChange)} pts`}, AQI{" "}
                          {signed(row.aqiChange)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-stone-700">
        {CATEGORY_ORDER.map((category) => (
          <li key={category}>
            <span className="mr-1 inline-block h-3 w-3 align-middle" style={{ backgroundColor: AQI_COLORS[category] }} /> {category}
          </li>
        ))}
        <li>
          <span className="mr-1 inline-block h-3 w-3 border border-stone-300 align-middle" style={{ backgroundColor: MISSING_FILL }} /> No valid
          annual AQI
        </li>
      </ul>
      <p className="mt-2 text-xs text-stone-600">
        Each cell is the annual AQI (top) and the Dynamic World built-up share within {data.radius_km} km (bottom). {data.aqi_method}
      </p>
      {data.city_trend.filter((row) => row.partial).map((row) => (
        <p key={row.year} className="mt-1 text-xs text-stone-600">{partialYearNote(row)}</p>
      ))}
      <p className="mt-1 text-xs text-stone-600">{data.caveat}</p>
    </Card>
  );
}
