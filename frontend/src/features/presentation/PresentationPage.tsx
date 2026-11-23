import { type ReactNode, useEffect, useState } from "react";
import { GeoJSON, MapContainer, TileLayer } from "react-leaflet";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { Alert, Card, Kpi, Skeleton } from "@/components/ui/Card";
import { type BuiltUpAqiYears, partialYearNote, useAnnualAqiSurface, useBuiltUpAqiYears } from "@/features/relationships/builtupAqiYears";
import { BuiltUpTrendChart, TercileGapChart, gapSummary } from "@/features/relationships/BuiltUpAqiYearsCharts";
import { LandUseContrastChart, type LandUsePayload, useLandUseContrasts } from "@/features/scenarios/LandUseScenariosPage";
import { StationChangeTable } from "@/features/map/StationChangeTable";
import {
  AnnualStationsLayer,
  AqiFillLayer,
  AqiLinesLayer,
  AqiPanes,
  BUILT_BASELINE,
  BUILT_NEW,
  BuiltUpOverlay,
  ClassList,
  type SurfaceMode,
  signed,
  useYearStations,
} from "@/features/map/annualAqiLayers";

const CITY = "delhi";

type Step = { title: string; minutes: string; body: (data: BuiltUpAqiYears, landUse: LandUsePayload | undefined) => ReactNode; notes: (data: BuiltUpAqiYears, landUse: LandUsePayload | undefined) => string[] };

function StoryMap({
  data,
  year,
  base = null,
  mode = "level",
  builtUp = false,
  surface = false,
  stations = false,
  height = "h-[52vh]",
}: {
  data: BuiltUpAqiYears;
  year: number;
  base?: number | null;
  mode?: SurfaceMode;
  builtUp?: boolean;
  surface?: boolean;
  stations?: boolean;
  height?: string;
}) {
  const city = useQuery({ queryKey: ["city", CITY], queryFn: () => apiGet<any>("/cities/slug/current", { city: CITY }) });
  const aqi = useAnnualAqiSurface(CITY, surface ? year : null, base, mode);
  const yearStations = useYearStations(data, year, base, mode);
  const classes = (mode === "change" ? data.change_classes : data.aqi_classes)?.classes ?? [];
  return (
    <div className={`${height} overflow-hidden rounded-xl border border-stone-200`}>
      <MapContainer bounds={data.overlay_bounds} scrollWheelZoom={false}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <AqiPanes />
        {city.data?.boundary ? <GeoJSON data={city.data.boundary} style={{ color: "#1c1917", weight: 2, fillOpacity: 0 }} /> : null}
        {surface && aqi.data ? <AqiFillLayer surface={aqi.data} opacity={0.6} /> : null}
        {builtUp ? <BuiltUpOverlay city={CITY} year={year} bounds={data.overlay_bounds} /> : null}
        {surface && aqi.data ? <AqiLinesLayer surface={aqi.data} /> : null}
        {stations && yearStations ? <AnnualStationsLayer stations={yearStations} classes={classes} year={year} base={base} mode={mode} method={data.aqi_method} /> : null}
      </MapContainer>
    </div>
  );
}

function YearSlider({ years, value, onChange, label }: { years: number[]; value: number; onChange: (year: number) => void; label: string }) {
  return (
    <label className="block text-sm text-stone-700">
      {label}: <strong>{value}</strong>
      <input className="w-full" type="range" min={years[0]} max={years[years.length - 1]} step={1} value={value} onChange={(e) => onChange(Number(e.target.value))} />
      <span className="flex justify-between text-[11px] text-stone-500">
        <span>{years[0]}</span>
        <span>{years[years.length - 1]}</span>
      </span>
    </label>
  );
}

function Headline({ children }: { children: ReactNode }) {
  return <p className="font-display text-2xl leading-snug text-stone-900">{children}</p>;
}

function trendEnds(data: BuiltUpAqiYears) {
  const trend = data.city_trend;
  const first = trend[0];
  const last = trend[trend.length - 1];
  const lowest = trend.reduce((low, row) => ((row.mean_aqi ?? Infinity) < (low.mean_aqi ?? Infinity) ? row : low), first);
  const stations = trend.map((row) => row.stations);
  return { first, last, lowest, minStations: Math.min(...stations), maxStations: Math.max(...stations) };
}

