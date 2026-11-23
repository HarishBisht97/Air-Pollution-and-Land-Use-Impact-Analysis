import { useQuery } from "@tanstack/react-query";
import L from "leaflet";
import { GeoJSON, MapContainer, TileLayer } from "react-leaflet";
import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { Alert, Card, Skeleton } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";
import { formatNumber } from "@/lib/format";

const CITY = "delhi";
const DELHI_BOUNDS: L.LatLngBoundsExpression = [
  [28.4, 76.84],
  [28.88, 77.35],
];

type ContrastRow = {
  pollutant: string;
  unit: string;
  status: string;
  n_each?: number;
  n?: number;
  low_mean?: number;
  high_mean?: number;
  low_land_mean?: number;
  high_land_mean?: number;
  percent_difference?: number | null;
  reason?: string;
  stations_with_industry?: number;
  stations_with_park?: number;
  high_group_with_park?: number;
};

type Fit = {
  status: string;
  n?: number;
  message?: string;
  params?: Record<string, number | null>;
  pvalues?: Record<string, number | null>;
  r_squared?: number | null;
  distance_per_km?: number | null;
  caveat?: string;
};

type Spearman = { coefficient: number | null; p_value: number | null; n: number };

type FeatureCollection = { type: "FeatureCollection"; features: GeoJSON.Feature[] };

type LocalQuestions = {
  year: number;
  station_count: number;
  air_quality: string;
  land_cover: string;
  note: string;
  vegetation: { status: string; detail: string; pollutants: ContrastRow[] };
  parks: {
    status: string;
    reason?: string | null;
    message?: string;
    missing?: string[];
    detail?: string;
    pollutants?: ContrastRow[];
    polygons?: FeatureCollection;
  };
  roads: {
    status: string;
    message?: string;
    missing?: string[];
    detail?: string;
    spearman_no2?: Spearman;
    spearman_pm25?: Spearman;
    reading?: { reading: string; text: string };
    regression_no2?: Fit;
    regression_pm25?: Fit;
    lines?: FeatureCollection;
  };
  industry: {
    status: string;
    reason?: string | null;
    message?: string;
    missing?: string[];
    detail?: string;
    contrast?: ContrastRow;
    regression?: Fit | null;
    polygons?: FeatureCollection;
  };
  residential: {
    status: string;
    message?: string | null;
    missing?: string[];
    detail?: string;
    ranked?: { rank: number; station_id: string; name: string; ward: string | null; pm25: number; unit: string }[];
    unmeasured_ward_count?: number;
    ward_count?: number;
    wards?: FeatureCollection;
  };
  stations: FeatureCollection;
};

type Bin = { label: string; color: string; above: number };

const PM25_BINS: Bin[] = [
  { label: "Above 120 µg/m³", color: "#7c2d12", above: 120 },
  { label: "Above 100 to 120 µg/m³", color: "#c2410c", above: 100 },
  { label: "Above 80 to 100 µg/m³", color: "#ea580c", above: 80 },
  { label: "80 µg/m³ or below", color: "#d97706", above: -Infinity },
];

const NO2_BINS: Bin[] = [
  { label: "Above 50 µg/m³", color: "#1e3a8a", above: 50 },
  { label: "Above 40 to 50 µg/m³", color: "#1d4ed8", above: 40 },
  { label: "Above 30 to 40 µg/m³", color: "#3b82f6", above: 30 },
  { label: "30 µg/m³ or below", color: "#93c5fd", above: -Infinity },
];

function useLocalQuestions() {
  return useQuery({
    queryKey: ["local-questions"],
    queryFn: () => apiGet<LocalQuestions>("/analysis/local-questions", { city: CITY }),
  });
}

function binColor(bins: Bin[], value: number) {
  return bins.find((bin) => value > bin.above)?.color ?? bins[bins.length - 1].color;
}

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (character) => {
    const entities: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    return entities[character];
  });
}

function unitLabel(unit: string | undefined) {
  if (!unit || unit === "ug/m3") return "µg/m³";
  return unit;
}

function formatP(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "—";
  if (value < 0.001) return "< 0.001";
  return value.toFixed(3);
}

function formatRho(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(2);
}

function popupHtml(title: string, lines: [string, string][]) {
  const body = lines.map(([label, value]) => `${escapeHtml(label)}: ${escapeHtml(value)}`).join("<br/>");
  return `<strong>${escapeHtml(title)}</strong><br/>${body}`;
}

