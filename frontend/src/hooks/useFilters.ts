import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { AppFilters, defaultFilters, filtersFromSearch } from "@/lib/filters";

export function useFilters() {
  const [params, setParams] = useSearchParams();
  const filters = useMemo(() => filtersFromSearch(params.toString()), [params]);

  const update = (patch: Partial<AppFilters>) => {
    const next = { ...filters, ...patch };
    const search = new URLSearchParams(params);
    Object.entries(next).forEach(([key, value]) => search.set(key, value));
    setParams(search, { replace: true });
  };

  return { filters, update, defaults: defaultFilters };
}
