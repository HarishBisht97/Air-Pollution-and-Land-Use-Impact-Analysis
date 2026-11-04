export type AppFilters = {
  city: string;
  pollutant: string;
  from: string;
  to: string;
  resolution: string;
};

export const defaultFilters: AppFilters = {
  city: "delhi",
  pollutant: "PM2.5",
  from: "2000-01-01",
  to: "2026-12-31",
  resolution: "1000",
};

export function filtersFromSearch(search: string): AppFilters {
  const params = new URLSearchParams(search);
  return {
    city: params.get("city") || defaultFilters.city,
    pollutant: params.get("pollutant") || defaultFilters.pollutant,
    from: params.get("from") || defaultFilters.from,
    to: params.get("to") || defaultFilters.to,
    resolution: params.get("resolution") || defaultFilters.resolution,
  };
}

export function searchFromFilters(filters: AppFilters): string {
  const params = new URLSearchParams(filters);
  return params.toString();
}
