import { describe, expect, it } from "vitest";
import { stationChangeRows } from "@/features/map/StationChangeTable";
import type { StationFeature, StationYear } from "@/features/relationships/builtupAqiYears";

function year(aqi: number, category: string, built: number | null): StationYear {
  return { aqi, category, built, days: 300, poor_or_worse_days: 0 };
}

function station(station_id: string, name: string, years: Record<string, StationYear>): StationFeature {
  return { type: "Feature", geometry: { type: "Point", coordinates: [77.2, 28.6] }, properties: { station_id, name, years } };
}

const YEARS = [2018, 2019, 2020];

const features = [
  station("a", "Dense", { "2018": year(230, "Poor", 95), "2019": year(220, "Poor", 96), "2020": year(225, "Poor", 97) }),
  station("b", "Edge", { "2018": year(190, "Moderate", 50), "2020": year(210, "Poor", 62) }),
  station("c", "Rural", { "2018": year(205, "Poor", 12), "2019": year(180, "Moderate", 13) }),
  station("d", "Pusa", { "2019": year(170, "Moderate", 57) }),
  station("e", "Pusa", { "2019": year(210, "Poor", 58) }),
  station("f", "Empty", {}),
];

describe("stationChangeRows", () => {
  const rows = stationChangeRows(features, YEARS);

  it("drops stations without any year and sorts from least to most built-up", () => {
    expect(rows.map((row) => row.stationId)).toEqual(["c", "b", "d", "e", "a"]);
  });

  it("assigns bands from the first year's built-up share", () => {
    const band = Object.fromEntries(rows.map((row) => [row.stationId, row.band]));
    expect(band).toEqual({ c: "Under 30% built-up", b: "30–70% built-up", d: "30–70% built-up", e: "30–70% built-up", a: "90% built-up and over" });
  });

  it("keeps missing years as null and uses the first and last years present", () => {
    const edge = rows.find((row) => row.stationId === "b")!;
    expect(edge.cells[1]).toBeNull();
    expect(edge.first.year).toBe(2018);
    expect(edge.last.year).toBe(2020);
    expect(edge.builtChange).toBe(12);
    expect(edge.aqiChange).toBe(20);
  });

  it("labels duplicate names with the station id", () => {
    expect(rows.filter((row) => row.label.startsWith("Pusa")).map((row) => row.label)).toEqual(["Pusa (d)", "Pusa (e)"]);
    expect(rows.find((row) => row.stationId === "a")!.label).toBe("Dense");
  });

  it("classifies category change as worse, same, or better", () => {
    const change = Object.fromEntries(rows.map((row) => [row.stationId, row.categoryChange]));
    expect(change).toMatchObject({ a: "same", b: "worse", c: "better" });
  });
});
