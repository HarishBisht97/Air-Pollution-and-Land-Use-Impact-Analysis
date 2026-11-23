import { useMemo } from "react";
import type { FeatureCollection } from "geojson";
import { GeoJSON, ImageOverlay, Pane } from "react-leaflet";
import L from "leaflet";
import { downloadUrl } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { type AqiBands, type AqiClass, type AqiSurface, type BuiltUpAqiYears, classFill } from "@/features/relationships/builtupAqiYears";

export type SurfaceMode = "change" | "level";

export const CPCB_BOUNDARIES = [100, 200, 300, 400];
/** Same station colours as Station AQI on the relationships page. */
export const CPCB_CATEGORY_COLORS: Record<string, string> = {
  Good: "#14532d",
  Satisfactory: "#4d7c0f",
  Moderate: "#ea580c",
  Poor: "#dc2626",
  "Very Poor": "#b91c1c",
  Severe: "#7f1d1d",
};
export const BUILT_BASELINE = "rgba(120, 113, 108, 0.6)";
export const BUILT_NEW = "rgba(220, 38, 38, 0.82)";

export function signed(value: number) {
  return `${value > 0 ? "+" : ""}${formatNumber(value, 0)}`;
}

export function ClassList({ classes }: { classes: AqiClass[] }) {
  if (!classes.length) return null;
  return (
    <ul className="mt-2 grid grid-cols-2 gap-x-2 gap-y-1 text-[11px] text-stone-700">
      {classes.map((item) => (
        <li key={item.min_aqi} className="flex items-center" title={item.category}>
          <span className="mr-1 inline-block h-3 w-3 shrink-0 border border-stone-300" style={{ backgroundColor: item.fill }} />
          {item.label}
        </li>
      ))}
    </ul>
  );
}

/** Fill under the built-up image, contour lines and stations above it. */
export function AqiPanes() {
  return (
    <>
      <Pane name="aqi-fill" style={{ zIndex: 380 }} />
      <Pane name="aqi-lines" style={{ zIndex: 420 }} />
      <Pane name="aqi-stations" style={{ zIndex: 440 }} />
    </>
  );
}

function surfaceKey(surface: AqiSurface) {
  return `${surface.mode}-${surface.base ?? ""}-${surface.year}`;
}

export function bandShades(bands: AqiBands | undefined) {
  return [...(bands?.features ?? [])]
    .map((feature) => feature.properties)
    .filter((properties, index, all) => all.findIndex((item) => item.min_aqi === properties.min_aqi) === index)
    .sort((left, right) => left.min_aqi - right.min_aqi);
}

/** Filled bands with a thin outline, the same drawing as Station AQI in 2026. */
export function AnnualBandLayer({ bands, fillOpacity = 0.72 }: { bands: AqiBands; fillOpacity?: number }) {
  const change = bands.mode === "change";
  return (
    <GeoJSON
      key={`bands-${bands.mode}-${bands.base ?? ""}-${bands.year}-${fillOpacity}`}
      data={{ type: "FeatureCollection", features: bands.features } as FeatureCollection}
      style={(feature) => ({
        color: "#1c1917",
        weight: 0.6,
        opacity: 0.45,
        fillColor: feature?.properties?.fill ?? "#78716c",
        fillOpacity,
      })}
      onEachFeature={(feature, layer) => {
        const upper = feature.properties?.max_aqi;
        const range = upper == null ? `${feature.properties?.min_aqi}+` : `${feature.properties?.min_aqi}–${upper}`;
        layer.bindTooltip(change ? `Change ${range}` : `AQI ${range}`, { sticky: true });
      }}
    />
  );
}

export function AqiFillLayer({ surface, opacity }: { surface: AqiSurface; opacity: number }) {
  return (
    <GeoJSON
      key={`aqi-fill-${surfaceKey(surface)}-${opacity}`}
      data={surface.fills as any}
      pane="aqi-fill"
      style={(feature) => ({ stroke: false, fillColor: feature?.properties?.fill, fillOpacity: opacity })}
      onEachFeature={(feature, layer) => {
        const p = feature.properties;
        const what =
          surface.mode === "change"
            ? `Estimated change in annual AQI, ${surface.base} to ${surface.year}: ${p.label} (${p.category})`
            : `Estimated annual AQI ${surface.year}: ${p.label} (${p.category})`;
        layer.bindPopup(`${what}<br/>Interpolated between monitors. Not a measurement.`);
      }}
    />
  );
}

