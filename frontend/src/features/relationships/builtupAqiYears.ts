import { useQuery } from "@tanstack/react-query";
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

export type BuiltUpAqiYears = {
  status: string;
  baseline_year: number;
  years: YearStatistics[];
  city_trend: CityTrend[];
  type: "FeatureCollection";
  features: StationFeature[];
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