function Legend({ bins }: { bins: Bin[] }) {
  return (
    <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-stone-600">
      {bins.map((bin) => (
        <li key={bin.label} className="flex items-center gap-1">
          <span className="inline-block h-2.5 w-2.5 rounded-full border border-stone-800" style={{ background: bin.color }} />
          {bin.label}
        </li>
      ))}
    </ul>
  );
}

function QuestionMap({
  boundary,
  layer,
  layerStyle,
  stations,
  valueKey,
  bins,
  popup,
}: {
  boundary?: GeoJSON.GeoJsonObject;
  layer?: FeatureCollection;
  layerStyle: L.PathOptions | ((feature?: GeoJSON.Feature) => L.PathOptions);
  stations?: FeatureCollection;
  valueKey: string;
  bins: Bin[];
  popup: (properties: Record<string, unknown>) => string;
}) {
  return (
    <div>
      <div className="h-[420px] overflow-hidden rounded-xl border border-stone-200">
        <MapContainer bounds={DELHI_BOUNDS} scrollWheelZoom={false}>
          <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          {boundary ? <GeoJSON data={boundary} style={{ color: "#1c1917", weight: 2, fillOpacity: 0 }} /> : null}
          {layer?.features?.length ? (
            <GeoJSON
              data={layer}
              style={layerStyle}
              onEachFeature={(feature, leafletLayer) => {
                const name = feature.properties?.name;
                if (name) leafletLayer.bindPopup(`<strong>${escapeHtml(String(name))}</strong>`);
              }}
            />
          ) : null}
          {stations?.features?.length ? (
            <GeoJSON
              data={stations}
              pointToLayer={(feature, latlng) => {
                const raw = feature.properties?.[valueKey];
                const value = typeof raw === "number" ? raw : null;
                return L.circleMarker(latlng, {
                  radius: 7,
                  color: "#1c1917",
                  weight: 1,
                  fillColor: value == null ? "#a8a29e" : binColor(bins, value),
                  fillOpacity: 0.92,
                });
              }}
              onEachFeature={(feature, leafletLayer) => {
                leafletLayer.bindPopup(popup((feature.properties ?? {}) as Record<string, unknown>));
              }}
            />
          ) : null}
        </MapContainer>
      </div>
      <Legend bins={bins} />
    </div>
  );
}

function ContrastTable({ rows, lowLabel, highLabel }: { rows: ContrastRow[]; lowLabel: string; highLabel: string }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-xs uppercase text-stone-500">
          <th>Pollutant</th>
          <th>{lowLabel}</th>
          <th>{highLabel}</th>
          <th>Change</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.pollutant} className="border-b border-stone-100">
            <td>{row.pollutant}</td>
            <td>{row.status === "ok" ? `${formatNumber(row.low_mean, 1)} ${unitLabel(row.unit)}` : "—"}</td>
            <td>{row.status === "ok" ? `${formatNumber(row.high_mean, 1)} ${unitLabel(row.unit)}` : "—"}</td>
            <td>{row.status === "ok" && row.percent_difference != null ? `${formatNumber(row.percent_difference, 1)}%` : "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function landValue(value: number | undefined, digits: number, suffix: string) {
  const number = formatNumber(value, digits);
  return suffix.trim() === "%" ? `${number}%` : `${number} ${suffix.trim()}`;
}

function ContrastNote({ row, landDigits = 1, landSuffix = "%" }: { row: ContrastRow | undefined; landDigits?: number; landSuffix?: string }) {
  if (row?.status !== "ok") return null;
  return (
    <p className="mt-2 text-xs text-stone-500">
      {row.n_each} monitors in each group. The low group averages {landValue(row.low_land_mean, landDigits, landSuffix)} nearby and the high group averages{" "}
      {landValue(row.high_land_mean, landDigits, landSuffix)}.
    </p>
  );
}

function spearmanLine(label: string, stats: Spearman | undefined) {
  if (!stats) return null;
  return (
    <p className="text-sm text-stone-700">
      {label}: Spearman r {formatRho(stats.coefficient)} (p {formatP(stats.p_value)}, n {stats.n}). A negative r means higher concentration closer to the road.
    </p>
  );
}

