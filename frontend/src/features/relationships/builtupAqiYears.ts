import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";

export type YearStatistics = {
  year: number;
  n: number;
  status: string;
  pearson_r: number | null;
  p_value: number | null;
  aqi_per_10_points: number | null;
  n_each: number | null;
  most_built_aqi: number | null;
  least_built_aqi: number | null;
  gap: number | null;
  most_built_share: number | null;
  least_built_share: number | null;
};

export type CityTrend = {
  year: number;
  built_km2: number | null;
  mean_aqi: number | null;
  stations: number;
  poor_or_worse_share: number | null;
};

export type StationYear = { aqi: number; category: string; days: number; poor_or_worse_days: number; built: number | null };

export type StationFeature = {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: { station_id: string; name: string; years: Record<string, StationYear> };
};

export type AqiClass = { min_aqi: number; max_aqi: number; fill: string; label: string; category: string };

export type ClassSet = { edges: number[]; classes: AqiClass[]; line_levels: number[] };

export type AqiSurface = {
  mode: "level" | "change";
  year: number;
  base?: number;
  stations: number;
  improved?: number;
  worsened?: number;
  median_change?: number | null;
  fills: { type: "FeatureCollection"; features: any[] };
  lines: { type: "FeatureCollection"; features: any[] };
  classes: AqiClass[];
  line_levels: number[];
  method: string;
};

export const AQI_COLORS: Record<string, string> = {
  Good: "#3f6b4a",
  Satisfactory: "#65a30d",
  Moderate: "#ca8a04",
  Poor: "#ea580c",
  "Very Poor": "#b91c1c",
  Severe: "#7f1d1d",
};

export function classFill(aqi: number | null | undefined, classes: AqiClass[]) {
  if (aqi == null || !classes.length) return "#78716c";
  return (classes.find((item) => aqi < item.max_aqi) ?? classes[classes.length - 1]).fill;
}

export type BuiltUpAqiYears = {
  status: string;
  baseline_year: number;
  years: YearStatistics[];
  city_trend: CityTrend[];
  type: "FeatureCollection";
  features: StationFeature[];
  aqi_classes: ClassSet | null;
  change_classes: ClassSet;
  aqi_method: string;
  radius_km: number;
  boundary: string | null;
  land_cover: string;
  air_quality: string;
  caveat: string;
  overlay_bounds: [[number, number], [number, number]];
};

export function useBuiltUpAqiYears(city: string) {
  return useQuery({
    queryKey: ["builtup-aqi-years", city],
    queryFn: () => apiGet<BuiltUpAqiYears>("/analysis/builtup-aqi-years", { city }),
    enabled: city === "delhi",
    staleTime: Infinity,
  });
}

export function useAnnualAqiSurface(city: string, year: number | null, base: number | null, mode: "level" | "change") {
  const change = mode === "change";
  return useQuery({
    queryKey: ["annual-aqi-surface", city, mode, change ? base : null, year],
    queryFn: () =>
      change
        ? apiGet<AqiSurface>(`/analysis/annual-aqi-change-surface/${year}`, { city, base })
        : apiGet<AqiSurface>(`/analysis/annual-aqi-surface/${year}`, { city }),
    enabled: city === "delhi" && year != null && (!change || (base != null && base < year)),
    staleTime: Infinity,
    placeholderData: keepPreviousData,
  });
}