export function AqiLinesLayer({ surface }: { surface: AqiSurface }) {
  const change = surface.mode === "change";
  return (
    <GeoJSON
      key={`aqi-lines-${surfaceKey(surface)}`}
      data={surface.lines as any}
      pane="aqi-lines"
      style={(feature) => {
        const level = feature?.properties?.level;
        const major = change ? level === 0 : CPCB_BOUNDARIES.includes(level);
        return { color: "#1c1917", weight: major ? 2.6 : 1.1, opacity: major ? 0.95 : 0.75, dashArray: major ? undefined : "4 3" };
      }}
      onEachFeature={(feature, layer) => {
        const p = feature.properties;
        if (p.length_km >= 4) {
          const text = change ? (p.level === 0 ? "0" : signed(p.level)) : String(p.level);
          layer.bindTooltip(text, { permanent: true, direction: "center", className: "contour-label" });
        }
      }}
    />
  );
}

export function useYearStations(data: BuiltUpAqiYears | undefined, year: number | null, base: number | null, mode: SurfaceMode) {
  return useMemo(() => {
    if (!data || year == null) return null;
    const key = String(year);
    const baseKey = String(base);
    return {
      type: "FeatureCollection" as const,
      features: data.features
        .filter((feature) => feature.properties.years[key] && (mode === "level" || feature.properties.years[baseKey]))
        .map((feature) => {
          const current = feature.properties.years[key];
          const before = feature.properties.years[baseKey];
          const change = before ? Math.round((current.aqi - before.aqi) * 10) / 10 : null;
          return {
            ...feature,
            properties: { name: feature.properties.name, ...current, base_aqi: before?.aqi ?? null, change, value: mode === "change" ? change : current.aqi },
          };
        }),
    };
  }, [data, year, base, mode]);
}

export function AnnualStationsLayer({
  stations,
  classes,
  year,
  base,
  mode,
  method,
  fillFor,
}: {
  stations: NonNullable<ReturnType<typeof useYearStations>>;
  classes: AqiClass[];
  year: number;
  base: number | null;
  mode: SurfaceMode;
  method: string;
  fillFor?: (properties: { value?: number | null; category?: string }) => string;
}) {
  return (
    <GeoJSON
      key={`annual-aqi-${mode}-${base}-${year}-${classes.length}-${fillFor ? "custom" : "class"}`}
      data={stations as any}
      pointToLayer={(feature, latlng) =>
        L.circleMarker(latlng, {
          radius: 7,
          color: "#1c1917",
          fillColor: fillFor ? fillFor(feature.properties ?? {}) : classFill(feature.properties?.value, classes),
          fillOpacity: 1,
          weight: 1.5,
          pane: "aqi-stations",
        })
      }
      onEachFeature={(feature, layer) => {
        const p = feature.properties;
        const change = p.change == null ? "" : `<br/>Change since ${base}: <strong>${signed(p.change)}</strong> (${base}: ${p.base_aqi})`;
        const coverage = p.coverage_note ? `<br/>${p.coverage_note}` : "";
        layer.bindPopup(
          `<strong>${p.name}</strong><br/>Annual AQI ${year}: ${p.aqi} · ${p.category}${change}<br/>Built-up within 1 km: ${p.built ?? "—"}%<br/>${p.days} valid days, ${p.poor_or_worse_days} at Poor or worse${coverage}<br/>${method}`,
        );
      }}
    />
  );
}

export function BuiltUpOverlay({ city, year, bounds }: { city: string; year: number; bounds: BuiltUpAqiYears["overlay_bounds"] }) {
  return <ImageOverlay url={downloadUrl(`/analysis/builtup-overlay/${year}`, { city })} bounds={bounds} opacity={0.85} />;
}
