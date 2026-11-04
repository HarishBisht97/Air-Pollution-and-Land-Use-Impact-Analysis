export function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-IN", { dateStyle: "medium" });
}

export function dataKindLabel(kind: string | undefined): string {
  const labels: Record<string, string> = {
    observed: "Observed measurement",
    quality_controlled: "Quality-controlled observation",
    aggregated: "Spatially or temporally aggregated",
    satellite_index: "Satellite-derived index",
    classified: "Classified land cover",
    statistical_estimate: "Statistical estimate",
    model_prediction: "Model prediction",
    screening_score: "Screening score (not a health risk)",
  };
  return labels[kind ?? ""] ?? kind ?? "Unspecified";
}