function urbanization(landUse: LandUsePayload | undefined) {
  const built = landUse?.contrasts.find((item) => item.key === "built");
  const pick = (name: string) => built?.pollutants.find((row) => row.pollutant === name);
  return { pm25: pick("PM2.5"), no2: pick("NO2"), year: landUse?.year };
}

function QuestionStep({ data }: { data: BuiltUpAqiYears }) {
  const { first, last, minStations, maxStations } = trendEnds(data);
  return (
    <div className="space-y-5">
      <Headline>Does urbanization go with worse air in Delhi?</Headline>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi label="Years" value={`${first.year}–${last.year}`} hint="Annual CPCB AQI per monitor" />
        <Kpi label="Monitors" value={`${minStations}–${maxStations}`} hint="CPCB stations with 180+ valid days" />
        <Kpi label="Built-up land" value={`${formatNumber(first.built_km2, 0)} → ${formatNumber(last.built_km2, 0)} km²`} hint="Inside the Delhi boundary" />
        <Kpi label="Land cover" value="10 m" hint="Dynamic World, one map per year" />
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <Card title="Air quality">
          <p className="text-sm text-stone-700">{data.air_quality}.</p>
          <p className="mt-2 text-sm text-stone-600">{data.aqi_method}</p>
        </Card>
        <Card title="Land cover">
          <p className="text-sm text-stone-700">
            {data.land_cover}, share within {data.radius_km} km of each monitor. City totals use the {data.boundary}.
          </p>
        </Card>
      </div>
    </div>
  );
}

function UrbanizingStep({ data }: { data: BuiltUpAqiYears }) {
  const years = data.city_trend.map((row) => row.year);
  const [year, setYear] = useState(years[years.length - 1]);
  const row = data.city_trend.find((item) => item.year === year);
  const first = data.city_trend[0];
  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
      <StoryMap data={data} year={year} builtUp />
      <div className="space-y-3">
        <Headline>
          {signed((row?.built_km2 ?? 0) - (first.built_km2 ?? 0))} km² of built-up land since {first.year}
        </Headline>
        <YearSlider years={years} value={year} onChange={setYear} label="Year" />
        <ul className="space-y-1 text-sm">
          <li><span className="mr-2 inline-block h-3 w-3" style={{ backgroundColor: BUILT_BASELINE }} /> Built-up in {data.baseline_year}</li>
          <li><span className="mr-2 inline-block h-3 w-3" style={{ backgroundColor: BUILT_NEW }} /> Built-up since {data.baseline_year}</li>
        </ul>
        <div className="h-56">
          <BuiltUpTrendChart trend={data.city_trend} showAqi={false} />
        </div>
      </div>
    </div>
  );
}

function GapStep({ data }: { data: BuiltUpAqiYears }) {
  const summary = gapSummary(data);
  const { first, last } = trendEnds(data);
  return (
    <div className="space-y-4">
      <Headline>
        In {summary.allPositive ? "every" : "most"} year from {first.year} to {last.year}, monitors with the most built-up land nearby had worse air
      </Headline>
      <div className="grid gap-3 sm:grid-cols-3">
        <Kpi label="AQI gap, most vs least built-up nearby" value={`${formatNumber(summary.minGap, 0)}–${formatNumber(summary.maxGap, 0)}`} hint="AQI points, depending on the year" />
        <Kpi label="Pearson r, built-up vs AQI" value={`${formatNumber(summary.minR, 2)}–${formatNumber(summary.maxR, 2)}`} hint={`Positive in all ${summary.years} years`} />
        <Kpi label="AQI per 10 points of built-up" value={`+${formatNumber(summary.minSlope, 1)} to +${formatNumber(summary.maxSlope, 1)}`} hint="Within 1 km of the monitor" />
      </div>
      <div className="h-[44vh]">
        <TercileGapChart years={data.years} />
      </div>
    </div>
  );
}

