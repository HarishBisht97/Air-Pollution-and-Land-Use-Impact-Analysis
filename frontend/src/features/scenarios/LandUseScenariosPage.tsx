import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Alert, Card } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";
import { formatNumber } from "@/lib/format";

type PollutantContrast = {
  pollutant: string;
  unit: string;
  status: string;
  n_each?: number;
  low_land_mean?: number;
  high_land_mean?: number;
  low_mean?: number;
  high_mean?: number;
  percent_difference?: number | null;
};

type Contrast = {
  key: string;
  label: string;
  detail: string;
  pollutants: PollutantContrast[];
};

export type LandUsePayload = {
  year: number;
  station_count: number;
  land_cover: string;
  air_quality: string;
  note: string;
  contrasts: Contrast[];
  chart: Array<Record<string, string | number | null>>;
};

const COLORS: Record<string, string> = {
  built: "#57534e",
  crops: "#ca8a04",
  vegetation: "#14532d",
};

export function useLandUseContrasts() {
  return useQuery({
    queryKey: ["delhi-land-use"],
    queryFn: () => apiGet<LandUsePayload>("/analysis/delhi-land-use", { city: "delhi" }),
  });
}

export function LandUseContrastChart({ data }: { data: LandUsePayload | undefined }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data?.chart ?? []} margin={{ top: 28, right: 12, left: 12, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="pollutant" label={{ value: "Pollutant", position: "insideBottom", offset: -2 }} />
        <YAxis
          width={64}
          label={{ value: `Difference in ${data?.year ?? ""} mean (%)`, angle: -90, position: "insideLeft", textAnchor: "middle" }}
        />
        <Tooltip />
        <Legend verticalAlign="top" />
        <Bar dataKey="built" name="Urbanization" fill={COLORS.built} isAnimationActive={false} />
        <Bar dataKey="crops" name="Agriculture" fill={COLORS.crops} isAnimationActive={false} />
        <Bar dataKey="vegetation" name="Vegetation" fill={COLORS.vegetation} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function LandUseScenariosPage() {
  const query = useLandUseContrasts();
  const data = query.data;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl text-stone-900">Land use and air quality in Delhi</h1>
        <p className="mt-1 max-w-3xl text-sm text-stone-600">
          Three comparisons, using the same land-use ideas as Badia et al. (2025): more built-up area, more cropland, and more vegetation. Every number comes from Delhi monitors in 2024. Most of those monitors sit in built-up surroundings, so the cropland and vegetation groups are the stations with relatively more of those covers nearby.
        </p>
      </div>
      {query.isError ? <Alert tone="warn">Delhi land-use contrasts could not be loaded.</Alert> : null}
      {data ? (
        <Alert tone="info">
          {data.note} Land cover: {data.land_cover}. Air quality: {data.air_quality}. Stations with a 1 km window: {data.station_count}.
        </Alert>
      ) : null}
      <Card title={`How the 2024 mean changes when that land cover is more common nearby`}>
        <div className="h-80">
          <LandUseContrastChart data={data} />
        </div>
        <p className="mt-2 text-xs text-stone-500">
          X axis: pollutant. Y axis: percent difference between the highest third and the lowest third of that land cover within 1 km. A bar below zero means the high-share stations recorded a lower concentration.
        </p>
      </Card>
      <div className="grid gap-3 lg:grid-cols-3">
        {(data?.contrasts ?? []).map((contrast) => (
          <Card key={contrast.key} title={contrast.label}>
            <p className="mb-3 text-xs text-stone-500">{contrast.detail}</p>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-stone-500">
                  <th>Pollutant</th>
                  <th>Low third</th>
                  <th>High third</th>
                  <th>Change</th>
                </tr>
              </thead>
              <tbody>
                {contrast.pollutants.map((row) => (
                  <tr key={row.pollutant} className="border-b border-stone-100">
                    <td>{row.pollutant}</td>
                    <td>{row.status === "ok" ? `${formatNumber(row.low_mean, 1)} ${row.unit}` : "—"}</td>
                    <td>{row.status === "ok" ? `${formatNumber(row.high_mean, 1)} ${row.unit}` : "—"}</td>
                    <td>{row.percent_difference == null ? "—" : `${formatNumber(row.percent_difference, 1)}%`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {contrast.pollutants[0]?.status === "ok" ? (
              <p className="mt-2 text-xs text-stone-500">
                For {contrast.pollutants[0].pollutant}, {contrast.pollutants[0].n_each} stations in each third. Mean share of this land cover {formatNumber(contrast.pollutants[0].low_land_mean, 1)}% versus {formatNumber(contrast.pollutants[0].high_land_mean, 1)}%.
              </p>
            ) : null}
          </Card>
        ))}
      </div>
    </div>
  );
}
