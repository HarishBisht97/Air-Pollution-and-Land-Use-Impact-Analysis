import csv
import io
import json
from datetime import datetime
from typing import Any


def to_csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def methodology_block(city: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "study_area": city,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "methods": [
            "Observations stored as station point measurements; no silent interpolation.",
            "Distances and areas computed in the city projected CRS.",
            "NAAQS comparisons only when averaging periods match.",
            "NDVI/NDBI from labeled sample rasters unless real imagery is configured.",
        ],
        "limitations": [
            "Delhi seed lists twelve CAAQMS coordinates. Cells without a monitor may hold a labeled IDW estimate, not a measurement.",
            "Meteorology is not controlled.",
            "Sample rasters are not satellite observations.",
        ],
    }
    if extra:
        payload.update(extra)
    return payload
