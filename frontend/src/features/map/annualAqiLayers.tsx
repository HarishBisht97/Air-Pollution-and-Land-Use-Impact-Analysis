import { useMemo } from "react";
import { GeoJSON, ImageOverlay, Pane } from "react-leaflet";
import L from "leaflet";
import { downloadUrl } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { type AqiClass, type AqiSurface, type BuiltUpAqiYears, classFill } from "@/features/relationships/builtupAqiYears";

export type SurfaceMode = "change" | "level";

export const CPCB_BOUNDARIES = [100, 200, 300, 400];
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
}: {
  stations: NonNullable<ReturnType<typeof useYearStations>>;
  classes: AqiClass[];
  year: number;
  base: number | null;
  mode: SurfaceMode;
  method: string;
}) {
  return (
    <GeoJSON
      key={`annual-aqi-${mode}-${base}-${year}-${classes.length}`}
      data={stations as any}
      pointToLayer={(feature, latlng) =>
        L.circleMarker(latlng, {
          radius: 7,
          color: "#1c1917",
          fillColor: classFill(feature.properties?.value, classes),
          fillOpacity: 1,
          weight: 1.5,
          pane: "aqi-stations",
        })
      }
      onEachFeature={(feature, layer) => {
        const p = feature.properties;
        const change = p.change == null ? "" : `<br/>Change since ${base}: <strong>${signed(p.change)}</strong> (${base}: ${p.base_aqi})`;
        layer.bindPopup(
          `<strong>${p.name}</strong><br/>Annual AQI ${year}: ${p.aqi} · ${p.category}${change}<br/>Built-up within 1 km: ${p.built ?? "—"}%<br/>${p.days} valid days, ${p.poor_or_worse_days} at Poor or worse<br/>${method}`,
        );
      }}
    />
  );
}

export function BuiltUpOverlay({ city, year, bounds }: { city: string; year: number; bounds: BuiltUpAqiYears["overlay_bounds"] }) {
  return <ImageOverlay url={downloadUrl(`/analysis/builtup-overlay/${year}`, { city })} bounds={bounds} opacity={0.85} />;
}
