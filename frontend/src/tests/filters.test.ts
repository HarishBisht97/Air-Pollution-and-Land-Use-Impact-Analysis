import { describe, expect, it } from "vitest";
import { defaultFilters, filtersFromSearch, searchFromFilters } from "@/lib/filters";

describe("filter URL state", () => {
  it("parses query params", () => {
    const filters = filtersFromSearch("city=delhi&pollutant=PM10&from=2024-01-01&to=2024-06-01&resolution=1000");
    expect(filters.city).toBe("delhi");
    expect(filters.pollutant).toBe("PM10");
    expect(filters.resolution).toBe("1000");
  });

  it("falls back to defaults", () => {
    expect(filtersFromSearch("")).toEqual(defaultFilters);
  });

  it("round-trips", () => {
    const search = searchFromFilters(defaultFilters);
    expect(filtersFromSearch(search).city).toBe("delhi");
  });
});