function distanceFit(label: string, fit: Fit | undefined, unit: string) {
  if (!fit || fit.status !== "ok" || fit.distance_per_km == null) {
    return fit?.status === "insufficient_data" ? <p className="text-sm text-stone-600">{fit.message}</p> : null;
  }
  return (
    <p className="text-sm text-stone-700">
      Holding built-up share constant, the 2024 {label} mean changes by {formatNumber(fit.distance_per_km, 2)} {unit} for each extra kilometre from a major road (p{" "}
      {formatP(fit.pvalues?.distance_to_major_road_m)}, n {fit.n}).
    </p>
  );
}

function scatterPoints(stations: FeatureCollection, yKey: "no2" | "pm25") {
  return stations.features
    .map((feature) => feature.properties ?? {})
    .filter((properties) => typeof properties.distance_to_major_road_m === "number" && typeof properties[yKey] === "number")
    .map((properties) => ({
      name: String(properties.name ?? ""),
      distance_m: properties.distance_to_major_road_m as number,
      value: properties[yKey] as number,
    }));
}

function DistanceScatter({ points, yLabel, color }: { points: { name: string; distance_m: number; value: number }[]; yLabel: string; color: string }) {
  return (
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 8, bottom: 28, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="distance_m" name="Distance" type="number" unit=" m" tick={{ fontSize: 11 }} label={{ value: "Distance to major road (m)", position: "insideBottom", offset: -16, fontSize: 11 }} />
          <YAxis dataKey="value" name={yLabel} type="number" width={48} tick={{ fontSize: 11 }} label={{ value: yLabel, angle: -90, position: "insideLeft", fontSize: 11 }} />
          <Tooltip
            content={({ payload }) => {
              const row = payload?.[0]?.payload as { name?: string; distance_m?: number; value?: number } | undefined;
              if (!row) return null;
              return (
                <div className="rounded border border-stone-200 bg-white px-2 py-1 text-xs text-stone-800">
                  <p className="font-medium">{row.name}</p>
                  <p>{formatNumber(row.distance_m, 0)} m</p>
                  <p>
                    {yLabel} {formatNumber(row.value, 1)}
                  </p>
                </div>
              );
            }}
          />
          <Scatter data={points} fill={color} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

function metres(value: unknown) {
  return typeof value === "number" ? `${formatNumber(value, 0)} m` : "—";
}

export function LocalQuestionsPage() {
  const query = useLocalQuestions();
  const city = useQuery({
    queryKey: ["city", CITY],
    queryFn: () => apiGet<{ boundary?: GeoJSON.Feature }>("/cities/slug/current", { city: CITY }),
  });
  const data = query.data;
  const boundary = city.data?.boundary;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl text-stone-900">Local questions at Delhi monitors</h1>
        <p className="mt-1 max-w-3xl text-sm text-stone-600">
          Four neighbourhood comparisons for {data ? data.year : "2024"}. Each number is a monitor mean. Polygons and roads are outlines only.
        </p>
      </div>
      {query.isLoading ? <Skeleton className="h-40" /> : null}
      {query.isError ? <Alert>Local questions could not be loaded. Delhi station and Dynamic World files need to be in data/raw.</Alert> : null}
      {data ? (
        <Alert tone="info">
          {data.station_count} monitors. {data.note} Air quality: {data.air_quality}. Land cover: {data.land_cover}.
        </Alert>
      ) : null}

      {data ? (
        <section className="space-y-3">
          <h2 className="font-display text-2xl text-stone-900">Do monitors with more vegetation within 1 km have lower pollution?</h2>
          <p className="max-w-3xl text-sm text-stone-600">{data.vegetation.detail}. Park polygons are a separate test below.</p>
          <div className="grid gap-4 lg:grid-cols-2">
            <QuestionMap
              boundary={boundary}
              layer={data.parks.polygons}
              layerStyle={{ color: "#166534", weight: 1.5, fillOpacity: 0 }}
              stations={data.stations}
              valueKey="pm25"
              bins={PM25_BINS}
              popup={(properties) =>
                popupHtml(String(properties.name ?? "Monitor"), [
                  ["PM2.5", typeof properties.pm25 === "number" ? `${formatNumber(properties.pm25, 1)} µg/m³` : "—"],
                  ["Vegetation within 1 km", typeof properties.vegetation === "number" ? `${formatNumber(properties.vegetation, 1)}%` : "—"],
                  ["Park area within 500 m", typeof properties.park_area_m2 === "number" ? `${formatNumber(properties.park_area_m2, 0)} m²` : "—"],
                  ["Distance to a park", metres(properties.distance_to_park_m)],
                ])
              }
            />
            <Card title="Vegetation within 1 km">
              <ContrastTable rows={data.vegetation.pollutants} lowLabel="Least vegetation" highLabel="Most vegetation" />
              <ContrastNote row={data.vegetation.pollutants.find((row) => row.status === "ok")} />
              <p className="mt-3 text-xs text-stone-500">A negative change means the monitors with more vegetation nearby had a lower 2024 mean.</p>
            </Card>
          </div>
          <Card title="Parks within 500 m">
            {data.parks.status === "missing_data" ? <Alert>{data.parks.message}</Alert> : null}
            {data.parks.status === "insufficient_data" ? <Alert tone="info">{data.parks.reason}</Alert> : null}
            {data.parks.status === "ok" && data.parks.pollutants ? (
              <>
                <p className="mb-3 text-sm text-stone-600">{data.parks.detail}</p>
                <ContrastTable rows={data.parks.pollutants} lowLabel="Least park area" highLabel="Most park area" />
                <ContrastNote row={data.parks.pollutants.find((row) => row.status === "ok")} landDigits={0} landSuffix=" m²" />
              </>
            ) : null}
          </Card>
        </section>
      ) : null}

      {data ? (
        <section className="space-y-3">
          <h2 className="font-display text-2xl text-stone-900">Are monitors near major roads associated with higher NO2?</h2>
          <p className="max-w-3xl text-sm text-stone-600">
            {data.roads.detail ?? "Major roads are motorway, trunk, and primary. Secondary roads are left out."} Road buffers stay uncoloured.
          </p>
          {data.roads.status === "missing_data" ? <Alert>{data.roads.message}</Alert> : (
            <div className="grid gap-4 lg:grid-cols-2">
              <QuestionMap
                boundary={boundary}
                layer={data.roads.lines}
                layerStyle={{ color: "#44403c", weight: 1.5 }}
                stations={data.stations}
                valueKey="no2"
                bins={NO2_BINS}
                popup={(properties) =>
                  popupHtml(String(properties.name ?? "Monitor"), [
                    ["NO2", typeof properties.no2 === "number" ? `${formatNumber(properties.no2, 1)} µg/m³` : "—"],
                    ["PM2.5", typeof properties.pm25 === "number" ? `${formatNumber(properties.pm25, 1)} µg/m³` : "—"],
                    ["Distance to a major road", metres(properties.distance_to_major_road_m)],
                    ["Major-road length within 300 m", metres(properties.road_length_300_m)],
                    ["Built-up within 1 km", typeof properties.built === "number" ? `${formatNumber(properties.built, 1)}%` : "—"],
                  ])
                }
              />
              <div className="space-y-3">
                {data.roads.reading ? <Alert tone="info">{data.roads.reading.text}</Alert> : null}
                {spearmanLine("NO2", data.roads.spearman_no2)}
                {spearmanLine("PM2.5", data.roads.spearman_pm25)}
                {distanceFit("NO2", data.roads.regression_no2, "µg/m³")}
                {distanceFit("PM2.5", data.roads.regression_pm25, "µg/m³")}
                <Card title="Distance and 2024 NO2">
                  <DistanceScatter points={scatterPoints(data.stations, "no2")} yLabel="NO2" color="#1d4ed8" />
                </Card>
                <Card title="Distance and 2024 PM2.5">
                  <DistanceScatter points={scatterPoints(data.stations, "pm25")} yLabel="PM2.5" color="#c2410c" />
                </Card>
              </div>
            </div>
          )}
        </section>
      ) : null}

      {data ? (
        <section className="space-y-3">
          <h2 className="font-display text-2xl text-stone-900">Do monitors with more industrial land nearby have higher PM2.5?</h2>
          <p className="max-w-3xl text-sm text-stone-600">
            {data.industry.detail ?? "Industrial share uses mapped industrial polygons inside the same 1 km square as built-up land."} Industrial polygons stay uncoloured.
          </p>
          {data.industry.status === "missing_data" ? <Alert>{data.industry.message}</Alert> : (
            <div className="grid gap-4 lg:grid-cols-2">
              <QuestionMap
                boundary={boundary}
                layer={data.industry.polygons}
                layerStyle={{ color: "#9a3412", weight: 1.5, fillOpacity: 0 }}
                stations={data.stations}
                valueKey="pm25"
                bins={PM25_BINS}
                popup={(properties) =>
                  popupHtml(String(properties.name ?? "Monitor"), [
                    ["PM2.5", typeof properties.pm25 === "number" ? `${formatNumber(properties.pm25, 1)} µg/m³` : "—"],
                    ["Industrial land within 1 km", typeof properties.industrial_share === "number" ? `${formatNumber(properties.industrial_share, 1)}%` : "—"],
                    ["Distance to industry", metres(properties.distance_to_industry_m)],
                    ["Built-up within 1 km", typeof properties.built === "number" ? `${formatNumber(properties.built, 1)}%` : "—"],
                  ])
                }
              />
              <Card title="Industrial land and 2024 PM2.5">
                {data.industry.status === "insufficient_data" ? <Alert tone="info">{data.industry.reason}</Alert> : null}
                {data.industry.status === "ok" && data.industry.contrast ? (
                  <>
                    <ContrastTable rows={[data.industry.contrast]} lowLabel="Least industry" highLabel="Most industry" />
                    <ContrastNote row={data.industry.contrast} />
                    <p className="mt-3 text-sm text-stone-600">
                      {data.industry.contrast.stations_with_industry} monitors have any mapped industrial land within 1 km.
                    </p>
                    {data.industry.regression?.status === "ok" && data.industry.regression.params?.industrial_share != null ? (
                      <p className="mt-2 text-sm text-stone-700">
                        Holding built-up share constant, the 2024 PM2.5 mean changes by {formatNumber(data.industry.regression.params.industrial_share, 2)} µg/m³ for each extra percentage point of industrial land (p{" "}
                        {formatP(data.industry.regression.pvalues?.industrial_share)}, n {data.industry.regression.n}). The built-up coefficient in the same fit is{" "}
                        {formatNumber(data.industry.regression.params.built, 2)} µg/m³ per percentage point.
                      </p>
                    ) : null}
                  </>
                ) : null}
              </Card>
            </div>
          )}
        </section>
      ) : null}

      {data ? (
        <section className="space-y-3">
          <h2 className="font-display text-2xl text-stone-900">Which residential monitors have the highest PM2.5?</h2>
          <p className="max-w-3xl text-sm text-stone-600">
            {data.residential.detail ?? "The rank is the highest monitored PM2.5 at residential-class stations. Population is not included."} Wards without a residential monitor stay unmeasured.
          </p>
          {data.residential.status === "missing_data" ? <Alert>{data.residential.message}</Alert> : (
            <div className="grid gap-4 lg:grid-cols-2">
              <QuestionMap
                boundary={boundary}
                layer={data.residential.wards}
                layerStyle={(feature) => ({
                  color: feature?.properties?.measured ? "#44403c" : "#d6d3d1",
                  weight: feature?.properties?.measured ? 2 : 1,
                  fillOpacity: 0,
                })}
                stations={{
                  type: "FeatureCollection",
                  features: data.stations.features.filter((feature) =>
                    (data.residential.ranked ?? []).some((row) => row.station_id === feature.properties?.station_id),
                  ),
                }}
                valueKey="pm25"
                bins={PM25_BINS}
                popup={(properties) => {
                  const row = data.residential.ranked?.find((item) => item.station_id === properties.station_id);
                  return popupHtml(String(properties.name ?? "Monitor"), [
                    ["Rank", row ? String(row.rank) : "—"],
                    ["Ward", row?.ward ?? "Outside the ward layer"],
                    ["PM2.5", typeof properties.pm25 === "number" ? `${formatNumber(properties.pm25, 1)} µg/m³` : "—"],
                  ]);
                }}
              />
              <Card title={`Residential monitors, ${data.year} PM2.5`}>
                {data.residential.message ? <Alert tone="info">{data.residential.message}</Alert> : null}
                <p className="mb-3 text-sm text-stone-600">
                  {data.residential.unmeasured_ward_count} of {data.residential.ward_count} wards have no residential monitor in this ranking. Those wards are unmeasured.
                </p>
                <div className="max-h-[420px] overflow-auto">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-white">
                      <tr className="text-left text-xs uppercase text-stone-500">
                        <th>Rank</th>
                        <th>Monitor</th>
                        <th>Ward</th>
                        <th>PM2.5</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(data.residential.ranked ?? []).map((row) => (
                        <tr key={row.station_id} className="border-b border-stone-100">
                          <td>{row.rank}</td>
                          <td>{row.name}</td>
                          <td>{row.ward ?? "Outside the ward layer"}</td>
                          <td>
                            {formatNumber(row.pm25, 1)} {unitLabel(row.unit)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </div>
          )}
        </section>
      ) : null}
    </div>
  );
}