function TwistStep({ data }: { data: BuiltUpAqiYears }) {
  const { first, last } = trendEnds(data);
  const presets: { label: string; base: number; year: number }[] = [
    { label: `${first.year} → ${last.year}`, base: first.year, year: last.year },
    { label: "2019 → 2020 (lockdown)", base: 2019, year: 2020 },
    { label: "2020 → 2021", base: 2020, year: 2021 },
  ];
  const [preset, setPreset] = useState(0);
  const [showTable, setShowTable] = useState(false);
  const chosen = presets[preset];
  const surface = useAnnualAqiSurface(CITY, chosen.year, chosen.base, "change");
  return (
    <div className="space-y-4">
      <Headline>
        Yet the city mean AQI fell from {formatNumber(first.mean_aqi, 0)} to {formatNumber(last.mean_aqi, 0)} while Delhi kept building
      </Headline>
      {last.partial ? <p className="text-sm text-stone-600">{partialYearNote(last)}</p> : null}
      <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
        <div className="h-[48vh]">
          <BuiltUpTrendChart trend={data.city_trend} />
        </div>
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            {presets.map((item, index) => (
              <button
                key={item.label}
                type="button"
                className={`rounded-full px-3 py-1 text-sm ${index === preset ? "bg-ink text-white" : "border border-stone-300 bg-white text-stone-700"}`}
                onClick={() => setPreset(index)}
              >
                {item.label}
              </button>
            ))}
          </div>
          <StoryMap data={data} year={chosen.year} base={chosen.base} mode="change" surface stations height="h-[40vh]" />
          <p className="text-sm text-stone-700">
            {surface.data?.mode === "change" ? (
              <>
                {chosen.base} → {chosen.year}: <strong>{surface.data.improved}</strong> monitors improved, <strong>{surface.data.worsened}</strong> got worse, median change{" "}
                <strong>{signed(surface.data.median_change ?? 0)}</strong> AQI. Paler red is a larger fall; the solid line is no change.
              </>
            ) : (
              "Loading the change surface…"
            )}
          </p>
          <ClassList classes={data.change_classes.classes} />
        </div>
      </div>
      <button type="button" className="text-sm text-stone-600 underline" onClick={() => setShowTable((value) => !value)}>
        {showTable ? "Hide" : "Show"} the station-by-station table
      </button>
      {showTable ? <StationChangeTable data={data} selectedYear={chosen.year} /> : null}
    </div>
  );
}

function EvidenceStep({ landUse }: { landUse: LandUsePayload | undefined }) {
  const { pm25, no2, year } = urbanization(landUse);
  return (
    <div className="space-y-4">
      <Headline>Built-up surroundings carry more traffic pollution</Headline>
      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <div className="h-[46vh]">{landUse ? <LandUseContrastChart data={landUse} /> : <Skeleton className="h-full" />}</div>
        <div className="space-y-3">
          {[pm25, no2].map((row) =>
            row && row.status === "ok" ? (
              <Kpi
                key={row.pollutant}
                label={`${row.pollutant}, most vs least built-up nearby (${year})`}
                value={`${signed(row.percent_difference ?? 0)}%`}
                hint={`${formatNumber(row.low_mean, 1)} → ${formatNumber(row.high_mean, 1)} ${row.unit}`}
              />
            ) : null,
          )}
          <p className="text-sm text-stone-600">
            Same comparison as Badia et al. (2025): monitors with the most of a land cover within 1 km against monitors with the least. {landUse?.note}
          </p>
        </div>
      </div>
    </div>
  );
}

function TakeawayStep({ data }: { data: BuiltUpAqiYears }) {
  const summary = gapSummary(data);
  return (
    <div className="space-y-4">
      <Headline>
        Built-up areas carry a persistent penalty of about {formatNumber(summary.minGap, 0)}–{formatNumber(summary.maxGap, 0)} AQI points; city-wide policy moves the whole level
      </Headline>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="What the data shows">
          <ul className="list-disc space-y-2 pl-5 text-sm text-stone-700">
            <li>Delhi added built-up land every few years, mostly on its edges.</li>
            <li>In every year, the more built-up a monitor's surroundings, the worse its annual AQI.</li>
            <li>City-wide AQI fell over the same years, and jumped back after the 2020 lockdown, so emissions and weather set the overall level.</li>
            <li>Growth areas need green buffers and traffic controls as they are built, because the built-up penalty stays.</li>
          </ul>
        </Card>
        <Card title="Limitations">
          <ul className="list-disc space-y-2 pl-5 text-sm text-stone-700">
            <li>Association, not cause: traffic, industry, and monitor siting come with built-up land.</li>
            <li>The map between monitors is interpolated from 32–39 stations, so small patches are estimates.</li>
            <li>Dynamic World labels shift a little from year to year; comparisons use three equal groups of monitors and multi-year trends.</li>
            <li>Through 2024, annual AQI is built from daily concentrations and leaves out CO and ozone. 2025 and 2026 use CPCB's published hourly AQI; 2026 stops at 31 October.</li>
          </ul>
        </Card>
      </div>
      <Alert tone="info">{data.caveat}</Alert>
    </div>
  );
}

const STEPS: Step[] = [
  {
    title: "The question",
    minutes: "0:00–0:30",
    body: (data) => <QuestionStep data={data} />,
    notes: (data) => {
      const { first, last, minStations, maxStations } = trendEnds(data);
      return [
        "Does urbanization go with worse air in Delhi? I combined satellite land cover with official monitor data.",
        `Land cover is Google Dynamic World at 10 m, one map per year. Air quality is ${minStations}–${maxStations} CPCB monitors from ${first.year} to ${last.year}.`,
        "Through 2024 I computed the CPCB AQI from daily PM2.5, PM10, NO2, SO2, and NH3. 2025 and 2026 use CPCB's published hourly AQI, and 2026 stops at 31 October.",
      ];
    },
  },
  {
    title: "Delhi is urbanizing",
    minutes: "0:30–1:15",
    body: (data) => <UrbanizingStep data={data} />,
    notes: (data) => {
      const { first, last } = trendEnds(data);
      return [
        "Grey is land that was already built up in the first year; red is land that became built-up after it. Drag the slider.",
        `Built-up land inside Delhi went from about ${formatNumber(first.built_km2, 0)} to ${formatNumber(last.built_km2, 0)} km², roughly ${formatNumber((last.built_km2 ?? 0) - (first.built_km2 ?? 0), 0)} km² more.`,
        "Most of the new built-up land is on the edges: north-west, south-west, and east.",
        "If asked about small dips: the satellite classifier wobbles a little from year to year; the trend is clear.",
      ];
    },
  },
  {
    title: "More built-up, worse air",
    minutes: "1:15–2:30",
    body: (data) => <GapStep data={data} />,
    notes: (data) => {
      const summary = gapSummary(data);
      return [
        "I split the monitors into three equal groups by how much built-up land is within 1 km.",
        `In every year, monitors with the most built-up land nearby had worse annual AQI than monitors with the least, by ${formatNumber(summary.minGap, 0)} to ${formatNumber(summary.maxGap, 0)} points.`,
        `The correlation is positive every year (r ${formatNumber(summary.minR, 2)} to ${formatNumber(summary.maxR, 2)}), about ${formatNumber(summary.minSlope, 1)}–${formatNumber(summary.maxSlope, 1)} AQI per 10 extra points of built-up.`,
        `It holds across the ${summary.years} years with a valid comparison, including the COVID year, so it is not a one-off.`,
      ];
    },
  },
  {
    title: "The twist",
    minutes: "2:30–3:45",
    body: (data) => <TwistStep data={data} />,
    notes: (data) => {
      const { first, last, lowest } = trendEnds(data);
      return [
        `Built-up area went up, but the city mean AQI went down, from ${formatNumber(first.mean_aqi, 0)} to ${formatNumber(last.mean_aqi, 0)}, with a low of ${formatNumber(lowest.mean_aqi, 0)} in ${lowest.year}.`,
        `On the map (${first.year} → ${last.year}), most monitors improved. Point to the darker patches inside the no-change line: the few areas where AQI rose.`,
        "Click 2020 → 2021: every monitor got worse after the lockdown. That shows how strongly emissions and activity drive AQI.",
        "So where you are matters, because built-up areas are consistently worse. But the year-to-year trend is set city-wide by emission controls, fuels, and weather.",
      ];
    },
  },
  {
    title: "Pollutant evidence",
    minutes: "3:45–4:20",
    body: (_data, landUse) => <EvidenceStep landUse={landUse} />,
    notes: (_data, landUse) => {
      const { pm25, no2, year } = urbanization(landUse);
      return [
        `Using the land-use contrasts from Badia et al. 2025, monitors with the most built-up land nearby had ${pm25?.percent_difference != null ? `${signed(pm25.percent_difference)}% PM2.5` : "higher PM2.5"} and ${no2?.percent_difference != null ? `${signed(no2.percent_difference)}% NO2` : "higher NO2"} in ${year ?? "2024"}.`,
        "NO2 comes mostly from traffic, so the larger NO2 difference fits the idea that built-up land brings traffic emissions with it.",
      ];
    },
  },
  {
    title: "Takeaway",
    minutes: "4:20–5:00",
    body: (data) => <TakeawayStep data={data} />,
    notes: () => [
      "This is an association, not proof of cause. Traffic, industry, and where monitors are placed come with built-up land.",
      "The map between monitors is interpolated; small local patches are estimates, not measurements.",
      "Takeaway: urbanization is tied to a persistent local air-quality penalty. City-wide policy can lower AQI overall, but built-up areas stay the worst-affected, so growth areas need green buffers and traffic controls.",
    ],
  },
];

function clampStep(index: number) {
  return Number.isFinite(index) ? Math.min(STEPS.length - 1, Math.max(0, index)) : 0;
}

export function PresentationPage() {
  const builtUp = useBuiltUpAqiYears(CITY);
  const landUse = useLandUseContrasts();
  const [params, setParams] = useSearchParams();
  const step = clampStep(Number(params.get("step") ?? 1) - 1);
  const [showNotes, setShowNotes] = useState(true);
  const go = (next: number) => setParams({ step: String(clampStep(next) + 1) }, { replace: true });

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)) return;
      const move = event.key === "ArrowRight" || event.key === "PageDown" ? 1 : event.key === "ArrowLeft" || event.key === "PageUp" ? -1 : 0;
      if (move) {
        setParams(
          (current) => {
            const now = clampStep(Number(current.get("step") ?? 1) - 1);
            return { step: String(clampStep(now + move) + 1) };
          },
          { replace: true },
        );
      }
      if (event.key.toLowerCase() === "n") setShowNotes((value) => !value);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setParams]);

  const current = STEPS[step];
  const data = builtUp.data;

  return (
    <div className="space-y-4">
      <nav className="flex flex-wrap items-center gap-2" aria-label="Presentation steps">
        {STEPS.map((item, index) => (
          <button
            key={item.title}
            type="button"
            onClick={() => go(index)}
            className={`rounded-full px-3 py-1.5 text-sm ${index === step ? "bg-ink text-white" : index < step ? "bg-stone-200 text-stone-800" : "border border-stone-300 bg-white text-stone-600"}`}
          >
            {index + 1}. {item.title}
          </button>
        ))}
        <span className="ml-auto flex gap-2">
          <button type="button" className="rounded-md border border-stone-300 bg-white px-3 py-1.5 text-sm" onClick={() => setShowNotes((value) => !value)}>
            {showNotes ? "Hide" : "Show"} notes
          </button>
          <button type="button" className="rounded-md border border-stone-300 bg-white px-3 py-1.5 text-sm" onClick={() => document.documentElement.requestFullscreen?.()}>
            Full screen
          </button>
        </span>
      </nav>

      <section className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm">
        <header className="mb-4 flex items-baseline justify-between gap-3">
          <h2 className="text-sm uppercase tracking-[0.2em] text-moss">
            Step {step + 1} of {STEPS.length} · {current.title}
          </h2>
          <span className="text-xs text-stone-500">{current.minutes}</span>
        </header>
        {builtUp.isError ? <Alert>Built-up and annual AQI could not be loaded. Check that the API is running.</Alert> : null}
        {!data && !builtUp.isError ? <Skeleton className="h-[50vh]" /> : null}
        {data ? current.body(data, landUse.data) : null}
      </section>

      {showNotes && data ? (
        <aside className="rounded-xl border border-amber-200 bg-amber-50 p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-amber-900">Speaker notes</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-amber-950">
            {current.notes(data, landUse.data).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </aside>
      ) : null}

      <div className="flex items-center justify-between">
        <button type="button" className="rounded-md border border-stone-300 bg-white px-4 py-2 text-sm disabled:opacity-40" disabled={step === 0} onClick={() => go(step - 1)}>
          ← Back
        </button>
        <p className="text-xs text-stone-500">Arrow keys move between steps · N toggles notes</p>
        <button type="button" className="rounded-md bg-ink px-4 py-2 text-sm text-white disabled:opacity-40" disabled={step === STEPS.length - 1} onClick={() => go(step + 1)}>
          Next →
        </button>
      </div>
    </div>
  );
}
